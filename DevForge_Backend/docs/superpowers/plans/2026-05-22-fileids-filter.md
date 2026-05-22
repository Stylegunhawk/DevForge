# `fileIds` Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thread `fileIds` from `SemanticSearchRequest` through the full retrieval stack so that searches can be scoped to specific files.

**Architecture:** Add `file_ids: Optional[List[str]] = None` to five touch points bottom-up — cache key helper → semantic cache → both vector stores → `_vector_search()` → `retrieve_with_reranking()` → router. When `file_ids` is set, BM25 is skipped and vector search applies a metadata filter. Cache keys include a sorted `file_ids` suffix to prevent scope leakage.

**Tech Stack:** Python 3.12, FastAPI, ChromaDB 1.3.5, pgvector/asyncpg, pytest, unittest.mock

---

## File Map

| File | Change |
|---|---|
| `src/agents/rag/cache/query_normalizer.py:64` | Add `file_ids` param to `cache_key_from_query` |
| `src/agents/rag/cache/semantic_cache.py:85,162` | Add `file_ids` kwarg to `get()` and `set()` |
| `src/storage/chroma_store.py:98` | Add `file_ids` param + `where` filter to `search()` |
| `src/storage/pgvector_store.py:240` | Add `file_ids` param + SQL `ANY()` clause to `search()` |
| `src/agents/rag/agent.py:796` | Add `file_ids` to `_vector_search()`, pass to stores |
| `src/agents/rag/agent.py:837` | Add `file_ids` to `retrieve_with_reranking()`, BM25 skip, cache wiring |
| `src/api/routers/rag.py:226` | Pass `search_request.fileIds or None` to agent |
| `tests/test_rag.py` | Add 7 new tests (5 unit + 2 integration) |

---

## Task 1: Cache key — include `file_ids`

**Files:**
- Modify: `src/agents/rag/cache/query_normalizer.py:64-87`
- Test: `tests/test_rag.py`

- [ ] **Step 1: Write the failing tests**

Open `tests/test_rag.py` and append:

```python
# ── Task 1: cache_key_from_query with file_ids ──────────────────────────────

from src.agents.rag.cache.query_normalizer import cache_key_from_query

def test_cache_key_differs_with_different_file_ids():
    key_no_scope = cache_key_from_query("auth function", 5, tenant_id="t1")
    key_scoped   = cache_key_from_query("auth function", 5, tenant_id="t1", file_ids=("f_auth",))
    assert key_no_scope != key_scoped

def test_cache_key_order_independent_file_ids():
    key_a = cache_key_from_query("auth function", 5, tenant_id="t1", file_ids=("f_b", "f_a"))
    key_b = cache_key_from_query("auth function", 5, tenant_id="t1", file_ids=("f_a", "f_b"))
    assert key_a == key_b

def test_cache_key_none_file_ids_matches_no_arg():
    key_none = cache_key_from_query("auth function", 5, tenant_id="t1", file_ids=None)
    key_omit = cache_key_from_query("auth function", 5, tenant_id="t1")
    assert key_none == key_omit
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
cd DevForge_Backend
pytest tests/test_rag.py::test_cache_key_differs_with_different_file_ids tests/test_rag.py::test_cache_key_order_independent_file_ids tests/test_rag.py::test_cache_key_none_file_ids_matches_no_arg -v
```

Expected: `TypeError` — `cache_key_from_query() got an unexpected keyword argument 'file_ids'`

- [ ] **Step 3: Implement the change**

In `src/agents/rag/cache/query_normalizer.py`, replace lines 64–87:

```python
def cache_key_from_query(
    query: str,
    top_k: int,
    tenant_id: str = "default",
    file_ids: Optional[tuple] = None,
) -> str:
    """
    Generate SHA256 cache key from query + retrieval params + tenant + optional file scope.

    Args:
        query: User query string
        top_k: Number of results requested
        tenant_id: Tenant identifier
        file_ids: Optional sorted tuple of file IDs for scoped queries

    Returns:
        SHA256 hash (64 hex chars)
    """
    normalized = normalize_query(query)

    cache_input = f"{tenant_id}::{normalized}::{top_k}"
    if file_ids:
        cache_input += f"::files={'|'.join(sorted(file_ids))}"

    return hashlib.sha256(cache_input.encode('utf-8')).hexdigest()
```

