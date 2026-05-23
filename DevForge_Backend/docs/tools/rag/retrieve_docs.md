# retrieve_docs - RAG Document Retrieval Tool

**Version:** 1.3.0  
**Status:** ✅ Implemented & Frozen  
**Last Updated:** 2026-05-24  
**Last Verified:** 2026-05-24 — TypeScript AST fix applied; ingest-async auth corrected; cross-file expansion limitation documented

> **Note:** `retrieve_docs` is **not** registered in `SUPPORTED_TOOLS` and is not callable via `POST /api/gateway`. The canonical retrieval entry point is **`POST /api/v1/rag/chunk/semanticSearchForChat`** (tenant-JWT authenticated).

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
- 🆕 **Cloud Model Support** - Use `gpt-oss:20b-cloud` (`RAG_LOCAL_MODEL`) for memory-efficient response generation
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
- ✅ Dual vector store (ChromaDB local + Postgres pgvector). Qdrant is legacy/optional and not selectable via `VECTOR_BACKEND`.

---

## Phase 10.1 Features

### Code-Aware Chunking

**Supported Languages:**
- Python (`.py`) - Functions, classes, docstrings, imports
- JavaScript (`.js`, `.jsx`) - Functions, classes, JSDoc, imports
- TypeScript (`.ts`, `.tsx`) - Functions, classes, JSDoc, imports (fixed 2026-05-24)

> **TypeScript note (fixed 2026-05-24):** Before the fix, all TypeScript files produced `ast_fallback=True` chunks because the tree-sitter query did not handle `export_statement` wrappers or `type_identifier` class names. TypeScript now produces `chunk_type=class/function` chunks correctly. See [known_issues.md — Issue #5](./known_issues.md#issue-5).

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
    "docstring": "Add two numbers.",
    "ast_fallback": false
}
```

### Code Dependency Graph

**Graph Structure:**
- **Nodes:** Qualified IDs (`tenant::file::entity` format)
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

**Endpoint:** `POST /api/rag/ingest-async`

> **Auth:** This endpoint is in `PROTECTED_EXACT` in `JWTAuthMiddleware` (`src/core/middleware.py`) — it **is** JWT-protected. Previous docs incorrectly described it as unauthenticated. See [known_issues.md — Issue #4](./known_issues.md#issue-4).

```bash
curl -X POST http://localhost:8001/api/rag/ingest-async \
  -H "Authorization: Bearer <tenant_jwt>" \
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
| `/api/v1/rag/file/{id}[?force=true]` | `DELETE` | Removes file, vectors, and metadata (use `?force=true` to prune orphaned chunks) |
| `/api/v1/rag/message/{id}/query` | `DELETE` | Cleans up RAG queries for the specified message |

### Integration Architecture

- **Redis Metadata Store:** Tracks file status (`pending` → `processing` → `success/error`) and query logs.
- **Static File Serving:** Files are served via `/static/uploads` for frontend previews.
- **Two-Stage Retrieval:** The `semanticSearchForChat` endpoint automatically utilizes the Phase 12A RAGAgent's vector search and reranking capabilities.

### Authentication Model (per endpoint)

| Endpoint scope | Auth | Header |
|----------------|------|--------|
| `/api/v1/rag/*` (incl. `chunk/semanticSearchForChat`, `file/*`, `files`, `message/*`) | Tenant JWT (`JWTAuthMiddleware`) | `Authorization: Bearer <tenant_jwt>` |
| `/api/rag/ingest-async`, `/api/rag/task/{id}` | Tenant JWT (`JWTAuthMiddleware`, `PROTECTED_EXACT`) | `Authorization: Bearer <tenant_jwt>` |
| `/api/gateway`, `/mcp` | API key | `x-api-key: <key>` |

Canonical analytics endpoints live under **`/api/rag/analytics/*`** (not `/api/v1/rag/analytics/*`).

---

## Parameters

`POST /api/v1/rag/chunk/semanticSearchForChat` request body:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `messageId` | string | ✅ Yes | - | Client message ID for query logging |
| `userQuery` | string | ✅ Yes | - | The search query text |
| `fileIds` | array[string] | No | `null` | UUID list to restrict search to specific files |
| `top_k` | integer | No | `5` | Number of results to return (1-50) |

