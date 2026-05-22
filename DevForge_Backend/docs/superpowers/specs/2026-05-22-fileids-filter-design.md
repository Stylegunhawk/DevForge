# `fileIds` Filter — Backend Fix Design Spec

**Date:** 2026-05-22
**Branch:** `rag_resolve`
**Author:** Sid (with Claude)
**Status:** Approved — awaiting implementation plan

---

## 1. Problem

`SemanticSearchRequest.fileIds` is received by the router but silently ignored. It is never passed to `agent.retrieve_with_reranking()`, which has no `file_ids` parameter. Both vector store `search()` methods also have no file filter. Search always runs across the full tenant collection regardless of what `fileIds` the caller provides.

This breaks the frontend agentic RAG spec's core improvement: scoping retrieval to a specific file when the user names one (e.g. *"give me the authenticate function from auth.py"*).

---

## 2. Scope

Backend only. Five files changed (`rag.py`, `agent.py`, `chroma_store.py`, `pgvector_store.py`, cache helpers), one new parameter threaded through each, no new endpoints, no schema changes. The frontend spec (`rag_resolve` branch, agentic RAG redesign) depends on this fix.

---

## 3. Architecture

```
Router (rag.py)
  search_request.fileIds → agent.retrieve_with_reranking(file_ids=...)
        │
        ▼
Agent (agent.py: retrieve_with_reranking)
  file_ids present → skip BM25, call _vector_search(file_ids=...)
        │
        ▼
Agent (agent.py: _vector_search)
  passes file_ids → vector_store.search(file_ids=...)
        │
        ├─ ChromaVectorStore.search()
        │    where={"file_id": {"$in": file_ids}}
        │
        └─ PgVectorStore.search()
             WHERE metadata->>'file_id' = ANY($n)
```

Graph expansion, reranking, context shaper, query expansion — all untouched. The filter applies only at the vector retrieval step.

---

## 4. Design Decisions

### 4.1 BM25 behaviour when `file_ids` is set

When `file_ids` is provided, `use_hybrid` is forced to `False` for that call. BM25 runs on the full collection index with no per-file awareness; running it and post-filtering is unreliable when the user has many files (most hits would be from other files, yielding near-zero useful BM25 results). Vector-only with metadata filter is the correct path.

When `file_ids` is `None` or `[]`, hybrid search proceeds normally — no change to existing behaviour.

### 4.2 Empty list treated as no filter

`fileIds=[]` is normalised to `None` at the router before being passed to the agent. An empty list means "no scope specified" — full-collection search, hybrid enabled.

### 4.3 Graph expansion is NOT constrained to `file_ids`

`file_ids` scopes the **initial retrieval anchors** only. Graph expansion then follows call/import edges to related chunks in other files. This is intentional: a function in `auth.py` that calls a helper in `utils.py` should surface the helper. The user's intent is *start here*, not *only here*.

### 4.4 Cache key includes `file_ids`

Both the exact-match cache and the semantic cache key must include `file_ids` to prevent a scoped query from returning a cached result from a full-collection search (or vice versa).

Cache key construction: `sorted(file_ids)` tuple appended to the existing `(query, top_k, tenant_id)` key. Sorted to make key order-independent.

---

## 5. Changes

### 5.1 `src/api/routers/rag.py`

```python
# lines 224-229 — before
result = await agent.retrieve_with_reranking(
    query=query,
    top_k=search_request.top_k,
    use_reranking=True,
)

# after
result = await agent.retrieve_with_reranking(
    query=query,
    top_k=search_request.top_k,
    use_reranking=True,
    file_ids=search_request.fileIds or None,
)
```

### 5.2 `src/agents/rag/agent.py` — `retrieve_with_reranking()`

New parameter:
```python
async def retrieve_with_reranking(
    self,
    query: str,
    top_k: int = 5,
    use_reranking: bool = True,
    use_cache: bool = True,
    use_hybrid: bool = True,
    score_threshold: float = 0.0,
    file_ids: Optional[List[str]] = None,   # NEW
) -> dict:
```

Branch logic — add before the hybrid/vector search block:
```python
# When file_ids scoping is active, skip BM25 (no per-file awareness)
effective_use_hybrid = use_hybrid and not file_ids
```

Use `effective_use_hybrid` in place of `use_hybrid` for the hybrid branch decision. Pass `file_ids` to `_vector_search()`.

Cache key — update both cache call sites:
```python
cache_key = cache_key_from_query(
    query, top_k,
    tenant_id=self.tenant_id,
    file_ids=tuple(sorted(file_ids)) if file_ids else None,
)
```

Semantic cache — add `file_ids` kwarg to `get()` and `set()` calls:
```python
cached = await self._semantic_cache.get(
    query, intent,
    tenant_id=self.tenant_id,
    file_ids=tuple(sorted(file_ids)) if file_ids else None,
)
```

### 5.3 `src/agents/rag/agent.py` — `_vector_search()`

