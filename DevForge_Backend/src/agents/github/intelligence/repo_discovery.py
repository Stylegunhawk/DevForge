"""Intelligent repository discovery with fuzzy and semantic matching.

Internal component for github_operation tool - NOT a separate tool.
Provides fuzzy repo matching to handle ambiguous repo names.
"""

import logging
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from src.tools.github.tools import GitHubTools
from src.core.features import Feature, FeatureFlags

logger = logging.getLogger(__name__)


@dataclass
class RepoMatch:
    """Repository match result with confidence score"""
    
    full_name: str  # e.g., "owner/repo-name"
    confidence: float  # 0.0 to 1.0
    match_type: str  # "exact", "substring", "fuzzy"
    name: Optional[str] = None  # Short repo name
    description: Optional[str] = None  # Repo description
    url: Optional[str] = None  # Repo URL
    repo: Optional[Any] = None  # Optional PyGithub Repository object
    
    def __lt__(self, other):
        """Sort by confidence descending"""
        return self.confidence > other.confidence


class RepoDiscovery:
    """Intelligent repository discovery with fuzzy and semantic matching
    
    v0.8: Enhanced with performance caching (1hr TTL)
    """
    
    def __init__(self, github_tools: Optional[GitHubTools] = None):
        """Initialize with GitHub tools instance
        
        Args:
            github_tools: GitHubTools instance for API access (optional, creates one if not provided)
        """
        self.github_tools = github_tools or GitHubTools()
        self._repo_cache: Optional[List[dict]] = None
        self._cache_timestamp: float = 0
    
    async def fuzzy_search(
        self,
        query: str,
        max_results: int = 5
    ) -> List[RepoMatch]:
        """Fuzzy search for repositories
        
        Uses multiple matching strategies:
        1. Exact match
        2. Substring match
        3. Levenshtein distance (fuzzy)
        
        Args:
            query: Search query (e.g., "backend", "dfg bknd")
            max_results: Maximum number of results to return
            
        Returns:
            List of RepoMatch objects sorted by confidence
        """
        if not FeatureFlags.is_enabled(Feature.FUZZY_SEARCH):
            # Fallback to exact match only
            return await self._exact_match(query)
        
        # Get all repos (with caching)
        repos = await self._get_cached_repos()
        
        matches = []
        query_lower = query.lower()
        
        for repo in repos:
            repo_name_lower = repo["name"].lower()
            full_name_lower = repo["full_name"].lower()
            
            # 1. Exact match (highest confidence)
            if query_lower == repo_name_lower or query_lower == full_name_lower:
                matches.append(RepoMatch(
                    full_name=repo["full_name"],
                    name=repo["name"],
                    description=repo.get("description"),
                    url=repo.get("url"),
                    confidence=1.0,
                    match_type="exact"
                ))
                continue
            
            # 2. Substring match (high confidence)
            if query_lower in repo_name_lower:
                confidence = 0.9 - (len(repo_name_lower) - len(query_lower)) * 0.01
                confidence = max(0.7, confidence)
                
                matches.append(RepoMatch(
                    full_name=repo["full_name"],
                    name=repo["name"],
                    description=repo.get("description"),
                    url=repo.get("url"),
                    confidence=confidence,
                    match_type="substring"
                ))
                continue
            
            # 3. Fuzzy match using Levenshtein distance
            similarity = self._levenshtein_similarity(query_lower, repo_name_lower)
            
            if similarity > 0.5:
                matches.append(RepoMatch(
                    full_name=repo["full_name"],
                    name=repo["name"],
                    description=repo.get("description"),
                    url=repo.get("url"),
                    confidence=similarity,
                    match_type="fuzzy"
                ))
        
        # Sort by confidence and return top matches
        matches.sort()
        return matches[:max_results]
    
    async def _exact_match(self, query: str) -> List[RepoMatch]:
        """Fallback exact match when fuzzy search disabled"""
        repos = await self._get_cached_repos()
        
        for repo in repos:
            if query.lower() in [repo["name"].lower(), repo["full_name"].lower()]:
                return [RepoMatch(
                    full_name=repo["full_name"],
                    name=repo["name"],
                    description=repo.get("description"),
                    url=repo.get("url"),
                    confidence=1.0,
                    match_type="exact"
                )]
        
        return []
    
    async def _get_cached_repos(self) -> List[dict]:
        """Get repos with caching
        
        Returns:
            List of repository dictionaries
        """
        from src.core.config import settings
        
        current_time = time.time()
        cache_ttl = getattr(settings, 'GITOPS_REPO_CACHE_TTL', 3600)  # Default 1hr
        
        # Return cached if still valid
        if self._repo_cache and (current_time - self._cache_timestamp) < cache_ttl:
            return self._repo_cache
        
        # Fetch fresh data
        logger.info("Refreshing repo cache")
        self._repo_cache = self.github_tools.list_repos(limit=100)
        self._cache_timestamp = current_time
        
        return self._repo_cache
    
    def _levenshtein_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity between two strings using Levenshtein distance
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Use difflib's SequenceMatcher for simplicity
        return SequenceMatcher(None, s1, s2).ratio()
    
    # =========================================================================
    # Compatibility Aliases (for backward compatibility with existing tests)
    # =========================================================================
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings.
        
        Compatibility alias - converts similarity ratio to edit distance.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Edit distance (number of operations to transform s1 to s2)
        """
        # Simple implementation using dynamic programming
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity between two strings.
        
        Compatibility alias for _levenshtein_similarity.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        return self._levenshtein_similarity(s1, s2)
    
    async def get_best_match(
        self,
        query: str,
        confidence_threshold: float = 0.85
    ) -> Optional[RepoMatch]:
        """Get single best match above confidence threshold
        
        Args:
            query: Search query
            confidence_threshold: Minimum confidence to auto-select
            
        Returns:
            Best match if above threshold, None otherwise
        """
        matches = await self.fuzzy_search(query, max_results=1)
        
        if not matches:
            return None
        
        best_match = matches[0]
        
        if best_match.confidence >= confidence_threshold:
            return best_match
        
        return None
    
    def format_disambiguation_response(
        self,
        matches: List[RepoMatch]
    ) -> dict:
        """Format disambiguation response for Lobe Chat
        
        Args:
            matches: List of repo matches
            
        Returns:
            Response dict with disambiguation options
        """
        return {
            "success": False,
            "status": "needs_clarification",
            "message": "Multiple repositories match your query:",
            "options": [
                {
                    "full_name": match.full_name,
                    "name": match.name or match.full_name.split("/")[-1],
                    "description": match.description or "",
                    "confidence": round(match.confidence, 2),
                    "match_type": match.match_type
                }
                for match in matches[:3]
            ],
            "instruction": "Please specify which repository or use the full name (owner/repo)"
        }
