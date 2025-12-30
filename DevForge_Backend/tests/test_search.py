"""Unit tests for search functionality (brave_search.py and search_strategy.py)."""

import pytest
from unittest.mock import AsyncMock, patch
from src.agents.cheatsheet.brave_search import BraveSearchClient, SearchResult
from src.agents.cheatsheet.search_strategy import SearchQueryStrategy

class TestSearchQueryStrategy:
    """Test query generation strategy."""
    
    def setup_method(self):
        self.strategy = SearchQueryStrategy()
        
    def test_basic_query_generation(self):
        queries = self.strategy.build_queries(
            original_query="loops",
            detected_language="python",
            detected_libraries=[],
            skill_level="intermediate"
        )
        assert len(queries) >= 1
        assert "loops python cheatsheet" in queries
        
    def test_library_specific_queries(self):
        queries = self.strategy.build_queries(
            original_query="build chain",
            detected_language="python",
            detected_libraries=["langchain"],
            skill_level="expert"
        )
        # Should contain library specific query
        assert any("langchain latest documentation" in q for q in queries)
        
    def test_expert_skill_level_queries(self):
        queries = self.strategy.build_queries(
            original_query="advanced concepts",
            detected_language="rust",
            detected_libraries=[],
            skill_level="expert"
        )
        assert any("advanced patterns" in q for q in queries)


@pytest.mark.asyncio
class TestBraveSearchClient:
    """Test Brave Search Client with mocked API."""
    
    async def test_search_returns_results(self):
        mock_response = {
            "web": {
                "results": [
                    {
                        "title": "Python Docs",
                        "url": "https://docs.python.org",
                        "description": "Official documentation",
                        "age": "2024"
                    }
                ]
            }
        }
        
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None
            )
            
            client = BraveSearchClient(api_key="test_key")
            results = await client.search_docs("python")
            
            assert len(results) == 1
            assert results[0].title == "Python Docs"
            assert results[0].url == "https://docs.python.org"
            
    async def test_missing_api_key_returns_empty(self):
        """Test graceful failure without API key."""
        with patch.dict("os.environ", {}, clear=True):
            client = BraveSearchClient(api_key=None)
            results = await client.search_docs("python")
            assert results == []

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
