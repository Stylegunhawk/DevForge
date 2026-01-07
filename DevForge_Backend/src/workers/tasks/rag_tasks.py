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
            
            # Wrapper for multiple files ingestion
            async def _ingest_all():
                total = 0
                for path in file_paths:
                    res = await agent.ingest_document(file_path=path)
                    total += res.get("chunks_created", 0)
                return total

            total_chunks = loop.run_until_complete(_ingest_all())
            
            # 3. Update status: success
            _update_file_status_sync(file_id, {
                "chunkingStatus": "success",
                "embeddingStatus": "success",
                "finishEmbedding": True,  # ⚠️ CRITICAL: Stops frontend polling
                "chunkCount": total_chunks
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
