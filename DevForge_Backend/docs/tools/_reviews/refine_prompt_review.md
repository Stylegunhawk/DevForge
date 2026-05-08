# refine_prompt — Doc vs Code Review
**Reviewed:** 2026-04-27
**Branch:** rag_resolve
**Doc(s):** docs/tools/refine_prompt.md, docs/tools/README.md
**Code:** src/agents/prompt_refiner/
**Verdict:** Mostly accurate (with one material LLM-model lie + version/manifest drift)

## Summary
The doc accurately describes architecture, parameters, domain set, skill levels, evidence/confidence math, and the dual-template pattern. Three real problems: (1) doc claims the LLM used is `deepseek-r1:8b` but the enhancer calls `select_model_by_task("routing")` which resolves to `settings.SUPERVISOR_MODEL`, currently `gpt-oss:20b-cloud` (`src/core/config.py:114`); (2) doc version is `0.9.1` while `manifests/devforge.json:6` is `0.8.0` and `docs/tools/README.md:3` is `0.7.0` — three distinct version strings; (3) doc lists `context_selector.py` and `context_orchestrator.py` as "Legacy/Merged" but the files still exist in the tree and are not imported by `agent.py`/`enhancer.py` — they are dead code, not merged.

## Verified claims
- Folder layout matches `src/agents/prompt_refiner/` (Glob result): all 11 listed files exist, including the two deprecated ones.
- 5 domains (`general, image, code, rag, llm`) confirmed: `templates.py:103-110` (`TEMPLATES` dict), `domain_handlers.py:14-39` (`DOMAIN_CONFIGS` for image/code/rag/llm — `general` falls back to `GENERAL_TEMPLATE`), `core/schemas.py:261` (`Literal["general","image","code","rag","llm"]`), and `manifests/devforge.json:122-128` enum.
- 3 skill levels (`beginner, intermediate, expert`) confirmed in `core/schemas.py:265` and `manifests/devforge.json:134-138`.
- Templates are hard-coded Python strings in `templates.py` (not files, not LLM-generated) — matches doc.
- Dual-template selection: `enhancer.py:97-101` switches to `code_context` when `domain=="code"` and `chosen_stack.confidence > 0.0`. Matches doc "EVIDENCE Block" section.
- Confidence formula (avg of top-3 weights, capped at 1.0) matches doc: `enhancer.py:262-264`.
- Weights: dependency 0.9, code 0.8, conversation 0.4 — match doc: `enhancer.py:182-211` and `dependency_analyzer.py` (Evidence(weight=0.9) by inspection of imports).
- `FRAMEWORK_NORMALIZED_MAP` in `enhancer.py:15-27` is identical to the doc snippet.
- API contract: `arguments` accepts `prompt`, `domain`, `skill_level`, `file_context`, `conversation_history`, `attached_files`, `project_files` — confirmed by `agent.py:188-194` and `routers/__init__.py:1454-1497`. Gateway endpoint registered at `routers/__init__.py:48`.
- Response shape (`success`, `data.refined_prompt`, `data.context_summary`, `data.chosen_stack`, `data.sanitization_log`, `data.domain`) matches `agent.py:200-213`.
- Tests `test_prompt_refiner.py` (line 1), `test_prompt_refiner_phase2.py`, `test_sanitizer.py`, `test_context_parser.py` all exist.
- "Context-aware" definition matches code: `agent.py:67-72,123-169` pulls from `conversation_history`, `attached_files`, `file_context`, `project_files` — no RAG, no prior session history beyond what the caller supplies.

## Discrepancies
1. **LLM model lie.** Doc `refine_prompt.md:294` says "LLM Refinement: `deepseek-r1:8b`". `enhancer.py:122` calls `model_router.select_model_by_task("routing")` → `model_router.py:373` returns `settings.SUPERVISOR_MODEL` → `config.py:114` is `"gpt-oss:20b-cloud"`. The doc-quoted model only matches the inline comment in `model_router.py:373`, not the actual config value.
2. **Version drift.** Doc header `refine_prompt.md:4` says `Version: 0.9.1`; `manifests/devforge.json:6` says `0.8.0`; `docs/tools/README.md:3` says `0.7.0`.
3. **"Legacy/Merged" claim is misleading.** `refine_prompt.md:49-50` says context_selector.py and context_orchestrator.py contain "Logic now in enhancer.py". Both files still exist and are not imported anywhere in `agent.py` or `enhancer.py` (Grep confirms only self-imports of `context_types`). They are orphaned, not merged.
4. **Manifest description is much thinner than the doc claims.** Doc bullets evidence tracking, sanitization, normalization. `manifests/devforge.json:112` only says "Refine and optimize a prompt for specific domains". `routers/__init__.py:86-90` description is similarly minimal. No mention of evidence/sanitization at the discovery surface.
5. **`domain` enum in doc parameter table** (`refine_prompt.md:67`) lists `"code, image, rag, llm"` but omits `general`, which is both the default and a valid enum value (manifest line 123, schemas.py:261). Minor but inconsistent with doc line 29.
6. **Confidence wording.** Doc says weight per source, but `_build_chosen_stack` (`enhancer.py:262`) computes `avg(top_3_weights)` across ALL evidence regardless of framework. The example at doc line 154 (`(0.9 + 0.8) / 2 = 0.85`) is correct only when there are exactly 2 evidence items; with 3+ items the divisor is 3, not 2. Doc could mislead.
7. **Phase 6 / "Phase Status" table** (`README.md:351`) marks Phase 6 Prompt Refinement Complete; doc itself says "Phase: 6". The numbering is consistent within the docs but not externally verifiable in code (no `phase` constant).

## Unverifiable
- "Fast execution (< 2s typical)" — no benchmark in repo.
- "58+ total tests across all phases" — count not verified; only file existence confirmed.
- Sanitization pattern count "15+" / "10+ injection variants" — `sanitizer.py` not deeply audited here.

## Stale / drift
- `refine_prompt.md:385`: "Last Updated: February 12, 2026" — stale relative to today (2026-04-27); not a bug, just notable.
- `context_selector.py` / `context_orchestrator.py` are dead files; either delete them or the doc's "Logic now in enhancer.py" comment is wrong.
- Three different version numbers across doc (0.9.1), manifest (0.8.0), README index (0.7.0).

## Recommended doc changes
1. Replace `deepseek-r1:8b` (line 294) with: "Model selected via `model_router.select_model_by_task('routing')` → `settings.SUPERVISOR_MODEL` (currently `gpt-oss:20b-cloud`)".
2. Reconcile versions — pick one and update `manifests/devforge.json:6`, `docs/tools/README.md:3`, and `refine_prompt.md:4` to match.
3. Either delete `context_selector.py` + `context_orchestrator.py` from the repo, or remove them from the folder-structure list in the doc.
4. Add `general` to the `domain` parameter description (line 67).
5. Fix the confidence example on line 154–155 to use 3 evidence items, or note the divisor is `min(3, len(evidence))`.
6. Expand `manifests/devforge.json` `refine_prompt` description to mention evidence-based refinement and sanitization, so MCP discovery surfaces the real capabilities.
