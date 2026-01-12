# DevForge RAG Architecture

**Version:** 15.1 Complete (Multi-Tenant) ✅  
**Phase:** Phase 15 Multi-Tenancy + Phase 3 strict filtering  
**Date:** 2026-01-09  
**Status:** Production Ready - Backend Contract Frozen

This document outlines the architecture of the Retrieval-Augmented Generation (RAG) system in DevForge Backend, covering ingestion, retrieval, reranking, and query intelligence.

---

## ❄️ Final RAG API Contract

To prevent regressions, the following endpoints are frozen with specific behavioral guarantees.

### 1. Common Requirements
*   **Header:** `X-User-ID` (Required) - Used to derive the `tenant_id` and sandbox the collection (`user_{tenant_id}`).
*   **Scope:** All operations are strictly isolated to the tenant provided in the header.

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

## 🔒 RAG API FREEZE – CANONICAL CURL SET

These curls define **"what correct means"**. If any future change breaks one of these, it is a regression.

### 1. File Upload (Async Ingestion)
**Purpose:** Create file record, persist tenant metadata, and trigger async ingestion. Return immediately with pending status.

```bash
curl -X POST "http://localhost:8000/api/v1/rag/file/upload" \
  -H "X-User-ID: dev_user_1" \
  -F "collection=default" \
  -F "files=@/absolute/path/to/file.py"
```

**Expected Guarantees:**
- `id` exists in response
- `size` matches source file bytes
- `tenant_id` saved as `dev_user_1`
- `collection_name` saved as `user_dev_user_1`
- `finishEmbedding: false`

### 2. File Status Polling
**Purpose:** UI polls until embedding completes. Single source of truth is Redis.

```bash
curl "http://localhost:8000/api/v1/rag/file/{file_id}"
```

**Expected Guarantees:**
- `finishEmbedding: true` ONLY after vectors are fully written to ChromaDB.
- `chunkCount > 0`
- Stable schema (no missing fields like `size`).

### 3. Semantic Search (Primary Entry Point)
**Purpose:** Query tenant-scoped vector store, apply reranking, apply context shaper, and filter orphans.

```bash
curl -X POST "http://localhost:8000/api/v1/rag/chunk/semanticSearchForChat" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: dev_user_1" \
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
curl -X POST "http://localhost:8000/api/v1/rag/chunk/semanticSearchForChat" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: dev_user_1" \
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
curl -X POST "http://localhost:8000/api/v1/rag/chunk/semanticSearchForChat" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: dev_user_2" \
  -d '{
    "messageId": "msg_iso_test",
    "userQuery": "How does the RAGAgent initialize?",
    "top_k": 5
  }'
```

**Expected Guarantees:**
- **Empty result set** (assuming `dev_user_2` has no files).
- Zero leakage from `dev_user_1`.

### 6. File Deletion (Hard Delete)
**Purpose:** Wipe data and invalidate cache.

```bash
curl -X DELETE "http://localhost:8000/api/v1/rag/file/{file_id}" \
  -H "X-User-ID: dev_user_1"
```

**Expected Guarantees:**
- File removed from Redis.
- Vectors removed from ChromaDB.
- Graph cache invalidated.

### 7. Post-Deletion Verification (Anti-Phantom)
**Purpose:** Ensure no ghost chunks survive in search results.

```bash
curl -X POST "http://localhost:8000/api/v1/rag/chunk/semanticSearchForChat" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: dev_user_1" \
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
- Cross-encoder reranking (ms-marco-MiniLM-L-6-v2)
- Vector store abstraction (ChromaDB/pgvector)
- Cloud LLM models (gpt-oss via Ollama)
- Local embeddings (nomic-embed-text)

---

## Non-Negotiable Architecture Rules

> [!CAUTION]
> These rules are **mandatory** for all Phase 10.1 implementation.

### 1. Graph Rules

| Rule | Enforcement |
|------|-------------|
| Graph is **derived state** | Rebuilt from chunk metadata on first access |
| Graph is **scoped per RAGAgent** | Each instance has its own `self._code_graph` |
| **No graph persistence** | No pickle, no database, no cache files |
| **No graph API endpoints** | Graph expansion is internal only |

**Implementation:**
```python
@property
def code_graph(self):
    if self._code_graph is None:
        self._code_graph = CodeGraph()
        # Rebuild from vector store metadata
        async for batch in self.vector_store.iter_chunk_metadata():
            self._code_graph.add_chunks_batch(batch)
    return self._code_graph
