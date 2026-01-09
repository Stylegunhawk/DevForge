import uuid
import math
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
    Returns chunks with fileId, fileUrl, and normalized similarity.
    """
    # Get RAGAgent (your existing Phase 12A implementation)
    agent = get_shared_rag_agent()
    
    # Use rewritten query if available, else original
    query = request.rewriteQuery or request.userQuery
    
    # Phase 12A: retrieve_with_reranking
    result = await agent.retrieve_with_reranking(
        query=query,
        top_k=request.top_k,
        use_reranking=True
    )
    
    # Transform to ChatFileChunk format
    response_chunks = []
    
    # Use .get() for safety and handle both Dicts and Objects
    documents = result.get("documents", [])
    logging.info(f"[DEBUG] Search returned {len(documents)} documents")
    
    for i, doc in enumerate(documents):
        # --- NORMALIZATION LAYER ---
        if isinstance(doc, dict):
            metadata = doc.get("metadata", {})
            # ✅ FIX ISSUE 2: Defensive Content Extraction
            content = doc.get("content") or doc.get("page_content") or ""
            score = doc.get("score") or doc.get("similarity") or 0.0
            doc_id = doc.get("id")
        else:
            metadata = getattr(doc, "metadata", {})
            # ✅ FIX ISSUE 2: Defensive Content Extraction
            content = getattr(doc, "content", None) or getattr(doc, "page_content", "") or ""
            score = getattr(doc, "score", 0.0)
            doc_id = getattr(doc, "id", None)

        # 1. Normalize Similarity Score (Robust Fix)
        # ✅ FIX ISSUE 1: Distinguish Logits vs Distances vs Probabilities
        try:
            score_val = float(score)
            
            # Case A: Explicit Reranker Score (Logits)
            if metadata.get("rerank_score") is not None:
                normalized_score = _sigmoid(score_val)
                
            # Case B: Standard Cosine/Similarity [0.0 - 1.0]
            elif 0.0 <= score_val <= 1.0:
                normalized_score = score_val
                
            # Case C: Likely Distance (>1.0 usually means L2 distance)
            # Invert it so smaller distance = higher score
            else:
                normalized_score = 1 / (1 + abs(score_val))
                
        except (ValueError, TypeError):
            normalized_score = 0.0

        # 2. File ID Resolution
        file_id = metadata.get("file_id")
        file_meta = None
        
        if file_id:
            file_meta = await redis_store.get_file_metadata(file_id)
        
        if not file_meta:
            # Fallback path lookup
            path = metadata.get("source")
            if path:
                file_meta = await redis_store.get_file_metadata_by_path(path)
        
        # 3. Fallback Logic
        if not file_meta:
            # Note: This fallback indicates the chunk originated from a legacy ingestion path
            # (e.g. script-based, not API-driven) and confirms that only API-ingested 
            # files now produce valid metadata. This is expected behavior during migration.
            file_meta = {
                "id": file_id or "unknown",
                "name": Path(metadata.get("source", "unknown")).name,
                "fileType": "text/plain",
                "url": ""
            }

        # 4. Create Response Chunk
        # ✅ FIX ISSUE 3: Prefer chunk_id from metadata for consistency
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
            role=metadata.get("role", "supporting")  # Phase 13: Expose role
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
# 4. FILE DELETION
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
            agent.vector_store.delete_by_source(file_path)
        except Exception as e:
            print(f"Failed to delete vectors for {file_path}: {e}")
            
    else:
        print(f"Warning: diskPath not found for file {file_id}")
    
    # Delete metadata
    await redis_store.delete_file_metadata(file_id)
    
    return {
        "success": True,
        "fileId": file_id
    }

# ============================================================================
# 5. QUERY DELETION
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