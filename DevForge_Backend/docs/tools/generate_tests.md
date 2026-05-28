# generate_tests — AI Unit-Test Generation with Static Validation

**Tool Name:** `generate_tests`
**Version:** 1.0.0
**Status:** Production
**Last Updated:** 2026-05-27

---

## Overview

`generate_tests` produces a **ready-to-run unit-test file** from a pasted
function, class, or module. One Ollama `code_gen` call generates the test
source; the response is then **statically validated** before it is returned:

1. **Parse-check** — the generated file is parsed by tree-sitter; any ERROR
   nodes trigger one regeneration attempt before the call gives up.
2. **Import-symbol guard** — names imported from the module under test are
   compared against the symbols actually defined in the pasted source. Any
   hallucinated reference is recorded in `unresolved_symbols` and triggers
   one regeneration attempt feeding the bad names back into the prompt.

There is **no execution**. The contract is "the file parses cleanly **and**
its imports reference real symbols" — not "the tests pass at runtime". This
keeps the call a fast, sandbox-free, single-MCP-call operation.

Key properties:

- **3 languages, 3 frameworks** — Python/pytest, JavaScript/TypeScript with
  Jest (default) or Vitest (opt-in).
- **No hallucinated APIs** — symbols imported from the source-under-test are
  guarded against the actual public surface extracted via tree-sitter.
- **Honest output** — the `validated` field is `"static"`, `"partial"`, or
  `"unparseable"`, so the caller knows exactly what level of guarantee they
  got. Hallucinated imports surface in `unresolved_symbols` rather than
  being silently scrubbed.
- **Optional RAG enrichment** — when `use_repo_context: true`, related
  dependency snippets are pulled from the tenant's indexed repo and added to
  the prompt for better signature accuracy. Best-effort: degrades to a no-op
  when no repo is indexed.

---

## Features

- One LLM call per attempt (plus at most one retry on parse/guard failure)
- Tree-sitter validation reuses the same `tree_sitter_languages` parsers RAG
  uses (no extra deps)
- Anti-hallucination guard inspired by `generate_cheatsheet`'s "drop
  hallucinated id" pattern
- Suggested `filename` per framework convention (`test_<name>.py`,
  `<name>.test.ts`) — IDE can save in one click
- Structured `cases[]` extracted from the generated file via AST walk
- Token-aware analytics flow through `model_router.invoke_with_usage(task_type="test_generation")`
- Fails open on degraded conditions: missing `module_path` → import uses a
  clearly-flagged placeholder + warning; RAG unavailable → empty enrichment;
  parse fails twice → best-effort output with `validated: "unparseable"` and a warning

---

## Supported Languages & Frameworks

| Language | Default framework | Allowed `framework` values |
|----------|-------------------|----------------------------|
| `python` | `pytest` | `pytest` |
| `javascript` | `jest` | `jest`, `vitest` |
| `typescript` | `jest` | `jest`, `vitest` |

Invalid combinations (e.g. `language: "python", framework: "jest"`) return
`success: false` with a clear message — do **not** retry with a different
value; surface the error to the user.

Unsupported languages (anything outside `python`/`javascript`/`typescript`)
are rejected at the Pydantic gate with `success: false`.

---

## Folder Structure

```
src/agents/testgen/
├── agent.py            # Orchestrator: validate → extract symbols → enrich → generate → validate → assemble
├── ast_tools.py        # tree-sitter: extract_defined_symbols, parse_ok, extract_module_imports, extract_test_cases
├── conventions.py      # Pure: resolve_framework, suggested_filename, import_line, placeholder module
├── enrich.py           # Best-effort RAG enrichment (degrades to []) via get_rag_agent(...).retrieve_with_reranking
├── generator.py        # Prompt builder + single Ollama call (task_type="test_generation") + fence stripping
└── request_model.py    # GenerateTestsRequest Pydantic gate (max-length, enums)

manifests/devforge.json # Tool entry surfaced via /api/gateway
src/api/mcp/schemas.py  # GenerateTestsInput — FastMCP auto-generated schema
src/api/mcp/server.py   # @mcp.tool registration (simple-tool branch → _dispatch)
src/api/mcp/descriptions.py  # Agent-instructive description shown via tools/list
tests/test_testgen.py   # 25 behavior tests (LLM mocked)
docs/superpowers/specs/2026-05-27-generate-tests-design.md  # Approved design spec
```

---