Also ensure `Optional` is imported at the top of the file:
```python
from typing import Optional
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
pytest tests/test_rag.py::test_cache_key_differs_with_different_file_ids tests/test_rag.py::test_cache_key_order_independent_file_ids tests/test_rag.py::test_cache_key_none_file_ids_matches_no_arg -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/agents/rag/cache/query_normalizer.py tests/test_rag.py
git commit -m "feat(rag): add file_ids to cache_key_from_query for scoped cache isolation"
```

---

## Task 2: Semantic cache — scope `get()` and `set()` by `file_ids`

**Files:**
- Modify: `src/agents/rag/cache/semantic_cache.py:85-168`
- Test: `tests/test_rag.py`

The semantic cache uses `intent_key = f"{tenant_id}::{intent}"` as its bucket key. When `file_ids` is set, we extend the bucket key so scoped and unscoped queries never share cache entries.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rag.py`:

```python
# ── Task 2: SemanticCache scoped by file_ids ────────────────────────────────

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.rag.cache.semantic_cache import SemanticCache

@pytest.mark.asyncio
async def test_semantic_cache_scoped_miss_on_different_file_ids():
    """A cache entry stored without file_ids must not be returned for a scoped query."""
    cache = SemanticCache(similarity_threshold=0.92)

    fake_embedding = MagicMock()
    fake_embedding.similarity = MagicMock(return_value=0.99)  # would be a hit without scoping

    fake_result = {"documents": ["doc1"], "reranked": True}

    with patch.object(cache, '_embed_query', new=AsyncMock(return_value=fake_embedding)):
        # Store without file_ids
        await cache.set("auth function", "code_search", fake_result, tenant_id="t1")
        # Retrieve with file_ids — must be a MISS (different bucket)
        hit = await cache.get("auth function", "code_search", tenant_id="t1", file_ids=("f_auth",))
        assert hit is None
```

- [ ] **Step 2: Run test — verify it FAILS**

```bash
pytest tests/test_rag.py::test_semantic_cache_scoped_miss_on_different_file_ids -v
```

Expected: FAIL — `TypeError: get() got an unexpected keyword argument 'file_ids'`

- [ ] **Step 3: Implement the change**

In `src/agents/rag/cache/semantic_cache.py`, update `get()` signature (line 85):

```python
async def get(
    self,
    query: str,
    intent: str,
    tenant_id: str = "default",
    query_embedding=None,
    file_ids: Optional[tuple] = None,
) -> Optional[Dict[str, Any]]:
```

Inside `get()`, replace the `intent_key` line (line 106):

```python
scope_suffix = f"::files={'|'.join(sorted(file_ids))}" if file_ids else ""
intent_key = f"{tenant_id}::{intent}{scope_suffix}"
```

Update `set()` signature (line 162):

```python
async def set(
    self,
    query: str,
    intent: str,
    results: Dict[str, Any],
    tenant_id: str = "default",
    query_embedding=None,
    file_ids: Optional[tuple] = None,
):
```

Inside `set()`, replace the `intent_key` line (line 186):

```python
scope_suffix = f"::files={'|'.join(sorted(file_ids))}" if file_ids else ""
intent_key = f"{tenant_id}::{intent}{scope_suffix}"
```

Also add `Optional` to the imports at the top of the file if not already present:
```python
from typing import Optional, Dict, Any
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
pytest tests/test_rag.py::test_semantic_cache_scoped_miss_on_different_file_ids -v
```

Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add src/agents/rag/cache/semantic_cache.py tests/test_rag.py
git commit -m "feat(rag): scope semantic cache bucket by file_ids to prevent cross-scope hits"
```

---

## Task 3: ChromaDB store — `file_ids` metadata filter in `search()`

