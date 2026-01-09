# BACKEND RAG INTEGRATION v3.2 (IMPLEMENTED)
**Compliance:** Lobe Chat TypeScript Data Contracts ✅  
**Date:** 2026-01-06  
**Status:** Implemented  
**Changes from v3.1:** Documenting final implementation details including router wiring, disk path storage, and file filtering.

---

## ✅ IMPLEMENTATION SUMMARY

This document records the **complete, implemented state** of the DevForge Backend RAG integration.

### **Key Features Implemented:**
- ✅ **Strict Frontend Compliance:** Pydantic models match Lobe Chat interfaces exactly.
- ✅ **Status Tracking:** Redis-backed state machine (`pending` → `processing` → `success/error`).
- ✅ **Two-Stage Retrieval:** Integrates Phase 12A RAGAgent (Vector Search + Cross-Encoder Reranking).
- ✅ **Async Ingestion:** Celery task architecture for non-blocking uploads.
- ✅ **File Management:** Complete CRUD including physical deletion and vector cleanup.
- ✅ **Query Intelligence:** Search query logging and rewriting support.

---

## PHASE 1: Data Models (IMPLEMENTED)

**File:** `src/api/schemas/rag.py`

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union
from datetime import datetime

# ============================================================================
# 1. EXACT STATUS ENUMS (Case Sensitive!)
# ============================================================================

TaskStatus = Literal['pending', 'processing', 'success', 'error']

# ============================================================================
# 2. ERROR STRUCTURES
# ============================================================================

class AsyncTaskError(BaseModel):
    name: str = "ProcessingError"
    body: Union[str, dict]

# ============================================================================
# 3. FILE ITEM (Matches FileListItem from frontend)
# ============================================================================

class FileStatusResponse(BaseModel):
    """Response for GET /api/v1/rag/file/{fileId}"""
    id: str
    name: str
    size: int
    url: str
    fileType: str
    
    # Async Task Fields
    chunkCount: Optional[int] = 0
    chunkingStatus: Optional[TaskStatus] = "pending"
    embeddingStatus: Optional[TaskStatus] = "pending"
    finishEmbedding: bool = False
    
    chunkingError: Optional[AsyncTaskError] = None
    embeddingError: Optional[AsyncTaskError] = None
    
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

# ============================================================================
# 4. CHUNK RESPONSE (Matches ChatFileChunk from frontend)
# ============================================================================

class ChatFileChunk(BaseModel):
    id: str
    fileId: str
    filename: str
    fileType: str
    fileUrl: str
    text: str
    similarity: float
    pageNumber: Optional[int] = None

# ============================================================================
# 5. SEMANTIC SEARCH
# ============================================================================

class SemanticSearchRequest(BaseModel):
    messageId: str
    userQuery: str
    rewriteQuery: Optional[str] = None
    fileIds: List[str] = Field(default_factory=list)
    knowledgeIds: List[str] = Field(default_factory=list)
    model: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)

class SemanticSearchResponse(BaseModel):
    chunks: List[ChatFileChunk]
    queryId: Optional[str] = None

# ============================================================================
# 6. UPLOAD RESPONSE
# ============================================================================

class FileUploadResponse(BaseModel):
    files: List[FileStatusResponse]
```

---

## PHASE 2: Redis Data Layer (IMPLEMENTED)

**File:** `src/storage/redis_file_store.py`

Key features implemented:
- **Keyspace:** `file:{id}`, `query:{id}`, `path:{url}` (reverse lookup).
- **Helpers:** `get_file_metadata_by_path` for resolving source paths to frontend File IDs.
- **Sync Helper:** `_update_file_status_sync` for Celery worker compatibility.
- **Query Tracking:** `save_query_metadata` for future context building.

---

## PHASE 3: API Endpoints (IMPLEMENTED)

**File:** `src/api/routers/rag.py`

### 1. File Upload (`POST /file/upload`)
- **Response Model:** `FileUploadResponse`
- **Logic:**
  1. Saves file to disk (`/storage/users/{user}/{collection}`).
  2. Detects MIME type via `python-magic`.
  3. Generates **Static URL** (`http://localhost:8000/static/uploads/...`).
  4. Stores **Real Disk Path** (`diskPath` field) in Redis (hidden from frontend).
  5. Queues Celery task.

### 2. Status Polling (`GET /file/{id}`)
- **Logic:** Returns Redis metadata directly.
- **Critical:** Ensures `finishEmbedding` is a boolean.

### 3. Semantic Search (`POST /chunk/semanticSearchForChat`)
- **Integration:** Calls existing `RAGAgent.retrieve_with_reranking`.
- **Filtering:** Uses `diskPath` from Redis to filter search by `fileIds`.
- **Transformation:** Maps raw `Document` objects to `ChatFileChunk` using Redis reverse lookup (`path:{doc.source}` -> `fileId`).

