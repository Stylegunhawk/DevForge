# DevForge RAG Architecture

**Version:** 12A Complete ✅  
**Phase:** Phase 12A Query Intelligence  
**Date:** 2025-12-17  
**Status:** Production Ready

This document outlines the architecture of the Retrieval-Augmented Generation (RAG) system in DevForge Backend, covering ingestion, retrieval, reranking, and query intelligence.

---

## Overview

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
