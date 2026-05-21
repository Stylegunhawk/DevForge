# src/tools/github/tools.py
"""
GitHub operations tools using PyGithub.
Phase 3.3 implementation with lazy initialization for test safety.
"""

import logging
import os
import time
import ipaddress
import socket
from functools import wraps
from urllib.parse import urlparse
import base64
import httpx
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from github import Github, GithubException, Auth, RateLimitExceededException
from github.Repository import Repository
from github.GithubObject import NotSet

logger = logging.getLogger(__name__)


# === Error Enrichment ===

_SCOPE_MAP: Dict[str, List[str]] = {
    "delete_repo":         ["delete_repo", "repo"],
    "create_repo":         ["repo"],
    "commit_file":         ["repo"],
    "create_pull_request": ["repo"],
    "merge_pr":            ["repo"],
    "create_branch":       ["repo"],
    "delete_branch":       ["repo"],
    "create_issue":        ["repo"],
    "close_issue":         ["repo"],
    "update_issue":        ["repo"],
    "add_comment":         ["repo"],
    "create_release":      ["repo"],
    "create_webhook":      ["write:repo_hook"],
    "delete_webhook":      ["write:repo_hook"],
    "trigger_workflow":    ["workflow"],
}


def _enrich_github_error(exc: "GithubException", operation: str) -> str:
    """Convert raw PyGithub exceptions into actionable error messages."""
    status = getattr(exc, "status", None)
    data = getattr(exc, "data", {}) or {}
    raw_msg = data.get("message", str(exc)) if isinstance(data, dict) else str(exc)
    if status == 403:
        scopes = _SCOPE_MAP.get(operation, ["repo"])
        scope_str = ", ".join(scopes)
        return (
            f"GitHub permission denied for '{operation}'. "
            f"Your PAT needs these scopes: [{scope_str}]. "
            f"Re-generate at https://github.com/settings/tokens/new"
        )
    if status == 404:
        return (
            f"Resource not found for '{operation}'. "
            f"Check repo_name format (must be 'owner/repo')."
        )
    if status == 422:
        return f"GitHub validation error for '{operation}': {raw_msg}"
    return f"GitHub API error {status} for '{operation}': {raw_msg}"


def _validate_safe_url(url: str) -> None:
    """SSRF guard. Reject non-http(s) schemes and URLs resolving to private,
    loopback, link-local, or multicast IPs (IPv4 and IPv6).

    Raises ValueError on rejection. Returns silently on safe URLs.

    Note: resolves the hostname to an IP at validation time. Callers must use
    `follow_redirects=False` and re-validate on every 3xx Location header to
    prevent redirect-based SSRF.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Invalid file_url: must be a non-empty string")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Invalid file_url scheme '{parsed.scheme}'. Only http/https are allowed."
        )
    if not parsed.hostname:
        raise ValueError("Invalid file_url: missing hostname")

    try:
        addrinfo = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve file_url host '{parsed.hostname}': {e}") from e

    for entry in addrinfo:
        addr = entry[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError(
                f"file_url resolves to a disallowed address ({addr}). "
                "Private, loopback, link-local, multicast, and reserved IPs are blocked."
            )


def _safe_fetch_url(url: str, *, max_redirects: int = 2, timeout: float = 60.0) -> bytes:
    """Fetch URL bytes — local disk read or SSRF-validated HTTP, in that order.

    1. Delegates to the FileStore registry first (LocalFileStore for own-server
       URLs; S3FileStore / MongoFileStore when those backends are activated).
       Local reads happen in-process with no network call and no SSRF risk.
    2. Falls back to SSRF-validated HTTP fetch for external / CDN URLs.

    Disables automatic redirect following so every hop is validated against
    the SSRF rules before being chased. Caps hops at `max_redirects`.

    Raises:
        ValueError  — SSRF rejection or file too large (> 100 MB)
        RuntimeError — HTTP failure or redirect limit exceeded
    """
    from src.storage.file_store import read_upload_url
    local_bytes = read_upload_url(url)
    if local_bytes is not None:
        return local_bytes

    current_url = url
    for hop in range(max_redirects + 1):
        _validate_safe_url(current_url)
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            with client.stream("GET", current_url) as response:
                if 300 <= response.status_code < 400:
                    location = response.headers.get("Location")
                    if not location:
                        raise RuntimeError(
                            f"file_url returned {response.status_code} with no Location header"
                        )
                    if hop >= max_redirects:
                        raise RuntimeError(
                            f"file_url exceeded max_redirects={max_redirects}"
                        )
                    current_url = location
                    continue
                response.raise_for_status()
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > 100 * 1024 * 1024:
                    raise ValueError(
                        f"File too large: {content_length} bytes (GitHub limit is 100MB)"
                    )
                content_bytes = response.read()
                if len(content_bytes) > 100 * 1024 * 1024:
                    raise ValueError(
                        f"File too large: {len(content_bytes)} bytes (GitHub limit is 100MB)"
                    )
                return content_bytes
    raise RuntimeError(f"file_url fetch failed after {max_redirects} redirects")


def handle_rate_limits(func):
    """Decorator to handle GitHub API rate limits."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (RateLimitExceededException, GithubException) as e:
            status = getattr(e, 'status', None)
            data = getattr(e, 'data', {})
            headers = getattr(e, 'headers', {})
            
            # Check for rate limit indicators
            is_rate_limit = (
                isinstance(e, RateLimitExceededException) or 
                status == 429 or 
                (status == 403 and 'rate limit' in str(data.get('message', '')).lower())
            )
            
            if is_rate_limit:
                retry_after = headers.get('Retry-After')
                limit_reset = headers.get('X-RateLimit-Reset')
                
                wait_time = 60  # Default fallback
                if retry_after:
                    wait_time = int(retry_after)
                elif limit_reset:
                    wait_time = max(1, int(float(limit_reset) - time.time()))
                
                msg = f"GitHub API rate limit exceeded. Please retry after {wait_time} seconds."
                logger.warning(msg, extra={"wait_time": wait_time})
                
                # Re-raise as a clean exception that can be caught by the agent
                raise Exception(msg) from e
            raise
    return wrapper


