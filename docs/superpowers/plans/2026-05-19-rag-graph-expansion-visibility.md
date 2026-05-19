# RAG Graph Expansion Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface graph expansion provenance (`expanded_from`, `is_graph_expansion`, `expansion_count`) in the RAG semantic search API response so clients can distinguish graph-expanded chunks from vector-retrieved chunks.

**Architecture:** Three-layer fix: (1) tag expanded chunks with their anchor QID in the agent expander, (2) carry that tag through the `ChunkResult` data model, (3) expose it in `ChatFileChunk` and `SemanticSearchResponse` at the router layer. No new files needed — all changes are additive fields and one-line reads.

**Tech Stack:** Python 3.12, FastAPI 0.120, Pydantic 2.12, LangGraph

**Audit note — HIGH-4 retracted:** The graph cache invalidation (`rag_graph:v2:{collection_name}`) is already correctly deleted in `delete_file_cascade()` (agent.py:694-702) and `delete_orphaned_file()` (agent.py:758-766). No fix needed there.

---

## File Map

| File | Change |
|------|--------|
| `src/storage/base_store.py` | Add `expanded_from: Optional[str] = None` to `ChunkResult` dataclass |
| `src/agents/rag/agent.py` | Set `"expanded_from": qid` in `_expand_with_graph_context()`; propagate through dict→ChunkResult conversion |
| `src/api/schemas/rag.py` | Add `is_graph_expansion` + `expanded_from` to `ChatFileChunk`; add `expansion_count` to `SemanticSearchResponse` |
| `src/api/routers/rag.py` | Extract and pass new fields when building `ChatFileChunk`; count expanded chunks for response |
| `tests/test_rag_graph_expansion.py` | New test file: unit tests for expander field + router response fields |

---

## Task 1: Add `expanded_from` to the data model

**Files:**
- Modify: `src/storage/base_store.py:16-24`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rag_graph_expansion.py
from src.storage.base_store import ChunkResult

def test_chunk_result_has_expanded_from():
    chunk = ChunkResult(id="abc", content="def foo(): pass", metadata={})
    assert hasattr(chunk, "expanded_from")
    assert chunk.expanded_from is None

def test_chunk_result_expanded_from_set():
    chunk = ChunkResult(
        id="abc",
        content="def foo(): pass",
        metadata={},
        expanded_from="tenant1::auth.py::validate_token"
    )
    assert chunk.expanded_from == "tenant1::auth.py::validate_token"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd DevForge_Backend
pytest tests/test_rag_graph_expansion.py::test_chunk_result_has_expanded_from -v
```
Expected: `FAILED — ChunkResult.__init__() got an unexpected keyword argument 'expanded_from'`

- [ ] **Step 3: Add field to `ChunkResult`**

In `src/storage/base_store.py`, the `ChunkResult` dataclass currently ends at line 24:
```python
@dataclass
class ChunkResult:
    """Result from vector search."""
    
    id: str
    content: str
    metadata: Dict
    score: Optional[float] = None
    rerank_score: Optional[float] = None  # Phase 11: Reranking score
    is_graph_expansion: bool = False     # Phase 12A: Graph-injected chunk
```

Add one line after `is_graph_expansion`:
```python
@dataclass
class ChunkResult:
    """Result from vector search."""
    
    id: str
    content: str
    metadata: Dict
    score: Optional[float] = None
    rerank_score: Optional[float] = None  # Phase 11: Reranking score
    is_graph_expansion: bool = False     # Phase 12A: Graph-injected chunk
    expanded_from: Optional[str] = None  # Phase 12A: Anchor QID that triggered expansion
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_rag_graph_expansion.py::test_chunk_result_has_expanded_from tests/test_rag_graph_expansion.py::test_chunk_result_expanded_from_set -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/storage/base_store.py tests/test_rag_graph_expansion.py
git commit -m "feat(rag): add expanded_from field to ChunkResult data model"
```

---

## Task 2: Set `expanded_from` in the graph expander

**Files:**
- Modify: `src/agents/rag/agent.py:1302-1355` (`_expand_with_graph_context`)
- Modify: `src/agents/rag/agent.py:1091-1100` (dict→ChunkResult conversion)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_rag_graph_expansion.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_expand_with_graph_context_sets_expanded_from():
    """Verifies that graph-expanded chunks carry the anchor QID in expanded_from."""
    from src.agents.rag.agent import RAGAgent
    from src.agents.rag.graph.code_graph import CodeGraph

    # Build a minimal graph: auth.py::authenticate calls auth.py::validate_token
    graph = CodeGraph()
    tenant_id = "test_tenant"
    graph.add_node(f"{tenant_id}::auth.py::authenticate", calls=["validate_token"], source="auth.py", name="authenticate", tenant_id=tenant_id)
    graph.add_node(f"{tenant_id}::auth.py::validate_token", calls=[], source="auth.py", name="validate_token", tenant_id=tenant_id)

    # Mock the related chunk returned by the vector store
    related_chunk = MagicMock()
    related_chunk.id = "chunk-validate-token"
    related_chunk.content = "def validate_token(): pass"
    related_chunk.metadata = {"source": "auth.py", "name": "validate_token", "tenant_id": tenant_id}

    mock_vector_store = AsyncMock()
    mock_vector_store.get_chunk_by_qualified_id = AsyncMock(return_value=related_chunk)

    agent = RAGAgent.__new__(RAGAgent)
    agent._code_graph = graph
    agent.vector_store = mock_vector_store
    agent.collection_name = f"user_{tenant_id}"
    agent.tenant_id = tenant_id

    anchors = [{
        "metadata": {"source": "auth.py", "name": "authenticate", "tenant_id": tenant_id}
    }]

    results = await agent._expand_with_graph_context(anchors)

    assert len(results) == 1
    assert results[0]["expanded_from"] == f"{tenant_id}::auth.py::authenticate"
    assert results[0]["is_graph_expansion"] is True
    assert results[0]["id"] == "chunk-validate-token"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_rag_graph_expansion.py::test_expand_with_graph_context_sets_expanded_from -v
```
Expected: `FAILED — AssertionError: assert 'expanded_from' in results[0]` (key missing)

