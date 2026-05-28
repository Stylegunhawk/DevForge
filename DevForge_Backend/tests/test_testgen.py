"""Behavior tests for the generate_tests tool.

Two layers:
  - Pure tree-sitter / conventions units (no mocks).
  - Agent behavior via generate_tests_invoke with the LLM (generator.run_llm)
    mocked, so assertions are deterministic and no Ollama call is made.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.testgen import ast_tools, conventions
from src.agents.testgen.agent import generate_tests_invoke

PY_SRC = "def add(a, b):\n    return a + b\n\nclass Calc:\n    def mul(self, x, y):\n        return x * y\n"
JS_SRC = "export function add(a, b) { return a + b; }\nexport const sub = (a, b) => a - b;\n"


def _llm(source: str, tokens: int = 10):
    """An AsyncMock standing in for generator.run_llm → (source, tokens)."""
    return AsyncMock(return_value=(source, tokens))


# --------------------------------------------------------------------------- #
# Pure units: ast_tools
# --------------------------------------------------------------------------- #


class TestAstTools:
    def test_extract_defined_symbols_python(self):
        assert ast_tools.extract_defined_symbols(PY_SRC, "python") == {"add", "Calc"}

    def test_extract_defined_symbols_js(self):
        assert ast_tools.extract_defined_symbols(JS_SRC, "javascript") == {"add", "sub"}

    def test_parse_ok_true_for_valid(self):
        assert ast_tools.parse_ok("def f():\n    return 1\n", "python") is True

    def test_parse_ok_false_for_syntax_error(self):
        assert ast_tools.parse_ok("def f(:\n  pass", "python") is False

    def test_module_imports_match_only_target_module(self):
        test = "import os\nfrom calc import add, subtract\nfrom other import x\n"
        assert ast_tools.extract_module_imports(test, "python", "calc") == {"add", "subtract"}

    def test_js_module_imports(self):
        test = "import { add, sub } from './m';\nimport x from 'lib';\n"
        assert ast_tools.extract_module_imports(test, "javascript", "./m") == {"add", "sub"}

    def test_extract_test_cases_python(self):
        test = "def test_a():\n    assert add(1) == 1\n\ndef helper():\n    pass\n"
        cases = ast_tools.extract_test_cases(test, "python")
        assert [c["name"] for c in cases] == ["test_a"]


# --------------------------------------------------------------------------- #
# Pure units: conventions
# --------------------------------------------------------------------------- #


class TestConventions:
    def test_default_frameworks(self):
        assert conventions.resolve_framework("python", None) == "pytest"
        assert conventions.resolve_framework("javascript", None) == "jest"
        assert conventions.resolve_framework("typescript", None) == "jest"

    def test_vitest_allowed_for_ts(self):
        assert conventions.resolve_framework("typescript", "vitest") == "vitest"

    def test_pytest_rejected_for_js(self):
        with pytest.raises(conventions.FrameworkError):
            conventions.resolve_framework("javascript", "pytest")

    def test_jest_rejected_for_python(self):
        with pytest.raises(conventions.FrameworkError):
            conventions.resolve_framework("python", "jest")

    def test_filename_and_import_line(self):
        assert conventions.suggested_filename("src.utils.auth", "python") == "test_auth.py"
        assert conventions.suggested_filename("../src/auth", "typescript") == "auth.test.ts"
        assert conventions.suggested_filename(None, "python") == "test_generated.py"
        assert conventions.import_line("python", "src.calc", ["add"]) == "from src.calc import add"
        assert conventions.import_line("javascript", "./m", ["a", "b"]) == "import { a, b } from './m';"


# --------------------------------------------------------------------------- #
# Agent behavior (LLM mocked)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestGenerateTestsAgent:
    async def test_python_happy_path_static(self):
        generated = "from src.calc import add\n\ndef test_add_returns_sum():\n    assert add(1, 2) == 3\n"
        with patch("src.agents.testgen.generator.run_llm", _llm(generated, 42)):
            result = await generate_tests_invoke(
                {"code": PY_SRC, "language": "python", "module_path": "src.calc"}
            )
        assert result["success"] is True
        data = result["data"]
        assert data["validated"] == "static"
        assert data["framework"] == "pytest"
        assert data["filename"] == "test_calc.py"
        assert data["unresolved_symbols"] == []
        assert [c["name"] for c in data["cases"]] == ["test_add_returns_sum"]
        assert result["tokens_used"] == 42

    async def test_import_guard_marks_partial(self):
        # references a symbol that does not exist in the source
        generated = "from src.calc import add, subtract\n\ndef test_x():\n    assert add(1, 1) == 2\n"
        run_llm = _llm(generated)
        with patch("src.agents.testgen.generator.run_llm", run_llm):
            result = await generate_tests_invoke(
                {"code": PY_SRC, "language": "python", "module_path": "src.calc"}
            )
        data = result["data"]
        assert data["validated"] == "partial"
        assert data["unresolved_symbols"] == ["subtract"]
        assert any("subtract" in w for w in data["warnings"])
        assert run_llm.await_count == 2  # one retry attempted

    async def test_unparseable_after_retry(self):
        run_llm = _llm("def (:: this is not valid", 5)
        with patch("src.agents.testgen.generator.run_llm", run_llm):
            result = await generate_tests_invoke(
                {"code": PY_SRC, "language": "python", "module_path": "src.calc"}
            )
        data = result["data"]
        assert result["success"] is True
        assert data["validated"] == "unparseable"
        assert data["warnings"]
        assert run_llm.await_count == 2

    async def test_retry_recovers_to_static(self):
        good = "from src.calc import add\n\ndef test_add():\n    assert add(1, 1) == 2\n"
        run_llm = AsyncMock(side_effect=[("garbage(:", 5), (good, 7)])
        with patch("src.agents.testgen.generator.run_llm", run_llm):
            result = await generate_tests_invoke(
                {"code": PY_SRC, "language": "python", "module_path": "src.calc"}
            )
        assert result["data"]["validated"] == "static"
        assert run_llm.await_count == 2
        assert result["tokens_used"] == 12

    async def test_js_defaults_to_jest(self):
        generated = "import { add } from '../calc';\ntest('adds', () => { expect(add(1, 2)).toBe(3); });\n"
        with patch("src.agents.testgen.generator.run_llm", _llm(generated)):
            result = await generate_tests_invoke(
                {"code": JS_SRC, "language": "javascript", "module_path": "../calc"}
            )
        assert result["data"]["framework"] == "jest"
        assert result["data"]["validated"] == "static"
        assert result["data"]["filename"] == "calc.test.js"

    async def test_ts_vitest_override(self):
        generated = "import { add } from '../calc';\ntest('adds', () => { expect(add(1, 2)).toBe(3); });\n"
        with patch("src.agents.testgen.generator.run_llm", _llm(generated)):
            result = await generate_tests_invoke(
                {
                    "code": JS_SRC,
                    "language": "typescript",
                    "framework": "vitest",
                    "module_path": "../calc",
                }
            )
        assert result["data"]["framework"] == "vitest"

    async def test_invalid_framework_combo_fails(self):
        run_llm = _llm("unused")
        with patch("src.agents.testgen.generator.run_llm", run_llm):
            result = await generate_tests_invoke(
                {"code": PY_SRC, "language": "python", "framework": "jest"}
            )
        assert result["success"] is False
        assert "not valid for python" in result["data"]["message"]
        run_llm.assert_not_awaited()  # rejected before generation

    async def test_placeholder_import_warning(self):
        generated = "from module_under_test import add\n\ndef test_add():\n    assert add(1, 1) == 2\n"
        with patch("src.agents.testgen.generator.run_llm", _llm(generated)):
            result = await generate_tests_invoke({"code": PY_SRC, "language": "python"})
        data = result["data"]
        assert data["filename"] == "test_generated.py"
        assert any("placeholder" in w for w in data["warnings"])
        assert data["validated"] == "static"

    async def test_no_testable_symbols_fails(self):
        run_llm = _llm("unused")
        with patch("src.agents.testgen.generator.run_llm", run_llm):
            result = await generate_tests_invoke(
                {"code": "print(add(1, 2))\n", "language": "python"}
            )
        assert result["success"] is False
        assert "No top-level functions" in result["data"]["message"]
        run_llm.assert_not_awaited()

    async def test_unsupported_language_rejected(self):
        result = await generate_tests_invoke({"code": "puts 1", "language": "ruby"})
        assert result["success"] is False

    async def test_oversized_code_rejected(self):
        result = await generate_tests_invoke(
            {"code": "x = 1\n" * 4000, "language": "python"}  # > 16000 chars
        )
        assert result["success"] is False

    async def test_standalone_does_not_call_rag(self):
        generated = "from src.calc import add\n\ndef test_add():\n    assert add(1, 1) == 2\n"
        fake_rag = AsyncMock(return_value=["snippet"])
        with patch("src.agents.testgen.generator.run_llm", _llm(generated)), patch(
            "src.agents.testgen.agent.fetch_repo_context", fake_rag
        ):
            result = await generate_tests_invoke(
                {"code": PY_SRC, "language": "python", "module_path": "src.calc"}
            )
        fake_rag.assert_not_awaited()
        assert result["data"]["repo_context_used"] is False

    async def test_repo_context_used_when_enabled(self):
        generated = "from src.calc import add\n\ndef test_add():\n    assert add(1, 1) == 2\n"
        fake_rag = AsyncMock(return_value=["def add(a, b): ..."])
        with patch("src.agents.testgen.generator.run_llm", _llm(generated)), patch(
            "src.agents.testgen.agent.fetch_repo_context", fake_rag
        ):
            result = await generate_tests_invoke(
                {
                    "code": PY_SRC,
                    "language": "python",
                    "module_path": "src.calc",
                    "use_repo_context": True,
                }
            )
        fake_rag.assert_awaited_once()
        assert result["data"]["repo_context_used"] is True