**Files:**
- Modify: `src/storage/chroma_store.py:98-147`
- Test: `tests/test_rag.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rag.py`:

```python
# ── Task 3: ChromaVectorStore file_ids filter ───────────────────────────────

from unittest.mock import AsyncMock, MagicMock, patch
from src.storage.chroma_store import ChromaVectorStore

@pytest.mark.asyncio
async def test_chroma_search_passes_where_filter_when_file_ids_set():
    """search() must pass where={"file_id": {"$in": [...]}} to collection.query when file_ids is set."""
    store = ChromaVectorStore.__new__(ChromaVectorStore)

    mock_collection = MagicMock()
    mock_collection.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    store._collection = mock_collection

    await store.search(
        query_embedding=[0.1, 0.2, 0.3],
        top_k=5,
        file_ids=["f_auth", "f_utils"],
    )

    call_kwargs = mock_collection.query.call_args.kwargs
    assert call_kwargs.get("where") == {"file_id": {"$in": ["f_auth", "f_utils"]}}

@pytest.mark.asyncio
async def test_chroma_search_no_where_filter_when_file_ids_none():
    """search() must NOT pass a where filter when file_ids is None."""
    store = ChromaVectorStore.__new__(ChromaVectorStore)

    mock_collection = MagicMock()
    mock_collection.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    store._collection = mock_collection

    await store.search(
        query_embedding=[0.1, 0.2, 0.3],
        top_k=5,
        file_ids=None,
    )

    call_kwargs = mock_collection.query.call_args.kwargs
    assert call_kwargs.get("where") is None
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
pytest tests/test_rag.py::test_chroma_search_passes_where_filter_when_file_ids_set tests/test_rag.py::test_chroma_search_no_where_filter_when_file_ids_none -v
```

Expected: `TypeError` — `search() got an unexpected keyword argument 'file_ids'`

- [ ] **Step 3: Implement the change**

In `src/storage/chroma_store.py`, replace the `search()` method (lines 98–147):

```python
async def search(
    self,
    query_embedding: List[float],
    top_k: int = 5,
    score_threshold: float = 0.0,
    file_ids: Optional[List[str]] = None,
) -> List[ChunkResult]:
    """
    Search for similar chunks in ChromaDB.
    When file_ids is set, restricts results to those matching any of the given file IDs.
    """
    where = {"file_id": {"$in": file_ids}} if file_ids else None

    results = await asyncio.to_thread(
        self._collection.query,
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    chunk_results = []

    if not results or not results["ids"]:
        return []

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for i in range(len(ids)):
        chunk_results.append(ChunkResult(
            id=ids[i],
            content=documents[i],
            metadata=metadatas[i] or {},
            score=distances[i],
        ))

    return chunk_results
```

Also ensure `Optional` is imported at the top of the file:
```python
from typing import Optional, List
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
pytest tests/test_rag.py::test_chroma_search_passes_where_filter_when_file_ids_set tests/test_rag.py::test_chroma_search_no_where_filter_when_file_ids_none -v
```

Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/storage/chroma_store.py tests/test_rag.py
git commit -m "feat(rag): add file_ids metadata filter to ChromaVectorStore.search()"
```

---

## Task 4: pgvector store — `file_ids` SQL filter in `search()`

**Files:**
- Modify: `src/storage/pgvector_store.py:240-290`
- Test: `tests/test_rag.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rag.py`:

```python
# ── Task 4: PgVectorStore file_ids filter ──────────────────────────────────

from unittest.mock import AsyncMock, MagicMock, patch, call
from src.storage.pgvector_store import PgVectorStore

@pytest.mark.asyncio
async def test_pgvector_search_includes_file_id_any_clause_when_file_ids_set():
    """search() SQL must contain ANY($n) and bind file_ids when file_ids is provided."""
    store = PgVectorStore.__new__(PgVectorStore)
    store.table_name = "rag_chunks"
    store.collection_name = "user_t1"

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    store._get_conn = AsyncMock(return_value=mock_conn)

    await store.search(
        query_embedding=[0.1, 0.2],
        top_k=5,
        tenant_id="t1",
        collection_name="user_t1",
        file_ids=["f_auth"],
    )

    assert mock_conn.fetch.called
    sql_arg = mock_conn.fetch.call_args.args[0]
    assert "ANY(" in sql_arg
    # file_ids list should be among the bind params
    bind_params = mock_conn.fetch.call_args.args[1:]
    assert ["f_auth"] in bind_params
