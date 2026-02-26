# retrieve_docs - RAG Document Retrieval Tool

**Version:** 15.3 (Strict Multi-Tenancy)  
**Version:** 3.4 (Sequential Support)  
**Status:** ✅ Implemented & Frozen  
**Last Updated:** February 26, 2026

---

## Overview

The `retrieve_docs` tool provides intelligent semantic document search with **Phase 12A Query Intelligence** and **Phase 15 Multi-Tenancy** enhancements.

**Phase 15 Features (NEW!):**
- 🆕 **Strict Multi-Tenancy** - Isolated collections via `X-User-ID` header.
- 🆕 **Frozen API Contract** - Guaranteed semantic priority and orphan filtering.
- 🆕 **Safety Valve Chunking** - Auto-split large AST entities (>2000 chars) for model safety.

**Phase 12A Features:**
- ✅ **3-Tier Intent Classification** - Auto-detect code_search, explain, debug, general intents
- ✅ **Intent-Aware Query Expansion** - Generate 2-3 related queries per intent
- ✅ **Semantic Caching by Intent** - Cache similar queries for 10-50ms responses
- 🆕 **Cloud Model Support** - Use gpt-oss:120b-cloud for memory-efficient response generation
- 🆕 **Analytics Endpoints** - Track intent distribution, expansion quality, cache hits

**Phase 13 Features (NEW!):**
- 🆕 **Deterministic Context Shaping** - Post-retrieval deduplication & ordering
- 🆕 **Role-Based Context** - Explicit `entry`, `dependency`, `supporting` roles
- 🆕 **Qualified ID Deduplication** - Handles overloaded functions & classes correctly

**Phase 11 Features:**
- ✅ Two-stage retrieval (Vector search → Cross-encoder reranking)
- ✅ Code-aware score boosting
- ✅ Sigmoid normalized scores

**Phase 10.1 Features:**
- ✅ Async ingestion via Celery task queue (optional)
- ✅ Tree-sitter AST parsing for code files (Python, JS, TS)
- ✅ Code dependency graph with BFS traversal
- ✅ Graph-based context expansion
- ✅ Multi-format support (PDF, MD, TXT, DOCX, PY, JS, TS)
- ✅ Dual vector store (ChromaDB local + Qdrant cloud)

---

## Phase 10.1 Features

### Code-Aware Chunking

**Supported Languages:**
- Python (`.py`) - Functions, classes, docstrings, imports
- JavaScript (`.js`, `.jsx`) - Functions, classes, JSDoc, imports
- TypeScript (`.ts`, `.tsx`) - Functions, classes, JSDoc, imports

**AST Extraction:**
```python
# Input: utils.py
def add(a, b):
    """Add two numbers."""
    return a + b

# Output: Chunk with metadata
{
    "chunk_type": "function",
    "name": "add",
    "language": "python",
    "source": "utils.py",
    "start_line": 1,
    "end_line": 3,
    "calls": [],
    "docstring": "Add two numbers."
}
```

### Code Dependency Graph

**Graph Structure:**
- **Nodes:** Qualified IDs (`file::entity` format)
- **Edges:** Function calls and imports
- **Traversal:** BFS with configurable depth

**Context Expansion Example:**
```python
Query: "authentication function"
Initial Match: auth.py::authenticate

Graph Expansion (depth=2):
  auth.py::authenticate
    ↓ calls
  auth.py::validate_token
    ↓ imports
  utils.py::decode_jwt

Result: 3 related chunks (expanded context)
```

### Async Ingestion

**Endpoint:** `POST /rag/ingest-async`

```bash
curl -X POST http://localhost:8001/api/rag/ingest-async \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": ["src/auth.py", "src/utils.py"],
    "collection_name": "devforge_docs"
  }'
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "message": "Ingestion queued"
}
```

**Check Status:**
```bash
curl http://localhost:8001/api/rag/task/{task_id}
```

---

## Lobe Chat Frontend Integration (v3.2)

The RAG system is fully integrated with Lobe Chat's TypeScript data contracts via a dedicated router.

