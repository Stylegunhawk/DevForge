"""High-level cheatsheet tests (v0.11).

LLM-touching tests tolerate both 'curated' and 'curated_unpersonalized'
quality — when Ollama is unavailable or returns malformed JSON, the
deterministic fallback still produces a valid sheet from the seed pack.
"""

import pytest

from src.agents.cheatsheet.agent import generate_cheatsheet_invoke


@pytest.mark.asyncio
async def test_python_beginner_explicit_language_returns_curated():
    result = await generate_cheatsheet_invoke(
        {"language": "python", "skill_level": "beginner",
         "intent": "learning python basics"},
        tenant_id="t", integration_name="i", user_id="u",
    )
    assert result["success"] is True
    data = result["data"]
    assert data["language"] == "python"
    assert data["skill_level"] == "beginner"
    assert data["quality"] in ("curated", "curated_unpersonalized")
    assert data["markdown"].startswith("# Python Cheat Sheet - Beginner")


@pytest.mark.asyncio
async def test_unsupported_language_returns_failure():
    result = await generate_cheatsheet_invoke(
        {"language": "cobol", "skill_level": "beginner"},
        tenant_id="t", integration_name="i", user_id="u",
    )
    assert result["success"] is False
    msg = result["data"]["message"].lower()
    assert "cobol" in msg or "not supported" in msg


@pytest.mark.asyncio
async def test_no_inputs_returns_failure():
    result = await generate_cheatsheet_invoke(
        {}, tenant_id="t", integration_name="i", user_id="u",
    )
    assert result["success"] is False
    msg = result["data"]["message"].lower()
    assert "language" in msg or "intent" in msg or "at least one" in msg


@pytest.mark.asyncio
async def test_auto_detect_language_from_code_context():
    result = await generate_cheatsheet_invoke(
        {"code_context": "def hello():\n    print('hi')\n",
         "skill_level": "beginner"},
        tenant_id="t", integration_name="i", user_id="u",
    )
    assert result["success"] is True
    assert result["data"]["language"] == "python"


@pytest.mark.asyncio
async def test_intent_only_request_with_language():
    result = await generate_cheatsheet_invoke(
        {"language": "python", "intent": "refactoring to typed code"},
        tenant_id="t", integration_name="i", user_id="u",
    )
    assert result["success"] is True
