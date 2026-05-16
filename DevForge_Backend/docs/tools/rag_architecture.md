# DevForge RAG Architecture

**Version:** 0.8.0  
**Phase:** Phase 16 (Redis-Cached Graph Persistence). Note: phase numbering across the repo is inconsistent (sibling docs reference Phase 15.4); this doc pins to the highest active phase in `src/agents/rag/agent.py`.  
**Last Updated:** 2026-05-08  
**Status:** Production Ready - Backend Contract Frozen

This document outlines the architecture of the Retrieval-Augmented Generation (RAG) system in DevForge Backend, covering ingestion, retrieval, reranking, and query intelligence.

---

## Final RAG API Contract

To prevent regressions, the following endpoints are frozen with specific behavioral guarantees.

### 1. Common Requirements
*   **Header:** `Authorization: Bearer <tenant_jwt>` (Required) - Validated by `JWTAuthMiddleware` (`src/core/middleware.py:124-150`). The middleware reads `tenant_id` from the verified JWT payload and sets `request.state.tenant_id`, which derives the tenant-sandboxed collection (`user_{tenant_id}`). Missing or invalid tokens return `401` before the route runs.
*   **JWT Payload Contract:** Token must include a `tenant_id` claim (string).
*   **Scope:** All operations are strictly isolated to the tenant resolved from the JWT.

### 2. Endpoints

#### `POST /api/v1/rag/chunk/semanticSearchForChat`
Primary retrieval endpoint for Lobe Chat sessions.
*   **Request Schema:** `SemanticSearchRequest`
    *   `messageId`: unique UI message ID
    *   `userQuery`: the raw user string
    *   `rewriteQuery` (Optional): LLM-optimized query for better vector matching
    *   `fileIds` (Optional): whitelist of file IDs to search within
*   **Response Schema:** `SemanticSearchResponse`
*   **Guaranteed Behaviors:**
    *   **Strict Orphan Filtering:** Chunks belonging to files that have been deleted from Redis are automatically dropped.
    *   **Empty Content Filtering:** Chunks with empty or whitespace-only text are never returned.
    *   **Semantic Priority:** Results are returned in order of relevance (Rerank Logits → Sigmoid Normalized Similarity).

#### `GET /api/v1/rag/file/{fileId}`
Polling endpoint for processing status.
*   **Response Schema:** `FileStatusResponse`
*   **Guaranteed Behavior:**
    *   Returns `finishEmbedding: true` only when both chunking and embedding tasks are successful.
    *   Includes `size` (bytes) and `url` for preview.

#### `GET /api/v1/rag/files`
Batch endpoint for retrieving all files belonging to a tenant.
*   **Response Schema:** `List[FileStatusResponse]`
*   **Guaranteed Behavior:**
    *   Returns all file metadata for the tenant resolved from the `Authorization: Bearer <tenant_jwt>` header.
    *   Performs Redis SCAN to filter files by `tenant_id`.
    *   Returns empty array `[]` if tenant has no files.
    *   Full tenant isolation - no cross-tenant leakage.

#### `GET /api/v1/rag/file/{fileId}/chunks`
Sequential chunk retrieval for navigation & summarization.
*   **Response Schema:** `SemanticSearchResponse`
*   **Parameters:** `limit` (default: 5), `offset` (default: 0)
*   **Guaranteed Behavior:**
    *   **Strict Ordering:** Chunks are guaranteed to be returned in [chunk_index] order.
    *   **Persistence:** Uses existing vector store metadata for mapping.

#### `POST /api/v1/rag/file/upload`
Universal ingestion entry point.
*   **Body:** `multipart/form-data`
*   **Guaranteed Behavior:**
    *   Automatically detects MIME type.
    *   Initializes Redis tracking metadata before queuing Celery tasks.
    *   Async task will re-split AST chunks larger than 2000 characters (Safety Valve).

#### `DELETE /api/v1/rag/file/{fileId}`
Tear-down endpoint.
*   **Guaranteed Behavior:**
    *   Deletes physical file from disk.
    *   Deletes all corresponding vectors from ChromaDB (using `chunk_id` index).
    *   Deletes file tracking metadata from Redis (This triggers the Orphan Filter for existing cached search results).

---

## RAG API FREEZE – CANONICAL CURL SET

These curls define **"what correct means"**. If any future change breaks one of these, it is a regression.

### 1. File Upload (Async Ingestion)
**Purpose:** Create file record, persist tenant metadata, and trigger async ingestion. Return immediately with pending status.

