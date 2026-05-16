"""Tests for PromptEnhancer._compute_quality (v0.10).

Boundary cases per design spec §10.1:
    - empty signals → low, all four missing_signals
    - tokens=5, confidence=0.0 → medium (token gate alone)
    - tokens=8, confidence=0.7 → high (both gates)
    - tokens=1, confidence=0.9 → medium (confidence rescue)
"""

import pytest

from src.agents.prompt_refiner.enhancer import PromptEnhancer
from src.agents.prompt_refiner.context_types import (
    ChosenStack,
    CodeContext,
    CodeStructure,
    Evidence,
)


@pytest.fixture
def enhancer():
    return PromptEnhancer()


def _stack(languages=None, frameworks=None, databases=None, confidence=0.0):
    """Build a minimal ChosenStack with the typed lists we care about."""
    return ChosenStack(
        languages=languages or [],
        frameworks=frameworks or [],
        databases=databases or [],
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Grounding tier boundaries
# ---------------------------------------------------------------------------

def test_low_grounding_no_signals(enhancer):
    """Empty prompt-ish input with no evidence → low, all four missing."""
    q = enhancer._compute_quality("refactor", None, _stack())
    assert q["prompt_grounding"] == "low"
    assert set(q["missing_signals"]) == {"language", "framework", "database", "specificity"}
    # Low grounding triggers conversation_history suggestion; project_files
    # because framework+language missing; attached_files because no code.
    assert set(q["suggested_inputs"]) == {
        "attached_files", "conversation_history", "project_files",
    }


def test_medium_grounding_token_gate(enhancer):
    """tokens=5 alone bumps from low → medium even with zero confidence."""
    prompt = "fix the persistent login bug"  # 5 tokens
    q = enhancer._compute_quality(prompt, None, _stack())
    assert q["prompt_grounding"] == "medium"
    # specificity is satisfied (>=5 tokens); other three still missing
    assert "specificity" not in q["missing_signals"]
    assert "language" in q["missing_signals"]


def test_medium_grounding_confidence_rescue(enhancer):
    """Very short prompt + high confidence still produces medium."""
    stack = _stack(
        languages=["python"],
        frameworks=["FastAPI"],
        confidence=0.9,
    )
    q = enhancer._compute_quality("auth", None, stack)
    assert q["prompt_grounding"] == "medium"


def test_high_grounding_both_gates(enhancer):
    """tokens>=8 AND confidence>=0.7 produces high grounding."""
    prompt = "add OAuth2 with PKCE refresh-token rotation for FastAPI service"
    stack = _stack(
        languages=["python"],
        frameworks=["FastAPI"],
        databases=["PostgreSQL"],
        confidence=0.85,
    )
    q = enhancer._compute_quality(prompt, None, stack)
    assert q["prompt_grounding"] == "high"
    assert q["missing_signals"] == []


def test_high_grounding_requires_both_token_and_confidence(enhancer):
    """8 tokens but low confidence → still medium, not high."""
    prompt = "add OAuth2 with PKCE refresh-token rotation for service"  # 8 tokens
    q = enhancer._compute_quality(prompt, None, _stack(confidence=0.0))
    assert q["prompt_grounding"] == "medium"


# ---------------------------------------------------------------------------
# missing_signals composition
# ---------------------------------------------------------------------------

def test_missing_signals_drop_off_as_stack_fills(enhancer):
    prompt = "build something"  # 2 tokens — short, so 'specificity' missing
    # Step 1: empty stack
    q1 = enhancer._compute_quality(prompt, None, _stack())
    assert set(q1["missing_signals"]) == {"language", "framework", "database", "specificity"}

    # Step 2: framework known
    q2 = enhancer._compute_quality(prompt, None, _stack(frameworks=["FastAPI"]))
    assert "framework" not in q2["missing_signals"]
    assert "language" in q2["missing_signals"]

    # Step 3: framework + language
    q3 = enhancer._compute_quality(
        prompt, None, _stack(languages=["python"], frameworks=["FastAPI"]),
    )
    assert "framework" not in q3["missing_signals"]
    assert "language" not in q3["missing_signals"]

    # Step 4: framework + language + database (still missing specificity)
    q4 = enhancer._compute_quality(
        prompt, None,
        _stack(languages=["python"], frameworks=["FastAPI"], databases=["PostgreSQL"]),
    )
    assert q4["missing_signals"] == ["specificity"]


# ---------------------------------------------------------------------------
# suggested_inputs derivation
# ---------------------------------------------------------------------------

def test_suggested_inputs_includes_project_files_when_framework_missing(enhancer):
    q = enhancer._compute_quality("anything", None, _stack(languages=["python"]))
    assert "project_files" in q["suggested_inputs"]


def test_suggested_inputs_omits_attached_files_when_code_context_present(enhancer):
    ctx = CodeContext()
    ctx.code_structure = CodeStructure(imports=["from fastapi import FastAPI"])
    q = enhancer._compute_quality(
        "very specific prompt here mentioning concrete things",
        ctx,
        _stack(languages=["python"], frameworks=["FastAPI"], databases=["PostgreSQL"], confidence=0.85),
    )
    assert "attached_files" not in q["suggested_inputs"]


def test_suggested_inputs_includes_conversation_only_when_low(enhancer):
    # High grounding → no conversation suggestion
    q_high = enhancer._compute_quality(
        "specific eight-token request about implementing OAuth2 PKCE",
        None,
        _stack(languages=["python"], frameworks=["FastAPI"], databases=["PostgreSQL"], confidence=0.85),
    )
    assert "conversation_history" not in q_high["suggested_inputs"]

    # Low grounding → conversation suggestion present
    q_low = enhancer._compute_quality("fix", None, _stack())
    assert "conversation_history" in q_low["suggested_inputs"]


def test_suggested_inputs_is_sorted_and_deduplicated(enhancer):
    """Output set should always be sorted (stable for caller diffing)."""
    q = enhancer._compute_quality("fix", None, _stack())
    assert q["suggested_inputs"] == sorted(q["suggested_inputs"])
    assert len(q["suggested_inputs"]) == len(set(q["suggested_inputs"]))


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_quality_block_is_deterministic(enhancer):
    """Same inputs → identical output across repeated calls."""
    args = ("fix the auth bug", None, _stack(frameworks=["FastAPI"], confidence=0.9))
    results = [enhancer._compute_quality(*args) for _ in range(5)]
    assert all(r == results[0] for r in results)


def test_quality_block_handles_empty_prompt(enhancer):
    """Empty / None prompt should not raise — defensive handling."""
    q = enhancer._compute_quality("", None, _stack())
    assert q["prompt_grounding"] == "low"
    assert "specificity" in q["missing_signals"]