```

- [ ] **Step 2: Run test — verify it FAILS**

```bash
pytest tests/test_rag.py::test_pgvector_search_includes_file_id_any_clause_when_file_ids_set -v
```

Expected: `TypeError` — `search() got an unexpected keyword argument 'file_ids'`

- [ ] **Step 3: Implement the change**

In `src/storage/pgvector_store.py`, replace the `search()` method (lines 240–290):

```python
async def search(
    self,
    query_embedding: List[float],
    top_k: int = 5,
    score_threshold: float = 0.0,
    tenant_id: str = "default",
    collection_name: Optional[str] = None,
    file_ids: Optional[List[str]] = None,
) -> List[ChunkResult]:
    """Search for similar chunks using Cosine Distance with tenant filtering.
    When file_ids is set, restricts results to those matching any of the given file IDs.
    """
    conn = await self._get_conn()
    try:
        collection = collection_name or self.collection_name

        if file_ids:
            query = f"""
                SELECT chunk_id, content, metadata, 1 - (embedding <=> $1) as similarity
                FROM {self.table_name}
                WHERE tenant_id = $2
                  AND collection_name = $3
                  AND metadata->>'file_id' = ANY($4)
                ORDER BY embedding <=> $1
                LIMIT $5;
            """
            bind_params = (query_embedding, tenant_id, collection, file_ids, top_k)
        else:
            query = f"""
                SELECT chunk_id, content, metadata, 1 - (embedding <=> $1) as similarity
                FROM {self.table_name}
                WHERE tenant_id = $2
                  AND collection_name = $3
                ORDER BY embedding <=> $1
                LIMIT $4;
            """
            bind_params = (query_embedding, tenant_id, collection, top_k)

        logger.info(
            f"PgVector search: tenant={tenant_id}, collection={collection}, "
            f"top_k={top_k}, file_ids={file_ids}"
        )

        rows = await conn.fetch(query, *bind_params)

        logger.info(f"PgVector rows found: {len(rows)}")

        results = []
        for row in rows:
            metadata = json.loads(row["metadata"])
            metadata = self._ensure_list_types(metadata)
            logger.info(
                f"[RETRIEVE_DEBUG] After pg_vector retrieval: "
                f"type(metadata.get('calls'))={type(metadata.get('calls'))}, "
                f"calls={metadata.get('calls')}"
            )
            results.append(ChunkResult(
                id=row["chunk_id"],
                content=row["content"],
                metadata=metadata,
                score=float(row["similarity"]),
            ))

        return results

    finally:
        await conn.close()
```

- [ ] **Step 4: Run test — verify it PASSES**

```bash
pytest tests/test_rag.py::test_pgvector_search_includes_file_id_any_clause_when_file_ids_set -v
```

Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add src/storage/pgvector_store.py tests/test_rag.py
git commit -m "feat(rag): add file_ids ANY() SQL filter to PgVectorStore.search()"
```

---

## Task 5: Agent — thread `file_ids` through `_vector_search()`

**Files:**
- Modify: `src/agents/rag/agent.py:796-833`
- Test: `tests/test_rag.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rag.py`:

```python
# ── Task 5: _vector_search passes file_ids to store ────────────────────────

from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.rag.agent import RAGAgent

@pytest.mark.asyncio
async def test_vector_search_passes_file_ids_to_chroma_store():
    """_vector_search(file_ids=...) must call vector_store.search with file_ids kwarg."""
    agent = RAGAgent.__new__(RAGAgent)
    agent.backend = "chroma"
    agent.collection_name = "user_t1"
    agent.tenant_id = "t1"

    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[])
    mock_store.embeddings = MagicMock()
    mock_store.embeddings.embed_query = MagicMock(return_value=[0.1, 0.2])
    agent.vector_store = mock_store

    with patch("asyncio.to_thread", new=AsyncMock(return_value=[0.1, 0.2])):
        await agent._vector_search("auth function", top_k=5, file_ids=["f_auth"])

    mock_store.search.assert_called_once()
    call_kwargs = mock_store.search.call_args.kwargs
    assert call_kwargs.get("file_ids") == ["f_auth"]
```

