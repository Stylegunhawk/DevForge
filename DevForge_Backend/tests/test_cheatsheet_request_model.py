"""Tests for cheatsheet request model (v0.11)."""

import pytest
from pydantic import ValidationError

from src.agents.cheatsheet.request_model import CheatsheetRequest


def test_accepts_language_only():
    req = CheatsheetRequest(language="python")
    assert req.skill_level == "beginner"
    assert req.intent is None


def test_accepts_code_context_only():
    CheatsheetRequest(code_context="def foo(): pass")


def test_accepts_intent_only():
    CheatsheetRequest(intent="debugging async deadlock")


def test_rejects_all_three_missing():
    with pytest.raises(ValidationError):
        CheatsheetRequest()


def test_skill_level_enum():
    with pytest.raises(ValidationError):
        CheatsheetRequest(language="python", skill_level="novice")


def test_intent_max_length():
    with pytest.raises(ValidationError):
        CheatsheetRequest(intent="x" * 401)


def test_code_context_max_length():
    with pytest.raises(ValidationError):
        CheatsheetRequest(code_context="x" * 20001)
