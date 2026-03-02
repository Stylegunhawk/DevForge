import uuid
import math
import logging
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException

from src.core.config import settings
from src.api.schemas.rag import *
from src.storage.redis_file_store import RedisFileStore
from src.agents.rag.agent import get_rag_agent
from src.workers.tasks.rag_tasks import async_ingest_documents

router = APIRouter(prefix="/v1/rag", tags=["RAG"])
redis_store = RedisFileStore()
logger = logging.getLogger(__name__)

def _sigmoid(x: float) -> float:
    """Normalize raw logits (e.g. 351.63) to 0-1 range for UI display."""
    try:
        return 1 / (1 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0

# ============================================================================
# 1. FILE UPLOAD
# ============================================================================

@router.post("/file/upload", response_model=FileUploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    collection: str = Form("default"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Upload files and trigger async ingestion.
    Returns file metadata with 'pending' status.
    """
    tenant_id = x_user_id or "default"
    collection_name = f"user_{tenant_id}"
    
    results = []
    
    for file in files:
        file_id = str(uuid.uuid4())
        
        # Determine paths with isolation
        upload_dir = Path("data/uploads/users") / tenant_id / collection
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        safe_filename = f"{file_id}_{file.filename}"
        file_path = upload_dir / safe_filename
        
        # Save file to disk
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Detect MIME type
        import magic
        mime = magic.Magic(mime=True)
        file_type = mime.from_buffer(content)
            
        file_url = f"{settings.FILE_BASE_URL}/users/{tenant_id}/{collection}/{safe_filename}"
        
        # Initialize metadata in Redis (Replacing broken init_file_status)
        file_meta = {
            "id": file_id,
            "name": file.filename,
            "size": len(content),
            "url": file_url,
            "diskPath": str(file_path),
            "fileType": file_type,
            "tenant_id": tenant_id,
            "collection_name": collection_name,
            "chunkCount": 0,
            "chunkingStatus": "pending",
            "embeddingStatus": "pending",
            "finishEmbedding": False,
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat()
        }
        await redis_store.save_file_metadata(file_id, file_meta)
        
        # Trigger async ingestion
        async_ingest_documents.delay(
            file_paths=[str(file_path)],
            file_id=file_id,
            tenant_id=tenant_id,
            collection_name=collection_name
        )
        
        results.append(file_meta)
        
    return {"files": results}


# ============================================================================
# 2. FILE STATUS POLLING
# ============================================================================

@router.get("/file/{file_id}")
async def get_file_metadata(file_id: str):
    """
    Get file processing status.
    """
    status = await redis_store.get_file_metadata(file_id)
    if not status:
        # Compatibility: check get_file_metadata if get_file_metadata (alias) fails
        status = await redis_store.get_file_metadata(file_id)
        
    if not status:
        raise HTTPException(status_code=404, detail="File not found")
    return status

@router.get("/file/{file_id}/chunks", response_model=SemanticSearchResponse)
async def get_file_chunks(
    file_id: str,
    limit: int = 5,
    offset: int = 0,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Get all chunks for a specific file, ordered by chunk_index.
    """
    tenant_id = x_user_id or "default"
    collection_name = f"user_{tenant_id}"
    
    # Verify file exists and belongs to tenant
    file_meta = await redis_store.get_file_metadata(file_id)
    if not file_meta or file_meta.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="File not found or access denied")
    
    agent = get_rag_agent(tenant_id=tenant_id, collection_name=collection_name)
    chunks = await agent.get_file_chunks(file_id=file_id, limit=limit, offset=offset)
    
    response_chunks = []
    for doc in chunks:
        metadata = doc.get("metadata", {})
        content = doc.get("content") or ""
        
        response_chunks.append(ChatFileChunk(
            id=doc.get("id") or str(uuid.uuid4()),
            fileId=file_id,
            filename=file_meta["name"],
            fileType=file_meta["fileType"],
            fileUrl=file_meta["url"],
            text=content,
            similarity=1.0,  # Full relevance (direct selection)
            pageNumber=metadata.get("page", None),
            role=metadata.get("role", "supporting")
        ))
    
    return SemanticSearchResponse(
        chunks=response_chunks,
        queryId=None  # No query tracking for direct chunk retrieval
    )

@router.get("/files", response_model=List[FileStatusResponse])
async def get_all_files(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Get all files for the current tenant.
    Returns file metadata with processing status for each file.
    """
    tenant_id = x_user_id or "default"
    files = await redis_store.get_all_files_for_tenant(tenant_id)
    return files

# ============================================================================
# 3. SEMANTIC SEARCH
# ============================================================================

@router.post("/chunk/semanticSearchForChat", response_model=SemanticSearchResponse)
async def semantic_search_for_chat(
    request: SemanticSearchRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Semantic search with strict filtering for orphaned/phantom chunks.
    """
    tenant_id = x_user_id or "default"
    collection_name = f"user_{tenant_id}"
    
    agent = get_rag_agent(tenant_id=tenant_id, collection_name=collection_name)
    query = request.rewriteQuery or request.userQuery
    
    result = await agent.retrieve_with_reranking(
        query=query,
        top_k=request.top_k,
        use_reranking=True
    )
    
    response_chunks = []
    documents = result.get("documents", [])
    
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

        # 🛑 STRICT FILTER 1: Drop empty content
        if not content or not str(content).strip():
            continue

        # 2. Normalize Similarity Score
        try:
            score_val = float(score)
            if metadata.get("rerank_score") is not None:
                normalized_score = _sigmoid(score_val)
            elif 0.0 <= score_val <= 1.0:
                normalized_score = score_val
            else:
                normalized_score = 1 / (1 + abs(score_val))
        except (ValueError, TypeError):
            normalized_score = 0.0

        # 3. Resolve File Metadata
        file_id = metadata.get("file_id")
        file_meta = None
        
        if file_id:
            file_meta = await redis_store.get_file_metadata(file_id)
        
        if not file_meta and metadata.get("source"):
            file_meta = await redis_store.get_file_metadata_by_path(metadata.get("source"))
        
        # 🛑 STRICT FILTER 2: Drop Orphans (Deleted Files)
        # If Redis has no record of this file, it means the file was deleted.
        # We skip it so the UI doesn't show a broken "unknown" citation.
        if not file_meta:
            continue
            
        # 🛑 STRICT FILTER 3: Drop Malformed/Legacy Data
        if file_meta.get("id") == "unknown" or not file_meta.get("url"):
             continue

        final_chunk_id = metadata.get("chunk_id") or doc_id or str(uuid.uuid4())

        response_chunks.append(ChatFileChunk(
            id=final_chunk_id,
            fileId=file_meta["id"],
            filename=file_meta["name"],
            fileType=file_meta["fileType"],
            fileUrl=file_meta["url"],
            text=content,
            similarity=float(normalized_score),
            pageNumber=metadata.get("page", None),
            role=metadata.get("role", "supporting")
        ))
    
    query_id = str(uuid.uuid4())
    await redis_store.save_query_metadata(
        query_id=query_id,
        message_id=request.messageId,
        user_query=request.userQuery,
        rewrite_query=request.rewriteQuery,
        chunk_ids=[chunk.id for chunk in response_chunks]
    )
    
    return SemanticSearchResponse(
        chunks=response_chunks,
        queryId=query_id
    )
    
# ============================================================================
# 4. FILE DELETION
# ============================================================================

@router.delete("/file/{file_id}")
async def delete_file(file_id: str):
    """
    Delete file, metadata, and vector embeddings accurately using the factory.
    """
    file_meta = await redis_store.get_file_metadata(file_id)
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = file_meta.get("diskPath")
    tenant_id = file_meta.get("tenant_id", "default")
    collection_name = file_meta.get("collection_name", f"user_{tenant_id}")
    
    if file_path:
        # Delete from disk
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
        
        # Delete from Vector Store using the FACTORY
        try:
            agent = get_rag_agent(tenant_id=tenant_id, collection_name=collection_name)
            await agent.vector_store.delete_by_source(file_path, tenant_id=tenant_id, collection_name=collection_name)
            # Invalidate graph for this collection
            agent._code_graph = None
        except Exception as e:
            logger.error(f"Failed to delete vectors for {file_path}: {e}")
            
    # Delete metadata
    await redis_store.delete_file_metadata(file_id)
    
    return {"success": True, "fileId": file_id}

# ============================================================================
# 5. QUERY DELETION
# ============================================================================

@router.delete("/message/{message_id}/query")
async def delete_message_query(message_id: str):
    """
    Delete RAG query associated with a message.
    """
    deleted_count = await redis_store.delete_queries_by_message(message_id)
    return {"success": True, "messageId": message_id, "deletedQueries": deleted_count}