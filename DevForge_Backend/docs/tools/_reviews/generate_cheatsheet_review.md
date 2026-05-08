# generate_cheatsheet — Doc vs Code Review

**Reviewed:** 2026-05-08
**Branch:** rag_resolve
**Doc(s):** docs/tools/generate_cheatsheet.md, docs/tools/README.md
**Code:** src/agents/cheatsheet/, src/tools/cheatsheet/, src/api/routers/__init__.py, manifests/devforge.json
**Verdict:** Diverged

## Summary
The doc accurately describes the high-level pipeline (parse → detect libraries → score complexity → select sections → assemble markdown → quick reference) and the rule-based, no-LLM nature of the tool. But it diverges on almost every concrete number and on several behavioural claims: "15+ languages" is fiction (full templates exist only for `python`; quick-reference has no language switch at all and 19 listed "basic support" languages have no code path), the "15+ libraries" detector has 14 entries, the test count of 58 is off by an order of magnitude (4 tests in `test_cheatsheet.py`, ~47 across all cheatsheet test files), the `__init__.py` files in the folder-structure listing don't exist, and several "error response" claims (unsupported language, detection failed) are flatly wrong — the code silently falls back to Python instead. There is also a real default-value disagreement between `CheatsheetArgs` (`intermediate`) and the manifest/agent/doc (`beginner`), saved only by the fact that `CheatsheetArgs` is dead code never invoked at the gateway.

## Verified claims
- Tool registered in `SUPPORTED_TOOLS` mapped to `generate_cheatsheet_invoke` — `src/api/routers/__init__.py:49`.
- Import path `from src.agents.cheatsheet.agent import generate_cheatsheet_invoke` — `src/api/routers/__init__.py:15`.
- Manifest entry exists with `required: []`, default `skill_level: "beginner"`, enum `[beginner, intermediate, expert]` — `manifests/devforge.json:188-214`.
- Gateway JSON-Schema entry (`type: object`, properties `language`, `skill_level`, `code_context`, `required: []`) — `src/api/routers/__init__.py:1499-1517`.
- Pipeline order in `CheatsheetAgent.generate` matches doc: parse → detect libraries → calculate complexity → select language (explicit > auto) → select sections → assemble markdown → generate quick reference — `src/agents/cheatsheet/agent.py:50-141`.
- Skill-level enum `[beginner, intermediate, expert]` — `src/core/schemas.py:288` (Pydantic), `manifests/devforge.json:200-203`, `src/api/routers/__init__.py:1508`.
- Complexity scoring features list (imports, functions, classes, async_functions, decorators, comprehensions, context_managers, type_hints, lambda, generators) — exactly 10 features — `src/agents/cheatsheet/complexity_scorer.py:35-46`.
- Complexity thresholds `<10 → beginner`, `<30 → intermediate`, `≥30 → expert` — `src/agents/cheatsheet/complexity_scorer.py:66-71`.
- Library detector uses pre-compiled regex — `src/agents/cheatsheet/library_detector.py:42-48`.
- Hard cap of 7 sections, max 3 library sections — `src/agents/cheatsheet/section_selector.py:31-32, 70`.
- Multi-block parser splits on `\n\n---\n\n` and strips `// language` prefix — `src/agents/cheatsheet/context_parser.py:29-46`.
- Markdown output starts with `# {Language} Cheat Sheet - {Skill Level}` — `src/agents/cheatsheet/agent.py:150`.
- Response shape `{success, language, skill_level, markdown, data: {language, skill_level, detected_libraries, supported_libraries, complexity_score, sections}}` — `src/agents/cheatsheet/agent.py:128-141`.
- Async wrapper returns `{success, data, format: "markdown"}` — `src/agents/cheatsheet/agent.py:186-191`.
- `supported_libraries` is whitelisted to `['pandas', 'fastapi', 'asyncio']` — `src/agents/cheatsheet/agent.py:124`.
- Library-specific quick-ref entries exist for pandas, fastapi (intermediate) and asyncio (expert) — `src/agents/cheatsheet/quick_reference.py:48-85`.
- No LLM call in the cheatsheet pipeline; pure regex + Python templates — verified by absence of any `select_model_by_task`, Ollama, or LangChain import in `src/agents/cheatsheet/*.py` and `src/tools/cheatsheet/*.py`.