- [ ] **Step 2: Run test — verify it FAILS**

```bash
pytest tests/test_rag.py::test_vector_search_passes_file_ids_to_chroma_store -v
```

Expected: FAIL — `TypeError: _vector_search() got an unexpected keyword argument 'file_ids'`

- [ ] **Step 3: Implement the change**

In `src/agents/rag/agent.py`, replace `_vector_search()` (lines 796–833):

```python
async def _vector_search(
    self,
    query: str,
    top_k: int,
    score_threshold: float = 0.0,
    file_ids: Optional[List[str]] = None,
) -> List:
    """
    Vector-only search using configured vector store.

    Args:
        query: Search query
        top_k: Number of results
        score_threshold: Minimum similarity score (default: 0.0)
        file_ids: Optional list of file IDs to scope the search
    """
    query_embedding = await asyncio.to_thread(
        self.vector_store.embeddings.embed_query,
        query
    )

    if self.backend == "postgres":
        tenant_id = getattr(self, 'tenant_id', 'default')
        results = await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            score_threshold=score_threshold,
            tenant_id=tenant_id,
            collection_name=self.collection_name,
            file_ids=file_ids,
        )
    else:
        results = await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            score_threshold=score_threshold,
            file_ids=file_ids,
        )

    return results
```

- [ ] **Step 4: Run test — verify it PASSES**

```bash
pytest tests/test_rag.py::test_vector_search_passes_file_ids_to_chroma_store -v
```

Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add src/agents/rag/agent.py tests/test_rag.py
git commit -m "feat(rag): thread file_ids through _vector_search() to vector store backends"
```

---

## Task 6: Agent — `retrieve_with_reranking()`: BM25 skip + cache keying + all call sites

**Files:**
- Modify: `src/agents/rag/agent.py:837` (signature), `:960-1002` (search block), `:944-946` `:1066-1082` `:1176-1182` `:1209-1210` (cache call sites)
- Test: `tests/test_rag.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_rag.py`:

```python
# ── Task 6: retrieve_with_reranking file_ids wiring ────────────────────────

@pytest.mark.asyncio
async def test_retrieve_with_reranking_skips_bm25_when_file_ids_set():
    """When file_ids is set, the hybrid retriever must NOT be called."""
    agent = RAGAgent.__new__(RAGAgent)
    agent.backend = "chroma"
    agent.collection_name = "user_t1"
    agent.tenant_id = "t1"
    agent.reranker = None
    agent._code_graph = None
    agent._intent_classifier = None
    agent._query_expander = None
    agent._query_cache = None
    agent._semantic_cache = None
    agent._context_shaper = MagicMock()
    agent._context_shaper.shape_context = MagicMock(side_effect=lambda x: x)

    mock_hybrid = AsyncMock()
    agent._hybrid_retriever = mock_hybrid
    agent._bm25_index = MagicMock()
    agent._bm25_index.is_ready = MagicMock(return_value=True)

    agent._vector_search = AsyncMock(return_value=[])

    await agent.retrieve_with_reranking(
        query="auth function",
        top_k=5,
        file_ids=["f_auth"],
    )

    mock_hybrid.search.assert_not_called()
    agent._vector_search.assert_called_once()
    call_kwargs = agent._vector_search.call_args.kwargs
    assert call_kwargs.get("file_ids") == ["f_auth"]


