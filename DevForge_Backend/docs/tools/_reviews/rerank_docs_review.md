# rerank_docs — Doc vs Code Review
**Reviewed:** 2026-04-27
**Branch:** rag_resolve
**Doc(s):** docs/tools/rag/rerank_docs.md, docs/reranking.md, docs/tools/README.md
**Code:** src/agents/reranker.py, src/agents/rag/reranking/cross_encoder_reranker.py, src/agents/rag/agent.py, src/api/routers/__init__.py, src/core/config.py
**Verdict:** Diverged

## Summary
`rerank_docs` is documented as a first-class standalone tool (Phase 4, "Production Ready"), but it is NOT registered in the `SUPPORTED_TOOLS` map nor declared in `manifests/devforge.json`. Calling `POST /api/gateway` with `name=rerank_docs` returns "Tool not found." The actual reranker is wired in only as an internal stage of `retrieve_docs` (RAG agent). There are also two parallel reranker implementations (legacy `src/agents/reranker.py`, new `src/agents/rag/reranking/cross_encoder_reranker.py`) and two overlapping docs.

## Standalone tool or internal-only?
**Internal-only.** Definitive proof:
- `src/api/routers/__init__.py:45-54` — `SUPPORTED_TOOLS` contains only `generate_data`, `github_operation`, `refine_prompt`, `generate_cheatsheet`. No `rerank_docs`.
- `src/api/routers/__init__.py:646` / `:1044` — both `/api/gateway` and `/mcp` `tools/call` reject any tool not in `SUPPORTED_TOOLS`.
- `manifests/devforge.json` (lines 9-320) — the `api` array lists 7 tools; `rerank_docs` is absent.
- `src/agents/reranker.py:98` — `rerank_docs_invoke()` exists as a wrapper but is never imported or registered anywhere outside the file.
- A stale `rerank_docs` JSON-Schema entry at `src/api/routers/__init__.py:1429` is dead code (only consumed by `_get_tool_schema`, which is itself called only for entries already in `SUPPORTED_TOOLS`).
- The reranker IS invoked internally — `src/agents/rag/agent.py:1105-1118` calls `self.reranker.rerank(...)` then `apply_code_boost(...)` inside `retrieve_docs`.

## Verified claims
- Cross-encoder model `cross-encoder/ms-marco-MiniLM-L-6-v2` — `src/core/config.py:205`, `cross_encoder_reranker.py:43-48`. Matches doc.
- Sigmoid normalization to [0,1] — `cross_encoder_reranker.py:52-71`.
- Two-stage recall: 30 candidates → rerank → top-K — `agent.py:960` (`VECTOR_SEARCH_CANDIDATES=30`), config.py:207.
- Code-aware boosting `BOOST_FUNCTION=1.2`, `BOOST_CLASS=1.15`, `BOOST_IMPORT=1.0`, `BOOST_TEXT=0.95` — config.py:210-213, applied in `cross_encoder_reranker.py:147-162` and called from `agent.py:1108`.
- Fallback when <3 chunks pass threshold — `agent.py:1114-1124`.
- `RERANK_SCORE_THRESHOLD=0.3` — config.py:206, applied at `agent.py:1116`.
- Tests `tests/test_reranker.py` exist (9+ tests including `test_rerank_sorts_correctly`, `test_score_reset`, `test_empty_chunks`, `test_top_k_limit`).
- CPU-only model load — `cross_encoder_reranker.py:47`.

