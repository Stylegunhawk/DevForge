"""API Key storage and validation logic.

Handles database operations for API keys and provides a high-performance 
cache-first validation layer using Redis.
"""

import json
import logging
import hashlib
import uuid
import dataclasses
from typing import Optional, Dict, List
from datetime import datetime, timezone

from src.storage.db import PostgresPoolManager
from src.core.config import settings

logger = logging.getLogger(__name__)

@dataclasses.dataclass
class APIKeyMetadata:
    """Metadata associated with an API key."""
    id: str
    name: str
    tenant_id: str
    integration_name: str
    tier: str
    scopes: List[str]
    is_active: bool
    user_id: Optional[str] = None

class APIKeyStore:
    """Handles API key storage, retrieval, and validation."""

    def __init__(self):
        self._initialized = False

    async def _ensure_initialized(self):
        """Lazy initialization of the database schema."""
        if not self._initialized:
            pool = await PostgresPoolManager.get_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS api_keys (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        key_hash TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        integration_name TEXT NOT NULL,
                        tier TEXT DEFAULT 'free',
                        scopes JSONB DEFAULT '[]'::jsonb,
                        tenant_id TEXT NOT NULL,
                        is_active BOOLEAN DEFAULT true,
                        last_used_at TIMESTAMP WITH TIME ZONE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP WITH TIME ZONE,
                        user_id UUID REFERENCES users(id) ON DELETE SET NULL
                    );
                """)
                await conn.execute("CREATE INDEX IF NOT EXISTS api_keys_key_hash_idx ON api_keys(key_hash);")
                await conn.execute("CREATE INDEX IF NOT EXISTS api_keys_integration_idx ON api_keys(integration_name);")
            self._initialized = True

    @staticmethod
    def _hash_key(key: str) -> str:
        """Hash a raw API key for secure storage."""
        return hashlib.sha256(key.encode()).hexdigest()

    async def validate_key(self, raw_key: str) -> Optional[APIKeyMetadata]:
        """Validate an API key, checking cache first.
        
        Args:
            raw_key: The raw API key string from the request header.
            
        Returns:
            APIKeyMetadata if valid, else None.
        """
        key_hash = self._hash_key(raw_key)
        
        # 1. Check Redis Cache
        # (Redis client used directly to avoid circular imports if any)
        try:
            from src.storage.redis_file_store import RedisFileStore
            redis = RedisFileStore().client
            cache_key = f"api_key:{key_hash}"
            cached_data = await redis.get(cache_key)
            
            if cached_data:
                logger.debug(f"API key cache hit for hash: {key_hash[:8]}")
                data = json.loads(cached_data)
                return APIKeyMetadata(**data)
        except Exception as e:
            logger.warning(f"Redis cache check failed for API key: {e}")

        # 2. Check Database
        await self._ensure_initialized()
        pool = await PostgresPoolManager.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, name, tenant_id, integration_name, tier, scopes, is_active, user_id "
                "FROM api_keys WHERE key_hash = $1 AND is_active = true",
                key_hash
            )
            
            if not row:
                return None

            metadata = APIKeyMetadata(
                id=str(row["id"]),
                name=row["name"],
                tenant_id=row["tenant_id"],
                integration_name=row["integration_name"],
                tier=row["tier"],
                scopes=json.loads(row["scopes"]),
                is_active=row["is_active"],
                user_id=str(row["user_id"]) if row["user_id"] else None
            )

            # 3. Update Cache
            try:
                await redis.setex(
                    cache_key,
                    settings.QUERY_CACHE_TTL if hasattr(settings, 'API_KEY_CACHE_TTL') else 300,
                    json.dumps(dataclasses.asdict(metadata))
                )
            except Exception as e:
                logger.warning(f"Failed to cache API key metadata: {e}")

            return metadata

    async def create_key(
        self, 
        name: str, 
        tenant_id: str, 
        integration_name: str, 
        tier: str = "free", 
        scopes: List[str] = None,
        user_id: str = None
    ) -> str:
        """Create a new API key.
        
        Returns:
            The raw API key string (only shown once).
        """
        import secrets
        raw_key = f"df_{secrets.token_urlsafe(32)}"
        key_hash = self._hash_key(raw_key)
        
        await self._ensure_initialized()
        pool = await PostgresPoolManager.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO api_keys (key_hash, name, tenant_id, integration_name, tier, scopes, user_id) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                key_hash, name, tenant_id, integration_name, tier, json.dumps(scopes or []), 
                uuid.UUID(user_id) if user_id else None
            )
        
        return raw_key

    async def list_keys(self) -> List[Dict]:
        """List metadata for all API keys."""
        await self._ensure_initialized()
        pool = await PostgresPoolManager.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, integration_name, tier, scopes, tenant_id, is_active, created_at, last_used_at, user_id "
                "FROM api_keys ORDER BY created_at DESC"
            )
            return [dict(r) for r in rows]

    async def list_user_keys(self, user_id: str) -> List[Dict]:
        """List API keys owned by a specific user."""
        await self._ensure_initialized()
        pool = await PostgresPoolManager.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, integration_name, tier, scopes, tenant_id, is_active, created_at, last_used_at "
                "FROM api_keys WHERE user_id = $1 ORDER BY created_at DESC",
                uuid.UUID(user_id)
            )
            return [dict(r) for r in rows]

    async def revoke_key(self, key_id: str):
        """Revoke (deactivate) an API key and purge cache."""
        await self._ensure_initialized()
        pool = await PostgresPoolManager.get_pool()
        async with pool.acquire() as conn:
            # Get hash first for cache clearing
            key_hash = await conn.fetchval("SELECT key_hash FROM api_keys WHERE id = $1", key_id)
            if not key_hash:
                return
                
            await conn.execute("UPDATE api_keys SET is_active = false WHERE id = $1", key_id)
            
            # Clear Redis Cache
            try:
                from src.storage.redis_file_store import RedisFileStore
                redis = RedisFileStore().client
                await redis.delete(f"api_key:{key_hash}")
            except Exception as e:
                logger.warning(f"Failed to clear Redis cache for revoked key {key_id}: {e}")

# Global instance
api_key_store = APIKeyStore()