```bash
curl -X POST "http://localhost:8001/api/v1/rag/file/upload" \
  -H "Authorization: Bearer <tenant_jwt>" \
  -F "collection=default" \
  -F "files=@/absolute/path/to/file.py"
```

**Expected Guarantees:**
- `id` exists in response
- `size` matches source file bytes
- `tenant_id` saved as the value of the `tenant_id` claim from the JWT
- `collection_name` saved as `user_{tenant_id}`
- `finishEmbedding: false`

### 2. File Status Polling
**Purpose:** UI polls until embedding completes. Single source of truth is Redis.

```bash
curl "http://localhost:8001/api/v1/rag/file/{file_id}" \
  -H "Authorization: Bearer <tenant_jwt>"
```

**Expected Guarantees:**
- `finishEmbedding: true` ONLY after vectors are fully written to ChromaDB.
- `chunkCount > 0`
- Stable schema (no missing fields like `size`).

### 2b. Get All Files for Tenant
**Purpose:** Retrieve all file metadata for the current tenant.

```bash
curl "http://localhost:8001/api/v1/rag/files" \
  -H "Authorization: Bearer <tenant_jwt>"
```

**Expected Guarantees:**
- Returns array of `FileStatusResponse` objects.
- Only includes files belonging to the JWT-resolved tenant.
- Empty array `[]` if tenant has no files.
- Strict tenant isolation (filtered via Redis SCAN).

### 2c. Get Sequential Chunks
**Purpose:** Retrieve chunks in order for a specific file (summarization mode).

```bash
curl "http://localhost:8001/api/v1/rag/file/{file_id}/chunks?limit=10" \
  -H "Authorization: Bearer <tenant_jwt>"
```

**Expected Guarantees:**
- Ordered by `chunk_index` ASC.
- Supports pagination via `limit` and `offset`.
- Enriched metadata (filename, URL).

### 3. Semantic Search (Primary Entry Point)
**Purpose:** Query tenant-scoped vector store, apply reranking, apply context shaper, and filter orphans.

```bash
curl -X POST "http://localhost:8001/api/v1/rag/chunk/semanticSearchForChat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <tenant_jwt>" \
  -d '{
    "messageId": "msg_001",
    "userQuery": "How does the RAGAgent initialize?",
    "top_k": 5
  }'
```

**Expected Guarantees:**
- **No Orphans:** No chunks from deleted files.
- **No Empty Text:** Chunks with empty content are dropped.
- **Tenant Isolation:** No leakage from other users.
- **Semantic Priority:** Ordered by combined similarity + rerank score.
- `queryId` always returned.

### 4. Semantic Search (Rewrite Query Path)
**Purpose:** Ensure `rewriteQuery` is honored for better vector matching.

```bash
curl -X POST "http://localhost:8001/api/v1/rag/chunk/semanticSearchForChat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <tenant_jwt>" \
  -d '{
    "messageId": "msg_002",
    "userQuery": "graph rebuild",
    "rewriteQuery": "Explain how code_graph is cached using Redis",
    "top_k": 5
  }'
```

**Expected Guarantees:**
- `rewriteQuery` is used for retrieval.
- Results differ meaningfully from raw `userQuery`.

### 5. Multi-Tenant Isolation Verification
**Purpose:** Prove no cross-tenant leakage.

```bash
curl -X POST "http://localhost:8001/api/v1/rag/chunk/semanticSearchForChat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <tenant_b_jwt>" \
  -d '{
    "messageId": "msg_iso_test",
    "userQuery": "How does the RAGAgent initialize?",
    "top_k": 5
  }'
```

**Expected Guarantees:**
- **Empty result set** (assuming tenant B has no files).
- Zero leakage from tenant A.

### 6. File Deletion (Hard Delete)
**Purpose:** Wipe data and invalidate cache.

```bash
curl -X DELETE "http://localhost:8001/api/v1/rag/file/{file_id}" \
  -H "Authorization: Bearer <tenant_jwt>"
```

**Expected Guarantees:**
- File removed from Redis.
- Vectors removed from ChromaDB.
- Graph cache invalidated.

### 7. Post-Deletion Verification (Anti-Phantom)
**Purpose:** Ensure no ghost chunks survive in search results.

```bash
curl -X POST "http://localhost:8001/api/v1/rag/chunk/semanticSearchForChat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <tenant_jwt>" \
  -d '{
    "messageId": "msg_verify_del",
    "userQuery": "What is the agent structure?",
    "top_k": 5
  }'
```

