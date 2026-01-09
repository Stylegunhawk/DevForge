from typing import List, Optional
import asyncio
from celery import shared_task  # <--- Use this instead of importing 'app'
from pathlib import Path
import logging

from src.core.config import settings
from src.storage.redis_file_store import _update_file_status_sync
from src.agents.rag.agent import get_rag_agent

logger = logging.getLogger(__name__)

@shared_task  # <--- Decorator changed from @app.task to @shared_task
def async_ingest_documents(
    file_paths: List[str],
    file_id: str,
    tenant_id: str = "default",
    knowledge_id: Optional[str] = None,
    collection_name: str = "default_collection"
):
    """Async task for document ingestion with Multi-Tenant Isolation."""
    
    async def _ingest():
        try:
            # 1. Update status: processing
            _update_file_status_sync(file_id, {
                "chunkingStatus": "processing",
                "embeddingStatus": "processing"
            })

            # 2. Get Scoped Agent (Factory Pattern)
            agent = get_rag_agent(
                tenant_id=tenant_id, 
                collection_name=collection_name
            )
            
            # 3. Invalidate Graph Cache
            cache_key = f"rag_graph:{collection_name}"
            
            if settings.REDIS_URL:
                try:
                    import redis.asyncio as redis
                    r = redis.from_url(settings.REDIS_URL)
                    await r.delete(cache_key)
                    await r.close()
                    logger.info(f"Invalidated graph cache: {cache_key}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate graph cache: {e}")

            # 4. Ingest Files
            async def _ingest_all():
                total = 0
                for path in file_paths:
                    res = await agent.ingest_document(
                        file_path=path, 
                        file_id=file_id,
                        tenant_id=tenant_id,
                        knowledge_id=knowledge_id,
                        collection_name=collection_name
                    )
                    total += res.get("chunks_created", 0)
                return total

            chunks_created = await _ingest_all()
            
            # 5. Update status: success
            _update_file_status_sync(file_id, {
                "chunkingStatus": "success",
                "embeddingStatus": "success",
                "finishEmbedding": True,
                "chunkCount": chunks_created
            })
            
            return {
                "file_id": file_id, 
                "status": "success", 
                "chunks": chunks_created,
                "collection": collection_name
            }
            
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
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
            raise e

    # Run in async loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    return loop.run_until_complete(_ingest())