### New Integration Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/rag/file/upload` | `POST` | Upload files with MIME detection and async ingestion |
| `/api/v1/rag/file/{id}` | `GET` | Poll processing status until `finishEmbedding: true` |
| `/api/v1/rag/file/{id}/chunks` | `GET` | [Sequential chunk retrieval](get_file_chunks_api.md) |
| `/api/v1/rag/chunk/semanticSearchForChat` | `POST` | Primary search endpoint for Lobe Chat sessions |
| `/api/v1/rag/file/{id}` | `DELETE` | Removes file, vectors, and metadata |
| `/api/v1/rag/message/{id}/query` | `DELETE` | Cleans up RAG queries for the specified message |

### Integration Architecture

- **Redis Metadata Store:** Tracks file status (`pending` → `processing` → `success/error`) and query logs.
- **Static File Serving:** Files are served via `/static/uploads` for frontend previews.
- **Two-Stage Retrieval:** The `semanticSearchForChat` endpoint automatically utilizes the Phase 12A RAGAgent's vector search and reranking capabilities.

---

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | ✅ Yes | - | Search query for semantic retrieval |
| `file_paths` | array[string] | No | `[]` | Documents to ingest before searching |
| `top_k` | integer | No | `5` | Number of results to return (1-50) |
| `embed_model` | string | No | `"nomic-embed-text"` | Embedding model to use |
| `include_context` | boolean | No | `false` | Enable graph-based context expansion |

### New in Phase 10.1

**`include_context`** - Enable code graph expansion:
- Finds related functions via calls/imports
- BFS traversal (default depth: 2)
- Returns extended context with related code

**Example:**
```json
{
  "query": "authentication logic",
  "include_context": true,
  "top_k": 3
}
```

---

## API Usage

### Basic Search (Unchanged)

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "explain authentication in Express.js"
    }
  }'
```

### Search with Graph Context Expansion (New)

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "JWT token validation",
      "include_context": true,
      "top_k": 5
    }
  }'
```

**Response (with expansion):**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "content": "def validate_token(token): ...",
        "score": 0.92,
        "metadata": {
          "source": "auth.py",
          "chunk_type": "function",
          "name": "validate_token",
          "role": "entry"
        }
      },
      {
        "content": "def decode_jwt(token): ...",
        "score": null,  // Graph-expanded (no direct similarity)
        "metadata": {
          "source": "utils.py",
          "chunk_type": "function",
          "name": "decode_jwt",
          "expanded_from": "auth.py::validate_token",
          "role": "dependency"
        }
      }
    ],
    "query": "JWT token validation",
    "expanded": true,
    "expansion_count": 3
  }
}
```

### Async Ingestion (New)

```bash
# Queue ingestion
curl -X POST http://localhost:8001/api/rag/ingest-async \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": [
      "src/auth.py",
      "src/middleware.py",
      "tests/test_auth.py"
    ],
    "collection_name": "devforge_docs"
  }'

# Response
{
  "task_id": "abc123...",
  "status": "PENDING"
}

# Check status
curl http://localhost:8001/api/rag/task/abc123...

# Response
{
  "task_id": "abc123...",
  "status": "SUCCESS",
  "result": {
    "status": "completed",
    "results": [
      {"file": "src/auth.py", "success": true, "chunks": 15},
      {"file": "src/middleware.py", "success": true, "chunks": 8},
      {"file": "tests/test_auth.py", "success": true, "chunks": 12}
    ]
  }
}
```

---

## Document Processing Pipeline (Phase 10.1)

```
Documents (PDF/MD/TXT/DOCX/PY/JS/TS)
    ↓
[NEW] Async Task Queue (Celery + Redis)
    ↓
Read Content (async I/O)
    ↓
[NEW] File Type Detection
    ↓
├─ Code Files (.py, .js, .ts)
│     ↓
│  [NEW] Tree-sitter AST Parsing
│     ↓
│  Extract: functions, classes, imports, calls
│
└─ Other Files (.md, .txt, .pdf, .docx)
      ↓
   Text Chunking (500 chars, 50 overlap)
    ↓
Generate Embeddings (nomic-embed-text)
    ↓
Store in Vector DB (ChromaDB/Qdrant)
    ↓
[NEW] Build Code Graph (file::entity nodes)
    ↓
Semantic Search Query
    ↓
Retrieve Top-K Documents
    ↓
[NEW] Graph Expansion (BFS traversal)
    ↓
[NEW] Fetch Related Chunks by QID
    ↓