New parameter:
```python
async def _vector_search(
    self,
    query: str,
    top_k: int,
    score_threshold: float = 0.0,
    file_ids: Optional[List[str]] = None,   # NEW
) -> List[ChunkResult]:
```

Pass `file_ids` through to `self.vector_store.search(...)`.

### 5.4 `src/storage/chroma_store.py` — `search()`

New parameter and `where` construction:
```python
async def search(
    self,
    query_embedding: List[float],
    top_k: int = 5,
    score_threshold: float = 0.0,
    file_ids: Optional[List[str]] = None,   # NEW
) -> List[ChunkResult]:
    where = {"file_id": {"$in": file_ids}} if file_ids else None
    results = self._collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,          # None → no filter (existing behaviour)
        include=["documents", "metadatas", "distances"],
    )
```

### 5.5 `src/storage/pgvector_store.py` — `search()`

New parameter and SQL clause:
```python
async def search(
    self,
    query_embedding: List[float],
    top_k: int = 5,
    score_threshold: float = 0.0,
    tenant_id: str = "default",
    collection_name: Optional[str] = None,
    file_ids: Optional[List[str]] = None,   # NEW
) -> List[ChunkResult]:
```

Append to WHERE clause when `file_ids` is set:
```sql
AND metadata->>'file_id' = ANY($n)
```

Pass `file_ids` as a bind parameter. No change when `file_ids` is `None`.

### 5.6 Cache helpers (`src/agents/rag/cache/`)

`cache_key_from_query` needs to accept and incorporate `file_ids`:
```python
def cache_key_from_query(
    query: str,
    top_k: int,
    tenant_id: str = "default",
    file_ids: Optional[tuple] = None,
) -> str:
```

`SemanticCache.get()` and `SemanticCache.set()` need to accept `file_ids` kwarg and include it in their internal key construction.

---

## 6. Error Handling & Edge Cases

| Case | Behaviour |
|---|---|
| `fileIds = []` | Normalised to `None` at router. Full-collection search, hybrid runs normally. |
| All `fileIds` unknown | Vector store returns `[]`. Orphan filter (already in router) drops empty results. Response: `chunks: [], expansion_count: 0`. |
| Mix of valid and unknown `fileIds` | Filter passes all IDs; store returns only chunks that match. Unknown IDs silently absent — no error. |
| `fileIds` points at unembedded file (`finishEmbedding: false`) | Chunks not yet in vector store — returns `[]`. Frontend inventory already marks these `(processing — not searchable yet)`. |
| Single `fileId` | Works — both `$in` (Chroma) and `ANY()` (pgvector) handle single-element lists. |
| `ENABLE_HYBRID_SEARCH=false` with `file_ids` | Already on vector-only path. Filter applies normally. |
| Graph expansion after scoped retrieval | Expansion follows QID edges to chunks in *other* files. Intentional — `file_ids` scopes anchors, not the dependency graph. |
| Cache: same query, different `file_ids` | Different cache keys → separate entries. No leakage between scoped and full-collection results. |
| Cache: same `file_ids` in different order | `sorted()` makes key order-independent — same cache hit. |

---

## 7. Testing

All tests added to `tests/test_rag.py`. Existing 90+ tests must continue to pass — the new parameter defaults to `None`, preserving all current behaviour.

### Unit tests (5)

| Test | What it verifies |
|---|---|
| `test_fileids_filter_chroma` | `ChromaVectorStore.search()` called with correct `where` kwarg when `file_ids` set. |
| `test_fileids_filter_pgvector` | `PgVectorStore.search()` SQL contains `ANY($n)` clause when `file_ids` set. |
| `test_fileids_skips_bm25` | `retrieve_with_reranking(file_ids=[...])` — `_hybrid_retriever.search` call count = 0. |
| `test_fileids_empty_list_is_noop` | `file_ids=[]` identical to `file_ids=None` — hybrid runs, no WHERE filter. |
| `test_cache_key_includes_file_ids` | Same query, different `file_ids` → different keys. Different order same `file_ids` → same key. |

### Integration tests (2)

| Test | What it verifies |
|---|---|
| `test_semantic_search_fileids_scoped` | POST `semanticSearchForChat` with `fileIds=["f_auth"]` → all returned chunks have `file_id="f_auth"` in metadata. |
| `test_semantic_search_empty_fileids_is_full_search` | `fileIds=[]` returns same result count as `fileIds` omitted. |

---

## 8. Acceptance Criteria

1. POST `semanticSearchForChat` with `fileIds=["f_auth"]` returns only chunks whose `metadata.file_id == "f_auth"`.
2. POST `semanticSearchForChat` with `fileIds=[]` behaves identically to omitting `fileIds` (full-collection search, hybrid enabled).
3. Graph expansion may return chunks from files outside `fileIds` — this is correct and expected.
4. All 90+ existing RAG tests pass unchanged.
5. Both Chroma and pgvector backends apply the filter correctly (unit tests verify each store independently).
6. Cache: same query with different `fileIds` produces different cache entries; same `fileIds` in different order produces the same cache entry.

---

**End of design.**