## Discrepancies (doc says X, code does Y)

- **claim:** "15+ libraries" supported (lines 16, 24, 207).
  **reality:** `LIBRARY_SIGNATURES` has exactly 14 entries: pandas, numpy, matplotlib, scikit-learn, fastapi, flask, django, pydantic, asyncio, aiohttp, sqlalchemy, requests, httpx, pytest — `src/agents/cheatsheet/library_detector.py:8-36`.
  **severity:** minor

- **claim:** "15+ languages" / 19 listed languages with "Basic Support (Quick Reference Only)" (lines 84-86, doc/tools/README.md:153).
  **reality:** `BASE_TEMPLATES` contains a single language: `python` — `src/agents/cheatsheet/enhanced_templates.py:711-717`. `quick_reference.py` ignores its `language` argument entirely and returns Python-shaped snippets (`print(value)`, `def name(args):`) regardless of input — `src/agents/cheatsheet/quick_reference.py:30-87`. For any non-Python language the output is Python content under a Python-titled header (`# Javascript Cheat Sheet - Beginner` followed by Python `def`/`print` examples).
  **severity:** critical

- **claim:** Auto-detect language uses an extensive `LANGUAGE_PATTERNS` dict spanning ~10+ languages including go, rust, java, typescript (lines 192-201).
  **reality:** `detect_language_from_code` only branches on Python and JavaScript/TypeScript regexes and **defaults to `"python"`** for anything unrecognised — `src/tools/cheatsheet/tools.py:6-23`. There is no go/rust/java/etc. pattern.
  **severity:** important

- **claim:** Detection failure returns `{"success": false, "message": "Could not detect language from code context"}` (lines 561-568).
  **reality:** `detect_language_from_code` always returns a string ("python" by default), so the `if not language` branch in `agent.py:86-91` is unreachable from the auto-detect path. Random text → `language="python"`, success=true.
  **severity:** important

- **claim:** Unsupported language returns error like `"Language 'cobol' is not supported. Supported: python, javascript, …"` (lines 522-536).
  **reality:** No allow-list validation exists. `language` is lowercased and looked up in `BASE_TEMPLATES`; on miss, `select_sections` falls through to the safety-net at `section_selector.py:56-68` which silently emits Python-beginner sections regardless of the requested language. Header still says e.g. `# Cobol Cheat Sheet - Beginner`.
  **severity:** important

- **claim:** Folder structure includes `src/agents/cheatsheet/__init__.py` and `src/tools/cheatsheet/__init__.py` (lines 40, 53).
  **reality:** Neither file exists (verified via `ls -la`). The packages work because Python 3 supports implicit namespace packages.
  **severity:** minor

- **claim:** "Test Coverage" — `tests/test_cheatsheet.py # Unit tests (58 total)` (line 58).
  **reality:** `test_cheatsheet.py` contains 4 test functions (`test_generate_python_beginner`, `test_generate_javascript_intermediate`, `test_auto_detect_language`, `test_gateway_invoke_wrapper`) — `tests/test_cheatsheet.py:6,17,27,38`. The total across all cheatsheet-related test files (`test_cheatsheet.py:4 + test_complexity_scorer.py:8 + test_cheatsheet_context_parser.py:5 + test_cheatsheet_performance.py:5 + test_library_detector.py:7 + test_python_levels.py:4 + test_fallback.py:3 + test_integration.py:11`) is 47, not 58.
  **severity:** minor

