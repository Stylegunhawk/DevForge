# retrieve_docs (RAG) — Doc vs Code Review
**Reviewed:** 2026-04-27
**Branch:** rag_resolve
**Doc(s):**
- `DevForge_Backend/docs/tools/rag/retrieve_docs.md`
- `DevForge_Backend/docs/tools/rag_architecture.md`
- `DevForge_Backend/docs/tools/rag/rag_integration_flow.md`
- `DevForge_Backend/docs/tools/rag/get_files_api.md`, `get_file_chunks_api.md`
- `DevForge_Backend/docs/tools/README.md`
- `DevForge_Backend/docs/tools/rag_unification_verified.md`

**Code:**
- `DevForge_Backend/src/api/routers/rag.py`, `src/api/routers/__init__.py`
- `DevForge_Backend/src/agents/rag/agent.py`, `src/tools/rag/tools.py`
- `DevForge_Backend/src/storage/{base_store,chroma_store,pgvector_store}.py`
- `DevForge_Backend/src/core/config.py`, `src/main.py`
- `DevForge_Backend/manifests/devforge.json`, `tests/test_rag.py`

**Verdict:** Diverged

## Summary
Retrieval logic, multi-tenant routing, query intelligence, hybrid search, reranking, AST chunking, and graph expansion are all wired up and broadly match the docs. However, the docs describe a **gateway tool** (`retrieve_docs` via `POST /api/gateway`) that is **not registered**, claim **ChromaDB + Qdrant** as the dual backend while the actual default and supported pair is **Postgres (pgvector) + Chroma** (Qdrant exists only as a legacy `langchain-qdrant` path inside `tools.get_vector_store` and is not selectable via `VECTOR_BACKEND`), and reference endpoints/paths that do not exist (`/rag/retrieve`, several Phase-12A analytics endpoints partially). The README tool index is at v0.7.0 from Dec 2025 and significantly stale relative to v15.4 / v0.8.0 elsewhere.

