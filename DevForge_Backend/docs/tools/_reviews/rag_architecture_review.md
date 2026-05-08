# rag_architecture — Doc vs Code Review

**Reviewed:** 2026-05-08
**Branch:** rag_resolve
**Doc(s):** docs/tools/rag_architecture.md
**Code:** src/agents/rag/, src/storage/, src/core/config.py, src/api/routers/rag.py, src/core/middleware.py
**Verdict:** Diverged

## Summary
The doc captures the canonical retrieval flow (vector → rerank → context-shape) and most config defaults correctly, but its "Non-Negotiable Architecture Rules" no longer match the code: graph persistence to Redis was added (Phase 16), the QID format moved to `tenant::file::entity`, the layer diagram understates how Agents call into Tools, and `code_graph` is no longer a true lazy property — it requires explicit `await init_graph()`. The Module Structure table is also incomplete: entire production submodules (`cache/`, `expansion/`, `retrieval/`, `reranking/`, `analytics/`) and the active backend (`pgvector_store.py`) are absent or marked as legacy/future. Doc header claims "Phase 15.3" while code carries Phase 16 markers, and the canonical curls advertise `X-User-ID` for tenant scoping when the actual middleware reads tenant_id from a JWT bearer token.

## Verified claims
- Two-stage retrieval (vector → cross-encoder rerank) — `src/agents/rag/agent.py:837-1102`, `src/agents/rag/reranking/cross_encoder_reranker.py:23-78`.
- `RAGAgent` owns instance-scoped `self._code_graph`, no module-level globals — `src/agents/rag/agent.py:331`, init at `:473`, `:514`; no `global` graph anywhere in `src/`.
- BFS expansion with default `depth=2`, `max_results=10` — `src/agents/rag/graph/code_graph.py:131-177`; matches doc lines 526-528.
- Default settings: `RAG_CHUNK_SIZE=500`, `RAG_CHUNK_OVERLAP=50`, `RAG_TOP_K=5`, `RAG_EMBED_MODEL="nomic-embed-text"` — `src/core/config.py:135-138`, `133`.
- `ENABLE_CODE_GRAPH=True`, `GRAPH_CONTEXT_DEPTH=2`, `GRAPH_MAX_CONTEXT_CHUNKS=3` — `src/core/config.py:196-198`.
- `ENABLE_RERANKING=True`, `RERANK_MODEL="cross-encoder/ms-marco-MiniLM-L-6-v2"`, `VECTOR_SEARCH_CANDIDATES=30` — `src/core/config.py:204-207`.
- Boost factors `BOOST_FUNCTION=1.2`, `BOOST_CLASS=1.15` and applied in reranker — `src/core/config.py:210-213`, `cross_encoder_reranker.py:155-162`.
- Hybrid search BM25+Vector with `ENABLE_HYBRID_SEARCH=True`, `HYBRID_ALPHA=0.5` — `src/core/config.py:222-223`; BM25 wired via `BM25Index` — `src/agents/rag/retrieval/bm25_index.py`.
- 2000-char safety valve re-splits oversize AST chunks — `src/tools/rag/tools.py:301-326`.
- `iter_chunk_metadata(batch_size=500)` is the rebuild source for the graph — `src/agents/rag/agent.py:477`.
- Tenant-scoped collection `user_{tenant_id}` and per-(tenant,collection) agent cache key — `src/api/routers/rag.py:55-56`, `src/agents/rag/agent.py:229-232`.
- `BaseVectorStore` interface methods (`add_chunks`, `search`, `get_chunk_by_qualified_id`, `iter_chunk_metadata`) match the abstract signature shown in the doc — `src/storage/base_store.py:35-115`.
- ContextShaper Phase 13 stage (dedup → role assignment → ordering → limits) is real — `src/agents/rag/context_shaper.py:39-78`, called at `src/agents/rag/agent.py:1127, 1145, 1162`.
- Sequential chunk endpoint `GET /api/v1/rag/file/{fileId}/chunks` with `limit=5, offset=0` defaults — `src/api/routers/rag.py:141-146`.
- `SemanticSearchRequest` schema fields (`messageId`, `userQuery`, `rewriteQuery`, `fileIds`, `top_k`) — `src/api/schemas/rag.py:67-75`.

## Discrepancies (doc says X, code does Y)