**Expected Guarantees:**
- `chunks: []`
- No "unknown" citations.
- No empty placeholders.

---

## Architecture Rules

DevForge RAG system provides code-aware document retrieval with:
- **Two-stage retrieval:** Vector search → Cross-encoder reranking
- **Phase 12A Query Intelligence:**
  - 3-tier Intent Classification (rule-based → LLM → default)
  - Intent-aware Query Expansion
  - Semantic Caching by Intent
  - Analytics & Metrics Endpoints
- Semantic search with dependency graph expansion
- AST-based code chunking (Tree-sitter)
- Test-source linking
- Code-aware score boosting

**Technology Stack:**
- Async task processing (Celery + Redis optional)
- Cross-encoder reranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`)
- Vector store abstraction: ChromaDB + Postgres (pgvector). Qdrant exists as a legacy/optional LangChain wrapper inside `tools.get_vector_store` and is **not** selectable via `VECTOR_BACKEND`.
- Cloud LLM models (gpt-oss via Ollama)
- Local embeddings (nomic-embed-text)

---

## Non-Negotiable Architecture Rules

> [!CAUTION]
> These rules are **mandatory** across the active phase set (10.x through 16). Phase numbering is inconsistent across the repo; treat the rules — not the phase tag — as the contract.

### 1. Graph Rules

| Rule | Enforcement |
|------|-------------|
| Graph is **derived state with a Redis warm-start cache** | Rebuilt from `iter_chunk_metadata()` on cache miss; on hit, hydrated from Redis (Phase 16). |
| Graph is **scoped per RAGAgent** | Each instance owns `self._code_graph`; cache key is `rag_graph:v2:{collection_name}` with 1-hour TTL (`src/agents/rag/agent.py:436-509`). |
| **No on-disk persistence** | No pickle files, no DB rows for the graph itself; Redis is the only persistence layer and is treated as a cache. |
| **Cache invalidation hooks** | `ingest_document` and `delete_file_cascade` evict the Redis key (`agent.py:639-647, 695-708`). Legacy 2-segment QIDs detected on load also force a rebuild (`agent.py:454-456`). |
| **No graph API endpoints** | Graph expansion is internal only. |

**Implementation:**
```python
async def init_graph(self) -> None:
    # 1. Try Redis warm-start cache
    cache_key = f"rag_graph:v2:{self.collection_name}"
    cached = redis_client.get(cache_key)
    if cached:
        graph_dict = json.loads(cached)
        # Reject legacy 2-segment QIDs and fall through to rebuild
        if all(len(qid.split("::")) >= 3 for qid in graph_dict):
            self._code_graph = CodeGraph.from_dict(graph_dict)
            return

    # 2. Cache miss: rebuild from vector store metadata
    self._code_graph = CodeGraph()
    async for batch in self.vector_store.iter_chunk_metadata(batch_size=500):
        self._code_graph.add_chunks_batch(batch, tenant_id=self.tenant_id)

    # 3. Write back to Redis with 1-hour TTL
    redis_client.set(cache_key, json.dumps(self._code_graph.to_dict()), ex=3600)

# Note: `code_graph` is a property that REQUIRES `await agent.init_graph()`
# first — it raises RuntimeError if accessed before initialization
# (src/agents/rag/agent.py:403-418). It is not a lazy auto-init property.
```

### 2. Qualified ID Format

```
tenant::file::entity
```

- Separator: `::` (handles Windows paths like `C:\\src\\file.py`)
- **Three segments are required.** `CodeGraph.add_node` warns and rejects QIDs with fewer than 3 segments (`src/agents/rag/graph/code_graph.py:44-47`). Anchor QIDs are built as `f"{tenant_id}::{source}::{name}"` (`src/agents/rag/agent.py:1299, 1312`).
- **Legacy detection:** the cache load step rebuilds the graph if it finds 2-segment QIDs from older data (`agent.py:454-456`).
- Examples:
  - `dev_user_1::auth.py::authenticate`
  - `dev_user_1::utils.py::User.login`
  - `dev_user_1::test_utils.py::test_add`

**Why Double Colon?**
- Avoids conflicts with Windows paths (`C:\path\file.py`)
- Consistent with Rust (`::`), C++ (`::`)
- Easy to parse/validate

### 3. Layer Separation

```
┌─────────────────┐
│     Agents      │  ← Business logic, orchestration (entry point)
├─────────────────┤
│     Tools       │  ← Reusable functions invoked by agents
├─────────────────┤
│ BaseVectorStore │  ← Abstract interface
├─────────────────┤
│ Chroma/pgvector │  ← Backend implementations
└─────────────────┘
```

**Call Rules (production direction):**
- **Celery** → Agents (entry into business logic)
- **Agents** → Tools (`RAGAgent` imports `generate_response`, `ingest_documents`, `retrieve_docs` from `src/tools/rag/tools.py` — `agent.py:18-22`)
- **Tools** → Storage via `BaseVectorStore` (NEVER backend internals)

**Violations Result In:**
- Tight coupling
- Testing difficulties
- Backend lock-in

### 4. Forbidden Patterns

```python
# NEVER DO THIS
global code_graph
from src.agents.rag.agent import code_graph
vector_store._collection.get(...)  # Direct backend access
"file:entity"           # Single colon
"file::entity"          # 2-segment QID (legacy; rejected by add_node)

