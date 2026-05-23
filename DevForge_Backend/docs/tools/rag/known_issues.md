# RAG Known Issues

## Issue #1 — Celery graph cache key mismatch
**Status:** ✅ Fixed 2026-05-23  
**File:** `src/workers/tasks/rag_tasks.py`  
**Root cause:** Celery used `rag_graph:{collection}` but the agent reads `rag_graph:v2:{collection}`. Cache was never hit.  
**Fix:** Updated Celery cache key to `rag_graph:v2:{collection_name}`.

---

## Issue #2 — Orphaned pgvector chunks after file deletion
**Status:** ✅ Resolved operationally 2026-05-23  
**Root cause:** File deletions cleared Redis metadata but left pgvector rows. Orphan filter in `routers/rag.py` (lines 284–293) drops these at query time.  
**Operational fix:** Ran `scripts/purge_orphans.py --delete` to remove 1,282 orphaned chunks across all tenants. Procedure documented in `RAG_DEBUGGING.md`.

---

## Issue #3 — BM25 index stale after file deletion
**Status:** Open  
**Root cause:** BM25 index is in-memory per Gunicorn worker, built on agent startup. File deletions don't invalidate it. Workers must be restarted to reflect deletions.  
**Workaround:** Restart API container after bulk deletions, or call `POST /api/rag/bm25/rebuild` (affects one worker only).

---

## Issue #4 — POST /api/rag/ingest-async unprotected
**Status:** ✅ Already fixed (stale docs)  
**Root cause:** `JWTAuthMiddleware` in `src/core/middleware.py` has `PROTECTED_EXACT = {"/api/rag/ingest-async"}` — endpoint IS JWT-protected. No code change needed.

---

## Issue #5 — TypeScript AST chunking fallback for all exported classes
**Status:** ✅ Fixed 2026-05-24  
**File:** `src/agents/rag/chunking/code_chunker.py`  
**Root cause:** Two grammar mismatches in the tree-sitter query for TypeScript:
1. TypeScript exports wrap declarations: `export class Foo {}` → `export_statement > class_declaration` (not bare `class_declaration`)
2. TypeScript class names use `type_identifier` node type (not `identifier`)

Result: 0 entities extracted for every TypeScript file → `ast_fallback=True` on all TS chunks → no graph edges for TypeScript code.

**Fix:** Updated the TS tree-sitter query to handle both exported and non-exported forms, and use `type_identifier`:
```python
query_str = """
(function_declaration name: (identifier) @func_name) @function
(class_declaration name: (type_identifier) @class_name) @class
(export_statement (function_declaration name: (identifier) @func_name) @function)
(export_statement (class_declaration name: (type_identifier) @class_name) @class)
"""
```
**Robustness gap exposed:** No per-language unit test for chunk metadata; `ast_fallback=True` only raises a WARNING — upload shows `chunkingStatus: "success"` regardless. See Issue #7 for follow-up.

---

## Issue #6 — Cross-file graph expansion returns 0
**Status:** ✅ Fixed 2026-05-24  
**Files:** `src/agents/rag/graph/code_graph.py`, `src/agents/rag/agent.py`  
**Root cause:** `add_node` always resolves call targets to the same source file:
```python
called_qid = f"{tenant_id}::{source}::{call_name}"  # always same source file
```
When `UserRepository` (user-repository.ts) calls `CacheStore` (imported from cache.ts), the graph created `user-repository.ts::UserRepository → user-repository.ts::CacheStore`. But `user-repository.ts::CacheStore` has no pgvector entry (CacheStore is defined in cache.ts), so `get_chunk_by_qualified_id` returned `None` and the expansion was silently skipped.

**Fix:** Added `CodeGraph.resolve_cross_file_edges()` — a post-processing step called after all chunks are loaded (in `agent.py::init_graph`). It:
1. Detects "dangling" nodes: exist in the adjacency list but have no chunk metadata
2. For each dangling node, looks for a real node with the same entity name in a different file
3. If exactly 1 match (unambiguous): rewires all incoming edges to the real node
4. If 0 or >1 matches: skips (avoids false positives on overloaded names)
5. Is idempotent — safe to call twice (second call finds nothing to rewire)

Called in both code paths of `init_graph`: after cold-start build (before Redis caching) and after cache load (to clean up dangling edges re-created by `from_dict`).

**Tests:** `tests/test_rag_graph_expansion.py` — 4 new tests covering single match rewire, ambiguous skip, no-op when clean, idempotency.

---

## Issue #7 — No validation that AST chunking succeeded
**Status:** Open  
**Root cause:** The file upload response returns `chunkingStatus: "success"` even when all chunks have `ast_fallback=True`. The caller has no visibility into chunk quality.  
**Fix needed:** Expose `ast_fallback_count` in the file detail response (`GET /api/v1/rag/file/{id}`). Surface a warning when >50% of chunks are fallback.