> Graph expansion runs **unconditionally** when `ENABLE_CODE_GRAPH=true`; there is no per-request flag.  
> When `fileIds` is provided, BM25/hybrid search is disabled and vector-only search runs with `WHERE metadata->>'file_id' = ANY(fileIds)`.

---

## API Usage

### Basic Search

```bash
curl -X POST http://localhost:8001/api/v1/rag/chunk/semanticSearchForChat \
  -H "Authorization: Bearer <tenant_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "messageId": "msg-001",
    "userQuery": "explain authentication in Express.js",
    "top_k": 5
  }'
```

### Search with Graph Context Expansion

Graph expansion runs automatically when `ENABLE_CODE_GRAPH=true`; there is no per-request flag.

```bash
curl -X POST http://localhost:8001/api/v1/rag/chunk/semanticSearchForChat \
  -H "Authorization: Bearer <tenant_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "messageId": "msg-abc",
    "userQuery": "JWT token validation",
    "top_k": 5
  }'
```

### Search Scoped to Specific Files (fileIds filter)

When `fileIds` is provided, the search is restricted to those files and BM25/hybrid search is disabled (vector-only):

```bash
curl -X POST http://localhost:8001/api/v1/rag/chunk/semanticSearchForChat \
  -H "Authorization: Bearer <tenant_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "messageId": "msg-xyz",
    "userQuery": "cache TTL expiry",
    "fileIds": ["96af7ff2-...", "4009d097-..."],
    "top_k": 5
  }'
```

