"""Prompt construction + single Ollama call for generate_tests.

Mirrors src/agents/cheatsheet/personalizer.py: one model_router call,
content-only output, deterministic post-processing. Retries are orchestrated
by agent.py (it validates between attempts), so this module exposes a pure
prompt builder and a thin LLM runner.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from src.core.model_router import model_router

logger = logging.getLogger(__name__)

_COVERAGE_GUIDANCE = {
    "happy_path": "Cover only the main success paths with representative inputs.",
    "edge_cases": "Focus on edge cases: boundaries, empty/None inputs, and error/exception paths.",
    "all": "Cover the main success paths AND edge cases (boundaries, empty/None inputs, error/exception paths).",
}

_FRAMEWORK_NOTE = {
    "pytest": (
        "Use pytest: plain functions named test_*, bare assert statements, and "
        "pytest.raises(...) for exceptions. Use fixtures / monkeypatch where helpful."
    ),
    "jest": (
        "Use Jest: describe/test (or it) blocks and expect(...). "
        "Use jest.mock(...) for dependencies where helpful."
    ),
    "vitest": (
        "Use Vitest: import { describe, it, expect, vi } from 'vitest'; "
        "use describe/it blocks, expect(...), and vi.mock(...) where helpful."
    ),
}

SYSTEM_PROMPT = """You are a senior test engineer. You write unit tests for code that is GIVEN to you.

Hard rules:
- ONLY test functions/classes that exist in the provided source. NEVER invent functions, methods, classes, or modules that are not present.
- Import the code under test using EXACTLY the import line provided. Do not change it.
- Output ONLY the test file source code. No markdown fences, no prose, no explanation."""

_LANG_TAGS = {"python", "javascript", "typescript", "js", "ts", "jsx", "tsx", "py"}


def build_prompt(
    *,
    code: str,
    language: str,
    framework: str,
    coverage: str,
    import_line: str,
    defined_symbols: List[str],
    instructions: Optional[str],
    repo_snippets: List[str],
    feedback: Optional[str] = None,
) -> str:
    parts = [
        SYSTEM_PROMPT,
        f"LANGUAGE: {language}",
        f"FRAMEWORK: {framework} — {_FRAMEWORK_NOTE[framework]}",
        f"COVERAGE: {_COVERAGE_GUIDANCE[coverage]}",
        f"IMPORT THE CODE UNDER TEST WITH EXACTLY THIS LINE:\n{import_line}",
        f"ALLOWED SYMBOLS (only these exist in the source): {', '.join(defined_symbols)}",
    ]
    if instructions:
        parts.append(f"ADDITIONAL INSTRUCTIONS: {instructions}")
    if repo_snippets:
        joined = "\n\n".join(f"# context {i + 1}\n{s}" for i, s in enumerate(repo_snippets))
        parts.append(
            "RELATED REPO CONTEXT (dependency signatures for reference only — do not test these directly):\n"
            + joined
        )
    if feedback:
        parts.append(
            f"YOUR PREVIOUS ATTEMPT HAD A PROBLEM: {feedback}\n"
            f"Fix it and output ONLY valid {language} test source."
        )
    parts.append("SOURCE UNDER TEST:\n" + code)
    parts.append("Return the complete test file now:")
    return "\n\n".join(parts)


def _strip_fences(content: str) -> str:
    s = content.strip()
    if "```" in s:
        segments = s.split("```")
        if len(segments) >= 3:
            block = segments[1]
            if "\n" in block:
                first, rest = block.split("\n", 1)
                if first.strip().lower() in _LANG_TAGS:
                    block = rest
            return block.strip()
    return s


async def run_llm(
    prompt: str,
    *,
    tenant_id: str,
    integration_name: str,
    user_id: Optional[str],
) -> Tuple[str, int]:
    """Single LLM call. Returns (test_source, total_tokens). Raises on hard failure."""
    model_name = model_router.select_model_by_task("code_gen")
    response = await model_router.invoke_with_usage(
        prompt=prompt,
        model_name=model_name,
        task_type="test_generation",
        tenant_id=tenant_id,
        integration_name=integration_name,
        user_id=user_id,
    )
    content = response.content if hasattr(response, "content") else str(response)
    tokens = 0
    usage = getattr(response, "usage", None)
    if usage is not None:
        tokens = getattr(usage, "total_tokens", 0) or 0
    return _strip_fences(content), tokens