Return Results with Extended Context
```

---

## Code Graph Features

### Qualified ID (QID) Format

**Structure:** `file::entity`

**Examples:**
- `auth.py::authenticate`
- `utils.py::User.login`
- `middleware.ts::validateRequest`

**Why Double Colon?**
- Handles Windows paths (`C:\src\file.py`)
- Consistent with Rust/C++ syntax
- Easy to parse and validate

### Graph Traversal

**Algorithm:** Breadth-First Search (BFS)  
**Configuration:**
```python
GRAPH_CONTEXT_DEPTH = 2      # Max traversal depth
GRAPH_MAX_CONTEXT_CHUNKS = 3 # Max related chunks
```

**Example:**
```
Query: "authentication"
Match: auth.py::authenticate

BFS Traversal:
  Depth 0: auth.py::authenticate
  Depth 1: auth.py::validate_token (called by authenticate)
  Depth 1: utils.py::hash_password (imported by authenticate)
  Depth 2: utils.py::generate_salt (called by hash_password)

Result: 4 chunks (1 initial + 3 related)
```

### Test-Source Linking

**Automatic Detection:**
- `test_*.py` → `*.py`
- `*_test.py` → `*.py`
- `*.spec.ts` → `*.ts`
- `*.test.js` → `*.js`

**Metadata Enhancement:**
```json
{
  "source": "auth.py",
  "name": "authenticate",
  "test_files": ["test_auth.py", "auth_test.py"]
}
```

---

## Technology Stack (Updated)

### Phase 10.1 Additions

| Technology | Version | Purpose |
|------------|---------|---------|
| **Celery** | 5.3.4 | Async task queue |
| **Redis** | 5.0.1 | Celery broker/backend |
| **Tree-sitter** | 0.25.2 | AST parsing |
| **tree-sitter-python** | 0.25.0 | Python grammar |
| **tree-sitter-javascript** | 0.25.0 | JS grammar |
| **tree-sitter-typescript** | 0.23.2 | TS grammar |

### Existing Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| ChromaDB | 1.3.5 | Local vector store |
| Qdrant Client | 1.16.1 | Cloud vector store |
| LangChain | 1.0.3 | Embeddings and chains |
| sentence-transformers | 5.1.2 | Reranking |
| PyPDF | 6.4.0 | PDF parsing |
| python-docx | Latest | DOCX parsing |

---

## Configuration (Updated)

### RAG Settings

```python
# Chunking
RAG_CHUNK_SIZE = 500  # Characters per chunk (text files)
RAG_CHUNK_OVERLAP = 50  # Overlap between chunks

# Retrieval
RAG_TOP_K = 5  # Default results
RAG_SCORE_THRESHOLD = 0.5  # Minimum similarity score

# Embedding
RAG_EMBED_MODEL = "nomic-embed-text"

# [NEW] Code Graph
ENABLE_CODE_GRAPH = True  # Enable graph expansion
GRAPH_CONTEXT_DEPTH = 2   # BFS depth limit
GRAPH_MAX_CONTEXT_CHUNKS = 3  # Max related chunks

