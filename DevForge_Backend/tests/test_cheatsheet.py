"""Tests for Cheat Sheet Agent."""

import pytest
from src.agents.cheatsheet.agent import CheatsheetAgent, generate_cheatsheet_invoke

@pytest.mark.asyncio
async def test_generate_python_beginner():
    """Test generating a beginner Python cheat sheet."""
    agent = CheatsheetAgent()
    result = await agent.generate(language="python", skill_level="beginner")
    
    assert result["success"] is True
    assert result["language"] == "python"
    assert result["skill_level"] == "beginner"
    assert "Python Cheat Sheet - Beginner" in result["markdown"]
    assert "Variables & Types" in result["markdown"]

@pytest.mark.asyncio
async def test_generate_javascript_intermediate():
    """Test generating an intermediate JavaScript cheat sheet."""
    agent = CheatsheetAgent()
    result = await agent.generate(language="javascript", skill_level="intermediate")
    
    assert result["success"] is True
    assert result["language"] == "javascript"
    assert "JavaScript Cheat Sheet - Intermediate" in result["markdown"]
    assert "DOM Manipulation" in result["markdown"]

@pytest.mark.asyncio
async def test_auto_detect_language():
    """Test language auto-detection from code context."""
    agent = CheatsheetAgent()
    code = "def my_func(): print('hello')"
    result = await agent.generate(code_context=code, skill_level="expert")
    
    assert result["success"] is True
    assert result["language"] == "python"
    assert "Python Cheat Sheet - Expert" in result["markdown"]

@pytest.mark.asyncio
async def test_gateway_invoke_wrapper():
    """Test the gateway wrapper function."""
    result = await generate_cheatsheet_invoke({
        "language": "typescript",
        "skill_level": "beginner"
    })
    
    assert result["success"] is True
    assert result["data"]["language"] == "typescript"
    assert "TypeScript Cheat Sheet - Beginner" in result["data"]["markdown"]