@pytest.mark.asyncio
async def test_retrieve_with_reranking_empty_file_ids_uses_hybrid():
    """When file_ids=[], hybrid search must run normally (empty list = no scope)."""
    agent = RAGAgent.__new__(RAGAgent)
    agent.backend = "chroma"
    agent.collection_name = "user_t1"
    agent.tenant_id = "t1"
    agent.reranker = None
    agent._code_graph = None
    agent._intent_classifier = None
    agent._query_expander = None
    agent._query_cache = None
    agent._semantic_cache = None
    agent._context_shaper = MagicMock()
    agent._context_shaper.shape_context = MagicMock(side_effect=lambda x: x)
    agent._bm25_index = MagicMock()
    agent._bm25_index.is_ready = MagicMock(return_value=True)

    mock_hybrid = MagicMock()
    mock_hybrid.search = AsyncMock(return_value=[])
    agent._hybrid_retriever = mock_hybrid

    from src.core.config import settings
    with patch.object(settings, "ENABLE_HYBRID_SEARCH", True), \
         patch.object(settings, "ENABLE_RERANKING", False), \
         patch.object(settings, "ENABLE_CODE_GRAPH", False), \
         patch.object(settings, "ENABLE_INTENT_CLASSIFICATION", False), \
         patch.object(settings, "ENABLE_QUERY_EXPANSION", False), \
         patch.object(settings, "ENABLE_SEMANTIC_CACHE", False), \
         patch.object(settings, "ENABLE_QUERY_CACHE", False):
        await agent.retrieve_with_reranking(
            query="auth function",
            top_k=5,
            file_ids=[],   # empty → treat as None → hybrid runs
        )

    mock_hybrid.search.assert_called_once()
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
pytest tests/test_rag.py::test_retrieve_with_reranking_skips_bm25_when_file_ids_set tests/test_rag.py::test_retrieve_with_reranking_empty_file_ids_uses_hybrid -v
```

Expected: `TypeError` — `retrieve_with_reranking() got an unexpected keyword argument 'file_ids'`

- [ ] **Step 3: Update the signature**

In `src/agents/rag/agent.py`, update the `retrieve_with_reranking` signature at line 837:

```python
async def retrieve_with_reranking(
    self,
    query: str,
    top_k: int = 5,
    use_reranking: bool = True,
    use_cache: bool = True,
    use_hybrid: bool = True,
    score_threshold: float = 0.0,
    file_ids: Optional[List[str]] = None,
) -> dict:
```

- [ ] **Step 4: Normalise `file_ids` and add BM25-skip branch**

Directly after the `query = str(query) if query else ""` line (≈ line 868), add:

```python
# Normalise: empty list → None (no scope)
file_ids = file_ids if file_ids else None
# When scoping to specific files, BM25 has no per-file awareness — use vector-only
effective_use_hybrid = use_hybrid and not file_ids
```

In the search block (lines 960–1002), replace every reference to `use_hybrid` with `effective_use_hybrid`:

```python
# Phase 12A Step 4: Multi-Query Retrieval + Fusion (for expanded queries)
initial_top_k = settings.VECTOR_SEARCH_CANDIDATES if (use_reranking and settings.ENABLE_RERANKING) else top_k

if len(expanded_queries) > 1:
    from src.agents.rag.expansion import ResultFusion
    fusion = ResultFusion()
    all_results = []
    for eq in expanded_queries:
        eq_results = await self._vector_search(eq, initial_top_k, score_threshold, file_ids=file_ids)
        all_results.append(eq_results)
    initial_results = fusion.fuse(all_results, top_k=initial_top_k)
    logger.info(f"[PHASE 12A] Fused {len(expanded_queries)} result sets → {len(initial_results)} docs")

elif effective_use_hybrid and self._hybrid_retriever and settings.ENABLE_HYBRID_SEARCH:
    if not self._bm25_index.is_ready():
        logger.warning("BM25 not ready, initializing...")
        await self.init_bm25()
    if self._hybrid_retriever:
        try:
            initial_results = await self._hybrid_retriever.search(
                query, top_k=initial_top_k, alpha=settings.HYBRID_ALPHA
            )
            logger.debug(f"Hybrid search returned {len(initial_results)} results")
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}, falling back to vector-only")
            initial_results = await self._vector_search(query, initial_top_k, score_threshold, file_ids=file_ids)
    else:
        initial_results = await self._vector_search(query, initial_top_k, score_threshold, file_ids=file_ids)