## Discrepancies
1. **`rerank_docs` is not callable as a standalone gateway/MCP tool**, contrary to `rerank_docs.md:29` ("Standalone or RAG-integrated usage"), the curl examples (`rerank_docs.md:78-93`, `:368-403`), and `docs/tools/README.md:111` ("Standalone or RAG-integrated").
2. **Response schema mismatch.** Doc shows `{"reranked_docs": [{text, score}], "original_count", "returned_count"}` (`rerank_docs.md:99-114`), but `rerank_docs_invoke` in `src/agents/reranker.py:122-130` returns `{"data": {"documents": [...], "count": N}}` — different field names; no per-doc score is returned.
3. **`top_k` default**: doc claims `5` (`rerank_docs.md:43`); manifest schema entry at `routers/__init__.py:1447-1449` documents default 5; legacy `reranker.py:113` does default 5 — fine. But the actual RAG path uses `top_k * 2` and re-sorts (`agent.py:1105`), which is not documented.
4. **Two reranker implementations**: `src/agents/reranker.py` (the file the doc cites at `rerank_docs.md:336`) is the legacy minimal version with no sigmoid normalization, no code-aware boost, no threshold filtering. The actually-used class is `src/agents/rag/reranking/cross_encoder_reranker.py`. The doc points readers at the dead one.
5. **Input-schema mismatch.** Doc says `documents: array[string]` (`rerank_docs.md:42`). Stale gateway schema at `routers/__init__.py:1436-1445` says `array[object]` with `{content, metadata}`. Neither matches the legacy `rerank_docs_invoke` which would accept whatever is passed.
6. **Phase numbering inconsistent.** `docs/tools/README.md:104, :349` calls this "Phase 4". `rerank_docs.md:4` calls it "Phase 15.4 Integrated"; line 18 says "Phase 11"; `docs/reranking.md:4` says "Phase 12A". Code comment at `config.py:203` says "Phase 11". No single source of truth.
7. **Doc claims `RERANK_MIN_SCORE=0.0`** (`rerank_docs.md:264`) — actual setting is `RERANK_SCORE_THRESHOLD=0.3` (config.py:206). Wrong name and wrong value.
8. **Dependency versions** — `rerank_docs.md:331` claims `sentence-transformers 3.3.1`, but `DevForge_Backend/CLAUDE.md` pins `sentence-transformers 2.6` and `transformers 4.38`.

## Unverifiable
- "10-20% relevance improvement" / "75% → 90% top-1" / "65% → 85% top-5" (`rerank_docs.md:226-246`, `README.md:112`). No benchmark file or metric harness found in repo. `tests/test_reranking_performance.py` exists but was not inspected for these specific numbers.
- "<200ms" / "150ms reranking time" — code comments in `cross_encoder_reranker.py:29, :41` say "100-150ms for 30 candidates" but no asserted measurement.
- "90MB" model size, "50-100 docs/second" throughput (`rerank_docs.md:158-162`).

## Stale / drift
- `src/agents/reranker.py` and its `rerank_docs_invoke` wrapper appear orphaned — never imported by routers, supervisor, or RAG agent. Likely Phase-4 leftovers superseded by `src/agents/rag/reranking/`.
- The `rerank_docs` JSON-Schema entry at `src/api/routers/__init__.py:1429-1453` is unreachable (filtered out before schema lookup) — dead schema.
- `rerank_docs.md` "Last Updated: March 23, 2026" but `docs/tools/README.md` says "December 2, 2025" — version drift across the doc set.
- Phase tags drifting (4 vs 11 vs 12A vs 15.4) across docs/code.

## Recommended doc changes
1. Remove all "Standalone tool" framing from `rerank_docs.md` and `docs/tools/README.md` — clarify reranking is **only** invoked internally as part of `retrieve_docs`.
2. Strip the curl `name=rerank_docs` examples (`rerank_docs.md:78-93, :368-403`); they will return "Tool not found."
3. Update `rerank_docs.md:336` to point at `src/agents/rag/reranking/cross_encoder_reranker.py` (the live class) instead of the legacy `src/agents/reranker.py`.
4. Replace `RERANK_MIN_SCORE=0.0` with the real `RERANK_SCORE_THRESHOLD=0.3` and document the fallback ladder (≥3 / 1-2 / 0 chunks pass).
5. Document `BOOST_*` boosts and the `top_k * 2` re-sort step in the RAG flow (currently undocumented).
6. Pin one phase label across `rerank_docs.md`, `docs/reranking.md`, `docs/tools/README.md`, and `config.py` comments.
7. Either delete `src/agents/reranker.py` + the dead `rerank_docs` schema block in `routers/__init__.py:1429`, OR actually wire `rerank_docs_invoke` into `SUPPORTED_TOOLS` and the manifest if standalone exposure is desired.

## Doc consolidation note
**Yes — merge `docs/reranking.md` into `docs/tools/rag/rerank_docs.md`.** They overlap heavily (model, sigmoid, boosting, two-stage flow) and disagree on phase numbering. `docs/reranking.md` is more accurate to the code (correct threshold, correct fallback logic, correct mermaid pipeline) while `rerank_docs.md` is more user-facing but factually wrong on the standalone-tool premise. Recommend: keep `docs/tools/rag/rerank_docs.md` as the canonical entry, fold the technical "How it works / Sigmoid / Boosting / Fallback" sections from `docs/reranking.md` into it, and replace `docs/reranking.md` with a redirect stub.
