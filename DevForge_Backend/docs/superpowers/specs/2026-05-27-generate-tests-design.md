# generate_tests — Design Spec

**Date:** 2026-05-27
**Status:** Approved (brainstorming) → implementation
**Author:** Sid (with Claude)
**Tool name:** `generate_tests` · **Feature folder:** `src/agents/testgen/`

## 1. Purpose

A fifth MCP developer tool: given pasted source code, generate a ready-to-run
unit-test file in the correct framework. Test generation is the standout
2026 developer-productivity trend; it maps cleanly onto DevForge's existing
stack (tree-sitter AST already used by RAG, Ollama via `model_router`, and the
`generate_cheatsheet` "never invent code" discipline).

It follows the established single-call tool shape: stateless, IDE-invoked
(Cursor/VSCode), authenticated via `x-api-key`, dispatched through the FastMCP
SDK at `/mcp`.

## 2. Decisions (from brainstorming)

| Decision | Choice |
|----------|--------|
| Input source | Pasted `code` (primary) + optional `use_repo_context` RAG enrichment |
| Languages | Python → pytest; JavaScript/TypeScript → Jest (Vitest optional) |
| Correctness | **Static** validation — tree-sitter parse-check + import-symbol guard. **No code execution / no sandbox.** |
| Output | Rich: `test_file` + `cases[]` + `unresolved_symbols[]` + `validated` + suggested `filename` |
| JS default framework | Jest |
| Validation failure | One regeneration retry, then return best-effort with an honest `validated` flag |

### Refinements made during implementation planning
- `validated` is a three-value enum (`static` / `partial` / `unparseable`)
  rather than the originally-sketched two values — this reports import-guard
  gaps honestly instead of collapsing them.
- `use_repo_context` enriches the **LLM prompt** with retrieved dependency
  snippets (better signatures). The import guard stays strict on the source's
  own symbols, so RAG context cannot cause the guard to pass a hallucinated
  symbol. Response carries `repo_context_used: bool` for honesty. Degrades to
  a no-op (never blocks) when the tenant has no indexed repo.

## 3. Input contract

MCP-layer model `GenerateTestsInput` (flat params in `src/api/mcp/schemas.py`,
mirrored by agent-layer `GenerateTestsRequest` in `request_model.py`):

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `code` | str | required | Source under test. Pydantic max-length ~16000 (token bound). |
| `language` | enum | required | `python` \| `javascript` \| `typescript` |
| `framework` | enum? | none | `pytest` \| `jest` \| `vitest`. Defaults: py→pytest, js/ts→jest. Invalid lang/framework combo → `success:false`. |
| `module_path` | str? | none | Import hint, e.g. `src.utils.auth` (py) or `../src/auth` (js/ts). Drives the import line + suggested filename. |
| `coverage` | enum | `all` | `happy_path` \| `edge_cases` \| `all` |
| `use_repo_context` | bool | `false` | Optional RAG prompt enrichment. |
| `instructions` | str? | none | Free-form steer, e.g. "focus on error paths". Max-length gated. |

When `module_path` is absent, the import targets a placeholder module
(`module_under_test` / `./module_under_test`) and a warning is added telling
the caller to fix the import path.

## 4. Output contract

```json
{
  "success": true,
  "data": {
    "framework": "pytest",
    "language": "python",
    "filename": "test_auth.py",
    "test_file": "<full test source>",
    "cases": [
      {"name": "test_verify_token_valid", "asserts": "returns decoded claims"},
      {"name": "test_verify_token_expired", "asserts": "raises ExpiredSignatureError"}
    ],
    "unresolved_symbols": [],
    "validated": "static",
    "coverage": "all",
    "repo_context_used": false,
    "warnings": []
  },
  "format": "code"
}
```

- `validated`:
  - `static` — parses cleanly AND every symbol imported from the
    module-under-test exists in the pasted source. `unresolved_symbols == []`.
  - `partial` — parses cleanly, but one or more imported symbols don't resolve
    (after one retry). Those names are listed in `unresolved_symbols`.
  - `unparseable` — still has tree-sitter ERROR nodes after one retry.
    Best-effort `test_file` returned; `cases` may be empty.
- Honesty guarantee, stated in the tool description: the tool guarantees the
  output **parses** and its **imports reference real symbols**. It does **not**
  guarantee the tests pass at runtime (no execution).

## 5. Module layout (`src/agents/testgen/`)

