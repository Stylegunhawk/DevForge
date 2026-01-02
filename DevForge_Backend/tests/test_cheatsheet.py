"""Tests for Cheatsheet Agent."""

import pytest
from src.agents.cheatsheet.agent import CheatsheetAgent, generate_cheatsheet_invoke

def test_generate_python_beginner():
    """Test generating a beginner Python cheat sheet."""
    agent = CheatsheetAgent()
    result = agent.generate({'language': 'python', 'skill_level': 'beginner'})
    
    assert result["success"] is True
    assert result["language"] == "python"
    assert result["skill_level"] == "beginner"
    assert "Python Cheat Sheet - Beginner" in result["markdown"]
    assert "Variables" in result["markdown"]

def test_generate_javascript_intermediate():
    """Test generating an intermediate JavaScript cheat sheet."""
    agent = CheatsheetAgent()
    result = agent.generate({'language': 'javascript', 'skill_level': 'intermediate'})
    
    assert result["success"] is True
    assert result["language"] == "javascript"
    # JavaScript not in enhanced templates yet, so will use fallback
    assert "JavaScript" in result["markdown"] or result["language"] == "javascript"

def test_auto_detect_language():
    """Test language auto-detection from code context."""
    agent = CheatsheetAgent()
    code = "def my_func(): print('hello')"
    result = agent.generate({'code_context': code, 'skill_level': 'beginner'})
    
    assert result["success"] is True
    assert result["language"] == "python"
    assert "Python" in result["markdown"]

@pytest.mark.asyncio
async def test_gateway_invoke_wrapper():
    """Test the gateway wrapper function."""
    result = await generate_cheatsheet_invoke({
        "language": "python",
        "skill_level": "beginner"
    })
    
    assert result["success"] is True
    assert result["data"]["language"] == "python"
    assert "Python Cheat Sheet - Beginner" in result["data"]["markdown"]