## Inputs

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `code` | `string` | yes | Source under test, verbatim. Max length **16 000** chars (Pydantic-enforced; oversized → `success:false`). |
| `language` | `"python" \| "javascript" \| "typescript"` | yes | Anything else is rejected at the gate. |
| `framework` | `"pytest" \| "jest" \| "vitest"` | no | Defaults: py→pytest, js/ts→jest. Invalid combos rejected with a clear message. |
| `module_path` | `string` | no, **strongly recommended** | Import hint, e.g. `"src.utils.auth"` (python) or `"../src/auth"` (js/ts). Without it the generated import uses a placeholder and a warning is added. Max length 300. |
| `coverage` | `"happy_path" \| "edge_cases" \| "all"` | no | Default `"all"`. Steers what the LLM tries to cover. |
| `use_repo_context` | `boolean` | no | Default `false`. When `true`, related snippets from the tenant's RAG index are added to the prompt for accurate dependency signatures. Best-effort: no-op when nothing's indexed. |
| `instructions` | `string` | no | Free-form 1-line steer, e.g. `"focus on error paths"`. Max length 1000. |

---

## Outputs

Top-level keys:

| Field | Type | Notes |
|-------|------|-------|
| `success` | `bool` | `false` only for validation failures (bad framework combo, oversized input, no testable symbols). LLM/parse issues still return `success:true` with `validated` downgraded. |
| `data` | `object` | See below. |
| `format` | `"code"` | Constant — content type hint for the caller. |
| `tokens_used` | `int` | Total LLM tokens consumed (sum across attempts). |

`data` fields:

| Field | Type | Notes |
|-------|------|-------|
| `framework` | `string` | The resolved framework (`pytest`/`jest`/`vitest`). |
| `language` | `string` | Echoed input. |
| `filename` | `string` | Suggested file name (`test_auth.py`, `auth.test.ts`, …). |
| `test_file` | `string` | Full generated source. Save under `filename`. |
| `cases` | `[{name, asserts}]` | Test-case names + a heuristic one-line "asserts" preview. The `asserts` value may be empty for tests that use `pytest.raises(...)` or `expect(...).toBe(...)` without a literal `assert` keyword — names are always accurate. |
| `unresolved_symbols` | `[string]` | Imports from the module-under-test that don't exist in the pasted source. Empty when `validated == "static"`. |
| `validated` | `"static" \| "partial" \| "unparseable"` | See guarantee table below. |
| `coverage` | `string` | Echoed input. |
| `repo_context_used` | `bool` | `true` iff RAG enrichment was requested **and** returned at least one snippet. |
| `warnings` | `[string]` | Human-readable notes (placeholder import, validation gaps, etc.). |

### `validated` semantics

| Value | Parse | Imports resolve | Notes |
|-------|-------|----------------|-------|
| `"static"` | ✅ | ✅ all resolve | The guaranteed-quality result. `unresolved_symbols == []`. |
| `"partial"` | ✅ | ⚠️ some don't | LLM produced an import for a symbol the source doesn't define. The names are listed in `unresolved_symbols`; review before running. |
| `"unparseable"` | ❌ | n/a | Two attempts failed to produce a syntactically valid file. Best-effort output returned; `cases` may be empty. Warning included. |

---

## Pipeline

1. **Validate** input via `GenerateTestsRequest` (Pydantic). Bad request → `success:false`.
2. **Resolve framework** (`conventions.resolve_framework`). Invalid combo → `success:false`.
3. **Extract defined symbols** from `code` via tree-sitter (`ast_tools.extract_defined_symbols`). Zero symbols → `success:false` with "no top-level functions or classes found to test".
4. **Conventions** — compute `module_name` (uses `module_path` or placeholder), `import_line`, `filename`. If `module_path` is missing, append a placeholder warning.
5. **Optional RAG enrich** — when `use_repo_context: true` and `tenant_id != "unknown"`, call `enrich.fetch_repo_context` which wraps `get_rag_agent(...).retrieve_with_reranking(...)` in a try/except (any failure → `[]`).
6. **Generate** the test file with `generator.run_llm` — one Ollama call (`model_router.select_model_by_task("code_gen")`, `task_type="test_generation"`).
7. **Static validation:**
   - Parse-check the result; on ERROR-node failure, retry once feeding the parser error back; remaining failure → `validated="unparseable"`.
   - Import guard: imports from `module_name` minus `defined_symbols`; non-empty → retry once with explicit "these don't exist: …; only use: …"; remaining diff → `validated="partial"`, list in `unresolved_symbols`.