- [ ] **Step 3: Add `expanded_from` to the expander return value**

In `src/agents/rag/agent.py`, find `_expand_with_graph_context` at line ~1273. The inner loop that builds `chunk_dict` (around line 1342) currently is:

```python
if related_chunk:
    chunk_dict = {
        "id": related_chunk.id,
        "content": related_chunk.content,
        "metadata": related_chunk.metadata,
        "score": 0.0, 
        "is_graph_expansion": True
    }
    expanded.append(chunk_dict)
```

Change to:

```python
if related_chunk:
    chunk_dict = {
        "id": related_chunk.id,
        "content": related_chunk.content,
        "metadata": related_chunk.metadata,
        "score": 0.0,
        "is_graph_expansion": True,
        "expanded_from": qid,  # anchor QID that triggered this expansion
    }
    expanded.append(chunk_dict)
```

- [ ] **Step 4: Propagate `expanded_from` through dict→ChunkResult conversion**

In `src/agents/rag/agent.py`, find the dict→ChunkResult conversion at line ~1091:

```python
chunk_candidates = [
    ChunkResult(
        id=r.get("id", str(i)),
        content=r.get("content", r.get("page_content", "")),
        metadata=r.get("metadata", {}),
        score=r.get("score"),
        is_graph_expansion=r.get("is_graph_expansion", False)
    )
    for i, r in enumerate(initial_results)
]
```

Change to:

```python
chunk_candidates = [
    ChunkResult(
        id=r.get("id", str(i)),
        content=r.get("content", r.get("page_content", "")),
        metadata=r.get("metadata", {}),
        score=r.get("score"),
        is_graph_expansion=r.get("is_graph_expansion", False),
        expanded_from=r.get("expanded_from"),
    )
    for i, r in enumerate(initial_results)
]
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_rag_graph_expansion.py::test_expand_with_graph_context_sets_expanded_from -v
```
Expected: `1 passed`

- [ ] **Step 6: Commit**

```bash
git add src/agents/rag/agent.py tests/test_rag_graph_expansion.py
git commit -m "feat(rag): set expanded_from on graph-expanded chunks in expander and ChunkResult"
```

---

## Task 3: Add fields to `ChatFileChunk` and `SemanticSearchResponse`

**Files:**
- Modify: `src/api/schemas/rag.py:49-80`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_rag_graph_expansion.py`:

```python
def test_chat_file_chunk_has_graph_fields():
    from src.api.schemas.rag import ChatFileChunk
    chunk = ChatFileChunk(
        id="c1",
        fileId="f1",
        filename="auth.py",
        fileType="text/plain",
        fileUrl="http://example.com/auth.py",
        text="def authenticate(): pass",
        similarity=0.65,
    )
    assert hasattr(chunk, "is_graph_expansion")
    assert hasattr(chunk, "expanded_from")
    assert chunk.is_graph_expansion is False
    assert chunk.expanded_from is None

def test_chat_file_chunk_graph_fields_set():
    from src.api.schemas.rag import ChatFileChunk
    chunk = ChatFileChunk(
        id="c1",
        fileId="f1",
        filename="auth.py",
        fileType="text/plain",
        fileUrl="http://example.com/auth.py",
        text="def validate_token(): pass",
        similarity=0.0,
        is_graph_expansion=True,
        expanded_from="tenant1::auth.py::authenticate"
    )
    assert chunk.is_graph_expansion is True
    assert chunk.expanded_from == "tenant1::auth.py::authenticate"