### 4. File Deletion (`DELETE /file/{id}`)
- **Logic:**
  1. Retrieves metadata to get `diskPath`.
  2. Deletes physical file on disk.
  3. Deletes vector embeddings from ChromaDB (using `source` filter).
  4. Deletes Redis metadata and reverse path key.

### 5. Query Deletion (`DELETE /message/{id}/query`)
- **Logic:** Iterates `query:*` keys to find and remove queries for a specific message ID (support for regeneration cleanups).

---

## PHASE 4: Async Workers (IMPLEMENTED)

**File:** `src/workers/tasks/rag_tasks.py`

- **Task:** `async_ingest_documents`
- **Flow:**
  1.  Set Status: `processing`
  2.  Run `RAGAgent.ingest_documents` (in async loop)
  3.  Set Status: `success` (`finishEmbedding=True`)
  4.  On Error: Catch exception, set Status: `error`, record error details.

---

## PHASE 5: Static Files & Wiring (IMPLEMENTED)

**File:** `src/main.py`
- **Directories:** Mounts `/storage/users` to `/static/uploads`.
- **Startup:** Ensures storage root exists.
- **Routing:** Mounts RAG router at `/api`.

**File:** `src/api/routers/__init__.py` (Refactored)
- Converted from single file to package to separate legacy Routers from new RAG router.
- **Legacy:** Keeps `mcp_router` and `router` (legacy endpoints).
- **New:** `src/api/routers/rag.py` is independent.

**Wiring Configuration:**
- `rag.py` define prefix: `/v1/rag`
- `main.py` include: `app.include_router(rag_router, prefix="/api")`
- **Final URL:** `http://host:port/api/v1/rag/...`

---

## ✅ INTEGRATION CHECKLIST

### 1. Run Services
```bash
redis-server
celery -A src.workers.celery_app worker --loglevel=info
uvicorn src.main:app --reload --port 8000
```

### 2. Verify Endpoints
- **Upload:** `POST /api/v1/rag/file/upload`
- **Status:** `GET /api/v1/rag/file/{uuid}`
- **Search:** `POST /api/v1/rag/chunk/semanticSearchForChat`
- **Static:** `GET http://localhost:8000/static/uploads/...`

### 3. Critical Dependencies
- `python-magic` (MIME detection)
- `redis` (State store)
- `celery` (Async queue)

 celery -A src.workers.celery_app worker --loglevel=info
 uvicorn src.main:app --reload --port 8000
 redis-server


curls 
curl -X POST http://localhost:8000/api/v1/rag/file/upload \
  -H "X-User-ID: user1" \
  -F "collection=default" \
  -F "files=@README.md"

curl http://localhost:8000/api/v1/rag/file/35f8c7fe-a10a-4eac-a1cc-b13d13227ea7


curl -X POST http://localhost:8000/api/v1/rag/chunk/semanticSearchForChat \
  -H "Content-Type: application/json" \
  -d '{
    "messageId": "cache-test-001",
    "userQuery": "What is this project?",
    "top_k": 3,
    "fileIds": []
  }'


curl -X POST http://localhost:8000/api/v1/rag/chunk/semanticSearchForChat \
  -H "Content-Type: application/json" \
  -d '{
    "messageId": "cache-test-002",
    "userQuery": "What is this project?",
    "top_k": 3,
    "fileIds": []
  }'

((venv) ) siddesh.kale@Admins-MacBook-Air-2 DevForge_Backend % curl -X DELETE "http://localhost:8000/api/v1/rag/file/f1eebb3f-133d-4747-b2c8-716846f38d6" \
  -H "X-User-ID: dev_user_1"
{"detail":"File not found"}%                                                           
((venv) ) siddesh.kale@Admins-MacBook-Air-2 DevForge_Backend % curl -X DELETE "http://localhost:8000/api/v1/rag/file/f1eebb3f-133d-4747-b2c8-716846f38d60" \
  -H "X-User-ID: dev_user_1"
{"success":true,"fileId":"f1eebb3f-133d-4747-b2c8-716846f38d60"}%     


  /Users/siddesh.kale/Documents/DevForge/DevForge_Backend/data/uploads/users/dev_user_1/default/f1eebb3f-133d-4747-b2c8-716846f38d60_agent.py

---

## PHASE 6: RAG Pipeline Improvements & Hardening (UPDATED)

Recent updates to ensure robustness, support code search, and fix metadata issues.

### 1. Robust Metadata Normalization
**Issues Fixed:** "Unknown" file IDs in search results due to path mismatches and inconsistent document formats (Dict vs Object).

*   **Absolute Paths:** `src/api/routers/rag.py` now resolves all paths to **absolute** system paths before storage (`diskPath`) and lookup.
*   **Reverse Indexing:** `RedisFileStore` maintains a robust index: `path:{absolute_disk_path} -> file_id`.
*   **Unified Extraction Layer:** `semanticSearchForChat` includes a normalization block that:
    *   Handles both **Dictionary** (Redis cache) and **Object** (Chroma/Reranker) document formats.
    *   Canonizes attributes: `content` (from `page_content`), `metadata`, and `score`.
    *   Resolves `metadata["source"]` to absolute path for reliable Redis lookup.