# ALWAYS DO THIS
await agent.init_graph()                # explicit initialization
self.code_graph                         # instance property (post-init)
await self.vector_store.get_chunk_by_qualified_id(qid)
"tenant::file::entity"                  # 3-segment QID
```

---

## Component Architecture

### Ingestion Pipeline

```
File Upload
    ↓
Celery Task Queue (async_ingest_documents)
    ↓
RAGAgent.ingest_document()
    ↓
tools.ingest_documents()
    ↓
Code Detection (file extension)
    ↓
├─ Code Files (.py, .js, .ts, .jsx, .tsx)
│     ↓
│  CodeChunker (Tree-sitter AST)
│     ↓
│  Extract: functions, classes, imports, calls
│
└─ Other Files (.md, .txt, .pdf)
      ↓
   TextChunker (overlap strategy)
    ↓
Generate Embeddings (OllamaEmbeddings)
    ↓
ChromaVectorStore.add_chunks()
    ↓
Vector DB + Metadata Storage
```

### Retrieval Pipeline

```
User Query
    ↓
RAGAgent.retrieve_with_context(query)
    ↓
── Phase 12A Query Intelligence (agent.py:881-1002) ──
  Intent Classification (rule-based → LLM → default)
    ↓
  Semantic Cache Check (cosine ≥ 0.92 → return cached)
    ↓
  Intent-aware Query Expansion (multi-query fan-out)
    ↓
  Hybrid (BM25 + Vector) OR Vector-only retrieval
    ↓
  Reciprocal Rank Fusion (RRF) across expanded queries
─────────────────────────────────────────────────────
    ↓
Initial Results (semantic similarity)
    ↓
Graph Expansion (if enabled)
    ↓
CodeGraph.get_related(qid, depth=2)
    ↓
Fetch Related Chunks via QID
    ↓
Merge + Deduplicate
    ↓
Cross-Encoder Reranking
    ↓
Context Shaper (Deterministic)
    ↓
  1. Qualified ID Deduplication
  2. Role Assignment (Entry/Dependency/Supporting)
  3. Deterministic Ordering
  4. Hard Limits
    ↓
Return Shaped Context
```

### Graph Rebuild

```
await RAGAgent.init_graph()        # explicit; not a lazy auto-init
    ↓
Redis lookup: rag_graph:v2:{collection_name}
    ↓
  ├─ HIT (and QIDs are 3-segment) → hydrate CodeGraph from JSON → done
  └─ MISS or legacy 2-segment QIDs detected:
        ↓
     CodeGraph() initialization
        ↓
     vector_store.iter_chunk_metadata(batch_size=500)
        ↓
     For each batch:
        ↓
       Extract metadata (NO embeddings)
        ↓
       Build QID (tenant::file::entity)
        ↓
       Add edges (calls, imports)
        ↓
     redis_client.set(cache_key, json.dumps(graph), ex=3600)
        ↓
     Graph Ready (in-memory + Redis-cached, derived state)
