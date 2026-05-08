# generate_data — Doc vs Code Review

**Reviewed:** 2026-04-27
**Branch:** rag_resolve
**Doc(s):** docs/tools/generate_data.md, docs/tools/generate_data_flowchart.md, docs/tools/README.md
**Code:** src/tools/datagen/, src/agents/datagen/, src/api/routers/__init__.py, manifests/devforge.json
**Verdict:** Diverged

## Summary
The doc is structurally correct on the high-level architecture (Phase 1 3-layer design, V1/V2 split, mode selection) but contains several concrete contradictions with the code: it under-claims FK enforcement (which is actually wired up), miscounts lexical mappings, lists incorrect default V1 fields, and disagrees with the manifest on row bounds. Manifest, doc, and code all carry different version/limit values.

## Verified claims
- `generate_data` is registered in `SUPPORTED_TOOLS` mapped to `datagen_agent` — `src/api/routers/__init__.py:46`.
- Mode selection: V2 when `prompt` or `domain` provided, else V1 — `src/agents/datagen/agent.py:74`.
- Pydantic params (`rows`, `format`, `fields`, `prompt`, `domain`, `realism_level`, `enable_semantic_generation`) and types match doc — `src/core/schemas.py:156-180`.
- Domains supported = `ecommerce`, `saas`, `iot_devices` — `src/core/schemas.py:169`.
- Realism levels = `basic`, `medium`, `high` — `src/core/schemas.py:173`.
- V1 row bounds 1-10000 enforced — `src/tools/datagen/tools.py:111`.
- `generate_advanced_data_v2` is the V2 entry point invoked by the agent — `src/agents/datagen/agent.py:16,82`.
- Phase 1 component files exist exactly where doc claims (`semantic_analyzer_v2.py`, `lexical_dict.py`, `pattern_classifier.py`, `context_classifier.py`, `llm_classifier.py`, `catalog_factory.py`, `semantic_router.py`, `advanced_generator_v2.py`).
- `ENABLE_SEMANTIC_ANALYZER` env flag — `src/agents/datagen/agent.py:19`.
- Test `TestEndToEnd::test_banking_example_no_llm_prose` exists — `tests/test_semantic_analyzer_v2.py:281,290`.

## Discrepancies (doc says X, code does Y)

- **claim:** "303 lexical mappings" (multiple places, e.g. lines 47, 589, 624, 900).
  **reality:** `len(LEXICAL_DICT) == 299` — `src/tools/datagen/lexical_dict.py:10`.
  **severity:** minor

- **claim:** Foreign keys are NOT enforced; `RelationshipEngine` "exists but is not used by `advanced_generator_v2.py`" (lines 634, 667, 671, 821, 877).
  **reality:** `RelationshipEngine` is imported and used in `_generate_with_relationships` and `_validate_fk_integrity`; FK integrity is validated and surfaced as `fk_integrity` in the response — `src/tools/datagen/advanced_generator_v2.py:25,134-153,292,461-468`.
  **severity:** critical (the doc actively misleads users into post-processing FKs that the code already enforces)

- **claim:** `enable_semantic_generation` "is not part of the `DataGenArgs` Pydantic schema" (lines 445, 672).
  **reality:** It IS a typed `bool` field in `DataGenArgs` with default `True` — `src/core/schemas.py:177-180`.
  **severity:** important

- **claim:** Default V1 fields are `name, email, phone, address, company, job, date` (line 100).
  **reality:** Code uses first 8 keys: `name, email, address, phone, company, job, date_of_birth, city` — `src/tools/datagen/tools.py:24-35,117`.
  **severity:** important

- **claim:** "rows (1-10,000)" globally (lines 32, 67).
  **reality:** Pydantic gate is 1-10000 (`src/core/schemas.py:160`), but the V2 internal validator allows 1-100000 (`src/tools/datagen/advanced_generator_v2.py:774`), and the manifest advertises 1-100000 (`manifests/devforge.json:18-20`). Three values, none consistent.
  **severity:** important

