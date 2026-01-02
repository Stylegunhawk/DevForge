"""Security and validation utilities for GitHub operations.

Implements token scope checking, input sanitization, and permission validation.
"""

import re
import logging
from typing import List, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """GitHub token information"""
    scopes: Set[str]
    has_admin: bool
    rate_limit_remaining: int


class SecurityValidator:
    """Security validation for GitHub operations"""
    
    # Required scopes for different operations
    SCOPE_REQUIREMENTS = {
        "read_repos": {"repo"},
        "create_repo": {"repo", "admin:org"},  # admin:org if creating in org
        "delete_repo": {"repo", "delete_repo"},
        "create_issue": {"repo"},
        "create_pr": {"repo"},
        "commit_file": {"repo"},
        "scaffold_repo": {"repo", "admin:org"},  # May need admin
        "ci_analysis": {"repo"},
        "changelog": {"repo"}
    }
    
    def __init__(self, github_client):
        """Initialize with GitHub client
        
        Args:
            github_client: PyGithub client instance
        """
        self.github_client = github_client
        self._token_info = None
    
    def get_token_info(self) -> TokenInfo:
        """Get token information including scopes
        
        Returns:
            TokenInfo with scopes and rate limit
        """
        if self._token_info is None:
            # Get authenticated user to check token
            user = self.github_client.get_user()
            
            # Get scopes from OAuth header (if available)
            # Note: PyGithub doesn't expose this directly, we'd need to check headers
            # For now, we'll do a best-effort check
            scopes = set()
            
            try:
                # Try to check admin access
                try:
                    # Attempt admin operation (will fail if no admin scope)
                    orgs = list(user.get_orgs())
                    if orgs:
                        scopes.add("admin:org")
                except:
                    pass
                
                # Assume repo scope if we can get repos
                repos = list(user.get_repos())
                if repos:
                    scopes.add("repo")
                
                # Check rate limit
                rate_limit = self.github_client.get_rate_limit()
                remaining = rate_limit.core.remaining
                
                self._token_info = TokenInfo(
                    scopes=scopes,
                    has_admin="admin:org" in scopes,
                    rate_limit_remaining=remaining
                )
                
            except Exception as e:
                logger.error(f"Failed to get token info: {e}")
                # Return minimal info
                self._token_info = TokenInfo(
                    scopes={"repo"},  # Assume basic repo access
                    has_admin=False,
                    rate_limit_remaining=0
                )
        
        return self._token_info
    
    def ensure_token_scopes(
        self,
        operation: str,
        required_scopes: Optional[List[str]] = None
    ):
        """Ensure token has required scopes for operation
        
        Args:
            operation: Operation name
            required_scopes: Optional list of required scopes (overrides defaults)
            
        Raises:
            PermissionError: If token lacks required scopes
        """
        if required_scopes is None:
            required_scopes = self.SCOPE_REQUIREMENTS.get(operation, {"repo"})
        else:
            required_scopes = set(required_scopes)
        
        token_info = self.get_token_info()
        missing = required_scopes - token_info.scopes
        
        if missing:
            raise PermissionError(
                f"Token missing required scopes for '{operation}': {sorted(missing)}. "
                f"Please add these scopes to your GitHub Personal Access Token."
            )
        
        logger.info(f"Token has required scopes for '{operation}': {sorted(required_scopes)}")
    
    def check_rate_limit(self, min_remaining: int = 100) -> bool:
        """Check if rate limit is sufficient
        
        Args:
            min_remaining: Minimum remaining requests required
            
        Returns:
            True if sufficient rate limit, False otherwise
        """
        token_info = self.get_token_info()
        
        if token_info.rate_limit_remaining < min_remaining:
            logger.warning(
                f"Low rate limit: {token_info.rate_limit_remaining} remaining "
                f"(minimum: {min_remaining})"
            )
            return False
        
        return True