```

---

## Module Structure

### `/src/workers` - Async Task Queue

**Purpose:** Background document ingestion  
**Technology:** Celery + Redis

| File | Responsibility |
|------|----------------|
| `celery_app.py` | Celery configuration, broker/backend |
| `tasks/rag_tasks.py` | Document ingestion tasks |

**Key Features:**
- Async task processing
- Progress tracking
- Per-file error handling
- Task status API (`/rag/task/{task_id}`)

### `/src/agents/rag` - RAG Orchestration

**Purpose:** Core RAG logic and graph management

| File | Responsibility |
|------|----------------|
| `agent.py` | RAGAgent class, graph ownership |
| `context_shaper.py` | Deterministic context shaping & role assignment |
| `graph/code_graph.py` | In-memory dependency graph |
| `chunking/base_chunker.py` | Abstract chunker base class |
| `chunking/code_chunker.py` | Tree-sitter AST parsing |
| `chunking/text_chunker.py` | Fallback text chunking |
| `linking/test_linker.py` | Test-source linking — **implemented but not wired into the production ingestion path**; only exercised in `tests/test_day6_validation.py`. |
| `cache/query_cache.py` | Exact-match query cache |
| `cache/semantic_cache.py` | Cosine-similarity (≥0.92) semantic cache |
| `cache/query_normalizer.py` | Query normalization for cache keys |
| `expansion/query_expander.py` | Intent-aware multi-query expansion |
| `expansion/result_fusion.py` | Reciprocal Rank Fusion across expanded queries |
| `retrieval/bm25_index.py` | BM25 lexical index |
| `retrieval/hybrid_retriever.py` | BM25 + vector hybrid retrieval (`HYBRID_ALPHA`) |
| `reranking/base_reranker.py` | Reranker abstract base |
| `reranking/cross_encoder_reranker.py` | Cross-encoder reranker (ms-marco-MiniLM) |
| `analytics/intent_classifier.py` | 3-tier intent classification (rule → LLM → default) |

**Architecture:**
- `RAGAgent` owns `self._code_graph` (instance-scoped)
- `ContextShaper` is purely deterministic (logical ordering/dedup)
- Graph is initialized via explicit `await agent.init_graph()` from `iter_chunk_metadata()` with Redis warm-start cache
- NO global state, NO on-disk persistence (Redis-only, with TTL + invalidation hooks)

### `/src/storage` - Vector Store Abstraction

**Purpose:** Abstract interface for vector backends

| File | Responsibility |
|------|----------------|
| `base_store.py` | BaseVectorStore interface |
| `chroma_store.py` | ChromaDB implementation |
| `pgvector_store.py` | pgvector implementation (**production default** per `config.py:130`) |

**Key Methods:**
```python
class BaseVectorStore(ABC):
    async def add_chunks(...) -> int
    async def search(...) -> List[ChunkResult]
    async def get_chunk_by_qualified_id(qid) -> ChunkResult
    async def iter_chunk_metadata(batch_size) -> AsyncIterator[List[Dict]]
