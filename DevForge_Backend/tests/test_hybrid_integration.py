"""End-to-end integration tests for Hybrid LLM Cheatsheet System.

Verifies the full pipeline from Agent -> Router -> [LLM|Template] -> Response.
External APIs (Anthropic, Brave) are mocked to ensure stability.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.cheatsheet.agent import CheatsheetAgent, generate_cheatsheet_invoke

@pytest.mark.asyncio
class TestHybridIntegration:
    
    def setup_method(self):
        # Reset singleton if needed or create fresh instance
        self.agent = CheatsheetAgent()
        
    async def test_template_path_pandas(self):
        """Test that stable libraries (Pandas) still use the fast template path."""
        args = {
            "query": "pandas dataframe",
            "code_context": "import pandas as pd",
            "language": "python"
        }
        
        # Mock LLM generator to ensure it's NOT called
        self.agent.llm_generator = AsyncMock()
        
        result = await self.agent.generate(args)
        
        assert result['success'] is True
        assert result['data']['method'] == 'template'
        assert not self.agent.llm_generator.generate.called
        
    async def test_llm_path_sql(self):
        """Test that unsupported languages (SQL) route to LLM."""
        args = {
            "query": "sql joins",
            "code_context": "SELECT * FROM users",
            "language": "sql"
        }
        
        # Mock LLM Generator success
        mock_llm_response = MagicMock()
        mock_llm_response.markdown = "# SQL Joins\n..."
        mock_llm_response.generation_method = "llm_primary"
        mock_llm_response.web_search_used = False
        mock_llm_response.sources = []
        mock_llm_response.validation_score = 95.0
        mock_llm_response.quality_indicators = {}
        mock_llm_response.retry_count = 0
        
        # We need to mock the internal LLM generator of the agent
        # Since agent init creates it, we patch it on the instance
        self.agent.llm_generator = AsyncMock()
        self.agent.llm_generator.generate.return_value = mock_llm_response
        self.agent.domain_detector.should_use_llm = MagicMock(return_value=(True, "unsupported_language:sql"))
        
        result = await self.agent.generate(args)
        
        assert result['success'] is True
        assert result['data']['method'] == 'llm_primary'
        assert result['data']['llm_generated'] is True
        assert result['data']['routing_reason'] == "unsupported_language:sql"
        
    async def test_llm_fallback_on_validation_failure(self):
        """Test that if LLM fails (exception), we fall back gracefully."""
        args = {
            "query": "sql joins",
            "language": "sql"
        }
        
        # Mock LLM to raise exception
        self.agent.llm_generator = AsyncMock()
        self.agent.llm_generator.generate.side_effect = Exception("LLM API Down")
        
        # Force routing to LLM
        self.agent.domain_detector.should_use_llm = MagicMock(return_value=(True, "unsupported_language:sql"))
        
        # Should not crash, but return success=True (generic fallback or error message)
        # Note: Current implementation falls through to select_sections. 
        # For SQL, select_sections falls back to Python template (the original bug), 
        # OR returns empty sections if we fixed it.
        # Let's check what it returns.
        
        result = await self.agent.generate(args)
        
        # The agent catches the exception and falls through to template logic
        # For SQL, it might return generic python content or empty
        # We just want to ensure it caught the error and didn't crash
        assert result['success'] is True
        # Method should NOT be llm-based
        assert result['data'].get('llm_generated') is not True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