class GitHubTools:
    """GitHub API operations wrapper using PyGithub.
    
    Uses lazy initialization to prevent network calls at import time.
    Set GITOPS_MOCK_GITHUB=true to skip all GitHub API calls (for testing).
    """
    
    def __init__(self, token: Optional[str] = None, lazy: bool = True):
        self.token = token
        self._client: Optional[Github] = None
        self._user = None
        self._mock_mode = os.getenv("GITOPS_MOCK_GITHUB", "").lower() in ("true", "1", "yes")
        
        # Validate token early (but don't connect yet)
        if not self._mock_mode and not self.token:
            raise ValueError(
                "GitHub token required. Please provide a valid GitHub Personal Access Token from the frontend."
            )
        
        # Legacy behavior: initialize immediately if lazy=False
        if not lazy and not self._mock_mode:
            self._init_client()
    
    def _init_client(self) -> None:
        """Initialize the GitHub client (called lazily on first use)."""
        if self._client is not None:
            return
            
        if self._mock_mode:
            logger.info("GitHub client in MOCK mode - no API calls will be made")
            return
            
        auth = Auth.Token(self.token)
        # Bound the underlying socket timeout so a stalled GitHub API call cannot
        # hang the executor thread indefinitely. The agent layer wraps each call
        # in asyncio.wait_for(..., timeout=15.0), but that does not cancel the
        # synchronous PyGithub call running in run_in_executor — we need a real
        # socket-level cap here too. Configurable via GITHUB_HTTP_TIMEOUT env.
        http_timeout = int(os.getenv("GITHUB_HTTP_TIMEOUT", "10"))
        self._client = Github(auth=auth, timeout=http_timeout)
        self._user = self._client.get_user()
        
        logger.info(
            f"GitHub client initialized for user: {self._user.login}",
            extra={"username": self._user.login}
        )
    
    @property
    def client(self) -> Github:
        """Get GitHub client (lazy initialization)."""
        if self._mock_mode:
            raise RuntimeError("GitHub client not available in mock mode")
        if self._client is None:
            self._init_client()
        return self._client
    
    @property
    def user(self):
        """Get authenticated user (lazy initialization)."""
        if self._mock_mode:
            raise RuntimeError("GitHub user not available in mock mode")
        if self._user is None:
            self._init_client()
        return self._user
    
    @handle_rate_limits
    def list_repos(
        self,
        visibility: str = "all",
        sort: str = "updated",
        limit: int = 10,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """List user repositories.
        
        Args:
            visibility: Repository visibility ('all', 'public', 'private')
            sort: Sort by ('updated', 'created', 'pushed', 'full_name')
            limit: Maximum number of repos to return
            
        Returns:
            List of repository information dicts
        """
        try:
            start_time = time.time()
            repos = self.user.get_repos(
                visibility=visibility,
                sort=sort
            )
            fetched_repos = repos.get_page(page - 1)[:limit]
            result = []
            api_duration = time.time() - start_time
            
            for repo in fetched_repos:
                result.append({
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "description": repo.description,
                    "private": repo.private,
                    "url": repo.html_url,
                    "clone_url": repo.clone_url,
                    "language": repo.language,
                    "stars": repo.stargazers_count,
                    "forks": repo.forks_count,
                    "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                    "created_at": repo.created_at.isoformat() if repo.created_at else None,
                })
            
            logger.info(
                f"Listed {len(result)} repositories in {api_duration:.2f}s",
                extra={
                    "count": len(result), 
                    "visibility": visibility,
                    "duration_ms": int(api_duration * 1000)
                }
            )
            return result
            
        except GithubException as e:
            # handle_rate_limits decorator will catch rate limits, otherwise re-raise
            logger.error(
                f"Failed to list repos: {e.status} - {e.data}",
                extra={"status": e.status, "error": str(e)},
                exc_info=True
            )
            raise
    
    @handle_rate_limits
    def create_repo(
        self,
        name: str,
        description: str = "",
        private: bool = False,
        auto_init: bool = True,
        gitignore_template: Optional[str] = None,
        license_template: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new repository.
        
        Args:
            name: Repository name
            description: Repository description
            private: Make repository private
            auto_init: Initialize with README
            gitignore_template: Gitignore template (e.g., 'Python', 'Node')
            license_template: License template (e.g., 'mit', 'apache-2.0')
            
        Returns:
            Created repository information
        """
        try:
            start_time = time.time()
            repo = self.user.create_repo(
                name=name,
                description=description or NotSet,
                private=private,
                auto_init=auto_init,
                gitignore_template=gitignore_template or NotSet,
                license_template=license_template or NotSet
            )
            duration = time.time() - start_time
            
            result = {
                "name": repo.name,
                "full_name": repo.full_name,
                "description": repo.description,
                "private": repo.private,
                "url": repo.html_url,
                "clone_url": repo.clone_url,
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
            }
            
            logger.info(
                f"Created repository: {repo.full_name} in {duration:.2f}s",
                extra={
                    "repo": repo.full_name, 
                    "private": private,
                    "duration_ms": int(duration * 1000)
                }
            )
            return result
            
        except GithubException as e:
            logger.error(
                f"Failed to create repo '{name}': {e.status} - {e.data}",
                extra={"repo_name": name, "status": e.status, "error": str(e)},
                exc_info=True
            )
            raise
    
    @handle_rate_limits
    def create_issue(
        self,
        repo_name: str,
        title: str,
        body: str = "",
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create an issue in a repository.
        
        Args:
            repo_name: Repository name (format: 'owner/repo' or just 'repo' for user repos)
            title: Issue title
            body: Issue description/body
            labels: List of label names
            assignees: List of GitHub usernames to assign
            
        Returns:
            Created issue information
        """
        try:
            # Handle both 'owner/repo' and 'repo' formats
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            
            repo = self.client.get_repo(repo_name)
            
            start_time = time.time()
            issue = repo.create_issue(
                title=title,
                body=body or NotSet,
                labels=labels or NotSet,
                assignees=assignees or NotSet
            )
            duration = time.time() - start_time
            
            result = {
                "number": issue.number,
                "title": issue.title,
                "body": issue.body,
                "state": issue.state,
                "url": issue.html_url,
                "labels": [label.name for label in issue.labels],
                "assignees": [assignee.login for assignee in issue.assignees],
                "created_at": issue.created_at.isoformat() if issue.created_at else None,
            }
            
            logger.info(
                f"Created issue #{issue.number} in {repo_name} in {duration:.2f}s",
                extra={
                    "repo": repo_name, 
                    "issue_number": issue.number,
                    "duration_ms": int(duration * 1000)
                }
            )
            return result
            
        except GithubException as e:
            logger.error(
                f"Failed to create issue in '{repo_name}': {e.status} - {e.data}",
                extra={"repo": repo_name, "status": e.status, "error": str(e)},
                exc_info=True
            )
            raise
    
    @handle_rate_limits
    def commit_file(
        self,
        repo_name: str,
        file_path: str,
        content: Optional[str] = None,
        commit_message: str = "",
        branch: str = "main",
        create_if_missing: bool = True,
        file_url: Optional[str] = None,
        delete: bool = False,
    ) -> Dict[str, Any]:
        """Commit a file to a repository.
        
        Args:
            repo_name: Repository name (format: 'owner/repo' or just 'repo')
            file_path: Path to file in repo (e.g., 'src/app.py')
            content: File content as string (optional if file_url provided)
            commit_message: Commit message
            branch: Branch name (default: 'main')
            create_if_missing: Create file if it doesn't exist, else update
            file_url: Optional URL to fetch binary content from
            delete: Delete the target file instead of creating/updating it
            
        Returns:
            Commit information
        """
        try:
            if not delete and not content and not file_url:
                raise ValueError("Either 'content' or 'file_url' must be provided")

            if file_url and not delete:
                logger.info(f"Fetching binary content from: {file_url}")
                max_retries = 3
                fetch_success = False
                last_error: Optional[Exception] = None
                for attempt in range(max_retries):
                    try:
                        # SSRF-validated fetch — rejects private/loopback IPs and
                        # validates every redirect hop against the same rules.
                        content_bytes = _safe_fetch_url(file_url, max_redirects=2, timeout=60.0)

                        encoded_debug = base64.b64encode(content_bytes[:50]).decode("utf-8")
                        logger.info(f"Encoded content preview (first 20 chars): {encoded_debug[:20]}")
                        content = content_bytes
                        logger.info(f"Successfully fetched content ({len(content)} bytes)")
                        fetch_success = True
                        break
                    except ValueError:
                        # SSRF/size validation failures must not retry — the URL is
                        # permanently disallowed, retrying just wastes time.
                        raise
                    except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError) as e:
                        last_error = e
                        if attempt == max_retries - 1:
                            logger.error(f"Failed to fetch file after {max_retries} attempts: {e}")
                            raise
                        logger.warning(f"Fetch attempt {attempt + 1} failed: {e}. Retrying...")
                        time.sleep(1)  # Simple backoff

                if not fetch_success:
                    raise RuntimeError(f"Failed to fetch content from {file_url}: {last_error}")

            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            
            repo = self.client.get_repo(repo_name)
            
            start_time = time.time()
            if delete:
                existing_file = repo.get_contents(file_path, ref=branch)
                result = repo.delete_file(
                    path=existing_file.path,
                    message=commit_message,
                    sha=existing_file.sha,
                    branch=branch,
                )
                action = "deleted"
            elif file_url:
                # URL path: Always Delete-then-Create for clean upload (prevents corruption)
                # This works for both binary (PDF/images) and text (JS/Python) files
                try:
                    existing_file = repo.get_contents(file_path, ref=branch)
                    repo.delete_file(
                        path=existing_file.path,
                        message=f"Delete existing {file_path} for fresh upload via URL",
                        sha=existing_file.sha,
                        branch=branch
                    )
                    logger.info(f"Deleted existing file for fresh upload: {file_path}")
                except GithubException as e:
                    if e.status != 404:
                        raise
                
                result = repo.create_file(
                    path=file_path,
                    message=commit_message or "Upload file via URL",
                    content=content,
                    branch=branch
                )
                action = "uploaded (fresh)"
            else:
                # Text path: Standard update or create
                try:
                    existing_file = repo.get_contents(file_path, ref=branch)
                    result = repo.update_file(
                        path=file_path,
                        message=commit_message,
                        content=content,
                        sha=existing_file.sha,
                        branch=branch
                    )
                    action = "updated"
                except GithubException as e:
                    if e.status == 404 and create_if_missing:
                        result = repo.create_file(
                            path=file_path,
                            message=commit_message,
                            content=content,
                            branch=branch
                        )
                        action = "created"
                    else:
                        raise

            duration = time.time() - start_time
            
            commit_info = {
                "action": action,
                "file_path": file_path,
                "commit_sha": result["commit"].sha if isinstance(result, dict) else result.sha if hasattr(result, "sha") else "unknown",
                "commit_message": commit_message,
                "branch": branch,
                "url": result["commit"].html_url if isinstance(result, dict) else result.html_url if hasattr(result, "html_url") else None,
            }
            
            logger.info(
                f"{action.capitalize()} file '{file_path}' in {repo_name} in {duration:.2f}s",
                extra={
                    "repo": repo_name, 
                    "file": file_path, 
                    "action": action,
                    "duration_ms": int(duration * 1000)
                }
            )
            return commit_info
            
        except GithubException as e:
            logger.error(
                f"Failed to commit file '{file_path}' to '{repo_name}': {e.status} - {e.data}",
                extra={"repo": repo_name, "file": file_path, "status": e.status, "error": str(e)},
                exc_info=True
            )
            raise
    
    @handle_rate_limits
    def create_pull_request(
        self,
        repo_name: str,
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
        draft: bool = False
    ) -> Dict[str, Any]:
        """Create a pull request.
        
        Args:
            repo_name: Repository name (format: 'owner/repo' or just 'repo')
            title: PR title
            head: Head branch name (branch with changes)
            base: Base branch name (branch to merge into)
            body: PR description
            draft: Create as draft PR
            
        Returns:
            Created PR information
        """
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            
            repo = self.client.get_repo(repo_name)
            
            start_time = time.time()
            pr = repo.create_pull(
                title=title,
                body=body or NotSet,
                head=head,
                base=base,
                draft=draft
            )
            duration = time.time() - start_time
            
            result = {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body,
                "state": pr.state,
                "draft": pr.draft,
                "head": pr.head.ref,
                "base": pr.base.ref,
                "url": pr.html_url,
                "created_at": pr.created_at.isoformat() if pr.created_at else None,
            }
            
            logger.info(
                f"Created PR #{pr.number} in {repo_name}: {head} -> {base} in {duration:.2f}s",
                extra={
                    "repo": repo_name, 
                    "pr_number": pr.number, 
                    "head": head, 
                    "base": base,
                    "duration_ms": int(duration * 1000)
                }
            )
            return result
            
        except GithubException as e:
            logger.error(
                f"Failed to create PR in '{repo_name}': {e.status} - {e.data}",
                extra={"repo": repo_name, "status": e.status, "error": str(e)},
                exc_info=True
            )
            raise

    @handle_rate_limits
    def merge_pr(
        self,
        repo_name: str,
        pr_number: int,
        merge_method: str = "merge",
        commit_title: str = None,
        commit_message: str = None,
        base: str = None,  # used for risk-gate context only — not passed to GitHub
    ) -> Dict[str, Any]:
        """Merge a pull request.

        Args:
            repo_name: Repository (owner/repo)
            pr_number: PR number to merge
            merge_method: 'merge', 'squash', or 'rebase'
            commit_title: Optional title for the merge commit
            commit_message: Optional body for the merge commit
            base: Ignored at execution time; used by risk_gate for branch checks

        Returns:
            Merge result dict
        """
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            repo = self.client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            merge_kwargs = {"merge_method": merge_method}
            if commit_title:
                merge_kwargs["commit_title"] = commit_title
            if commit_message:
                merge_kwargs["commit_message"] = commit_message
            result = pr.merge(**merge_kwargs)
            return {
                "merged": result.merged,
                "message": result.message,
                "sha": result.sha,
                "pr_number": pr_number,
                "repo_name": repo_name,
            }
        except GithubException as e:
            logger.error(
                f"Failed to merge PR #{pr_number} in '{repo_name}': {e.status} - {e.data}",
                extra={"repo": repo_name, "pr_number": pr_number, "status": e.status},
            )
            raise

    # === PR Inspection Operations ===

    @handle_rate_limits
    def list_pull_requests(
        self,
        repo_name: str,
        state: str = "open",
        base: Optional[str] = None,
        head: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            kwargs: Dict[str, Any] = {"state": state}
            if base:
                kwargs["base"] = base
            if head:
                kwargs["head"] = head
            prs = repo.get_pulls(**kwargs)
            results = []
            for pr in prs:
                if len(results) >= limit:
                    break
                results.append({
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "author": pr.user.login,
                    "head": pr.head.ref,
                    "base": pr.base.ref,
                    "draft": pr.draft,
                    "url": pr.html_url,
                })
            return {"pull_requests": results, "count": len(results), "repo": repo_name}
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "list_pull_requests"))

    @handle_rate_limits
    def get_pr(self, repo_name: str, pr_number: int) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            return {
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "author": pr.user.login,
                "head": pr.head.ref,
                "base": pr.base.ref,
                "draft": pr.draft,
                "mergeable": pr.mergeable,
                "body": pr.body,
                "labels": [label.name for label in (pr.labels or [])],
                "assignees": [a.login for a in (pr.assignees or [])],
                "reviewers": [r.login for r in (pr.requested_reviewers or [])],
                "commits": pr.commits,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "changed_files": pr.changed_files,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
                "url": pr.html_url,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "get_pr"))

    # === Issue Management Operations ===

    @handle_rate_limits
    def close_issue(self, repo_name: str, issue_number: int) -> Dict[str, Any]:
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            issue.edit(state="closed")
            return {
                "closed": True,
                "issue_number": issue_number,
                "repo": repo_name,
                "url": issue.html_url,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "close_issue"))

    @handle_rate_limits
    def update_issue(
        self,
        repo_name: str,
        issue_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            kwargs: Dict[str, Any] = {}
            if title is not None:
                kwargs["title"] = title
            if body is not None:
                kwargs["body"] = body
            if state is not None:
                kwargs["state"] = state
            if labels is not None:
                kwargs["labels"] = labels
            if assignees is not None:
                kwargs["assignees"] = assignees
            issue.edit(**kwargs)
            return {
                "updated": True,
                "issue_number": issue_number,
                "repo": repo_name,
                "url": issue.html_url,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "update_issue"))

    @handle_rate_limits
    def add_comment(self, repo_name: str, issue_number: int, body: str) -> Dict[str, Any]:
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            comment = issue.create_comment(body)
            return {
                "comment_id": comment.id,
                "url": comment.html_url,
                "issue_number": issue_number,
                "repo": repo_name,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "add_comment"))

    # === Commit History Operations ===

    @handle_rate_limits
    def list_commits(
        self,
        repo_name: str,
        branch: str = "main",
        limit: int = 20,
        author: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            repo = self.client.get_repo(repo_name)
            kwargs: Dict[str, Any] = {"sha": branch}
            if author:
                kwargs["author"] = author
            if since:
                kwargs["since"] = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if until:
                kwargs["until"] = datetime.fromisoformat(until.replace("Z", "+00:00"))
            commits_iter = repo.get_commits(**kwargs)
            results = []
            for commit in commits_iter:
                if len(results) >= limit:
                    break
                results.append({
                    "sha": commit.sha,
                    "message": commit.commit.message,
                    "author": commit.commit.author.name,
                    "date": commit.commit.author.date.isoformat(),
                    "url": commit.html_url,
                })
            return {"commits": results, "count": len(results), "branch": branch, "repo": repo_name}
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "list_commits"))

    @handle_rate_limits
    def get_commit(self, repo_name: str, sha: str) -> Dict[str, Any]:
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            repo = self.client.get_repo(repo_name)
            commit = repo.get_commit(sha)
            raw_files = list(commit.files)  # materialise once (GitHub caps at 300)
            return {
                "sha": commit.sha,
                "message": commit.commit.message,
                "author": commit.commit.author.name,
                "author_email": commit.commit.author.email,
                "date": commit.commit.author.date.isoformat(),
                "files": [
                    {
                        "filename": f.filename,
                        "status": f.status,
                        "additions": f.additions,
                        "deletions": f.deletions,
                    }
                    for f in raw_files[:100]
                ],
                "files_truncated": len(raw_files) > 100,
                "stats": {
                    "additions": commit.stats.additions,
                    "deletions": commit.stats.deletions,
                    "total": commit.stats.total,
                },
                "url": commit.html_url,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "get_commit"))

    # === Release Management Operations ===

    @handle_rate_limits
    def list_releases(self, repo_name: str, limit: int = 10) -> Dict[str, Any]:
        """List GitHub releases for a repository.

        Args:
            repo_name: Repository name (format: 'owner/repo' or just 'repo')
            limit: Maximum number of releases to return (default: 10)

        Returns:
            Dict with releases list and count
        """
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            repo = self.client.get_repo(repo_name)
            results = []
            for release in repo.get_releases():
                if len(results) >= limit:
                    break
                results.append({
                    "id": release.id,
                    "tag_name": release.tag_name,
                    "name": release.title,
                    "draft": release.draft,
                    "prerelease": release.prerelease,
                    "created_at": release.created_at.isoformat(),
                    "published_at": release.published_at.isoformat() if release.published_at else None,
                    "url": release.html_url,
                })
            return {"releases": results, "count": len(results), "repo": repo_name}
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "list_releases"))

    @handle_rate_limits
    def create_release(
        self,
        repo_name: str,
        tag_name: str,
        name: str,
        body: str = "",
        draft: bool = False,
        prerelease: bool = False,
        target_commitish: str = "main",
    ) -> Dict[str, Any]:
        """Create a new GitHub release with a tag.

        Args:
            repo_name: Repository name (format: 'owner/repo' or just 'repo')
            tag_name: Tag name for the release (e.g. 'v1.0.0')
            name: Release title
            body: Release notes / description
            draft: Create as a draft release
            prerelease: Mark as a pre-release
            target_commitish: Branch or commit SHA to tag (default: 'main')

        Returns:
            Created release metadata
        """
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            repo = self.client.get_repo(repo_name)
            release = repo.create_git_release(
                tag=tag_name,
                name=name,
                message=body,
                draft=draft,
                prerelease=prerelease,
                target_commitish=target_commitish,
            )
            return {
                "id": release.id,
                "tag_name": release.tag_name,
                "name": release.title,
                "draft": release.draft,
                "prerelease": release.prerelease,
                "url": release.html_url,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "create_release"))

    # === GitHub Actions Operations ===

    @handle_rate_limits
    def trigger_workflow(
        self,
        repo_name: str,
        workflow_id: str,
        ref: str = "main",
        inputs: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Trigger a GitHub Actions workflow dispatch event.

        Args:
            repo_name: Repository name (format: 'owner/repo' or just 'repo')
            workflow_id: Workflow filename (e.g. 'ci.yml') or numeric ID string
            ref: Branch or tag ref to trigger the workflow on (default: 'main')
            inputs: Optional key/value inputs for the workflow_dispatch event

        Returns:
            Dict with triggered status, workflow_id, ref, inputs, and repo
        """
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            repo = self.client.get_repo(repo_name)
            # workflow_id can be a filename ("ci.yml") or numeric ID string
            try:
                wf = repo.get_workflow(int(workflow_id))
            except (ValueError, TypeError):
                wf = repo.get_workflow(workflow_id)
            result = wf.create_dispatch(ref=ref, inputs=inputs or {})
            return {
                "triggered": result,
                "workflow_id": workflow_id,
                "ref": ref,
                "inputs": inputs,
                "repo": repo_name,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "trigger_workflow"))

    # === Webhook Management Operations ===

    @handle_rate_limits
    def create_webhook(
        self,
        repo_name: str,
        url: str,
        events: Optional[List[str]] = None,
        content_type: str = "json",
        active: bool = True,
        secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        _validate_safe_url(url)  # SSRF guard — same as commit_file.file_url
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            repo = self.client.get_repo(repo_name)
            config: Dict[str, Any] = {"url": url, "content_type": content_type}
            if secret:
                config["secret"] = secret
            hook = repo.create_hook(
                name="web",
                config=config,
                events=events or ["push"],
                active=active,
            )
            return {
                "hook_id": hook.id,
                "url": url,
                "events": events or ["push"],
                "active": hook.active,
                "repo": repo_name,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "create_webhook"))

    @handle_rate_limits
    def list_webhooks(self, repo_name: str) -> Dict[str, Any]:
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            repo = self.client.get_repo(repo_name)
            results = []
            for hook in repo.get_hooks():
                config = hook.config or {}
                results.append({
                    "id": hook.id,
                    "name": hook.name,
                    "events": list(hook.events),
                    "active": hook.active,
                    "url": config.get("url", ""),
                })
            return {"webhooks": results, "count": len(results), "repo": repo_name}
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "list_webhooks"))

    @handle_rate_limits
    def delete_webhook(self, repo_name: str, hook_id: int) -> Dict[str, Any]:
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            repo = self.client.get_repo(repo_name)
            hook = repo.get_hook(hook_id)
            hook.delete()
            return {"deleted": True, "hook_id": hook_id, "repo": repo_name}
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "delete_webhook"))

    @handle_rate_limits
    def browse_files(
        self,
        repo_name: str,
        path: str = "/"
    ) -> List[Dict[str, Any]]:
        """List repository content (file tree).
        
        Args:
            repo_name: Repository name
            path: Directory path to list (default: /)
            
        Returns:
            List of file/directory objects
        """
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            
            repo = self.client.get_repo(repo_name)
            contents = repo.get_contents(path.lstrip("/"))
            
            result = []
            if not isinstance(contents, list):
                contents = [contents]
                
            for item in contents:
                result.append({
                    "name": item.name,
                    "path": item.path,
                    "type": item.type,
                    "size": item.size,
                    "url": item.html_url
                })
            
            return result
        except Exception as e:
            if "404" in str(e):
                raise ValueError(f"Repository '{repo_name}' not found. Check the repo name and your token has access.")
            logger.error(f"Failed to browse files in '{repo_name}' at '{path}': {e}")
            raise

    @handle_rate_limits
    def read_file(
        self,
        repo_name: str,
        file_path: str,
        branch: str = None,
    ) -> Dict[str, Any]:
        """Read content of a specific file.

        Args:
            repo_name: Repository name
            file_path: Relative path to the file
            branch: Branch/ref to read from (defaults to repo default branch)

        Returns:
            File content and metadata
        """
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"

            repo = self.client.get_repo(repo_name)
            kwargs = {}
            if branch:
                kwargs["ref"] = branch
            content_file = repo.get_contents(file_path.lstrip("/"), **kwargs)
            
            if isinstance(content_file, list):
                raise ValueError(f"'{file_path}' is a directory, not a file")
                
            return {
                "name": content_file.name,
                "path": content_file.path,
                "content": content_file.decoded_content.decode("utf-8"),
                "size": content_file.size,
                "encoding": content_file.encoding,
                "sha": content_file.sha,
                "url": content_file.html_url
            }
        except Exception as e:
            if "404" in str(e):
                raise ValueError(f"File or Repository not found: Check '{repo_name}/{file_path}'")
            logger.error(f"Failed to read file '{file_path}' in '{repo_name}': {e}")
            raise

    @handle_rate_limits
    def search_code(
        self,
        query: str,
        repo_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search code across repository.
        
        Args:
            query: Search query string
            repo_name: Optional repository name to narrow search
            
        Returns:
            Search results with file snippets
        """
        try:
            full_query = query
            if repo_name:
                if '/' not in repo_name:
                    repo_name = f"{self.user.login}/{repo_name}"
                full_query = f"{query} repo:{repo_name}"
            
            # Code search specifically. PyGithub's PaginatedList raises IndexError
            # when sliced on empty results (the lazy buffer has nothing to index),
            # so iterate with an explicit cap instead of using `results[:20]`.
            results = self.client.search_code(query=full_query)

            result_list = []
            for item in results:
                if len(result_list) >= 20:
                    break
                result_list.append({
                    "name": item.name,
                    "path": item.path,
                    "repo": item.repository.full_name,
                    "url": item.html_url,
                })

            return {
                "results": result_list,
                "count": len(result_list),
                "query": query,
                "note": "GitHub code search indexes with 30–60s lag for newly pushed content.",
            }
        except Exception as e:
            if "404" in str(e):
                raise ValueError(f"Repository '{repo_name}' not found for code search.")
            logger.error(f"Search failed for query '{query}': {e}")
            raise

    @handle_rate_limits
    def list_branches(self, repo_name: str) -> List[Dict[str, Any]]:
        """List all branches in a repository.

        Args:
            repo_name: Repository name (format: 'owner/repo' or just 'repo')

        Returns:
            List of branch information dicts
        """
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"

            repo = self.client.get_repo(repo_name)
            branches = repo.get_branches()

            result = []
            for branch in branches:
                result.append({
                    "name": branch.name,
                    "sha": branch.commit.sha,
                    "protected": branch.protected,
                })

            logger.info(
                f"Listed {len(result)} branches in {repo_name}",
                extra={"repo": repo_name, "count": len(result)}
            )
            return result

        except GithubException as e:
            logger.error(
                f"Failed to list branches in '{repo_name}': {e.status} - {e.data}",
                extra={"repo": repo_name, "status": e.status},
                exc_info=True,
            )
            raise

    @handle_rate_limits
    def create_branch(
        self,
        repo_name: str,
        branch_name: str,
        from_branch: str = "main",
    ) -> Dict[str, Any]:
        """Create a new branch in a repository.

        Args:
            repo_name: Repository name (format: 'owner/repo' or just 'repo')
            branch_name: Name of the new branch to create
            from_branch: Source branch to branch from (default: 'main')

        Returns:
            Created branch information
        """
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"

            repo = self.client.get_repo(repo_name)

            # Get the SHA of the source branch tip
            source_ref = repo.get_git_ref(f"heads/{from_branch}")
            source_sha = source_ref.object.sha

            start_time = time.time()
            new_ref = repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=source_sha,
            )
            duration = time.time() - start_time

            result = {
                "branch_name": branch_name,
                "from_branch": from_branch,
                "sha": source_sha,
                "ref": new_ref.ref,
            }

            logger.info(
                f"Created branch '{branch_name}' from '{from_branch}' in {repo_name} ({duration:.2f}s)",
                extra={"repo": repo_name, "branch": branch_name, "from": from_branch},
            )
            return result

        except GithubException as e:
            logger.error(
                f"Failed to create branch '{branch_name}' in '{repo_name}': {e.status} - {e.data}",
                extra={"repo": repo_name, "branch": branch_name, "status": e.status},
                exc_info=True,
            )
            raise

    @handle_rate_limits
    def delete_branch(self, repo_name: str, branch_name: str) -> Dict[str, Any]:
        """Delete a branch from a repository.

        Args:
            repo_name: Repository name (format: 'owner/repo' or just 'repo')
            branch_name: Name of the branch to delete

        Returns:
            Deletion confirmation
        """
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"

            repo = self.client.get_repo(repo_name)
            ref = repo.get_git_ref(f"heads/{branch_name}")
            ref.delete()

            result = {
                "deleted_branch": branch_name,
                "repo": repo_name,
                "status": "deleted",
            }

            logger.info(
                f"Deleted branch '{branch_name}' from {repo_name}",
                extra={"repo": repo_name, "branch": branch_name},
            )
            return result

        except GithubException as e:
            logger.error(
                f"Failed to delete branch '{branch_name}' in '{repo_name}': {e.status} - {e.data}",
                extra={"repo": repo_name, "branch": branch_name, "status": e.status},
                exc_info=True,
            )
            raise

    @handle_rate_limits
    def delete_repo(self, repo_name: str) -> Dict[str, Any]:
        """Delete a repository permanently.

        CRITICAL: This operation is irreversible.
        Uses exact-match lookup only — fuzzy matching is intentionally disabled.
        If the repository is not found with this exact name, raises an error and
        never guesses or suggests alternatives.

        Args:
            repo_name: Exact repository name (must be 'owner/repo' format)

        Returns:
            Deletion confirmation

        Raises:
            ValueError: If repo_name is not in 'owner/repo' format
            GithubException: If repo not found (404) or permission denied (403)
        """
        # Enforce exact owner/repo format — no auto-qualification allowed
        if '/' not in repo_name:
            raise ValueError(
                f"Repository name must be in 'owner/repo' format for deletion. "
                f"Got: '{repo_name}'. Refusing to guess the owner."
            )

        try:
            # Exact lookup — no fuzzy resolution at any layer
            repo = self.client.get_repo(repo_name)
            full_name = repo.full_name  # capture before deletion

            start_time = time.time()
            repo.delete()
            duration = time.time() - start_time

            result = {
                "deleted_repo": full_name,
                "status": "deleted",
            }

            logger.warning(
                f"DELETED repository: {full_name} (took {duration:.2f}s)",
                extra={"repo": full_name},
            )
            return result

        except GithubException as e:
            if e.status == 404:
                # Hard error — never suggest alternatives
                raise GithubException(
                    status=404,
                    data={"message": f"Repository '{repo_name}' not found. No repository was deleted."},
                    headers={}
                )
            logger.error(
                f"Failed to delete repo '{repo_name}': {e.status} - {e.data}",
                extra={"repo": repo_name, "status": e.status},
                exc_info=True,
            )
            raise


