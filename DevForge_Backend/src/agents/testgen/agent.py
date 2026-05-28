"""generate_tests agent — unit-test generation with static validation.

Pipeline:
  1. Validate request
  2. Resolve framework (language/framework compatibility)
  3. Extract the importable surface of the pasted source (tree-sitter)
  4. Compute import line / filename conventions
  5. Optional RAG enrichment (never blocks)
  6. Generate + statically validate (parse-check + import guard), one retry
  7. Extract test cases + assemble response

No code execution: the guarantee is "parses cleanly + imports reference real
symbols", surfaced via the `validated` field.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import ValidationError

from src.agents.testgen import ast_tools, conventions, generator
from src.agents.testgen.enrich import fetch_repo_context
from src.agents.testgen.request_model import GenerateTestsRequest

logger = logging.getLogger(__name__)


def _failure(message: str) -> dict:
    return {"success": False, "data": {"message": message}, "format": "code"}


async def generate_tests_invoke(
    args: dict,
    tenant_id: str = "unknown",
    integration_name: str = "unknown",
    user_id: Optional[str] = None,
) -> dict:
    """MCP gateway entry point for the generate_tests tool."""
    # 1. Validate request
    try:
        req = GenerateTestsRequest(**args)
    except ValidationError as e:
        first = e.errors()[0]
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        msg = first.get("msg", "Invalid request.")
        return _failure(f"{loc}: {msg}" if loc else msg)

    # 2. Resolve framework
    try:
        framework = conventions.resolve_framework(req.language, req.framework)
    except conventions.FrameworkError as e:
        return _failure(str(e))

    # 3. Extract importable surface of the source under test
    defined = ast_tools.extract_defined_symbols(req.code, req.language)
    if not defined:
        return _failure(
            "No top-level functions or classes found to test in the provided code. "
            "Paste a module or function/class definition (not a call site)."
        )

    # 4. Conventions
    module_name = conventions.import_module_name(req.module_path, req.language)
    imp_line = conventions.import_line(req.language, module_name, sorted(defined))
    filename = conventions.suggested_filename(req.module_path, req.language)
    warnings: list[str] = []
    if conventions.is_placeholder_module(req.module_path):
        warnings.append(
            f"No module_path provided — the generated import uses placeholder "
            f"'{module_name}'. Fix the import path before running."
        )

    # 5. Optional RAG enrichment (best-effort, never blocks)
    repo_snippets: list[str] = []
    repo_context_used = False
    if req.use_repo_context:
        query = "definitions and dependencies for: " + ", ".join(sorted(defined))
        repo_snippets = await fetch_repo_context(tenant_id, query)
        repo_context_used = bool(repo_snippets)

    # 6. Generate + statically validate, with one retry
    def _prompt(feedback: Optional[str]) -> str:
        return generator.build_prompt(
            code=req.code,
            language=req.language,
            framework=framework,
            coverage=req.coverage,
            import_line=imp_line,
            defined_symbols=sorted(defined),
            instructions=req.instructions,
            repo_snippets=repo_snippets,
            feedback=feedback,
        )

    total_tokens = 0
    test_src = ""
    validated = "unparseable"
    unresolved: list[str] = []
    feedback: Optional[str] = None

    for _attempt in range(2):
        try:
            test_src, tokens = await generator.run_llm(
                _prompt(feedback),
                tenant_id=tenant_id,
                integration_name=integration_name,
                user_id=user_id,
            )
        except Exception as e:
            logger.error(f"generate_tests LLM call failed: {e}")
            return _failure(f"Test generation failed: {e}")
        total_tokens += tokens
        unresolved = []

        if not ast_tools.parse_ok(test_src, req.language):
            feedback = "the output did not parse as valid source (syntax error)."
            validated = "unparseable"
            continue

        imported = ast_tools.extract_module_imports(test_src, req.language, module_name)
        unresolved = sorted(imported - defined)
        if unresolved:
            feedback = (
                f"you imported symbols that do NOT exist in the source: "
                f"{', '.join(unresolved)}. Only use these symbols: {', '.join(sorted(defined))}."
            )
            validated = "partial"
            continue

        validated = "static"
        break

    # 7. Cases + final warnings
    cases = ast_tools.extract_test_cases(test_src, req.language)
    if validated == "partial":
        warnings.append(
            f"Imported symbols not found in the source (kept, but verify): {', '.join(unresolved)}."
        )
    elif validated == "unparseable":
        warnings.append(
            "Generated tests did not parse after a retry — returned best-effort output; review before running."
        )

    return {
        "success": True,
        "data": {
            "framework": framework,
            "language": req.language,
            "filename": filename,
            "test_file": test_src,
            "cases": cases,
            "unresolved_symbols": unresolved,
            "validated": validated,
            "coverage": req.coverage,
            "repo_context_used": repo_context_used,
            "warnings": warnings,
        },
        "format": "code",
        "tokens_used": total_tokens or 1,
    }
