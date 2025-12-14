"""RAG Celery tasks for async document processing.

Phase 10.1: Async ingestion with progress tracking and error isolation.

ARCHITECTURE COMPLIANCE (see docs/rag_architecture.md):
✅ Calls RAGAgent (NOT tools)
✅ No global graph references
✅ Uses async_to_sync wrapper
"""

import logging
from typing import List, Optional

from celery import shared_task
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


@shared_task(bind=True, soft_time_limit=300, max_retries=3, acks_late=True)
def async_ingest_documents(
    self,
    file_paths: List[str],
    collection_name: str = "devforge_docs",
    embed_model: str = "nomic-embed-text",
) -> dict:
    """
    Async document ingestion with per-file error isolation.
    
    ARCHITECTURE: Calls RAGAgent directly, NEVER tools.
    
    Args:
        file_paths: List of file paths to ingest
        collection_name: Target collection name
        embed_model: Embedding model to use
    
    Returns:
        Dictionary with ingestion results per file
    """
    # Import here to avoid circular imports
    from src.agents.rag.agent import RAGAgent
    
    logger.info(
        f"Starting async ingestion: {len(file_paths)} files",
        extra={"task_id": self.request.id, "collection": collection_name}
    )
    
    # Create agent instance (each task gets its own)
    agent = RAGAgent(collection_name=collection_name)
    
    results = []
    successful = 0
    failed = 0
    
    for i, file_path in enumerate(file_paths):
        # Update progress
        progress = {
            "current": i + 1,
            "total": len(file_paths),
            "file": file_path,
            "percent": int((i + 1) / len(file_paths) * 100),
        }
        self.update_state(state="PROGRESS", meta=progress)
        
        try:
            # CORRECT: Call agent method, NOT tool
            result = async_to_sync(agent.ingest_document)(
                file_path=file_path,
                embed_model=embed_model,
            )
            results.append({
                "file": file_path,
                "success": True,
                "chunks_created": result.get("chunks_created", 0),
            })
            successful += 1
            logger.info(f"Ingested: {file_path}")
            
        except Exception as e:
            # Per-file error isolation
            error_msg = str(e)
            results.append({
                "file": file_path,
                "success": False,
                "error": error_msg,
            })
            failed += 1
            logger.error(f"Failed to ingest {file_path}: {error_msg}")
    
    final_result = {
        "status": "completed",
        "task_id": self.request.id,
        "collection": collection_name,
        "total_files": len(file_paths),
        "successful": successful,
        "failed": failed,
        "results": results,
    }
    
    logger.info(
        f"Ingestion completed: {successful}/{len(file_paths)} successful",
        extra=final_result
    )
    
    return final_result


@shared_task(bind=True)
def health_check(self) -> dict:
    """Simple health check task for verifying Celery connectivity."""
    return {
        "status": "healthy",
        "task_id": self.request.id,
        "worker": self.request.hostname,
    }
