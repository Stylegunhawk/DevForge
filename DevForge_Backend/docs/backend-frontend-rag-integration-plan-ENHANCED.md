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
