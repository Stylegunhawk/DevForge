import uuid
from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException
from typing import List, Optional
from pathlib import Path
import logging
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
            "diskPath": str(file_path.resolve()),  # Store absolute resolved path
            
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
    
    # NOTE: File filtering logic is prepared but disabled until Agent supports it
    # target_file_paths = ... (logic is fine, just unused for now)
    
    # Phase 12A: retrieve_with_reranking
    result = await agent.retrieve_with_reranking(
        query=query,
        top_k=request.top_k,
        # file_paths=target_file_paths,
        use_reranking=True
    )
    
    # Transform to ChatFileChunk format
    response_chunks = []
    
    # Use .get() for safety and handle both Dicts and Objects
    documents = result.get("documents", [])
    logging.info(f"[DEBUG] Search returned {len(documents)} documents")
    
    for i, doc in enumerate(documents):
        # --- NORMALIZATION LAYER ---
        # 1. canonize attributes
        doc_obj = doc if not isinstance(doc, dict) else None
        doc_dict = doc if isinstance(doc, dict) else None
        
        # Extract metadata
        if doc_dict:
            metadata = doc_dict.get("metadata") or {}
        else:
            metadata = getattr(doc_obj, "metadata", {}) or {}
            
        # Extract content (try multiple keys)
        if doc_dict:
            content = doc_dict.get("content") or doc_dict.get("page_content") or ""
        else:
            content = getattr(doc_obj, "content", None) or getattr(doc_obj, "page_content", "") or ""
            
        # Extract score
        if doc_dict:
            score = doc_dict.get("score") or doc_dict.get("similarity") or 0.0
        else:
            score = getattr(doc_obj, "score", None) or getattr(doc_obj, "similarity", 0.0)

        # 2. Resolve Path
        source_path = metadata.get("source", "")
        resolved_path = None
        
        if source_path:
            try:
                # Resolve to absolute path for Redis lookup
                resolved_path = str(Path(source_path).resolve())
            except Exception as e:
                logging.warning(f"Path resolution failed for '{source_path}': {e}")
                resolved_path = source_path # Fallback

        # Debug logs
        logging.info(f"[DEBUG] Doc {i}: type={type(doc)}, content_len={len(content)}, score={score}")
        logging.info(f"[DEBUG] Doc {i} path: source='{source_path}' -> resolved='{resolved_path}'")
        
        # 3. Redis Lookup
        file_meta = None
        if resolved_path:
            file_meta = await redis_store.get_file_metadata_by_path(resolved_path)
            
        logging.info(f"[DEBUG] Redis lookup result: {'FOUND' if file_meta else 'MISSING'}")
        
        # 3. Fallback logic
        if not file_meta:
            file_meta = {
                "id": "unknown",
                "name": Path(source_path).name if source_path else "unknown",
                "fileType": "text/plain",
                "url": "",
            }
        
        # 4. Create Response Chunk
        response_chunks.append(ChatFileChunk(
            id=metadata.get("chunk_id", str(uuid.uuid4())),
            fileId=file_meta["id"],
            filename=file_meta["name"],
            fileType=file_meta["fileType"],
            fileUrl=file_meta["url"],
            text=content,
            similarity=float(score),
            pageNumber=metadata.get("page", None)
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
