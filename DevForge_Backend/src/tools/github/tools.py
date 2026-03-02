# src/tools/github/tools.py
"""
GitHub operations tools using PyGithub.
Phase 3.3 implementation with lazy initialization for test safety.
"""

import logging
import os
import time
from functools import wraps
import base64
import httpx
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from github import Github, GithubException, Auth, RateLimitExceededException
from github.Repository import Repository
from github.GithubObject import NotSet

logger = logging.getLogger(__name__)


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
        self._client = Github(auth=auth)
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
        limit: int = 10
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
            
            # Fetch slice immediately to force API call for timing measurement if lazy
            result = []
            fetched_repos = list(repos[:limit])
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
        file_url: Optional[str] = None
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
            
        Returns:
            Commit information
        """
        try:
            if not content and not file_url:
                raise ValueError("Either 'content' or 'file_url' must be provided")

            if file_url:
                logger.info(f"Fetching binary content from: {file_url}")
                max_retries = 3
                fetch_success = False
                for attempt in range(max_retries):
                    try:
                        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                            # Stream to check size before full download (Production Guard)
                            with client.stream("GET", file_url) as response:
                                response.raise_for_status()
                                content_length = response.headers.get("Content-Length")
                                if content_length and int(content_length) > 100 * 1024 * 1024:
                                    raise ValueError(f"File too large: {content_length} bytes (GitHub limit is 100MB)")
                                
                                content_bytes = response.read()
                                if len(content_bytes) > 100 * 1024 * 1024:
                                    raise ValueError(f"File too large: {len(content_bytes)} bytes (GitHub limit is 100MB)")
                                
                                # Log first 20 chars of encoded content for verification
                                encoded_debug = base64.b64encode(content_bytes[:50]).decode("utf-8")
                                logger.info(f"Encoded content preview (first 20 chars): {encoded_debug[:20]}")
                                
                                content = content_bytes
                                logger.info(f"Successfully fetched content ({len(content)} bytes)")
                                fetch_success = True
                                break
                    except (httpx.RequestError, httpx.HTTPStatusError) as e:
                        if attempt == max_retries - 1:
                            logger.error(f"Failed to fetch file after {max_retries} attempts: {e}")
                            raise
                        logger.warning(f"Fetch attempt {attempt + 1} failed: {e}. Retrying...")
                        time.sleep(1) # Simple backoff
                
                if not fetch_success:
                    raise RuntimeError(f"Failed to fetch content from {file_url}")

            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            
            repo = self.client.get_repo(repo_name)
            
            start_time = time.time()
            if file_url:
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
        file_path: str
    ) -> Dict[str, Any]:
        """Read content of a specific file.
        
        Args:
            repo_name: Repository name
            file_path: Relative path to the file
            
        Returns:
            File content and metadata
        """
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            
            repo = self.client.get_repo(repo_name)
            content_file = repo.get_contents(file_path.lstrip("/"))
            
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
            
            # Code search specifically
            results = self.client.search_code(query=full_query)
            
            result_list = []
            # Limit to top 20 results for performance
            for item in list(results[:20]):
                result_list.append({
                    "name": item.name,
                    "path": item.path,
                    "repo": item.repository.full_name,
                    "url": item.html_url
                })
                
            return result_list
        except Exception as e:
            if "404" in str(e):
                raise ValueError(f"Repository '{repo_name}' not found for code search.")
            logger.error(f"Search failed for query '{query}': {e}")
            raise


# Convenience functions for agent usage
def list_repos(
    token: Optional[str] = None,
    visibility: str = "all",
    sort: str = "updated",
    limit: int = 10
) -> List[Dict[str, Any]]:
    """List user repositories (convenience wrapper)."""
    tools = GitHubTools(token=token)
    return tools.list_repos(visibility=visibility, sort=sort, limit=limit)


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