```

### `/src/api` - API Endpoints

**Purpose:** HTTP API for RAG operations

All routes are mounted under the `/api` prefix (`src/main.py:81`).

**Lobe Chat canonical surface (`/api/v1/rag/*`):**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/rag/file/upload` | POST | Universal ingestion entry point |
| `/api/v1/rag/file/{fileId}` | GET | File status polling |
| `/api/v1/rag/file/{fileId}` | DELETE | Hard delete (file + vectors + cache) |
| `/api/v1/rag/file/{fileId}/chunks` | GET | Sequential chunk retrieval (`limit=5, offset=0`) |
| `/api/v1/rag/files` | GET | Batch file metadata for tenant |
| `/api/v1/rag/chunk/semanticSearchForChat` | POST | Primary semantic search |

**Async ingestion + ops surface (`/api/rag/*`):**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/rag/ingest-async` | POST | Queue async ingestion (Celery) |
| `/api/rag/task/{task_id}` | GET | Get Celery task status |
| `/api/rag/metrics` | GET | RAG metrics |
| `/api/rag/health` | GET | RAG health check |
| `/api/rag/cache/clear` | POST | Clear query/semantic caches |
| `/api/rag/bm25/rebuild` | POST | Rebuild BM25 index |

**Analytics surface (`/api/rag/analytics/*`)** — see `src/api/routers/__init__.py:457-540` for the full list.

---

## Data Flow & State Management

### Chunk Metadata Structure

```python
{
    "content": "def add(a, b):\n    return a + b",
    "metadata": {
        "chunk_type": "function",        # function, class, import, text
        "name": "add",                    # Entity name
        "language": "python",             # python, javascript, typescript
        "source": "utils.py",             # File path
        "start_line": 10,                 # Start line in source
        "end_line": 11,                   # End line in source
        "imports": ["math"],              # Import dependencies
        "calls": ["validate"],            # Function calls
        "docstring": "Add two numbers",   # Extracted docstring
        "test_files": ["test_utils.py"]   # Linked test files (aspirational: TestLinker is not wired into the production ingest path)
    }
}
```

### Graph Structure

```python
CodeGraph:
    _graph: Dict[str, Set[str]]  # QID → related QIDs
    _metadata: Dict[str, Dict]   # QID → chunk metadata

# Example:
{
    "utils.py::add": {"utils.py::validate"},
    "utils.py::validate": set(),
}
```

**Traversal:**
- BFS with configurable depth (default: 2)
- Max context chunks (default: 3)
- Deduplication by QID

---

## Configuration

### Environment Variables

```bash
# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TASK_SOFT_TIME_LIMIT=300

# Vector Store
VECTOR_BACKEND=postgres  # Options: chroma | postgres (default: postgres). Qdrant is legacy/optional and not selectable here.
CHROMA_PERSIST_DIR=./data/chromadb
# USE_PGVECTOR is deprecated — superseded by VECTOR_BACKEND (config.py:192)

# Code Graph
ENABLE_CODE_GRAPH=true
GRAPH_CONTEXT_DEPTH=2
GRAPH_MAX_CONTEXT_CHUNKS=3

# Chunking
RAG_CHUNK_SIZE=500
RAG_CHUNK_OVERLAP=50

# Embeddings
RAG_EMBED_MODEL=nomic-embed-text
OLLAMA_HOST=http://localhost:11434
```

---

## Quick Reference

### Component Locations

| Component | Location | Responsibility |
|-----------|----------|----------------|
| RAGAgent | `src/agents/rag/agent.py` | Orchestration, owns graph |
| CodeGraph | `src/agents/rag/graph/code_graph.py` | In-memory graph, BFS |
| CodeChunker | `src/agents/rag/chunking/code_chunker.py` | Tree-sitter AST parsing |
| TestLinker | `src/agents/rag/linking/test_linker.py` | Test-source linking |
| BaseVectorStore | `src/storage/base_store.py` | Abstract interface |
| ChromaVectorStore | `src/storage/chroma_store.py` | ChromaDB implementation |
| rag_tasks | `src/workers/tasks/rag_tasks.py` | Celery async tasks |

### Architecture Compliance Checklist

- Graph is derived state (rebuilt from metadata, cached in Redis with 1-hour TTL)
- Graph is instance-scoped (`self._code_graph`)
- QID format is `tenant::file::entity` (3 segments, `::` separator)
- NO global graph variables
- NO on-disk graph persistence (Redis-only, with invalidation hooks)
- NO backend internals in agent layer
- Celery → Agents (entry into business logic)
- Agents → Tools → BaseVectorStore (production direction)

---

## Related Documentation

- [Integration Flow](./rag/rag_integration_flow.md) - Complete call chains
- [retrieve_docs Tool](./rag/retrieve_docs.md) - API reference
- [Phase 10.1 Plan](../brain/.../implementation_plan.md) - Original requirements

---

**Maintainer:** DevForge Team  
**Version History:**
- v0.8.0 (May 2026) - Doc reconciliation: JWT auth (drop `X-User-ID`), `tenant::file::entity` QID, Redis-cached graph (Phase 16), Phase 12A query intelligence in retrieval flow, expanded module table, `VECTOR_BACKEND=chroma|postgres` (Qdrant marked legacy/optional), Lobe Chat + ops endpoints surfaced.
- v15.4 (early 2026) - Sibling integration-flow doc reference (Phase 15.4).
- v15.3 (Feb 2026) - Sequential chunk retrieval; backend contract frozen.
- v14 - Phase 14 work.
- v13 - Context Shaper (deterministic dedup → role assignment → ordering → limits).
- v12A - Query intelligence (intent classification, semantic cache, query expansion, RRF).
- v12 - Hybrid search (BM25 + vector).
- v11.x - Cross-encoder reranking, code-aware boost factors.
- v10.1 (Dec 2025) - Code graph, async queue, vector abstraction.
- v3.1 (Dec 2025) - Initial RAG implementation.




**CANONICAL FOR FRONTEND (PHASE 15 ONLY)**
The following endpoints are the ONLY ones used by Lobe Chat:
- /api/v1/rag/file/upload
- /api/v1/rag/file/{id}
- /api/v1/rag/file/{id}/chunks (NEW - sequential retrieval)
- /api/v1/rag/files (batch retrieval)
- /api/v1/rag/chunk/semanticSearchForChat
- /api/v1/rag/file/{id} (DELETE)

All other endpoints are legacy or internal tools.
