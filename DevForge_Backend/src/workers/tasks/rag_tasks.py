from celery import shared_task
import asyncio
from pathlib import Path
from typing import List

from src.agents.rag.agent import get_shared_rag_agent
from src.storage.redis_file_store import _update_file_status_sync

@shared_task
def async_ingest_documents(file_paths: List[str], collection: str, file_id: str):
    """
    Celery task for async document ingestion.
    State transitions: pending → processing → success/error
    """
    try:
        # 1. Update status: processing
        _update_file_status_sync(file_id, {
            "chunkingStatus": "processing",
            "embeddingStatus": "processing"
        })
        
        # 2. Run ingestion (async wrapper for Celery sync context)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            agent = get_shared_rag_agent()
            
            # Your existing RAGAgent.ingest_document method
            result = loop.run_until_complete(
                agent.ingest_documents(
                    file_paths=file_paths,
                    collection_name=collection
                )
            )
            
            # 3. Update status: success
            _update_file_status_sync(file_id, {
                "chunkingStatus": "success",
                "embeddingStatus": "success",
                "finishEmbedding": True,  # ⚠️ CRITICAL: Stops frontend polling
                "chunkCount": result.get("chunks_created", 0)
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        # 4. Update status: error
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
        
        raise  # Re-raise for Celery retry logic
