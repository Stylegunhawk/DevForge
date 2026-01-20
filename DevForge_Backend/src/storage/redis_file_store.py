import json
import redis.asyncio as redis
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime
from src.core.config import settings

class RedisFileStore:
    """
    Manages file metadata in Redis.
    Key structure:
        file:{file_id} → FileStatusResponse JSON
        path:{file_path} → file_id (reverse lookup)
        query:{query_id} → QueryMetadata JSON
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        # Fallback priority: explicit arg > REDIS_URL > CELERY_BROKER_URL > default
        self.redis_url = (
            redis_url 
            or settings.REDIS_URL 
            or settings.CELERY_BROKER_URL 
            or "redis://localhost:6379/0"
        )
        self.client = redis.from_url(self.redis_url, decode_responses=True)
    
    # ========================================================================
    # FILE METADATA CRUD
    # ========================================================================
    
    async def save_file_metadata(
        self, 
        file_id: str, 
        metadata: Dict,
        ttl: int = 86400 * 7  # 7 days
    ) -> None:
        """Save file metadata to Redis"""
        await self.client.set(
            f"file:{file_id}",
            json.dumps(metadata),
            ex=ttl
        )
        
        # Reverse lookup: path → file_id
        if "url" in metadata:
            await self.client.set(
                f"path:{metadata['url']}",
                file_id,
                ex=ttl
            )
        
        # Reverse lookup: diskPath → file_id (for RAG retrieval)
        if "diskPath" in metadata:
            await self.client.set(
                f"path:{metadata['diskPath']}",
                file_id,
                ex=ttl
            )
    
    async def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        """Get file metadata by ID"""
        data = await self.client.get(f"file:{file_id}")
        if not data:
            return None
        
        result = json.loads(data)
        
        # Ensure finishEmbedding is boolean
        if isinstance(result.get("finishEmbedding"), str):
            result["finishEmbedding"] = result["finishEmbedding"].lower() == "true"
        
        return result
    
    async def get_file_metadata_by_path(self, file_path: str) -> Optional[Dict]:
        """
        ⚠️ CRITICAL: Maps file path → file metadata
        Required for semantic search to return fileId/fileUrl
        """
        # Get file_id from reverse lookup
        file_id = await self.client.get(f"path:{file_path}")
        if not file_id:
            return None
        
        return await self.get_file_metadata(file_id)
    
    async def update_file_status(self, file_id: str, updates: Dict) -> None:
        """Update specific fields in file metadata"""
        metadata = await self.get_file_metadata(file_id)
        if not metadata:
            raise ValueError(f"File {file_id} not found")
        
        metadata.update(updates)
        await self.save_file_metadata(file_id, metadata)
    
    async def delete_file_metadata(self, file_id: str) -> None:
        """Delete file metadata and reverse lookup"""
        metadata = await self.get_file_metadata(file_id)
        if metadata and "url" in metadata:
            await self.client.delete(f"path:{metadata['url']}")
        
        await self.client.delete(f"file:{file_id}")
    
    # ========================================================================
    # QUERY METADATA CRUD
    # ========================================================================
    
    async def save_query_metadata(
        self,
        query_id: str,
        message_id: str,
        user_query: str,
        rewrite_query: Optional[str],
        chunk_ids: List[str],
        ttl: int = 86400  # 1 day
    ) -> None:
        """Save RAG query metadata for tracking"""
        query_data = {
            "id": query_id,
            "messageId": message_id,
            "userQuery": user_query,
            "rewriteQuery": rewrite_query,
            "chunkIds": chunk_ids,
            "createdAt": datetime.utcnow().isoformat()
        }
        
        await self.client.set(
            f"query:{query_id}",
            json.dumps(query_data),
            ex=ttl
        )
    
    async def delete_queries_by_message(self, message_id: str) -> int:
        """
        Delete all queries associated with a message.
        Returns number of queries deleted.
        """
        deleted_count = 0
        
        # Iterate through all query keys
        async for key in self.client.scan_iter("query:*"):
            try:
                query_data = await self.client.get(key)
                if not query_data:
                    continue
                
                data = json.loads(query_data)
                if data.get("messageId") == message_id:
                    await self.client.delete(key)
                    deleted_count += 1
            except Exception as e:
                print(f"Error processing query key {key}: {e}")
                continue
        
        return deleted_count

# ========================================================================
# SYNC HELPER (for Celery tasks)
# ========================================================================

def _update_file_status_sync(file_id: str, updates: Dict):
    """Synchronous file status update for Celery tasks"""
    import redis
    
    # Use settings to determine URL
    redis_url = (
        settings.REDIS_URL 
        or settings.CELERY_BROKER_URL 
        or "redis://localhost:6379/0"
    )
    
    client = redis.from_url(redis_url, decode_responses=True)
    
    # Get current metadata
    data = client.get(f"file:{file_id}")
    if not data:
        return
    
    metadata = json.loads(data)
    metadata.update(updates)
    
    # Save back with same TTL
    client.set(f"file:{file_id}", json.dumps(metadata), ex=86400 * 7)
