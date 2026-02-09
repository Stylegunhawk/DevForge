FINAL BACKEND IMPLEMENTATION PLAN v3.0
Compliance: Lobe Chat TypeScript Data Contracts ✅ Date: 2026-01-06 Status: Construction Ready

PHASE 1: Data Models (FastAPI)
We must define Pydantic models that mirror the Frontend Interfaces exactly.

File: src/api/schemas/rag.py

Python

from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union

# 1. Exact Status Enums (Case Sensitive!)
TaskStatus = Literal['pending', 'processing', 'success', 'error']

# 2. Error Structure
class AsyncTaskError(BaseModel):
    name: str = "ProcessingError"
    body: Union[str, dict]

# 3. File Item (Matches FileListItem)
class FileStatusResponse(BaseModel):
    id: str
    name: str  # Matches 'filename' in chunks, 'name' in list
    size: int
    url: str   # Critical for preview
    fileType: str # MIME type
    
    # Async Task Fields
    chunkCount: Optional[int] = 0
    chunkingStatus: TaskStatus = "pending"
    embeddingStatus: TaskStatus = "pending"
    finishEmbedding: bool = False # Critical: Controls polling stop
    
    chunkingError: Optional[AsyncTaskError] = None
    embeddingError: Optional[AsyncTaskError] = None

# 4. Chunk Response (Matches ChatFileChunk)
class ChatFileChunk(BaseModel):
    id: str
    fileId: str
    filename: str
    fileType: str
    fileUrl: str
    text: str
    similarity: float # Frontend will .toFixed(1)
    pageNumber: Optional[int] = None

class SemanticSearchResponse(BaseModel):
    chunks: List[ChatFileChunk]
    queryId: Optional[str] = None
PHASE 2: API Endpoints (Updated Logic)
2.1 File Upload (Initialize with 'pending')
Endpoint: POST /api/v1/rag/file/upload

Changes from v2.1:

Initial status is now pending (was idle).

Generates a static url for the file.

Python

@router.post("/api/v1/rag/file/upload", response_model=dict)
async def upload_files(
    files: List[UploadFile],
    collection: str = Form("default"),
    user_id: str = Header("default"),
):
    results = []
    base_url = "http://localhost:8000/static/uploads" # Configure this env var
    
    for file in files:
        file_id = str(uuid.uuid4())
        # ... [File saving logic same as v2.1] ...
        
        # Metadata matching FileListItem strictly
        file_metadata = {
            "id": file_id,
            "name": file.filename,
            "size": len(content),
            "fileType": file.content_type or "text/plain",
            "url": f"{base_url}/{user_id}/{collection}/{file_id}_{file.filename}",
            
            # CRITICAL: Start with 'pending'
            "chunkingStatus": "pending",
            "embeddingStatus": "pending", 
            "finishEmbedding": False,
            "chunkCount": 0
        }
        
        # Save to Redis and trigger Celery...
        # ...
        
    return {"files": results}
2.2 Polling Endpoint (Strict Status)
Endpoint: GET /api/v1/rag/file/{fileId}

Changes from v2.1:

Returns the specific Pydantic model.

Python

@router.get("/api/v1/rag/file/{file_id}", response_model=FileStatusResponse)
async def get_file_status(file_id: str):
    metadata = await redis_client.get(f"file:{file_id}")
    if not metadata:
        raise HTTPException(404, detail="File not found")
    
    data = json.loads(metadata)
    
    # Ensure finishEmbedding is boolean (Redis stores strings sometimes)
    if isinstance(data.get("finishEmbedding"), str):
        data["finishEmbedding"] = data["finishEmbedding"].lower() == "true"
        
    return data
2.3 Semantic Search (Field Mapping)
Endpoint: POST /api/v1/rag/chunk/semanticSearchForChat

Changes from v2.1:

Maps backend source path to frontend fileUrl.

Ensures similarity is float.

Python

@router.post("/api/v1/rag/chunk/semanticSearchForChat", response_model=SemanticSearchResponse)
async def semantic_search_for_chat(request: SemanticSearchRequest):
    # ... [Retrieval Logic Phase 12A] ...
    
    response_chunks = []
    for doc in result.documents:
        # Retrieve original file metadata from Redis to get URL/ID
        # (You need the helper function get_file_metadata_by_path)
        file_path = doc.metadata.get("source")
        file_meta = await get_file_metadata_by_path(file_path)
        
        response_chunks.append({
            "id": doc.metadata.get("chunk_id", str(uuid.uuid4())),
            "fileId": file_meta["id"] if file_meta else "unknown",
            "filename": file_meta["name"] if file_meta else Path(file_path).name,
            "fileType": file_meta["fileType"] if file_meta else "text/plain",
            "fileUrl": file_meta["url"] if file_meta else "",
            "text": doc.page_content,
            "similarity": float(doc.metadata.get("score", 0.0)),
            # Add page number if your PDF parser supports it
            "pageNumber": doc.metadata.get("page", 1) 
        })

    return {
        "chunks": response_chunks,
        "queryId": str(uuid.uuid4())
    }
PHASE 3: Celery Task (State Machine)
The state transitions must occur in the exact order the frontend expects.

File: src/workers/tasks/rag_tasks.py

Python

@shared_task
def async_ingest_documents(file_paths: List[str], collection: str, file_id: str):
    try:
        # 1. Update: Processing
        _update_file_status_sync(file_id, {
            "chunkingStatus": "processing",
            "embeddingStatus": "processing"
        })
        
        # ... [Run Ingestion Logic] ...
        
        # 2. Update: Success
        _update_file_status_sync(file_id, {
            "chunkingStatus": "success",
            "embeddingStatus": "success",
            "finishEmbedding": True, # CRITICAL: Triggers frontend stop
            "chunkCount": result.get("chunks_created", 0)
        })

    except Exception as e:
        # 3. Update: Error
        error_payload = {
            "name": type(e).__name__,
            "body": {"detail": str(e)}
        }
        _update_file_status_sync(file_id, {
            "chunkingStatus": "error",
            "embeddingStatus": "error",
            "chunkingError": error_payload,
            "finishEmbedding": False
        })
        raise
PHASE 4: Static File Serving (Required for fileUrl)
Since Lobe Chat needs to "preview" the file via fileUrl, your backend must serve the uploaded files.

File: src/main.py

Python

from fastapi.staticfiles import StaticFiles

# Mount the storage directory
app.mount("/static/uploads", StaticFiles(directory="/storage/users"), name="uploads")

# Security Note: In production, use S3 signed URLs or Nginx. 
# For this implementation, this enables the 'fileUrl' to work.
Integration Checklist for YOU
Enums: Verify your redis_client.set calls never use "idle" or "done". Only pending, processing, success.

MIME Types: When saving the file in upload_files, use python-magic or file.content_type to get accurate MIME types (e.g., application/pdf). Lobe uses this to select the icon.

URL Reachability: Ensure http://localhost:8000/static/uploads/... is reachable from your browser. If Lobe can't reach it, the preview modal will be blank.