| File | Responsibility |
|------|----------------|
| `request_model.py` | `GenerateTestsRequest` Pydantic gate (mirrors cheatsheet `request_model.py`). |
| `ast_tools.py` | Pure tree-sitter: `extract_defined_symbols(code, lang)`, `parse_ok(code, lang)` (no ERROR nodes), `extract_module_imports(test, lang, module_name)`, `extract_test_case_names(test, lang)`. Uses `tree_sitter_languages.get_parser/get_language` like `rag/chunking/code_chunker.py`. |
| `conventions.py` | Pure string logic: framework defaulting + validation, `suggested_filename`, `import_line`, language→extension. |
| `enrich.py` | `fetch_repo_context(tenant_id, query)` → list of snippets via `get_rag_agent(...).retrieve_with_reranking(...)`, wrapped in try/except → `[]` on any failure. |
| `generator.py` | Prompt building + single `model_router.invoke_with_usage(task_type="code_gen")` call + one retry. Returns raw test source + usage. Mirrors `cheatsheet/personalizer.py`. |
| `agent.py` | `generate_tests_invoke(args, tenant_id, integration_name, user_id)` orchestration + response assembly. |

## 6. Pipeline (`generate_tests_invoke`)

1. **Validate** args → `GenerateTestsRequest`; on `ValidationError` return
   `_failure(msg)`.
2. **Resolve framework** via `conventions` (default by language; reject invalid
   lang/framework combo).
3. **Extract defined symbols** from `code` with tree-sitter. None found →
   `success:false, "no functions or classes found to test"`.
4. **(Optional) RAG enrich** — if `use_repo_context` and `tenant_id != "unknown"`,
   `fetch_repo_context`; set `repo_context_used` accordingly. Never blocks.
5. **Generate** — `generator` builds the prompt (code + language + framework +
   coverage + computed import line + symbol whitelist + optional repo snippets +
   `instructions`) and calls Ollama (`task_type="code_gen"`).
6. **Validate (static):**
   - `parse_ok` on the generated test. Parse error → **one** regeneration pass
     feeding the error. Still failing → `validated="unparseable"` + warning.
   - **Import guard:** `extract_module_imports` from the test against the known
     module name; `hallucinated = imported - defined_symbols`. If non-empty →
     one regeneration naming the bad symbols + the allowed set. Remaining
     hallucinated names → `unresolved_symbols`, `validated="partial"`.
7. **Extract cases** (`test_*` defs / `it()`/`test()` blocks) → `[{name, asserts}]`.
8. **Assemble** filename + data; return.

## 7. Registration (verified against current code)

1. `src/agents/testgen/agent.py` exports `generate_tests_invoke`.
2. `src/api/routers/__init__.py` — import + `SUPPORTED_TOOLS["generate_tests"] = generate_tests_invoke`.
3. `src/api/mcp/schemas.py` — add `GenerateTestsInput`.
4. `src/api/mcp/descriptions.py` — add agent-instructive `TOOL_DESCRIPTIONS["generate_tests"]` (call pattern, the parse/import guarantee, latency + loading-indicator note).
5. `src/api/mcp/server.py` — add `@mcp.tool(name="generate_tests", ...)` flat-param fn → `_dispatch("generate_tests", ...)` (simple-tool branch).
6. `manifests/devforge.json` — add tool entry.
7. `tests/test_testgen.py`.

## 8. Testing (behavior-focused; LLM mocked for determinism)

- valid Python → parseable pytest file with ≥1 case (`generator` mocked).
- import guard drops a fabricated symbol → it appears in `unresolved_symbols`, `validated="partial"`.
- unparseable LLM output after retry → `validated="unparseable"`, warning present.
- unsupported language → `success:false` (no silent retry).
- oversized `code` → validation failure.
- JS defaults to `jest`; `framework:"vitest"` respected; py+jest rejected.
- `module_path` produces correct import line + filename; absent → placeholder + warning.
- `use_repo_context:false` works fully standalone (no RAG call).
- `ast_tools` unit tests: symbol extraction + parse_ok on real fixtures (no mock).

## 9. Latency

Single Ollama `code_gen` call (+ at most one retry) → ~5–20s. Tool description
instructs calling agents to show a loading indicator, matching
`generate_cheatsheet`.

## 10. Out of scope (future)

- **Test execution / sandbox** — explicitly rejected for v1 (arbitrary-code-execution
  surface + dependency resolution). The static guarantee is the v1 contract.
- Additional languages beyond py/js/ts (cheatsheet's other 6).
- Surgical AST removal of individual hallucinated test functions (v1 reports
  them in `unresolved_symbols` instead).