# Convenience functions for agent usage
def list_repos(
    token: Optional[str] = None,
    visibility: str = "all",
    sort: str = "updated",
    limit: int = 10,
    page: int = 1
) -> List[Dict[str, Any]]:
    """List user repositories (convenience wrapper)."""
    tools = GitHubTools(token=token)
    return tools.list_repos(visibility=visibility, sort=sort, limit=limit, page=page)


def create_repo(
    name: str,
    description: str = "",
    private: bool = False,
    token: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Create repository (convenience wrapper)."""
    tools = GitHubTools(token=token)
    return tools.create_repo(name=name, description=description, private=private, **kwargs)


def create_issue(
    repo_name: str,
    title: str,
    body: str = "",
    token: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Create issue (convenience wrapper)."""
    tools = GitHubTools(token=token)
    return tools.create_issue(repo_name=repo_name, title=title, body=body, **kwargs)


def commit_file(
    repo_name: str,
    file_path: str,
    content: Optional[str] = None,
    commit_message: str = "",
    token: Optional[str] = None,
    file_url: Optional[str] = None,
    delete: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """Commit file (convenience wrapper)."""
    tools = GitHubTools(token=token)
    return tools.commit_file(
        repo_name=repo_name,
        file_path=file_path,
        content=content,
        commit_message=commit_message,
        file_url=file_url,
        delete=delete,
        **kwargs
    )


def create_pull_request(
    repo_name: str,
    title: str,
    head: str,
    base: str = "main",
    body: str = "",
    token: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Create pull request (convenience wrapper)."""
    tools = GitHubTools(token=token)
    return tools.create_pull_request(
        repo_name=repo_name,
        title=title,
        head=head,
        base=base,
        body=body,
        **kwargs
    )
def browse_files(
    repo_name: str,
    path: str = "/",
    token: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Browse files (convenience wrapper)."""
    tools = GitHubTools(token=token)
    return tools.browse_files(repo_name=repo_name, path=path)


def read_file(
    repo_name: str,
    file_path: str,
    token: Optional[str] = None
) -> Dict[str, Any]:
    """Read file (convenience wrapper)."""
    tools = GitHubTools(token=token)
    return tools.read_file(repo_name=repo_name, file_path=file_path)


def search_code(
    query: str,
    repo_name: Optional[str] = None,
    token: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search code (convenience wrapper)."""
    tools = GitHubTools(token=token)
    return tools.search_code(query=query, repo_name=repo_name)
