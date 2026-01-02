"""Tests for repo discovery intelligence component.

Comprehensive tests for fuzzy repo matching and discovery.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass

from src.agents.github.intelligence.repo_discovery import RepoDiscovery, RepoMatch


class TestRepoMatch:
    """Test RepoMatch dataclass"""
    
    def test_repo_match_creation(self):
        """Test creating RepoMatch"""
        match = RepoMatch(
            full_name="owner/repo",
            confidence=0.95,
            match_type="exact",
            repo=MagicMock()
        )
        
        assert match.full_name == "owner/repo"
        assert match.confidence == 0.95
        assert match.match_type == "exact"
    
    def test_repo_match_sorting(self):
        """Test RepoMatch sorts by confidence descending"""
        match1 = RepoMatch(full_name="a/repo1", confidence=0.95, match_type="exact", repo=MagicMock())
        match2 = RepoMatch(full_name="b/repo2", confidence=0.85, match_type="fuzzy", repo=MagicMock())
        match3 = RepoMatch(full_name="c/repo3", confidence=0.90, match_type="fuzzy", repo=MagicMock())
        
        sorted_matches = sorted([match1, match2, match3])
        
        # Higher confidence first
        assert sorted_matches[0].confidence == 0.95
        assert sorted_matches[1].confidence == 0.90
        assert sorted_matches[2].confidence == 0.85


class TestRepoDiscovery:
    """Test RepoDiscovery class"""
    
    @pytest.fixture
    def discovery(self):
        """Create RepoDiscovery with mocked tools"""
        with patch('src.agents.github.intelligence.repo_discovery.GitHubTools'):
            return RepoDiscovery()
    
    def test_levenshtein_distance(self, discovery):
        """Test Levenshtein distance calculation"""
        # Exact match
        assert discovery._levenshtein_distance("test", "test") == 0
        
        # One character difference
        assert discovery._levenshtein_distance("test", "tess") == 1
        
        # Complete difference
        assert discovery._levenshtein_distance("abc", "xyz") == 3
        
        # Empty strings
        assert discovery._levenshtein_distance("", "test") == 4
        assert discovery._levenshtein_distance("test", "") == 4
    
    def test_calculate_similarity(self, discovery):
        """Test similarity calculation"""
        # Exact match
        assert discovery._calculate_similarity("test", "test") == 1.0
        
        # High similarity
        similarity = discovery._calculate_similarity("backend", "backend-api")
        assert similarity > 0.5
        
        # Low similarity
        similarity = discovery._calculate_similarity("abc", "xyz")
        assert similarity < 0.3
    
    @pytest.mark.asyncio
    async def test_exact_match(self, discovery):
        """Test exact repository match"""
        mock_repos = [{
            "full_name": "owner/my-repo",
            "name": "my-repo",
            "description": "Test Repo",
            "url": "https://github.com/owner/my-repo"
        }]
        
        discovery.github_tools.list_repos.return_value = mock_repos
        
        matches = await discovery.fuzzy_search("my-repo")
        
        assert len(matches) >= 1
        # Exact match should have high confidence
        best_match = matches[0]
        assert best_match.confidence >= 0.90
    
    @pytest.mark.asyncio
    async def test_fuzzy_match(self, discovery):
        """Test fuzzy repository matching"""
        mock_repos = [{
            "full_name": "owner/backend-api",
            "name": "backend-api",
            "description": "Backend API",
            "url": "https://github.com/owner/backend-api"
        }]
        
        discovery.github_tools.list_repos.return_value = mock_repos
        
        # Search with partial name
        matches = await discovery.fuzzy_search("backend")
        
        assert len(matches) >= 1
        assert matches[0].match_type in ["fuzzy", "substring"]
    
    @pytest.mark.asyncio
    async def test_no_match(self, discovery):
        """Test no matching repositories"""
        discovery.github_tools.list_repos.return_value = []
        
        matches = await discovery.fuzzy_search("nonexistent-repo")
        
        assert len(matches) == 0
    
    @pytest.mark.asyncio
    async def test_max_results(self, discovery):
        """Test max_results limit"""
        # Create 10 mock repos
        mock_repos = []
        for i in range(10):
            mock_repos.append({
                "full_name": f"owner/repo-{i}",
                "name": f"repo-{i}",
                "description": f"Repo {i}",
                "url": f"https://github.com/owner/repo-{i}"
            })
        
        discovery.github_tools.list_repos.return_value = mock_repos
        
        matches = await discovery.fuzzy_search("repo", max_results=3)
        
        assert len(matches) <= 3
    
    @pytest.mark.asyncio
    async def test_case_insensitive(self, discovery):
        """Test case-insensitive matching"""
        mock_repos = [{
            "full_name": "owner/MyRepo",
            "name": "MyRepo",
            "description": "My Repo",
            "url": "https://github.com/owner/MyRepo"
        }]
        
        discovery.github_tools.list_repos.return_value = mock_repos
        
        matches = await discovery.fuzzy_search("myrepo")
        
        assert len(matches) >= 1
        assert matches[0].confidence > 0.5


class TestRepoDiscoveryCaching:
    """Test caching functionality"""
    
    @pytest.mark.asyncio
    async def test_caching_logic(self):
        """Test that repos are cached and API is not recalled"""
        with patch('src.agents.github.intelligence.repo_discovery.GitHubTools') as MockTools:
            mock_tools = MockTools.return_value
            mock_repos = [{"name": "repo1", "full_name": "owner/repo1"}]
            mock_tools.list_repos.return_value = mock_repos
            
            discovery = RepoDiscovery(github_tools=mock_tools)
            
            # First call - should hit API
            matches1 = await discovery.fuzzy_search("repo1")
            assert len(matches1) == 1
            assert mock_tools.list_repos.call_count == 1
            
            # Second call - should use cache
            matches2 = await discovery.fuzzy_search("repo1")
            assert len(matches2) == 1
            assert mock_tools.list_repos.call_count == 1  # count should not increase


class TestRepoDiscoveryEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.fixture
    def discovery(self):
        with patch('src.agents.github.intelligence.repo_discovery.GitHubTools') as MockTools:
            return RepoDiscovery(github_tools=MockTools.return_value)
    
    @pytest.mark.asyncio
    async def test_empty_query(self, discovery):
        """Test empty search query"""
        discovery.github_tools.list_repos.return_value = []
        matches = await discovery.fuzzy_search("")
        
        # Should return empty or all repos
        assert isinstance(matches, list)
    
    @pytest.mark.asyncio
    async def test_special_characters(self, discovery):
        """Test query with special characters"""
        mock_repos = [{
            "full_name": "owner/my-repo",
            "name": "my-repo",
            "description": "Repo",
            "url": "http://url"
        }]
        
        discovery.github_tools.list_repos.return_value = mock_repos
        
        # Should handle special chars gracefully
        matches = await discovery.fuzzy_search("my-repo!")
        assert isinstance(matches, list)
    
    @pytest.mark.asyncio
    async def test_github_api_error(self, discovery):
        """Test GitHub API error handling"""
        discovery.github_tools.list_repos.side_effect = Exception("API Error")
        
        with pytest.raises(Exception):
            await discovery.fuzzy_search("repo")