# [NEW] Async Processing
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes
```

---

## Use Cases (Updated)

### 1. Code Documentation Search with Context

```json
{
  "query": "How does authentication middleware work?",
  "file_paths": ["src/middleware.ts"],
  "include_context": true,
  "top_k": 5
}
```

**Result:** Main authentication function + related helper functions via graph expansion

### 2. Test-Driven Documentation

```json
{
  "query": "authentication test cases",
  "file_paths": ["tests/test_auth.py", "src/auth.py"]
}
```

**Result:** Test files automatically linked to source implementations

### 3. Dependency Discovery

```json
{
  "query": "database connection",
  "include_context": true
}
```

**Result:** Main DB functions + all calling functions discovered via graph

### 4. Async Bulk Ingestion

```bash
# Ingest entire codebase asynchronously
POST /rag/ingest-async
{
  "file_paths": [
    "src/auth.py", "src/database.py", "src/models.py",
    "tests/test_auth.py", "tests/test_db.py",
    "docs/api.md", "docs/setup.md"
  ]
}
```

---

## Performance (Updated)

| Operation | Time | Notes |
|-----------|------|-------|
| Code file ingestion (1 .py) | 1-2s | With AST parsing |
| Text file ingestion (1 .md) | 500ms-1s | Standard chunking |
| Search query | <500ms | With caching |
| Graph expansion | +100-200ms | BFS traversal |
| Async task queue | Instant | Non-blocking |

---

## Architecture Components

### File Locations

| Component | Path | Responsibility |
|-----------|------|----------------|
| RAGAgent | `src/agents/rag/agent.py` | Orchestration, graph ownership |
| CodeGraph | `src/agents/rag/graph/code_graph.py` | In-memory dependency graph |
| CodeChunker | `src/agents/rag/chunking/code_chunker.py` | Tree-sitter AST parsing |
| TextChunker | `src/agents/rag/chunking/text_chunker.py` | Text fallback chunking |
| TestLinker | `src/agents/rag/linking/test_linker.py` | Test-source linking |
| BaseVectorStore | `src/storage/base_store.py` | Vector store abstraction |
| ChromaVectorStore | `src/storage/chroma_store.py` | ChromaDB implementation |
| Redis Store | `src/storage/redis_file_store.py` | Metadata persistence and state tracking |
| API (Lobe Chat) | `src/api/routers/rag.py` | Frontend-compliant integration router |
| API (Legacy) | `src/api/routers/__init__.py` | Original MCP and analytics endpoints |
| Celery Tasks | `src/workers/tasks/rag_tasks.py` | Async ingestion tasks |

---

## Error Handling (Updated)

### Async Task Failures

```json
{
  "task_id": "abc123",
  "status": "FAILURE",
  "error": "File not found: src/missing.py"
}
```

### AST Parsing Fallback

If Tree-sitter parsing fails, automatically falls back to text chunking:
```
[WARNING] AST parsing failed for auth.py: syntax error
[INFO] Falling back to text chunking for auth.py
```

---

## Best Practices (Updated)

1. **Code Files** - Enable `include_context=true` for graph expansion
2. **Async Ingestion** - Use `/rag/ingest-async` for large codebases
3. **Chunk Size** - 500 chars works well for text; code uses AST boundaries
4. **Top-K Selection** - Start with 5, increase if context is insufficient
5. **File Formats** - Code files (.py, .js, .ts) get AST parsing, others get text chunking
6. **Vector Store** - ChromaDB for dev, Qdrant for production

---

## Troubleshooting (Updated)

**Issue:** Code files not parsed correctly  
**Solution:** Check Tree-sitter installation: `pip install tree-sitter tree-sitter-python`

**Issue:** Graph expansion returns no results  
**Solution:** Verify `ENABLE_CODE_GRAPH=true` in config

**Issue:** Async tasks stuck in PENDING  
**Solution:** Check Celery worker and Redis: `celery -A src.workers.celery_app worker`

**Issue:** Poor search results for code  
**Solution:** Enable `include_context=true` to get related functions

---

## Related Tools & Documentation  

**Tools:**
- `rerank_docs` - Standalone document reranking
- `refine_prompt` - Optimize search queries (use `rag` domain)
- `generate_cheatsheet` - Generate documentation cheat sheets

**Documentation:**
- [RAG Architecture](../rag_architecture.md) - Architecture rules and patterns
- [Integration Flow](../rag_integration_flow.md) - Complete data flow
- [API Reference](../../README.md) - Full API documentation

---

## Examples

### Search with Context Expansion

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "user authentication flow",
      "include_context": true,
      "top_k": 5
    }
  }'
```

### Ingest Code Repository

```bash
curl -X POST http://localhost:8001/api/rag/ingest-async \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": [
      "src/auth/login.py",
      "src/auth/register.py",
      "src/auth/middleware.py",
      "tests/auth/test_login.py"
    ],
    "collection_name": "auth_module"
  }'
```

### Check Ingestion Status

```bash
curl http://localhost:8001/api/rag/task/{task_id}
```

---

⚠️ CANONICAL FOR FRONTEND (PHASE 15 ONLY)
The following endpoints are the ONLY ones used by Lobe Chat:
- /api/v1/rag/file/upload
- /api/v1/rag/file/{id}
- /api/v1/rag/chunk/semanticSearchForChat
- /api/v1/rag/file/{id} (DELETE)

All other endpoints are legacy or internal tools.




**Last Updated:** February 26, 2026  
**Version:** 15.3 (Phase 15.3 Complete)  
**Maintainer:** DevForge Team  
**Feedback:** Create an issue in the repository
