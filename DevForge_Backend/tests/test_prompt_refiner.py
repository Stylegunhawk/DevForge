"""Tests for Prompt Refiner Agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.prompt_refiner.agent import PromptRefinerAgent, refine_prompt_invoke
from src.agents.prompt_refiner.domain_handlers import DOMAIN_CONFIGS


@pytest.fixture
def mock_model_router():
    with patch("src.agents.prompt_refiner.enhancer.model_router") as mock:
        mock_chat = AsyncMock()
        mock_chat.ainvoke.return_value = MagicMock(content="Refined Prompt Content")
        mock.get_chat_model.return_value = mock_chat
        mock.select_model_by_task.return_value = "test-model"
        yield mock


@pytest.mark.asyncio
async def test_refine_general_prompt(mock_model_router):
    """Test refining a general prompt."""
    agent = PromptRefinerAgent()
    result = await agent.refine("Fix this bug", domain="general")
    
    assert result["success"] is True
    assert result["original_prompt"] == "Fix this bug"
    assert result["refined_prompt"] == "Refined Prompt Content"
    assert result["domain"] == "general"


@pytest.mark.asyncio
async def test_refine_image_prompt(mock_model_router):
    """Test refining an image prompt."""
    agent = PromptRefinerAgent()
    result = await agent.refine("A cat", domain="image")
    
    assert result["success"] is True
    assert result["domain"] == "image"
    # Verify template selection indirectly via success


@pytest.mark.asyncio
async def test_refine_code_prompt_with_context(mock_model_router):
    """Test refining a code prompt with file context."""
    agent = PromptRefinerAgent()
    context = "def hello(): pass"
    result = await agent.refine(
        "Add type hints", 
        domain="code", 
        file_context=context
    )
    
    assert result["success"] is True
    assert result["domain"] == "code"


@pytest.mark.asyncio
async def test_invalid_domain_fallback(mock_model_router):
    """Test fallback to general domain for invalid input."""
    agent = PromptRefinerAgent()
    result = await agent.refine("Hello", domain="invalid_domain")
    
    assert result["success"] is True
    assert result["domain"] == "general"


@pytest.mark.asyncio
async def test_gateway_invoke_wrapper(mock_model_router):
    """Test the gateway wrapper function."""
    result = await refine_prompt_invoke({
        "prompt": "Test prompt",
        "domain": "llm"
    })
    
    assert result["success"] is True
    assert result["tool"] == "refine_prompt"
    assert result["data"]["refined_prompt"] == "Refined Prompt Content"
