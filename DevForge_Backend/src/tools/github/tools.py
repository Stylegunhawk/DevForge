# src/tools/github/tools.py
"""
GitHub operations tools using PyGithub.
Phase 3.3 implementation.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from github import Github, GithubException, Auth
from github.Repository import Repository
from github.GithubObject import NotSet

from src.core.config import settings

logger = logging.getLogger(__name__)


class GitHubTools:
    """GitHub API operations wrapper using PyGithub."""
    
    def __init__(self, token: Optional[str] = None):
        """Initialize GitHub client.
        
        Args:
            token: GitHub personal access token. Falls back to settings.GITHUB_TOKEN
        """
        self.token = token or settings.GITHUB_TOKEN
        if not self.token:
            raise ValueError(
                "GitHub token required. Set GITHUB_TOKEN in .env or pass token parameter"
            )
        
        auth = Auth.Token(self.token)
        self.client = Github(auth=auth)
        self.user = self.client.get_user()
        
        logger.info(
            f"GitHub client initialized for user: {self.user.login}",
            extra={"username": self.user.login}
        )
    
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
            repos = self.user.get_repos(
                visibility=visibility,
                sort=sort
            )
            
            result = []
            for repo in repos[:limit]:
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
                f"Listed {len(result)} repositories",
                extra={"count": len(result), "visibility": visibility}
            )
            return result
            
        except GithubException as e:
            logger.error(
                f"Failed to list repos: {e.status} - {e.data}",
                extra={"status": e.status, "error": str(e)},
                exc_info=True
            )
            raise
    
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
            repo = self.user.create_repo(
                name=name,
                description=description or NotSet,
                private=private,
                auto_init=auto_init,
                gitignore_template=gitignore_template or NotSet,
                license_template=license_template or NotSet
            )
            
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
                f"Created repository: {repo.full_name}",
                extra={"repo": repo.full_name, "private": private}
            )
            return result
            
        except GithubException as e:
            logger.error(
                f"Failed to create repo '{name}': {e.status} - {e.data}",
                extra={"repo_name": name, "status": e.status, "error": str(e)},
                exc_info=True
            )
            raise
    
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
            
            issue = repo.create_issue(
                title=title,
                body=body or NotSet,
                labels=labels or NotSet,
                assignees=assignees or NotSet
            )
            
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
                f"Created issue #{issue.number} in {repo_name}",
                extra={"repo": repo_name, "issue_number": issue.number}
            )
            return result
            
        except GithubException as e:
            logger.error(
                f"Failed to create issue in '{repo_name}': {e.status} - {e.data}",
                extra={"repo": repo_name, "status": e.status, "error": str(e)},
                exc_info=True
            )
            raise
    
    def commit_file(
        self,
        repo_name: str,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str = "main",
        create_if_missing: bool = True
    ) -> Dict[str, Any]:
        """Commit a file to a repository.
        
        Args:
            repo_name: Repository name (format: 'owner/repo' or just 'repo')
            file_path: Path to file in repo (e.g., 'src/app.py')
            content: File content as string
            commit_message: Commit message
            branch: Branch name (default: 'main')
            create_if_missing: Create file if it doesn't exist, else update
            
        Returns:
            Commit information
        """
        try:
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            
            repo = self.client.get_repo(repo_name)
            
            # Check if file exists
            try:
                existing_file = repo.get_contents(file_path, ref=branch)
                # File exists - update it
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
                    # File doesn't exist - create it
                    result = repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=content,
                        branch=branch
                    )
                    action = "created"
                else:
                    raise
            
            commit_info = {
                "action": action,
                "file_path": file_path,
                "commit_sha": result["commit"].sha,
                "commit_message": commit_message,
                "branch": branch,
                "url": result["commit"].html_url,
            }
            
            logger.info(
                f"{action.capitalize()} file '{file_path}' in {repo_name}",
                extra={"repo": repo_name, "file": file_path, "action": action}
            )
            return commit_info
            
        except GithubException as e:
            logger.error(
                f"Failed to commit file '{file_path}' to '{repo_name}': {e.status} - {e.data}",
                extra={"repo": repo_name, "file": file_path, "status": e.status, "error": str(e)},
                exc_info=True
            )
            raise
    
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
            
            pr = repo.create_pull(
                title=title,
                body=body or NotSet,
                head=head,
                base=base,
                draft=draft
            )
            
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
                f"Created PR #{pr.number} in {repo_name}: {head} -> {base}",
                extra={"repo": repo_name, "pr_number": pr.number, "head": head, "base": base}
            )
            return result
            
        except GithubException as e:
            logger.error(
                f"Failed to create PR in '{repo_name}': {e.status} - {e.data}",
                extra={"repo": repo_name, "status": e.status, "error": str(e)},
                exc_info=True
            )
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
    content: str,
    commit_message: str,
    token: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Commit file (convenience wrapper)."""
    tools = GitHubTools(token=token)
    return tools.commit_file(
        repo_name=repo_name,
        file_path=file_path,
        content=content,
        commit_message=commit_message,
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