- **claim:** Validation stress-test: "Multi-Entity: relationships tracked but foreign keys not validated in Phase 1" (line 667).
  **reality:** FK validation runs and the response includes `fk_integrity.statistics` with `orphaned_children`, `parents_with_zero_children`, etc. — `advanced_generator_v2.py:151-153,461-468`.
  **severity:** important

- **claim:** Test counts: "180+ passing tests", "V1 backward compatibility (20 tests)", "Schema validation and LLM fallback (36 tests)" (lines 793-801).
  **reality:** Total `def test_*` across the listed suites = 169. `test_datagen.py` has 13 tests (not 20). `test_schema_designer.py` has 32 (not 36).
  **severity:** minor

- **claim:** README.md says "Version: 0.7.0" and lists 6 tools (lines 3, 5).
  **reality:** `manifests/devforge.json` declares `0.8.0` (line 6); `src/main.py` uses `0.8.0` (lines 58, 168); `Dockerfile` LABEL is `0.9.0` (line 56); `routers/__init__.py:602` advertises gateway version `0.1.0`. `SUPPORTED_TOOLS` registers only 4 tools (`generate_data`, `github_operation`, `refine_prompt`, `generate_cheatsheet`) — `src/api/routers/__init__.py:45-54`. `retrieve_docs` and `rerank_docs` are not gateway tools.
  **severity:** important

- **claim:** Doc `Version: 1.1.0` in header but Changelog only goes up to `Version 1.0.0` (lines 4, 894).
  **reality:** Internal inconsistency in the doc itself.
  **severity:** minor

- **claim:** Gateway tool description claims "rows: 1-100000" (line 62 of routers/__init__.py used by manifest text).
  **reality:** Pydantic rejects rows > 10000 before reaching V2 internals — users will get validation errors at 10001+ despite the advertised 100000 ceiling.
  **severity:** important

## Unverifiable

- Performance numbers ("<2s for 1,000 rows V1", "<5s V2 3 entities") — no benchmark in repo.
- Realism injection rates ("~5% nulls medium / ~10% nulls high / ~2% duplicates / ~1% outliers") — not spot-checked against `_apply_realism` source.
- Default entity row counts per domain (e.g. "100 customers, 50 products, 500 orders") — not traced into domain templates.

## Stale / drift

- Version sprawl: doc 1.1.0 / changelog 1.0.0 / README.md 0.7.0 / manifest 0.8.0 / main.py 0.8.0 / Dockerfile 0.9.0 / gateway response 0.1.0.
- README.md `Last Updated: December 2, 2025` while `generate_data.md` says `February 26, 2026`.
- Doc lists 6 tools; only 4 are actually wired into `SUPPORTED_TOOLS`.
- Doc references `tests/test_distributions.py`, `tests/test_domain_templates.py`, `tests/test_realism.py` — all exist; counts in doc are off by a few.

## Recommended doc changes

- Replace every "303 lexical mappings" with "299" (or read from `len(LEXICAL_DICT)`).
- Remove "FK not validated in Phase 1" language; describe the actual `_validate_fk_integrity` + `fk_integrity` response shape.
- Drop the line claiming `enable_semantic_generation` is not in the Pydantic schema.
- Fix V1 default fields list to match code: `name, email, address, phone, company, job, date_of_birth, city`.
- Reconcile row-bound: pick one limit (10000 per Pydantic) and update manifest + V2 internal check to match, OR raise Pydantic to 100000.
- Update Test Coverage section with actual per-suite counts (run `pytest --collect-only` and copy).
- Bump `docs/tools/README.md` version, last-updated date, and tool count to match `routers/__init__.py:SUPPORTED_TOOLS`.
- Reconcile doc header Version (1.1.0) with Changelog (latest entry is 1.0.0).
- Decide on a single project version (main.py vs Dockerfile vs manifest) and propagate.