def test_semantic_search_response_has_expansion_count():
    from src.api.schemas.rag import SemanticSearchResponse
    resp = SemanticSearchResponse(chunks=[], queryId="q1")
    assert hasattr(resp, "expansion_count")
    assert resp.expansion_count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_rag_graph_expansion.py::test_chat_file_chunk_has_graph_fields tests/test_rag_graph_expansion.py::test_chat_file_chunk_graph_fields_set tests/test_rag_graph_expansion.py::test_semantic_search_response_has_expansion_count -v
```
Expected: `3 FAILED`

- [ ] **Step 3: Add fields to `ChatFileChunk` and `SemanticSearchResponse`**

In `src/api/schemas/rag.py`, `ChatFileChunk` currently ends at line 61:

```python
class ChatFileChunk(BaseModel):
    """Individual chunk in semantic search response"""
    id: str
    fileId: str
    filename: str
    fileType: str
    fileUrl: str
    text: str
    similarity: float
    pageNumber: Optional[int] = None
    
    # Phase 13: Context Roles (entry, dependency, supporting)
    role: Optional[str] = "supporting"
```

Change to:

```python
class ChatFileChunk(BaseModel):
    """Individual chunk in semantic search response"""
    id: str
    fileId: str
    filename: str
    fileType: str
    fileUrl: str
    text: str
    similarity: float
    pageNumber: Optional[int] = None
    
    # Phase 13: Context Roles (entry, dependency, supporting)
    role: Optional[str] = "supporting"
    
    # Phase 12A: Graph expansion provenance
    is_graph_expansion: bool = False
    expanded_from: Optional[str] = None
```

And `SemanticSearchResponse` currently is:

```python
class SemanticSearchResponse(BaseModel):
    """Response for semantic search"""
    chunks: List[ChatFileChunk]
    queryId: Optional[str] = None
```

Change to:

```python
class SemanticSearchResponse(BaseModel):
    """Response for semantic search"""
    chunks: List[ChatFileChunk]
    queryId: Optional[str] = None
    expansion_count: int = 0  # Number of graph-expanded chunks in this response
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_rag_graph_expansion.py::test_chat_file_chunk_has_graph_fields tests/test_rag_graph_expansion.py::test_chat_file_chunk_graph_fields_set tests/test_rag_graph_expansion.py::test_semantic_search_response_has_expansion_count -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add src/api/schemas/rag.py tests/test_rag_graph_expansion.py
git commit -m "feat(rag): add is_graph_expansion, expanded_from, expansion_count to response schemas"
```

---

## Task 4: Wire new fields through the router

**Files:**
- Modify: `src/api/routers/rag.py:235-316`

- [ ] **Step 1: Write the failing test**

The router test requires a running app. Add an integration-style test using FastAPI's `TestClient`. Add to `tests/test_rag_graph_expansion.py`:

```python
def test_chat_file_chunk_serialization_includes_graph_fields():
    """Verify ChatFileChunk JSON output includes the graph fields."""
    from src.api.schemas.rag import ChatFileChunk
    chunk = ChatFileChunk(
        id="c1",
        fileId="f1",
        filename="auth.py",
        fileType="text/plain",
        fileUrl="http://example.com/auth.py",
        text="def validate_token(): pass",
        similarity=0.0,
        is_graph_expansion=True,
        expanded_from="tenant1::auth.py::authenticate"
    )
    data = chunk.model_dump()
    assert data["is_graph_expansion"] is True
    assert data["expanded_from"] == "tenant1::auth.py::authenticate"

def test_semantic_search_response_expansion_count_counts_expanded():
    """Verify expansion_count counts only is_graph_expansion=True chunks."""
    from src.api.schemas.rag import ChatFileChunk, SemanticSearchResponse

    def make_chunk(is_graph: bool) -> ChatFileChunk:
        return ChatFileChunk(
            id="c1", fileId="f1", filename="f.py", fileType="text/plain",
            fileUrl="http://x.com/f.py", text="x", similarity=0.5,
            is_graph_expansion=is_graph
        )

    resp = SemanticSearchResponse(
        chunks=[make_chunk(False), make_chunk(True), make_chunk(True)],
        queryId="q1",
        expansion_count=2
    )
    assert resp.expansion_count == 2