- **claim:** Default `skill_level` is `"beginner"` (line 70 parameter table; manifest line 204; doc body throughout).
  **reality:** Three sources, two values:
  - `CheatsheetArgs` (`src/core/schemas.py:288-291`) defaults to `"intermediate"` — disagrees with manifest/doc/agent.
  - `manifests/devforge.json:204` and the gateway JSON-Schema (`routers/__init__.py:1506-1510`) say `"beginner"`.
  - `cheatsheet_agent.generate` reads `arguments.get('skill_level', 'beginner')` — `src/agents/cheatsheet/agent.py:43`.
  Saved by the fact that `CheatsheetArgs` is **never invoked** in the request pipeline (`gateway_endpoint` passes `gateway_req.arguments or {}` straight to the agent — `src/api/routers/__init__.py:643,756`), but the schema is still importable dead code that contradicts the doc.
  **severity:** important

- **claim:** Pydantic schema has `language` as optional (parameter table line 68, "Either `language` or `code_context`" note line 72).
  **reality:** `CheatsheetArgs.language: str = Field(...)` — required (no default) — `src/core/schemas.py:287`. Inconsistent with both the doc and the manifest (`required: []`). Same caveat as above: schema is unused at runtime.
  **severity:** important

- **claim:** Phase 13 (doc header line 5).
  **reality:** `docs/tools/README.md:352` lists this as `Phase 7 | Cheat Sheets | ✅ Complete`. The two docs disagree.
  **severity:** minor

- **claim:** Generation flow diagram (line 416-433) shows "Profile Loading" and "Topic Selection" steps citing `LANGUAGE_PROFILES`.
  **reality:** The active pipeline (`CheatsheetAgent.generate`) does not read `LANGUAGE_PROFILES`. That dict lives in `language_profiles.py` and is only imported by `generator.py`, which is not imported by anything in the runtime path (Grep: only self-references). The selection mechanism is `BASE_TEMPLATES` + a fixed `priority` list inside `section_selector.py:39-47`.
  **severity:** important

- **claim:** "Code Location: Generator: `src/agents/cheatsheet/generator.py`, Profiles: `src/agents/cheatsheet/language_profiles.py`" (lines 437-440), and the implementation flow showing `LANGUAGE_PROFILES` topics dict (lines 384-405).
  **reality:** `generator.py`, `language_profiles.py`, `formatter.py`, and `src/tools/cheatsheet/templates.py` are **orphaned** — no module in the active call path imports them. Verified: `agent.py` imports only `context_parser`, `library_detector`, `complexity_scorer`, `section_selector`, `quick_reference` (`agent.py:6-11`) and `detect_language_from_code` (`agent.py:11`). `formatter.py` imports `templates.py`; `generator.py` imports `language_profiles.py`; nothing else imports either pair.
  **severity:** important

- **claim:** "Jinja2 — Templating (if needed)" listed under Technology Stack (line 412).
  **reality:** Jinja2 is imported only in `formatter.py:3`, which is dead code. The live `_assemble_markdown` builds markdown via plain `str.join` — `src/agents/cheatsheet/agent.py:143-171`.
  **severity:** minor

- **claim:** Quick-reference rows differ by language (per "Quick reference tables (skill-level specific)" line 30, and Examples section claiming JS/Rust/Go-specific quick refs at lines 484, 500, 516).
  **reality:** `_beginner_quick_ref` ignores `language` entirely — `src/agents/cheatsheet/quick_reference.py:30-40`. Same for `_intermediate_quick_ref` (line 43) and `_expert_quick_ref` (line 72). Output is identical Python syntax for every language.
  **severity:** important

- **claim:** Markdown code-fence language tag matches the requested language (implied by output examples).
  **reality:** `_assemble_markdown` writes `f"```{language}"` using whatever string was passed in (`agent.py:160`), so requesting `language: "rust"` produces ` ```rust ` fences around Python code lifted from `PYTHON_BEGINNER_BASE`.
  **severity:** important

- **claim:** Performance "Total: < 1s typical" with a per-step breakdown (lines 575-579).
  **reality:** Plausible given regex-only logic, but no benchmark exists in the repo to substantiate the < 10ms / < 500ms / < 50ms numbers.
  **severity:** unverifiable (listed below).

