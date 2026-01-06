import uuid
from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException
from typing import List, Optional
from pathlib import Path

from datetime import datetime

from src.core.config import settings
from src.api.schemas.rag import *
from src.storage.redis_file_store import RedisFileStore
from src.agents.rag.agent import get_shared_rag_agent
from src.workers.tasks.rag_tasks import async_ingest_documents

router = APIRouter(prefix="/v1/rag", tags=["RAG"])
redis_store = RedisFileStore()

# ============================================================================
# 1. FILE UPLOAD
# ============================================================================

@router.post("/file/upload", response_model=FileUploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    collection: str = Form("default"),
    user_id: str = Header("default", alias="X-User-ID"),
):
    """
    Upload files and trigger async ingestion.
    Returns file metadata with 'pending' status.
    """
    results = []
    base_url = settings.FILE_BASE_URL
    storage_root = Path(settings.STORAGE_ROOT)
    
    for file in files:
        # Generate file ID
        file_id = str(uuid.uuid4())
        
        # Save file to disk
        user_dir = storage_root / user_id / collection
        user_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = user_dir / f"{file_id}_{file.filename}"
        content = await file.read()
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Detect MIME type
        import magic
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(str(file_path))
        
        # Create metadata matching FileListItem
        file_metadata = {
            "id": file_id,
            "name": file.filename,
            "size": len(content),
            "fileType": file_type,
            "url": f"{base_url}/{user_id}/{collection}/{file_id}_{file.filename}",
            "diskPath": str(file_path),  # Store real disk path
            
            # Initial status: pending
            "chunkingStatus": "pending",
            "embeddingStatus": "pending",
            "finishEmbedding": False,
            "chunkCount": 0,
            
            # Timestamps
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
        }
        
        # Save to Redis
        await redis_store.save_file_metadata(file_id, file_metadata)
        
        # Trigger async ingestion (Celery)
        async_ingest_documents.delay(
            file_paths=[str(file_path)],
            collection=f"user_{user_id}_{collection}",
            file_id=file_id
        )
        
        results.append(file_metadata)
    
    return {"files": results}

# ============================================================================
# 2. FILE STATUS POLLING
# ============================================================================

@router.get("/file/{file_id}", response_model=FileStatusResponse)
async def get_file_status(file_id: str):
    """
    Poll file processing status.
    Frontend calls this every 2 seconds until finishEmbedding=true.
    """
    metadata = await redis_store.get_file_metadata(file_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    return metadata

# ============================================================================
# 3. SEMANTIC SEARCH
# ============================================================================

@router.post("/chunk/semanticSearchForChat", response_model=SemanticSearchResponse)
async def semantic_search_for_chat(request: SemanticSearchRequest):
    """
    Semantic search with Phase 12A query intelligence.
    Returns chunks with fileId, fileUrl, and similarity.
    """
    # Get RAGAgent (your existing Phase 12A implementation)
    agent = get_shared_rag_agent()
    
    # Use rewritten query if available, else original
    query = request.rewriteQuery or request.userQuery
    
    # Filter by files if provided
    target_file_paths = None
    if request.fileIds:
        target_file_paths = []
        for fid in request.fileIds:
            meta = await redis_store.get_file_metadata(fid)
            if meta and "diskPath" in meta:
                target_file_paths.append(meta["diskPath"])
            # If default files missing diskPath (legacy), implementation could fallback here if needed,
            # but strictly adhering to "Store and use" for new consistency.
    
    # Phase 12A: retrieve_with_reranking (your existing method)
    result = await agent.retrieve_with_reranking(
        query=query,
        top_k=request.top_k,
        file_paths=target_file_paths,
        use_reranking=True
    )
    
    # Transform to ChatFileChunk format
    response_chunks = []
    
    for doc in result["documents"]:
        # Get file metadata from path
        file_path = doc.metadata.get("source", "")
        file_meta = await redis_store.get_file_metadata_by_path(file_path)
        
        # Fallback if file not in Redis (older files)
        if not file_meta:
            file_meta = {
                "id": "unknown",
                "name": Path(file_path).name,
                "fileType": "text/plain",
                "url": "",
            }
        
        response_chunks.append(ChatFileChunk(
            id=doc.metadata.get("chunk_id", str(uuid.uuid4())),
            fileId=file_meta["id"],
            filename=file_meta["name"],
            fileType=file_meta["fileType"],
            fileUrl=file_meta["url"],
            text=doc.page_content,
            similarity=float(doc.metadata.get("score", 0.0)),
            pageNumber=doc.metadata.get("page", None)
        ))
    
    # Generate query ID
    query_id = str(uuid.uuid4())
    
    # Save query metadata for deletion support
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
# 4. FILE DELETION (NEW!)
# ============================================================================

@router.delete("/file/{file_id}")
async def delete_file(file_id: str):
    """
    Delete file, metadata, and vector embeddings.
    Required by Lobe Chat file manager.
    """
    # Get metadata
    file_meta = await redis_store.get_file_metadata(file_id)
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Use stored diskPath instead of driving it
    file_path = file_meta.get("diskPath")
    
    if file_path:
        # Delete physical file
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception as e:
            print(f"Failed to delete file {file_path}: {e}")
        
        # Delete vector embeddings
        try:
            agent = get_shared_rag_agent()
            deleted_count = agent.vector_store.delete(
                filter={"source": file_path}
            )
        except Exception as e:
            print(f"Failed to delete vectors for {file_path}: {e}")
            deleted_count = 0
            
    else:
        # Should not happen for new files
        print(f"Warning: diskPath not found for file {file_id}")
        deleted_count = 0
    
    # Delete metadata
    await redis_store.delete_file_metadata(file_id)
    
    return {
        "success": True,
        "fileId": file_id,
        "deletedChunks": deleted_count
    }

# ============================================================================
# 5. QUERY DELETION (NEW!)
# ============================================================================

@router.delete("/message/{message_id}/query")
async def delete_message_query(message_id: str):
    """
    Delete RAG query associated with a message.
    Required by Lobe Chat when regenerating responses.
    """
    deleted_count = await redis_store.delete_queries_by_message(message_id)
    
    return {
        "success": True,
        "messageId": message_id,
        "deletedQueries": deleted_count
    }