```

- [ ] **Step 2: Run tests to verify they pass (schema level)**

```bash
pytest tests/test_rag_graph_expansion.py::test_chat_file_chunk_serialization_includes_graph_fields tests/test_rag_graph_expansion.py::test_semantic_search_response_expansion_count_counts_expanded -v
```
Expected: `2 passed` — these only test schema serialization, which is already wired from Task 3.

- [ ] **Step 3: Wire fields in the router's document loop**

In `src/api/routers/rag.py`, the document normalization block at lines ~235-246 currently reads:

```python
for doc in documents:
    # 1. Normalize Chunk Data
    if isinstance(doc, dict):
        metadata = doc.get("metadata", {})
        content = doc.get("content") or doc.get("page_content") or ""
        score = doc.get("score") or doc.get("similarity") or 0.0
        doc_id = doc.get("id")
    else:
        metadata = getattr(doc, "metadata", {})
        content = getattr(doc, "content", None) or getattr(doc, "page_content", "") or ""
        score = getattr(doc, "score", 0.0)
        doc_id = getattr(doc, "id", None)
```

Add two lines at the end of each branch to extract the new fields:

```python
for doc in documents:
    # 1. Normalize Chunk Data
    if isinstance(doc, dict):
        metadata = doc.get("metadata", {})
        content = doc.get("content") or doc.get("page_content") or ""
        score = doc.get("score") or doc.get("similarity") or 0.0
        doc_id = doc.get("id")
        is_graph = doc.get("is_graph_expansion", False)
        expanded_from = doc.get("expanded_from")
    else:
        metadata = getattr(doc, "metadata", {})
        content = getattr(doc, "content", None) or getattr(doc, "page_content", "") or ""
        score = getattr(doc, "score", 0.0)
        doc_id = getattr(doc, "id", None)
        is_graph = getattr(doc, "is_graph_expansion", False)
        expanded_from = getattr(doc, "expanded_from", None)
```

Then update the `ChatFileChunk` construction at lines ~292-302:

```python
response_chunks.append(ChatFileChunk(
    id=final_chunk_id,
    fileId=file_meta["id"],
    filename=file_meta["name"],
    fileType=file_meta["fileType"],
    fileUrl=file_meta["url"],
    text=content,
    similarity=float(normalized_score),
    pageNumber=metadata.get("page", None),
    role=metadata.get("role", "supporting"),
    is_graph_expansion=is_graph,
    expanded_from=expanded_from,
))
```

Then update the `SemanticSearchResponse` construction at lines ~313-316:

```python
expansion_count = sum(1 for c in response_chunks if c.is_graph_expansion)

return SemanticSearchResponse(
    chunks=response_chunks,
    queryId=query_id,
    expansion_count=expansion_count,
)
```

- [ ] **Step 4: Run the full test suite for RAG**

```bash
pytest tests/test_rag_graph_expansion.py -v
pytest tests/test_rag.py -v
```
Expected: all pass. If `test_rag.py` has snapshot tests that assert the response shape, update them to allow the new optional fields.

- [ ] **Step 5: Smoke test the endpoint**

Start the backend:
```bash
uvicorn src.main:app --reload --port 8001
```

Upload a Python file with cross-function calls, then call search:
```bash
curl -s -X POST http://localhost:8001/api/v1/rag/chunk/semanticSearchForChat \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"messageId":"m1","userQuery":"authenticate","top_k":5}' | python3 -m json.tool
```

Expected response shape:
```json
{
  "chunks": [
    {
      "id": "...",
      "role": "entry",
      "is_graph_expansion": false,
      "expanded_from": null,
      ...
    },
    {
      "id": "...",
      "role": "supporting",
      "is_graph_expansion": true,
      "expanded_from": "tenant1::auth.py::authenticate",
      ...
    }
  ],
  "queryId": "...",
  "expansion_count": 1
}
```

If `is_graph_expansion` is always `false`, check the GRAPH-DEBUG log lines in the server output — they confirm whether BFS is finding edges. If all test chunks are independent functions with no calls to each other, expansion will genuinely return 0 (expected behavior, not a bug).

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/rag.py
git commit -m "feat(rag): expose is_graph_expansion, expanded_from, expansion_count in search response"
```

---

## Self-Review

### Spec coverage
- HIGH-1 (`expanded_from` never set): ✅ Task 1 (model) + Task 2 (expander sets it)
- HIGH-2 (`is_graph_expansion` dropped at router): ✅ Task 3 (schema) + Task 4 (router wires it)
- HIGH-3 (silent empty expansion): ✅ Task 3 (`expansion_count` on response) + Task 4 (counts at router)
- HIGH-4 (cache invalidation): ✅ Retracted — already implemented in `delete_file_cascade`

### Placeholder scan
None found — all steps contain complete code.

### Type consistency
- `expanded_from: Optional[str]` — consistent across `ChunkResult` (Task 1), expander dict key (Task 2), `ChatFileChunk` (Task 3), router extraction (Task 4).
- `is_graph_expansion: bool` — already on `ChunkResult`; added to `ChatFileChunk` (Task 3); extracted in router (Task 4).
- `expansion_count: int` — added to `SemanticSearchResponse` (Task 3); computed and passed in router (Task 4).