- **claim:** Architecture Rule 1 — "**No graph persistence** — No pickle, no database, no cache files" (lines 261-263) and the Forbidden Patterns block.
  **reality:** `init_graph()` reads/writes the graph to **Redis** with a 1-hour TTL — `src/agents/rag/agent.py:436-463, 498-509` (`cache_key = f"rag_graph:v2:{self.collection_name}"`, `redis_client.set(cache_key, json.dumps(graph_dict), ex=3600)`). The `ingest_document` and `delete_file_cascade` paths actively invalidate this Redis key (`agent.py:639-647, 695-708`). Persistence exists; the rule needs a "no on-disk pickle, but Redis-cached for warm starts" caveat.
  **severity:** critical

- **claim:** QID format is `file::entity` (lines 280-289), with examples `auth.py::authenticate`, `utils.py::User.login` (single tenant).
  **reality:** Code uses `tenant_id::file::entity` (3 segments). `CodeGraph.add_node` warns and rejects QIDs with fewer than 3 segments — `src/agents/rag/graph/code_graph.py:44-47` (`if len(parts) < 3: logger.warning("Invalid QID format (expected tenant::file::entity)...")`). Anchor QIDs are built as `f"{tenant_id}::{source}::{name}"` — `src/agents/rag/agent.py:1299, 1312`. The cache load step explicitly rebuilds the graph if it finds legacy 2-segment QIDs (`agent.py:454-456`).
  **severity:** critical

- **claim:** "`code_graph` (lazy property)" — the implementation snippet at lines 266-275 shows `@property` doing the rebuild on first access.
  **reality:** The property at `src/agents/rag/agent.py:403-418` raises `RuntimeError("Code graph not initialized. Call 'await agent.init_graph()' first.")` when `_code_graph is None`. Initialization is an explicit `async def init_graph()` (`agent.py:420`), called at retrieval time (`agent.py:1008-1009`). The property is not what the doc describes.
  **severity:** important

- **claim:** Layer Separation rule — "**Tools** → Agents (NEVER storage)" and "**Agents** → BaseVectorStore (NEVER backend internals)" (lines 308-312).
  **reality:** The Agent imports from Tools, not the other way around: `from src.tools.rag.tools import generate_response, ingest_documents, retrieve_docs` — `src/agents/rag/agent.py:18-22`, plus `agent.py:382, 620`. `tools.ingest_documents` then performs storage ops directly (chunking, embedding, vector store writes — `src/tools/rag/tools.py:407-415`). The actual call chain is `Agent → Tools → Storage`, not `Tools → Agents`. The arrow direction in the doc's call rules is inverted.
  **severity:** important

- **claim:** Vector Store config block — `VECTOR_BACKEND=chroma  # or qdrant` (line 543) and `pgvector_store.py — pgvector implementation (Phase 10.2)` (line 467).
  **reality:** `VECTOR_BACKEND: str = "postgres"  # Options: chroma, postgres` — `src/core/config.py:130`. `RAGAgent.__init__` only branches on `postgres` vs Chroma — `src/agents/rag/agent.py:319-329`. There is no `QdrantVectorStore` implementing `BaseVectorStore`; Qdrant is a legacy LangChain wrapper inside `tools.get_vector_store` and is not selectable via `VECTOR_BACKEND`. pgvector is the **production default**, not a future "Phase 10.2" item.
  **severity:** critical

- **claim:** Module Structure table for `/src/agents/rag` lists only `agent.py`, `context_shaper.py`, `graph/code_graph.py`, `chunking/code_chunker.py`, `chunking/text_chunker.py`, `linking/test_linker.py` (lines 444-452).
  **reality:** Production-active submodules are missing from the table:
    - `src/agents/rag/cache/{query_cache.py, semantic_cache.py, query_normalizer.py}` (instantiated `agent.py:343-348, 380-392`)
    - `src/agents/rag/expansion/{query_expander.py, result_fusion.py}` (`agent.py:371-376, 964`)
    - `src/agents/rag/retrieval/{bm25_index.py, hybrid_retriever.py}` (`agent.py:353-355, 550`)
    - `src/agents/rag/reranking/{base_reranker.py, cross_encoder_reranker.py}` (`agent.py:591`)
    - `src/agents/rag/analytics/intent_classifier.py` (`agent.py:360-365`)
    - `src/agents/rag/chunking/base_chunker.py` (the abstract base)
  **severity:** important

- **claim:** Component Architecture / Ingestion Pipeline says code files are `.py, .js, .ts` (line 350).
  **reality:** `SUPPORTED_LANGUAGES` in `src/agents/rag/chunking/code_chunker.py:21-27` covers `.py, .js, .ts, .tsx, .jsx`. JSX/TSX support is missing from the doc.
  **severity:** minor