class InputValidator:
    """Input validation and sanitization"""
    
    # Repository name pattern: lowercase, numbers, hyphens, underscores, dots
    REPO_NAME_PATTERN = re.compile(r'^[a-z0-9._-]+$')
    
    # Max lengths
    MAX_REPO_NAME_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 200
    MAX_COMMIT_MESSAGE_LENGTH = 500
    
    @classmethod
    def validate_repo_name(cls, name: str) -> str:
        """Validate and sanitize repository name
        
        Args:
            name: Repository name to validate
            
        Returns:
            Sanitized repository name
            
        Raises:
            ValueError: If name is invalid
        """
        if not name:
            raise ValueError("Repository name cannot be empty")
        
        # Convert to lowercase
        name = name.lower().strip()
        
        # Check length
        if len(name) > cls.MAX_REPO_NAME_LENGTH:
            raise ValueError(
                f"Repository name too long (max {cls.MAX_REPO_NAME_LENGTH} characters)"
            )
        
        # Check pattern
        if not cls.REPO_NAME_PATTERN.match(name):
            raise ValueError(
                "Repository name can only contain lowercase letters, numbers, "
                "hyphens, underscores, and dots"
            )
        
        # Reserved names
        if name in [".", "..", "git", ".git"]:
            raise ValueError(f"'{name}' is a reserved repository name")
        
        return name
    
    @classmethod
    def sanitize_description(cls, description: Optional[str]) -> Optional[str]:
        """Sanitize repository description
        
        Args:
            description: Description to sanitize
            
        Returns:
            Sanitized description or None
        """
        if not description:
            return None
        
        # Strip HTML tags
        description = re.sub(r'<[^>]+>', '', description)
        
        # Strip excessive whitespace
        description = ' '.join(description.split())
        
        # Truncate if too long
        if len(description) > cls.MAX_DESCRIPTION_LENGTH:
            description = description[:cls.MAX_DESCRIPTION_LENGTH - 3] + "..."
        
        return description.strip()
    
    @classmethod
    def sanitize_commit_message(cls, message: str) -> str:
        """Sanitize commit message
        
        Args:
            message: Commit message to sanitize
            
        Returns:
            Sanitized commit message
        """
        if not message:
            raise ValueError("Commit message cannot be empty")
        
        # Remove control characters
        message = ''.join(char for char in message if ord(char) >= 32 or char in '\n\r\t')
        
        # Truncate if too long
        if len(message) > cls.MAX_COMMIT_MESSAGE_LENGTH:
            first_line = message.split('\n')[0]
            if len(first_line) > 72:  # Standard first line length
                first_line = first_line[:69] + "..."
            message = first_line
        
        return message.strip()
    
    @classmethod
    def validate_enum(cls, value: str, allowed: List[str], param_name: str) -> str:
        """Validate enum parameter
        
        Args:
            value: Value to validate
            allowed: List of allowed values
            param_name: Parameter name for error message
            
        Returns:
            Validated value
            
        Raises:
            ValueError: If value not in allowed list
        """
        if value not in allowed:
            raise ValueError(
                f"Invalid {param_name}: '{value}'. "
                f"Allowed values: {', '.join(allowed)}"
            )
        
        return value


def check_idempotency(
    github_client,
    owner: str,
    repo_name: str,
    force: bool = False
) -> dict:
    """Check if repository already exists (idempotency)
    
    Args:
        github_client: PyGithub client
        owner: Repository owner
        repo_name: Repository name
        force: Whether to force creation
        
    Returns:
        Dict with exists flag and message
    """
    try:
        repo = github_client.get_repo(f"{owner}/{repo_name}")
        
        if not force:
            return {
                "exists": True,
                "success": False,
                "error": f"Repository '{owner}/{repo_name}' already exists",
                "options": [
                    "Use force=true to proceed anyway",
                    "Choose a different repository name"
                ],
                "existing_repo_url": repo.html_url
            }
        else:
            logger.warning(f"Repository {owner}/{repo_name} exists but force=true")
            return {"exists": True, "forced": True}
            
    except Exception:
        # Repository doesn't exist - good to proceed
        return {"exists": False}