else:
    initial_results = await self._vector_search(query, initial_top_k, score_threshold, file_ids=file_ids)
```

- [ ] **Step 5: Update all cache call sites**

There are **seven** cache call sites in `retrieve_with_reranking`. Update each one to include `file_ids`:

**Exact-match cache key (line ≈944):**
```python
cache_key = cache_key_from_query(
    query, top_k,
    tenant_id=getattr(self, 'tenant_id', 'default'),
    file_ids=tuple(sorted(file_ids)) if file_ids else None,
)
```

**Semantic cache get (line ≈899):**
```python
cached_result = await self._semantic_cache.get(
    query, intent,
    tenant_id=getattr(self, 'tenant_id', 'default'),
    file_ids=tuple(sorted(file_ids)) if file_ids else None,
)
```

**Exact-match cache set — first occurrence (line ≈1067):**
```python
await self._query_cache.set(
    cache_key_from_query(
        query, top_k,
        tenant_id=getattr(self, 'tenant_id', 'default'),
        file_ids=tuple(sorted(file_ids)) if file_ids else None,
    ),
    result,
)
```

**Semantic cache set — first occurrence (line ≈1072):**
```python
await self._semantic_cache.set(
    query, intent, result,
    tenant_id=getattr(self, 'tenant_id', 'default'),
    file_ids=tuple(sorted(file_ids)) if file_ids else None,
)
```

**Exact-match cache set — second occurrence (line ≈1177):**
Same replacement as first occurrence above.

**Semantic cache set — second occurrence (line ≈1182):**
Same replacement as first occurrence above.

**Exact-match cache set — third occurrence (line ≈1210):**
Same replacement as first occurrence above.

- [ ] **Step 6: Run tests — verify they PASS**

```bash
pytest tests/test_rag.py::test_retrieve_with_reranking_skips_bm25_when_file_ids_set tests/test_rag.py::test_retrieve_with_reranking_empty_file_ids_uses_hybrid -v
```

Expected: 2 PASSED

- [ ] **Step 7: Run all existing RAG tests — verify nothing regressed**

```bash
pytest tests/test_rag.py -v
```

Expected: all previously passing tests still PASS

- [ ] **Step 8: Commit**

```bash
git add src/agents/rag/agent.py tests/test_rag.py
git commit -m "feat(rag): add file_ids to retrieve_with_reranking — BM25 skip + scoped cache keys"
```

---

## Task 7: Router — pass `fileIds` to agent + integration tests

**Files:**
- Modify: `src/api/routers/rag.py:226-229`
- Test: `tests/test_rag.py`

- [ ] **Step 1: Write the failing integration tests**

Append to `tests/test_rag.py`:

```python
# ── Task 7: Router integration ─────────────────────────────────────────────

from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_router_passes_fileids_to_agent(monkeypatch):
    """POST semanticSearchForChat with fileIds must call retrieve_with_reranking(file_ids=[...])."""
    from src.main import app

    mock_agent = MagicMock()
    mock_agent.retrieve_with_reranking = AsyncMock(return_value={"documents": []})

    captured = {}

    async def mock_retrieve(**kwargs):
        captured.update(kwargs)
        return {"documents": []}

    mock_agent.retrieve_with_reranking = mock_retrieve

    with patch("src.api.routers.rag.get_rag_agent", return_value=mock_agent), \
         patch("src.api.routers.rag.redis_store") as mock_redis:
        mock_redis.get_file_metadata = AsyncMock(return_value=None)
        mock_redis.save_query_metadata = AsyncMock()

        client = TestClient(app)
        response = client.post(
            "/api/v1/rag/chunk/semanticSearchForChat",
            json={
                "messageId": "msg_test",
                "userQuery": "authenticate function",
                "fileIds": ["f_auth"],
            },
            headers={"Authorization": "Bearer test_token"},
        )

    assert captured.get("file_ids") == ["f_auth"]