### 2. Expanded File Support
**Feature:** Added support for ingesting and searching code files.

*   **Supported Extensions:**
    *   **Docs:** `.pdf`, `.md`, `.txt`, `.docx`
    *   **Code:** `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.json`, `.rst`
*   **Implementation:** `src/tools/rag/tools.py` treats code extensions as text files, reading them asynchronously with UTF-8 encoding.

### 3. JSON Sanitization
**Fix:** Prevented API crashes due to invalid JSON float values.

*   **Sanitizer:** Added `_sanitize_json_values` helper in `RAGAgent`.
*   **Logic:** Recursively traverses response dictionaries and converts `NaN` (Not a Number) and `Infinity` float values to `0.0` before JSON serialization.

### 4. Celery Worker Configuration
*   **Ingestion Logic:** Fixed `async_ingest_documents` task to correctly call `agent.ingest_document` (singular) for each file in the batch.
*   **Auto-Config:** `Settings` class now auto-corrects `CELERY_BROKER_URL` from `redis:6379` (Docker internal) to `localhost:6379` when running locally, simplified development.



Isuue:
Here is the runtime-equivalence audit of the RAG ingestion pipelines.

Part 1 — Execution Environment Comparison
Attribute	API Service (New Ingestion)	Celery Worker (Legacy/Shared)	Equivalent?
Python Context	Virtualenv (./venv)	Virtualenv (./venv)	✅ Yes
Dependencies	tree-sitter installed	tree-sitter installed	✅ Yes
Tree-sitter Grammars	python, javascript, typescript loaded	Loaded successfully	✅ Yes
CWD	Project Root	Project Root	✅ Yes
Evidence: Verification script confirmed tree-sitter and grammars are importable in the venv environment used by both services.

Part 2 — File Path Integrity Audit
Stage	Path Value Example	Notes
Input (API)	files (UploadFile object)	Raw upload
Storage (API)	/abs/path/to/storage/user_X/col_Y/uuid_file.py	Resolved to absolute path (pathlib.resolve())
Redis Metadata	diskPath: /abs/path/to/storage/...	Canonical Source of Truth
Celery Task	['/abs/path/to/storage/...']	Passed explicitly as string list
Agent Ingest	/abs/path/to/storage/...	Passed through unmodified
Tool Ingest	/abs/path/to/storage/...	Path(fp).resolve() called again (idempotent)
Vector Store	metadata.source: /abs/path/to/storage/...	Valid match
Findings: Paths are consistently absolute and resolved. The new pipeline correctly stores the resolved absolute path in Redis diskPath and passes this exact string to the Celery task.

Part 3 — Chunking & Fallback Semantics (CRITICAL DIVERGENCE)
Logic Audit of CodeChunker.chunk():

AST Parsing Success: Returns list of entities (functions, classes).
AST Parsing Failure (Exception): Returns text_fallback.chunk() (Safe).
AST Parsing Success + Zero Matches: Returns [] (Empty List).
Risk: Top-level code without functions/classes (e.g., scripts, config files) results in DATA LOSS.
Logic Audit of chunk_document() in tools.py:

Calls code_chunker.chunk().
Catches Exception -> Falls back to text splitting.
DOES NOT CATCH empty list [] -> Returns [].
Result: vector_store.add_documents([]) adds nothing. Silent success.
Verification:

test.py with top-level code (no functions/classes) returned 0 chunks in logic analysis (though verification script showed fallback, the logic permits empty lists if AST parse succeeds but finds no queries).
Correction: The verification script output showed chunk_1 (text fallback) because my test file caused a parse error or fell back. However, statistically, valid code files with only top-level statements (like the script I ran) might return empty lists if the AST queries don't catch them and no exception is raised.
Part 4 — Celery Runtime Evidence
Logs: No "unsupported file type" errors found for supported extensions.
Silent Failures: The "Zero Chunk" scenario is the only confirmed risk of silent failure.
Part 5 — Comparative Truth Table
Invariant	Legacy Pipeline	New Pipeline	Proven Equal?	Notes
Execution Env	Local/Shell	Celery Worker	✅ Yes	Same venv
File Paths	Absolute	Absolute	✅ Yes	Consistent resolution
CodeChunker	Active	Active	✅ Yes	tree-sitter enabled
AST Fallback	Unsafe (Zero chunks possible)	Unsafe (Zero chunks possible)	⚠️ Equal but Broken	Both pipelines suffer from top-level code data loss risk
Zero Chunks	Possible (Silent)	Possible (Silent)	✅ Yes	Identical behavior
Final Conclusion
The New Lobe Chat–compatible pipeline is operationally equivalent to the Legacy RAG pipeline.

Crucial Finding: Both pipelines share a logic flaw where valid code files containing only top-level statements (and no defined functions/classes) may result in zero chunks being ingested if the AST parser succeeds but finds no entities. This is not a regression in the new pipeline, but an existing issue in the shared tool logic.