- **claim:** Doc version `0.8.0` (line 4) — agrees with manifest and main.py but disagrees with `Dockerfile:56` (`0.9.0`) and `docs/tools/README.md:3` (`0.7.0`).
  **severity:** minor (broader project drift, not specific to this tool).

## Unverifiable
- `< 500ms` content generation, `< 10ms` language detection, `< 50ms` markdown formatting (lines 575-579) — no benchmarks in repo.
- "Last Updated: December 23, 2025" (line 691) — date claim, not code-verifiable.
- Doc-quoted "LANGUAGE_PATTERNS" snippet (lines 192-201) — does not exist as a real symbol anywhere in `src/`. It's an illustrative pseudo-snippet at best; treated as fabricated documentation rather than a verifiable claim.
- "LANGUAGE_PROFILES" snippet (lines 384-405) — the symbol exists in `language_profiles.py:3` but the file is dead code, so the snippet describes a code path that is never executed.

## Stale / drift
- Phase number disagreement: `generate_cheatsheet.md:5` (Phase 13) vs `docs/tools/README.md:352` (Phase 7).
- Version sprawl: doc 0.8.0 / manifest 0.8.0 / `main.py` 0.8.0 / `Dockerfile` 0.9.0 / `docs/tools/README.md` 0.7.0.
- Orphaned files: `src/agents/cheatsheet/{generator.py, formatter.py, language_profiles.py}` and `src/tools/cheatsheet/templates.py` are unreferenced from the runtime pipeline; the doc still lists them as core components and the comment in `agent.py` calls `generator.py` "Legacy content generation (fallback)" but it isn't even wired as a fallback.
- `CheatsheetArgs` Pydantic model in `src/core/schemas.py:284-303` is dead — gateway never validates with it. Either wire it up (and reconcile defaults) or delete it.
- `docs/tools/README.md:3` `Last Updated: December 2, 2025` while `generate_cheatsheet.md:691` says December 23, 2025.

## Recommended doc changes
1. Replace "15+ languages" / the 19-language Basic Support list with the truth: **only Python has full templates; all other languages return Python content with a relabelled header**. Either implement quick-reference variants per language, or document the current Python-only behaviour explicitly.
2. Replace the fabricated `LANGUAGE_PATTERNS` snippet (lines 192-201) with the real Python/JS-only logic from `src/tools/cheatsheet/tools.py:6-23`, and clarify that unrecognised input defaults to `"python"` rather than erroring.
3. Delete the "Detection Failed" and "Unsupported Language" error-response examples (lines 522-568) — the code does not produce them. Either add validation in the agent or remove the false claims.
4. Change "15+ libraries" to "14 libraries" everywhere; list exactly the 14 keys from `LIBRARY_SIGNATURES`.
5. Reconcile `skill_level` default: pick `"beginner"` (matches manifest, agent, gateway schema) and update `CheatsheetArgs` in `src/core/schemas.py:288` from `"intermediate"` to `"beginner"`. Same file: change `language: str = Field(...)` to `Optional[str] = None` to match manifest semantics. (Or: wire `CheatsheetArgs` into the route handler and adjust the doc.)
6. Remove `__init__.py` from the folder-structure listings (lines 40, 53), or add the empty files to the repo.
7. Update the test count: `tests/test_cheatsheet.py` has 4 tests; total across cheatsheet-related suites is 47. Not 58.
8. Either delete the orphaned files (`generator.py`, `formatter.py`, `language_profiles.py`, `src/tools/cheatsheet/templates.py`) or remove them from the doc's Code Location and Folder Structure sections — the runtime pipeline does not use them.
9. Drop "Jinja2" from the Technology Stack list — the live path uses string concatenation, not templating.
10. Reconcile Phase number with `docs/tools/README.md` (Phase 7 vs Phase 13).
11. Note in the API Usage section that the markdown code-fence language tag echoes the input string, but the **content** inside the fence is Python regardless — until per-language templates are added.
12. Reconcile project version across `Dockerfile`, `docs/tools/README.md`, and the doc header.