**Behaviour when `fileIds` present:**
- Vector-only search: `WHERE metadata->>'file_id' = ANY(fileIds)`
- BM25/hybrid fusion is skipped regardless of `ENABLE_HYBRID_SEARCH`
- Graph expansion still runs on the anchors if `ENABLE_CODE_GRAPH=true`
- ⚠️ Cross-file graph expansion will return 0 for inter-file call edges (see Issue #6 in [known_issues.md](./known_issues.md))

**Response (with expansion):**
```json
{
  "chunks": [
    {
      "id": "chunk-uuid-1",
      "fileId": "file-uuid",
      "filename": "auth.py",
      "fileType": "text/x-python",
      "fileUrl": "http://localhost:8001/static/...",
      "text": "def validate_token(token): ...",
      "similarity": 0.92,
      "pageNumber": null,
      "role": "entry",
      "is_graph_expansion": false,
      "expanded_from": null
    },
    {
      "id": "chunk-uuid-2",
      "fileId": "file-uuid-2",
      "filename": "utils.py",
      "fileType": "text/x-python",
      "fileUrl": "http://localhost:8001/static/...",
      "text": "def decode_jwt(token): ...",
      "similarity": 0.0,
      "pageNumber": null,
      "role": "supporting",
      "is_graph_expansion": true,
      "expanded_from": "tenant_id::auth.py::validate_token"
    }
  ],
  "queryId": "qid-abc123",
  "expansion_count": 1
}
```

### Async Ingestion

```bash
# Queue ingestion (JWT required — endpoint is in PROTECTED_EXACT)
curl -X POST http://localhost:8001/api/rag/ingest-async \
  -H "Authorization: Bearer <tenant_jwt>" \
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
Store in Vector DB (ChromaDB / Postgres pgvector)
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

**Structure:** `tenant::file::entity` (3 segments, enforced by `CodeGraph.add_node` — `src/agents/rag/graph/code_graph.py:44-47`)

**Examples:**
- `dev_user_1::auth.py::authenticate`
- `dev_user_1::utils.py::User.login`
- `dev_user_1::middleware.ts::validateRequest`

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

**Example (intra-file — works):**
```
Query: "authentication"
Match: auth.py::authenticate

BFS Traversal:
  Depth 0: auth.py::authenticate
  Depth 1: auth.py::validate_token (called by authenticate)
  Depth 2: auth.py::check_expiry (called by validate_token)

Result: 3 chunks (1 initial + 2 related)
```

**⚠️ Cross-file expansion (Issue #6 — open):**  
When entity A calls entity B imported from another file, the graph creates edge `file1.ts::A → file1.ts::B` (same source) rather than `file1.ts::A → file2.ts::B`. Since `file1.ts::B` has no pgvector entry, expansion returns 0 for these cross-file calls. See [known_issues.md — Issue #6](./known_issues.md#issue-6).

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
| pgvector | 0.2.5 | Postgres vector store (production default) |
| Qdrant Client | 1.16.1 | Legacy/optional (not selectable via `VECTOR_BACKEND`) |
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
RAG_SCORE_THRESHOLD = 0.0  # Minimum similarity score (0.0 = accept all results)
RERANK_SCORE_THRESHOLD = 0.3  # Minimum cross-encoder rerank score

# Vector backend
VECTOR_BACKEND = "postgres"  # one of: chroma | postgres

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
  "query": "database connection"
}
```

**Result:** Main DB functions + all calling functions discovered via graph

### 4. Async Bulk Ingestion

```bash
# Ingest entire codebase asynchronously
POST /api/rag/ingest-async
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

1. **Code Files** - Set `ENABLE_CODE_GRAPH=true` server-side; graph expansion runs unconditionally
2. **Async Ingestion** - Use `/api/rag/ingest-async` for large codebases (note: currently unauthenticated)
3. **Chunk Size** - 500 chars works well for text; code uses AST boundaries
4. **Top-K Selection** - Start with 5, increase if context is insufficient
5. **File Formats** - Code files (.py, .js, .ts) get AST parsing, others get text chunking
6. **Vector Store** - ChromaDB for dev, Postgres pgvector for production (Qdrant is legacy/optional)

---

## Troubleshooting (Updated)

**Issue:** Code files not parsed correctly  
**Solution:** Check Tree-sitter installation: `pip install tree-sitter tree-sitter-python`

**Issue:** `expansion_count` always 0 despite `ENABLE_CODE_GRAPH=true`  
**Root cause (fixed 2026-05-23):** Graph-expanded chunks enter with `rerank_score=0.0`. After reranking, they sort below all vector chunks and were cut by `filtered[:top_k]`. The fix appends graph extras after the top_k cut.  
**Resolution:** Fixed in `src/agents/rag/agent.py`. Ensure you are running the latest build.

**Issue:** `chunks: []` returned — all results empty  
**Likely cause:** Redis file metadata is absent. The orphan filter in `semantic_search_for_chat` drops any chunk whose `file_id` has no corresponding `file:<id>` key in Redis. This happens after a Redis flush or container restart without re-injecting metadata.  
**Workaround:** Re-upload files through the `/api/v1/rag/file/upload` endpoint so metadata is rebuilt, or inject Redis metadata manually.

**Issue:** Async tasks stuck in PENDING  
**Solution:** Check Celery worker and Redis: `celery -A src.workers.celery_app worker`

**Issue:** New file ingested but graph expansion ignores it  
**Status (fixed 2026-05-23):** `rag_tasks.py` now correctly invalidates `rag_graph:v2:{collection_name}` after each file ingest. If you are on an older build, flush manually: `redis-cli del rag_graph:v2:<collection_name>`. See [known_issues.md — Issue #1](./known_issues.md#issue-1).

**Issue:** `expansion_count` is 0 for cross-file calls (e.g. `UserRepository` calling `CacheStore` from another file)  
**Root cause (open — Issue #6):** `code_graph.py::add_node` resolves all call targets with the same source file path. When entity A in `file1.ts` calls entity B imported from `file2.ts`, the graph creates edge `file1.ts::A → file1.ts::B`, but `file1.ts::B` has no pgvector entry. `get_chunk_by_qualified_id` returns `None` → expansion silently skipped.  
**What works:** Intra-file BFS (entities calling other entities in the same file).  
**Workaround:** None currently. See [known_issues.md — Issue #6](./known_issues.md#issue-6).

**Issue:** `chunkingStatus: "success"` but results have no class/function chunks  
**Root cause (open — Issue #7):** The file status API returns `"success"` even when all chunks are text fallback (`ast_fallback=True`). This occurred for all TypeScript files before the 2026-05-24 AST fix.  
**Workaround:** Query `GET /api/v1/rag/file/{id}/chunks` and inspect `metadata.chunk_type` — all `"text"` means AST extraction failed. See [known_issues.md — Issue #7](./known_issues.md#issue-7).

**Issue:** Poor search results for code  
**Solution:** Ensure `ENABLE_CODE_GRAPH=true` server-side so graph expansion supplies related functions

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
curl -X POST http://localhost:8001/api/v1/rag/chunk/semanticSearchForChat \
  -H "Authorization: Bearer <tenant_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "messageId": "msg-001",
    "userQuery": "user authentication flow",
    "top_k": 5
  }'
```

### Ingest Code Repository

```bash
curl -X POST http://localhost:8001/api/rag/ingest-async \
  -H "Authorization: Bearer <tenant_jwt>" \
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




**Last Updated:** 2026-05-24  
**Version:** 1.3.0  
**Maintainer:** DevForge Team  
**Feedback:** Create an issue in the repository

---

## Changelog

### 2026-05-24 — v1.3.0

- **ingest-async auth corrected:** Endpoint is JWT-protected via `PROTECTED_EXACT` in `JWTAuthMiddleware`. All curl examples updated to include `Authorization: Bearer <tenant_jwt>`. Previous docs incorrectly said "unauthenticated".
- **Auth table corrected:** `/api/rag/ingest-async` row now shows correct JWT requirement.
- **Parameters table rewritten:** Now reflects actual `semanticSearchForChat` request body fields (`messageId`, `userQuery`, `fileIds`, `top_k`) instead of old internal tool params.
- **fileIds filter documented:** New section with curl example. Notes that fileIds disables BM25/hybrid and that cross-file graph expansion is still limited.
- **TypeScript AST fix noted:** Added note to Code-Aware Chunking section — TS files now produce `chunk_type=class/function` chunks correctly. `ast_fallback` field added to metadata example.
- **Cross-file expansion limitation (Issue #6):** Graph Traversal section updated with intra-file vs cross-file distinction. Troubleshooting entry added with root cause.
- **Issue #7 noted in troubleshooting:** `chunkingStatus: "success"` does not reveal text fallback; workaround via chunk inspection documented.
- **Celery cache key bug (Issue #1):** Troubleshooting entry updated from "open bug" to "fixed 2026-05-23".

### 2026-05-23 — v1.2.0: Graph expansion truncation fix + updated troubleshooting

- **Bug fixed:** `expansion_count` was always `0` because graph-expanded chunks (score=0.0) were cut by `filtered[:top_k]` after reranking. Fixed in `agent.py` — graph extras are now appended after the `top_k` cut.
- **Verified end-to-end:** `expansion_count: 1–2` confirmed in live API responses for queries like "bcrypt hash password" and "authenticate user validate credentials jwt".
- **Troubleshooting updated:** Added entries for the real root cause of `expansion_count=0`, orphan filter causing `chunks: []`, and the Celery cache key mismatch for new file ingestion.
- See [`known_issues.md`](./known_issues.md) for all open bugs with fix guidance.

### 2026-05-19 — v1.1.0: Graph Expansion Provenance Fields

- Added `is_graph_expansion: bool` to each `ChatFileChunk` in the response — `true` for BFS-expanded chunks, `false` for vector-retrieved chunks.
- Added `expanded_from: Optional[str]` to each `ChatFileChunk` — the anchor QID (`tenant::file::entity`) that triggered BFS expansion for this chunk; `null` for vector-retrieved chunks.
- Added `expansion_count: int` to `SemanticSearchResponse` — total number of graph-expanded chunks in the result set; `0` if graph expansion was not triggered or found no neighbors.
- Fixed response example: `expanded_from` is a **top-level chunk field**, not a metadata subfield. Previous docs showed it inside `metadata` — that was incorrect.
- Implementation: `src/storage/base_store.py` (`ChunkResult`), `src/agents/rag/agent.py` (`_expand_with_graph_context`), `src/api/schemas/rag.py` (`ChatFileChunk`, `SemanticSearchResponse`), `src/api/routers/rag.py` (router wiring). 8 unit tests in `tests/test_rag_graph_expansion.py`.