```

### 2. Qualified ID Format

```
file::entity
```

- Separator: `::` (handles Windows paths like `C:\\src\\file.py`)
- Examples:
  - `auth.py::authenticate`
  - `utils.py::User.login`
  - `test_utils.py::test_add`

**Why Double Colon?**
- Avoids conflicts with Windows paths (`C:\path\file.py`)
- Consistent with Rust (`::`), C++ (`::`)
- Easy to parse/validate

### 3. Layer Separation

```
┌─────────────────┐
│     Tools       │  ← LLM-facing, thin wrappers
├─────────────────┤
│     Agents      │  ← Business logic, orchestration
├─────────────────┤
│ BaseVectorStore │  ← Abstract interface
├─────────────────┤
│ Chroma/pgvector │  ← Backend implementations
└─────────────────┘
```

**Call Rules:**
- **Celery** → Agents (NEVER tools)
- **Agents** → BaseVectorStore (NEVER backend internals)
- **Tools** → Agents (NEVER storage)

**Violations Result In:**
- ❌ Tight coupling
- ❌ Testing difficulties
- ❌ Backend lock-in

### 4. Forbidden Patterns

```python
# ❌ NEVER DO THIS
global code_graph
from src.agents.rag.agent import code_graph
vector_store._collection.get(...)  # Direct backend access
"file:entity"  # Single colon

# ✅ ALWAYS DO THIS
self.code_graph  # Instance property
await self.vector_store.get_chunk_by_qualified_id(qid)
"file::entity"  # Double colon
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
├─ Code Files (.py, .js, .ts)
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
Generate Query Embedding
    ↓
ChromaVectorStore.search(embedding, top_k=5)
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
Context Shaper (Deterministic)  <-- NEW
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
RAGAgent.code_graph (lazy property)
    ↓
CodeGraph() initialization
    ↓
ChromaVectorStore.iter_chunk_metadata(batch_size=500)
    ↓
For each batch:
    ↓
  Extract metadata (NO embeddings)
    ↓
  Build QID (file::entity)
    ↓
  Add edges (calls, imports)
    ↓
Graph Ready (in-memory, derived state)
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
| `chunking/code_chunker.py` | Tree-sitter AST parsing |
| `chunking/text_chunker.py` | Fallback text chunking |
| `linking/test_linker.py` | Test-source linking |

**Architecture:**
- `RAGAgent` owns `self._code_graph` (instance-scoped)
- `ContextShaper` is purely deterministic (logical ordering/dedup)
- Graph is lazy-initialized from `iter_chunk_metadata()`
- NO global state, NO persistence

### `/src/storage` - Vector Store Abstraction

**Purpose:** Abstract interface for vector backends

| File | Responsibility |
|------|----------------|
| `base_store.py` | BaseVectorStore interface |
| `chroma_store.py` | ChromaDB implementation |
| `pgvector_store.py` | pgvector implementation (Phase 10.2) |

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

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/rag/ingest-async` | POST | Queue async ingestion |
| `/rag/task/{task_id}` | GET | Get task status |

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
        "test_files": ["test_utils.py"]   # Linked test files
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
VECTOR_BACKEND=chroma  # or qdrant
CHROMA_PERSIST_DIR=./data/chromadb
USE_PGVECTOR=false

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

- ✅ Graph is derived state (rebuilt from metadata)
- ✅ Graph is instance-scoped (`self._code_graph`)
- ✅ QID format uses `::` separator
- ✅ NO global graph variables
- ✅ NO graph persistence
- ✅ NO backend internals in agent layer
- ✅ Celery → Agents (not tools)
- ✅ Agents → BaseVectorStore (not backends)

---

## Related Documentation

- [Integration Flow](./rag_integration_flow.md) - Complete call chains
- [retrieve_docs Tool](./tools/retrieve_docs.md) - API reference
- [Phase 10.1 Plan](../brain/.../implementation_plan.md) - Original requirements

---

**Maintainer:** DevForge Team  
**Version History:**
- v10.1 (Dec 2025) - Code graph, async queue, vector abstraction
- v3.1 (Dec 2025) - Initial RAG implementation




⚠️ CANONICAL FOR FRONTEND (PHASE 15 ONLY)
The following endpoints are the ONLY ones used by Lobe Chat:
- /api/v1/rag/file/upload
- /api/v1/rag/file/{id}
- /api/v1/rag/chunk/semanticSearchForChat
- /api/v1/rag/file/{id} (DELETE)

All other endpoints are legacy or internal tools.