## Verified claims
- `/api/v1/rag/file/upload`, `/file/{id}`, `/file/{id}/chunks`, `/files`, `/chunk/semanticSearchForChat`, `/file/{id}` DELETE all exist as documented (`src/api/routers/rag.py:39-416`).
- Tenant JWT middleware applies to `/api/v1/rag/*` (`src/core/middleware.py:124`); per-tenant collection `user_{tenant_id}` (`rag.py:56`, `agent.py:229`).
- Two-stage retrieval: vector → cross-encoder reranking with sigmoid normalization is implemented in `agent.py:837-1100` and `_sigmoid` in `routers/rag.py:28`. `VECTOR_SEARCH_CANDIDATES=30` (`config.py:207`).
- Hybrid search (BM25+vector) is wired: `BM25Index` uses `rank_bm25.BM25Okapi` (`src/agents/rag/retrieval/bm25_index.py:12`); flag `ENABLE_HYBRID_SEARCH=true`, `HYBRID_ALPHA=0.5` (`config.py:222-223`).
- Query intelligence: intent classification, query expansion, semantic cache, exact-match query cache all instantiated in `RAGAgent.__init__` (`agent.py:341-399`); thresholds match (`SEMANTIC_CACHE_THRESHOLD=0.92`, `config.py:247`).
- AST chunking via `tree_sitter_languages` for `.py/.js/.ts/.jsx/.tsx` (`code_chunker.py:21-67`); test↔source linking present (`linking/test_linker.py:23-28`); 2000-char safety valve in `tools.chunk_document` (`tools.py:301-326`).
- Format support PDF/MD/TXT/DOCX confirmed (`tools.py:29-31, 219-244`) plus `.py/.js/.ts/.jsx/.tsx/.json/.rst` (broader than the doc's "PDF, MD, TXT, DOCX").
- Defaults: `RAG_CHUNK_SIZE=500`, `RAG_CHUNK_OVERLAP=50`, `RAG_TOP_K=5`, `RAG_EMBED_MODEL=nomic-embed-text` match the doc (`config.py:135-138`).
- Code graph rebuild is lazy + Redis-cached (`agent.py:420-500`), instance-scoped, derived from `iter_chunk_metadata` — matches architecture rules.

## Discrepancies (doc says X, code does Y)

1. **(critical) `retrieve_docs` is NOT registered as a gateway tool.** Doc says `POST /api/gateway` with `{"name":"retrieve_docs",...}` (`retrieve_docs.md:181-205, 588-598`), and `README.md:60-77` lists it as a Phase-3.1 gateway tool. Code: `SUPPORTED_TOOLS` in `src/api/routers/__init__.py:45-54` contains only `generate_data, github_operation, refine_prompt, generate_cheatsheet`. `retrieve_docs` is also absent from `manifests/devforge.json` (only 7 tools listed, none named retrieve_docs). The gateway endpoint exists, but calling `retrieve_docs` returns 404 with "Tool not found".

2. **(critical) "Dual vector store (ChromaDB local + Qdrant cloud)" is wrong.** Docs repeatedly state Chroma + Qdrant (`retrieve_docs.md:42, 396-399`; `README.md:67`). Code: `VECTOR_BACKEND` accepts `chroma | postgres` (default `postgres`) per `config.py:130` comment, and `RAGAgent.__init__` only branches on `postgres` vs Chroma (`agent.py:319-329`); `tools.ingest_documents` likewise (`tools.py:407-415`). Qdrant exists only as a legacy LangChain wrapper in `tools.get_vector_store` (`tools.py:129-161`) which is never reached when `VECTOR_BACKEND=postgres`. There is no `QdrantVectorStore` implementing `BaseVectorStore`. **pgvector/Postgres is the production default** but is omitted from every doc except `rag_architecture.md:467` which calls it Phase 10.2.

3. **(important) `POST /api/rag/ingest-async` is unauthenticated where the docs imply auth.** `retrieve_docs.md:99-122` shows curl with no auth headers. Code mounts this under `/api` not `/api/v1/rag`, so `JWTAuthMiddleware` does NOT apply (`middleware.py:124` only matches `/api/v1/rag/`). The async ingest also does not pass `tenant_id`/`file_id` (`routers/__init__.py:142-146`), so chunks land in the global `devforge_docs` collection without tenant isolation — contradicting the "Strict Multi-Tenancy" guarantee.

4. **(important) Doc cites endpoints that don't exist.**
   - `GET /rag/retrieve?query=...` (`rag_integration_flow.md:203`) — not implemented.
   - `/api/v1/rag/message/{id}/query` DELETE is documented (`retrieve_docs.md:139`) but the code path is `/api/v1/rag/message/{message_id}/query` (matches) — verified OK; however the table at `retrieve_docs.md:138` says `DELETE /api/v1/rag/file/{id}[?force=true]` removes file+vectors+metadata — `?force=true` exists (`rag.py:361`) ✓.
   - `/api/rag/analytics/cache-by-intent`, `expansion-quality`, `intent-distribution`, `fallback-usage` claimed in `rag_integration_flow.md:188-192` — these DO exist (`routers/__init__.py:457-540`), but the doc cites a 5th `/api/rag/metrics` which exists at `routers/__init__.py:198`. ✓ for analytics; minor: paths are under `/api/rag/...` not `/api/v1/rag/...`.

5. **(important) `RAG_SCORE_THRESHOLD` default mismatch.** Doc says `0.5` (`retrieve_docs.md:418`); code default is `0.0` (`config.py:138` with comment "Set to 0 to accept all results"). The `RERANK_SCORE_THRESHOLD` is `0.3`, not `0.5`.

6. **(important) `include_context` parameter is documented but not exposed.** Doc parameter table (`retrieve_docs.md:151-173`) lists `include_context: bool` for graph expansion. Code: `RetrieveDocsArgs` schema (`src/core/schemas.py:197+`) and `retrieve_with_reranking` (`agent.py:837-845`) take no such flag — graph expansion runs unconditionally when `ENABLE_CODE_GRAPH=true` (`agent.py:1004`). Callers cannot opt in/out per request as documented.

7. **(minor) "Cloud model gpt-oss:120b-cloud for response generation" claim** (`retrieve_docs.md:23`, `rag_integration_flow.md:165-168`). Code: `model_router` is referenced for `generate_response`, but `RAG_LOCAL_MODEL` is set to `gpt-oss:20b-cloud` (`config.py:117`), not the 120b variant for default rag flows.

8. **(minor) Phase-15.4 multi-tenant QID format `tenant::file::entity`** (`rag_integration_flow.md:524-530`) is enforced by validator (`agent.py:454`: `node.id.count("::") < 2`) ✓ but the canonical doc `rag_architecture.md:280` still describes `file::entity` (single tenant). Internal inconsistency.

9. **(minor) `get_files_api.md` says `X-User-ID` is optional and defaults to "default"**, but the code reads `request.state.tenant_id` set by `JWTAuthMiddleware`, which **rejects requests without a JWT** (`middleware.py:124+`). The header is not what the code consumes.

## ? Unverifiable
- Performance numbers ("<50ms cached, <200ms reranking", "Search query <500ms", "Graph expansion +100-200ms"): no benchmarks/perf tests in `tests/test_rag.py` — claims are aspirational.
- "10-20% relevance improvement" for reranking (`README.md:114`) — no measurement code.
- "rag_unification_verified" report dated; can't independently verify the line numbers cited in that doc — they no longer match (e.g., `agent.py:697` for `ingest_document` is actually `agent.py:597`).

## Stale / drift
- `docs/tools/README.md` header: **Version 0.7.0**, "Last Updated: December 2, 2025", lists 6 tools. Reality: `manifests/devforge.json` is **0.8.0** with 7 tools (`generate_data, github_operation, refine_prompt, generate_cheatsheet, generate_changelog, analyze_ci_failure, scaffold_repository`). `retrieve_docs` is in the README but **not in the manifest or `SUPPORTED_TOOLS`**.
- `retrieve_docs.md` header: "Version 15.4", "Phase 15 Multi-Tenancy" — consistent with `rag.py`. But coexists with the v0.7.0 README index → user-facing version drift.
- `rag_unification_verified.md` line numbers (e.g., `agent.py:697`, `tools.py:338`, `agent.py:775`) do not match current source.
- `rag_architecture.md:543` lists `VECTOR_BACKEND=chroma  # or qdrant` — should be `chroma | postgres`.
- `rag_architecture.md:467` calls pgvector "Phase 10.2" — pgvector is now production default.
- Tests in `test_rag.py` still test `get_vector_store_qdrant` (`test_rag.py:175`) but no test for `PgVectorStore` — test suite does not cover the production default backend.

## Recommended doc changes
1. Either register `retrieve_docs` in `SUPPORTED_TOOLS`/`manifests/devforge.json`, OR rewrite docs to drop gateway-tool framing — the canonical retrieval entry point is `POST /api/v1/rag/chunk/semanticSearchForChat`.
2. Replace "ChromaDB + Qdrant" with "ChromaDB + Postgres (pgvector)" everywhere; mark Qdrant as legacy/optional. Update `VECTOR_BACKEND` enum docs to match `config.py:130`.
3. Document the auth model per endpoint: tenant JWT for `/api/v1/rag/*`, no auth for `/api/rag/ingest-async` (or add it), API key for gateway.
4. Fix `RAG_SCORE_THRESHOLD` default to `0.0`; add `RERANK_SCORE_THRESHOLD=0.3`.
5. Remove or implement the `include_context` parameter — currently misleading.
6. Bump `docs/tools/README.md` to 0.8.0, update tool list to match the manifest, remove the December 2025 timestamp.
7. Update `rag_architecture.md` config block, layer diagram, and the "Phase 10.2" pgvector reference.
8. Drop `GET /rag/retrieve` from `rag_integration_flow.md`; align Phase-12A endpoint paths under `/api/rag/...`.
9. Reconcile single-vs-multi-tenant QID format note between `rag_architecture.md` and `rag_integration_flow.md`.
10. Refresh line numbers in `rag_unification_verified.md` or remove them.