- **claim:** "Retrieval Pipeline" diagram has the order `Initial Results → Graph Expansion → Cross-Encoder Reranking → Context Shaper` (lines 376-396).
  **reality:** This order is correct. However the diagram omits the **Phase 12A query intelligence prefix** that runs *before* the retrieval call: `Intent Classification → Semantic Cache Check → Query Expansion → (multi-query fan-out + RRF fusion) → Hybrid (BM25+Vector) OR Vector` — `src/agents/rag/agent.py:881-1002`. The doc only mentions Phase 12A in the bulleted "Architecture Rules" (lines 232-236) without showing it in the flow.
  **severity:** important

- **claim:** Module table lists `linking/test_linker.py — Test-source linking` and "Architecture Rules" advertises "Test-source linking" (lines 240, 451).
  **reality:** `TestLinker` is implemented (`src/agents/rag/linking/test_linker.py:32`) and exported from `linking/__init__.py`, but it is **never instantiated by the production path**. No imports in `src/agents/rag/agent.py` or `src/tools/rag/tools.py`; only test usage in `tests/test_day6_validation.py`. The "test_files" metadata field shown at line 506 is therefore aspirational on the ingestion path.
  **severity:** important

- **claim:** "API Endpoints" table lists `/rag/ingest-async` and `/rag/task/{task_id}` as the API surface (lines 482-485).
  **reality:** Real paths after main router mount are `/api/rag/ingest-async` and `/api/rag/task/{task_id}` — `src/main.py:81` (`app.include_router(router, prefix="/api")`), `src/api/routers/__init__.py:121, 158`. The table also entirely omits the canonical `/api/v1/rag/*` Lobe Chat surface that the doc itself freezes earlier (lines 22-72), the analytics endpoints under `/api/rag/analytics/*` (`routers/__init__.py:457-540`), `/api/rag/metrics` (`:198`), `/api/rag/health` (`:305`), `/api/rag/cache/clear` (`:389`), `/api/rag/bm25/rebuild` (`:417`).
  **severity:** important

- **claim:** Frozen API contract repeatedly states `X-User-ID` (Required) is "Used to derive the `tenant_id` and sandbox the collection" (line 17), and every canonical curl uses `-H "X-User-ID: dev_user_1"` (lines 84, 113, 127, 142, 162, 181, 198, 213).
  **reality:** `JWTAuthMiddleware` reads `tenant_id` exclusively from a verified JWT in the `Authorization: Bearer <token>` header — `src/core/middleware.py:124-150`; on missing/invalid token it returns 401 before the route runs. `request.state.tenant_id` is set from `payload.get("tenant_id")` (`middleware.py:150`), and the rag router reads only `request.state.tenant_id` — `src/api/routers/rag.py:24-26, 55, 151, 198, 220, 367`. There is no code path that reads the `X-User-ID` header. Every canonical curl in the doc would 401 against the running service.
  **severity:** critical

- **claim:** "Graph Rebuild" diagram shows `Build QID (file::entity)` (line 414).
  **reality:** Same QID drift as above — graph rebuild explicitly tags QIDs with tenant: `add_chunks_batch(valid_batch, tenant_id=getattr(self, 'tenant_id', 'default'))` — `src/agents/rag/agent.py:492`, and `CodeGraph.add_node` enforces 3 parts.
  **severity:** important

- **claim:** "Graph is **derived state** | Rebuilt from chunk metadata on first access" (line 260).
  **reality:** Half-true. After Phase 16 the rebuild is gated behind a Redis cache lookup — first access checks Redis, only rebuilds on cache miss or legacy-QID detection — `src/agents/rag/agent.py:436-470`. So the graph is "derived state with a Redis warm-start cache", not a pure rebuild-on-access.
  **severity:** important

- **claim:** Architecture Rule footer "Phase: Phase 15.3 Sequential Chunk Retrieval" / "Version: 15.3 Complete" (lines 3-5) and "These rules are mandatory for all Phase 10.1 implementation" (line 254).
  **reality:** Code carries explicit `Phase 16` markers for the Redis graph caching/invalidation work — `src/agents/rag/agent.py:424, 634`. Other docs in the same tree (`docs/tools/rag/rag_integration_flow.md:4`, `docs/tools/rag/rerank_docs.md:4`) reference Phase 15.4. The architecture doc is one minor version behind the integration-flow doc and one major step behind the agent code's actual checkpoint.
  **severity:** minor

