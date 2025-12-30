"""Unit tests for LLM cheatsheet generator (Mocked)."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.cheatsheet.llm_generator import LLMCheatsheetGenerator, ValidationError
from src.agents.cheatsheet.validators import ValidationResult

@pytest.mark.asyncio
class TestLLMCheatsheetGenerator:
    
    def setup_method(self):
        self.mock_validator = MagicMock()
        self.generator = LLMCheatsheetGenerator(
            validator=self.mock_validator,
            web_search_enabled=True
        )
        # Mock dependencies
        # Mock dependencies
        # self.generator.client = MagicMock() -> Removed
        self.generator.search_client = AsyncMock()
        self.generator.search_client.search_docs.return_value = []
        
    async def test_successful_generation(self):
        """Test happy path with valid output."""
        with patch("src.agents.cheatsheet.llm_generator.generate_text", new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "# Valid Markdown"
            
            # Setup validator passing
            self.mock_validator.validate.return_value = ValidationResult(
                passed=True, errors=[], quality_score=90.0
            )
            
            result = await self.generator.generate("python loops")
            
            assert result.markdown == "# Valid Markdown"
            assert result.retry_count == 0
            assert result.llm_generated is True
            mock_generate.assert_called_once()
        
    async def test_validation_retry_success(self):
        """Test validation failure triggers retry which succeeds."""
        with patch("src.agents.cheatsheet.llm_generator.generate_text", new_callable=AsyncMock) as mock_generate:
            # Setup LLM responses: First bad, Second good
            mock_generate.side_effect = ["# Bad", "# Good"]
            
            # Setup validator: First fail, Second pass
            self.mock_validator.validate.side_effect = [
                ValidationResult(passed=False, errors=["Too short"]),
                ValidationResult(passed=True, errors=[])
            ]
            
            result = await self.generator.generate("python loops")
            
            assert result.markdown == "# Good"
            assert result.retry_count == 1
            assert mock_generate.call_count == 2
        
    async def test_hard_fail_after_retry(self):
        """Test double validation failure raises ValidationError."""
        with patch("src.agents.cheatsheet.llm_generator.generate_text", new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "# Bad"
            
            # Setup validator: Always fail
            self.mock_validator.validate.return_value = ValidationResult(
                passed=False, errors=["Still bad"]
            )
            
            with pytest.raises(ValidationError):
                await self.generator.generate("python loops")
            
    async def test_web_search_trigger(self):
        """Test web search is called for 'latest' queries."""
        with patch("src.agents.cheatsheet.llm_generator.generate_text", new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "# Info"
            self.mock_validator.validate.return_value = ValidationResult(passed=True)
        
        # Setup valid search results
        mock_search_result = MagicMock()
        mock_search_result.url = "http://example.com"
        mock_search_result.title = "Example"
        mock_search_result.description = "Desc"
        self.generator.search_client.search_docs.return_value = [mock_search_result]
        
        # Call with "latest"
        result = await self.generator.generate("latest python features")
        
        # Search should be called
        assert self.generator.search_client.search_docs.called
        assert result.web_search_used is True

    def test_should_search_logic(self):
        """Test internal search decision logic."""
        # Keyword trigger
        assert self.generator._should_search("latest python", []) is True
        # Library trigger
        with patch('src.agents.cheatsheet.domain_detector.DomainDetector.FAST_EVOLVING_LIBS', ['langchain']):
            assert self.generator._should_search("help", ["langchain"]) is True
        # Stable lib trigger (False)
        assert self.generator._should_search("help", ["pandas"]) is False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
