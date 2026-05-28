"""Pure naming/framework conventions for generate_tests (no I/O, no AST)."""

from __future__ import annotations

from typing import Iterable

LANG_EXT = {"python": "py", "javascript": "js", "typescript": "ts"}

DEFAULT_FRAMEWORK = {"python": "pytest", "javascript": "jest", "typescript": "jest"}

VALID_FRAMEWORKS = {
    "python": {"pytest"},
    "javascript": {"jest", "vitest"},
    "typescript": {"jest", "vitest"},
}

_PY_PLACEHOLDER = "module_under_test"
_JS_PLACEHOLDER = "./module_under_test"


class FrameworkError(ValueError):
    """Raised when a framework is incompatible with the chosen language."""


def resolve_framework(language: str, framework: str | None) -> str:
    """Default the framework per language, or validate an explicit one."""
    if framework is None:
        return DEFAULT_FRAMEWORK[language]
    if framework not in VALID_FRAMEWORKS[language]:
        allowed = ", ".join(sorted(VALID_FRAMEWORKS[language]))
        raise FrameworkError(
            f"Framework {framework!r} is not valid for {language}. Allowed: {allowed}."
        )
    return framework


def module_basename(module_path: str | None, language: str) -> str:
    """Last meaningful segment of a module path, sans extension."""
    if not module_path:
        return "generated"
    if language == "python":
        return module_path.rsplit(".", 1)[-1] or "generated"
    seg = module_path.rstrip("/").rsplit("/", 1)[-1]
    for ext in (".tsx", ".jsx", ".mjs", ".cjs", ".ts", ".js"):
        if seg.endswith(ext):
            seg = seg[: -len(ext)]
            break
    return seg or "generated"


def import_module_name(module_path: str | None, language: str) -> str:
    """The module string the generated test imports from."""
    if module_path:
        return module_path
    return _PY_PLACEHOLDER if language == "python" else _JS_PLACEHOLDER


def is_placeholder_module(module_path: str | None) -> bool:
    return not module_path


def import_line(language: str, module_name: str, symbols: Iterable[str]) -> str:
    """Build the import statement the test should use for the code under test."""
    names = ", ".join(symbols)
    if language == "python":
        return f"from {module_name} import {names}"
    return f"import {{ {names} }} from '{module_name}';"


def suggested_filename(module_path: str | None, language: str) -> str:
    base = module_basename(module_path, language)
    if language == "python":
        return f"test_{base}.py"
    return f"{base}.test.{LANG_EXT[language]}"