## Unverifiable
- Performance claims: "CPU-friendly (~100-150ms for 30 candidates)", "~150ms for 30 candidates (CPU)", "~200MB in RAM" appear in `cross_encoder_reranker.py:29, 41` and align with the README's "<200ms reranking overhead", but no benchmark/perf test in `tests/` measures them.
- Latency target "<5ms average" for IntentClassifier (`analytics/intent_classifier.py:67`) — no measurement code.
- "1-hour TTL" for the Redis graph cache is real (`agent.py:501` — `ex=3600`); but no claim in this doc to verify against (the doc denies persistence entirely).

## Stale / drift
- Doc header **Version 15.3** / **Phase 15.3** — code shows Phase 16 (`agent.py:424, 634`); sibling docs reference Phase 15.4. Single source of truth for phase numbering does not exist in the repo (Phase tags are scattered: 10.1, 10.2, 11, 11.2, 12, 12A Day 1-6, 13, 14, 15.3, 15.4, 16).
- Line 254: "Phase 10.1 implementation" — outdated framing for rules that now span multiple phases.
- Line 467: "pgvector implementation (Phase 10.2)" — pgvector is the production default per `config.py:130`.
- Line 543: `VECTOR_BACKEND=chroma  # or qdrant` — should be `chroma | postgres`; default is `postgres`.
- Line 545: `USE_PGVECTOR=false` — listed as if active, but in code `USE_PGVECTOR` is a deprecated feature flag (`config.py:192` — "Feature flag, ChromaDB default") superseded by `VECTOR_BACKEND`.
- Lines 592-594 "Related Documentation" links are broken: `./rag_integration_flow.md` and `./tools/retrieve_docs.md` — actual paths are `./rag/rag_integration_flow.md` and `./rag/retrieve_docs.md` (the `tools/` subdirectory does not exist under `docs/tools/`).
- Line 600 Version History stops at "v10.1 (Dec 2025)" — no entries for Phases 11-16.
- Canonical curls (line 84 onward) use port `8000`; backend default is `8001` (`CLAUDE.md`, `src/main.py`).
- Line 244: "ms-marco-MiniLM-L-6-v2" model name is missing the `cross-encoder/` HuggingFace prefix that the code actually uses (`config.py:205`).
- Lines 50, 615 contain stray characters (trailing `|`, scattered emoji blocks) — minor formatting.

## Recommended doc changes
1. Rewrite Architecture Rule #1 ("No graph persistence") to acknowledge the Redis warm-start cache (Phase 16) with TTL, invalidation hooks, and which calls trigger eviction.
2. Update QID format section (lines 278-292) and the "Graph Rebuild" diagram (line 414) to `tenant::file::entity`; update the validator description to match `CodeGraph.add_node` (3-segment requirement, legacy detection).
3. Replace the `@property` snippet (lines 266-275) with the actual `init_graph()` flow: Redis lookup → cache validation → `iter_chunk_metadata` rebuild → cache write.
4. Fix layer-separation arrows: the production direction is `Agents → Tools → Storage`; either reflect that or refactor (out of scope for this review).
5. Replace `chroma | qdrant` with `chroma | postgres` in the config block and update `pgvector_store.py` to "production default", not "Phase 10.2".
6. Expand the `/src/agents/rag` Module Structure table to include `cache/`, `expansion/`, `retrieval/`, `reranking/`, `analytics/` and the `chunking/base_chunker.py` abstract base.
7. Remove `X-User-ID` from the Frozen API Contract and every canonical curl; replace with `Authorization: Bearer <tenant_jwt>`. Document the JWT payload contract (`tenant_id` claim).
8. Add Phase 12A query intelligence (intent → semantic cache → expansion → multi-query RRF) to the Retrieval Pipeline diagram (line 369).
9. Clarify TestLinker status — it is implemented but **not wired into the ingestion path**; either drop the architecture-rule advertisement or describe it as "available, not yet integrated".
10. Bump header to the highest active phase (16, or whatever is canonical), backfill Version History entries from Phase 11 onward, and fix the broken "Related Documentation" links to `./rag/...`.
11. Replace Code Files extension list `.py, .js, .ts` with `.py, .js, .ts, .jsx, .tsx`.
12. Update the API Endpoints table (lines 482-485) with full `/api/...` prefixes and the actual surface (Lobe Chat `/api/v1/rag/*`, analytics `/api/rag/analytics/*`, ops `/api/rag/{metrics,health,cache/clear,bm25/rebuild}`).
13. Rename `RERANK_MODEL` value to include the `cross-encoder/` prefix to match `config.py:205`.
14. Pin curls to port `8001` (or document the discrepancy).