@pytest.mark.asyncio
async def test_router_passes_none_when_fileids_empty(monkeypatch):
    """POST semanticSearchForChat with fileIds=[] must call retrieve_with_reranking(file_ids=None)."""
    from src.main import app

    captured = {}

    async def mock_retrieve(**kwargs):
        captured.update(kwargs)
        return {"documents": []}

    mock_agent = MagicMock()
    mock_agent.retrieve_with_reranking = mock_retrieve

    with patch("src.api.routers.rag.get_rag_agent", return_value=mock_agent), \
         patch("src.api.routers.rag.redis_store") as mock_redis:
        mock_redis.get_file_metadata = AsyncMock(return_value=None)
        mock_redis.save_query_metadata = AsyncMock()

        client = TestClient(app)
        client.post(
            "/api/v1/rag/chunk/semanticSearchForChat",
            json={
                "messageId": "msg_test",
                "userQuery": "authenticate function",
                "fileIds": [],
            },
            headers={"Authorization": "Bearer test_token"},
        )

    assert captured.get("file_ids") is None
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
pytest tests/test_rag.py::test_router_passes_fileids_to_agent tests/test_rag.py::test_router_passes_none_when_fileids_empty -v
```

Expected: FAIL — `retrieve_with_reranking` not called with `file_ids` kwarg

- [ ] **Step 3: Implement the router change**

In `src/api/routers/rag.py`, replace lines 226–229:

```python
# Before
result = await agent.retrieve_with_reranking(
    query=query,
    top_k=search_request.top_k,
    use_reranking=True,
)

# After
result = await agent.retrieve_with_reranking(
    query=query,
    top_k=search_request.top_k,
    use_reranking=True,
    file_ids=search_request.fileIds or None,
)
```

- [ ] **Step 4: Run integration tests — verify they PASS**

```bash
pytest tests/test_rag.py::test_router_passes_fileids_to_agent tests/test_rag.py::test_router_passes_none_when_fileids_empty -v
```

Expected: 2 PASSED

- [ ] **Step 5: Run the full test suite — verify no regressions**

```bash
pytest tests/ -v
```

Expected: all 90+ existing tests PASS, plus the 7 new tests

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/rag.py tests/test_rag.py
git commit -m "feat(rag): wire fileIds from SemanticSearchRequest through to retrieve_with_reranking"
```

---

## Final Verification

- [ ] **Smoke test with curl** (requires running stack: `docker compose --profile rag up -d`)

```bash
# Get a tenant JWT first (replace with a valid token from your dev setup)
TOKEN="<tenant_jwt>"

# Upload a test file
curl -X POST "http://localhost:8001/api/v1/rag/file/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@DevForge_Backend/tests/fixtures/auth.py"
# Note the returned file id, e.g. "f_auth_id"

# Wait for finishEmbedding: true
curl "http://localhost:8001/api/v1/rag/file/<f_auth_id>" \
  -H "Authorization: Bearer $TOKEN"

# Scoped search — should only return chunks from auth.py
curl -X POST "http://localhost:8001/api/v1/rag/chunk/semanticSearchForChat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messageId":"smoke1","userQuery":"authenticate function","fileIds":["<f_auth_id>"],"top_k":5}'

# Verify: every chunk in response has metadata.file_id == "<f_auth_id>"
```

- [ ] **All 7 new tests pass, all pre-existing tests pass**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: `X passed` with no failures, where X ≥ original count + 7

---

## Acceptance Criteria Checklist

- [ ] AC1: `fileIds=["f_auth"]` → only chunks with `file_id="f_auth"` returned
- [ ] AC2: `fileIds=[]` → full-collection search, hybrid enabled
- [ ] AC3: Graph expansion may return chunks from outside `fileIds` (no constraint added)
- [ ] AC4: All 90+ existing RAG tests pass
- [ ] AC5: Chroma and pgvector both apply the filter (unit tests verify each store)
- [ ] AC6: Same query + different `fileIds` → different cache entries; same `fileIds` different order → same cache entry