8. **Extract `cases`** (`ast_tools.extract_test_cases`) and assemble the response.

---

## Latency

- Cold/warm cloud-model call: roughly **5–20s** per attempt on the default `code_gen` chain (`qwen3-coder:480b-cloud` with fallback to `gpt-oss` family).
- At most **one** retry — so the worst-case wall time is ~2× one call.
- The tool description told via `tools/list` instructs calling agents to show a loading indicator, matching `generate_cheatsheet`'s pattern.

---

## Examples

### Python — happy path

```bash
curl -s -X POST http://localhost:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "x-api-key: <key>" \
  -d '{
    "jsonrpc":"2.0","id":1,"method":"tools/call",
    "params":{
      "name":"generate_tests",
      "arguments":{
        "code":"def add(a, b):\n    return a + b\n\ndef divide(a, b):\n    if b == 0:\n        raise ValueError\n    return a / b\n",
        "language":"python",
        "module_path":"src.calc"
      }
    }
  }'
```

Returns (truncated):

```json
{
  "success": true,
  "data": {
    "framework": "pytest",
    "language": "python",
    "filename": "test_calc.py",
    "test_file": "import pytest\nfrom src.calc import add, divide\n\ndef test_add_returns_sum():\n    assert add(1, 2) == 3\n...",
    "cases": [
      {"name": "test_add_returns_sum",   "asserts": "assert add(1, 2) == 3"},
      {"name": "test_divide_zero_denominator", "asserts": ""},
      {"name": "test_divide_normal_cases", "asserts": "assert divide(numerator, denominator) == expected"}
    ],
    "unresolved_symbols": [],
    "validated": "static",
    "coverage": "all",
    "repo_context_used": false,
    "warnings": []
  },
  "format": "code",
  "tokens_used": 582
}
```

### TypeScript with Vitest, RAG enrichment on

```bash
curl -s -X POST http://localhost:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "x-api-key: <key>" \
  -d '{
    "jsonrpc":"2.0","id":2,"method":"tools/call",
    "params":{
      "name":"generate_tests",
      "arguments":{
        "code":"export function verifyToken(t: string) { ... }",
        "language":"typescript",
        "framework":"vitest",
        "module_path":"../src/auth",
        "use_repo_context": true,
        "coverage":"edge_cases",
        "instructions":"focus on expired and malformed tokens"
      }
    }
  }'
```

### No `module_path` — placeholder warning

If `module_path` is omitted, the generated import targets a placeholder:

- Python → `from module_under_test import …`
- JS/TS → `import { … } from './module_under_test'`

The response includes a warning like:

> "No module_path provided — the generated import uses placeholder 'module_under_test'. Fix the import path before running."

The IDE / caller should rewrite that import to the real path before saving.

---

## Failure Modes

| Condition | Response |
|-----------|----------|
| `code` empty or > 16 000 chars | `success:false` (Pydantic validation) |
| Unsupported `language` (e.g. `"ruby"`) | `success:false` (Literal enum) |
| Invalid framework/language combo (e.g. `python` + `jest`) | `success:false` with framework error message |
| No `def`/`class` in `code` | `success:false`, "no top-level functions or classes found to test" |
| LLM returns un-parseable text twice | `success:true`, `validated:"unparseable"`, warning included, `cases` may be empty |
| LLM imports a symbol the source doesn't define (twice) | `success:true`, `validated:"partial"`, `unresolved_symbols` populated, warning included |
| RAG enrichment requested but no repo indexed | `repo_context_used:false`, no warning (silent, by design) |
| Ollama / model_router error | `success:false`, `data.message` carries the underlying error |

---

## Versioning

- **v1.0.0 (2026-05-27)** — initial release: Python + JS/TS, static validation, optional RAG enrichment, suggested filename, structured `cases[]`, honest `validated` enum.

Future candidates (out of scope today):

- Additional languages from `generate_cheatsheet`'s set (go, rust, java, ruby, php, csharp).
- Sandboxed execution to upgrade `validated` to a runtime pass/fail signal — explicitly deferred due to arbitrary-code-execution + dependency-resolution complexity.
- Surgical AST removal of individual hallucinated test functions (today we report them in `unresolved_symbols` instead).

See the full design rationale in [`../superpowers/specs/2026-05-27-generate-tests-design.md`](../superpowers/specs/2026-05-27-generate-tests-design.md).
