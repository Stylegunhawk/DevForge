"""API Key storage and validation logic.

Handles database operations for API keys and provides a high-performance 
cache-first validation layer using Redis.
"""

import json
import logging
import hashlib
import uuid
import dataclasses
from typing import Optional, Dict, List, Any
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
    expires_at: Optional[datetime] = None
    expiry_duration: Optional[str] = None
    hourly_limit_override: Optional[int] = None
    monthly_limit_override: Optional[int] = None

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
        
        # 1. Check Redis Cache (v2 with user_id support)
        # (Redis client used directly to avoid circular imports if any)
        try:
            from src.storage.redis_file_store import RedisFileStore
            redis = RedisFileStore().client
            cache_key = f"api_key:v2:{key_hash}"  # v2 prefix with user_id support
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
                "SELECT id, name, tenant_id, integration_name, tier, scopes, is_active, user_id, expires_at, expiry_duration, hourly_limit_override, monthly_limit_override "
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
                user_id=str(row["user_id"]) if row["user_id"] else None,
                expires_at=row["expires_at"],
                expiry_duration=row["expiry_duration"],
                hourly_limit_override=row["hourly_limit_override"],
                monthly_limit_override=row["monthly_limit_override"]
            )

            # 3. Update Cache (v2 with user_id support)
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
        user_id: str = None,
        expiry_duration: Optional[str] = None
    ) -> str:
        """Create a new API key.
        
        Returns:
            The raw API key string (only shown once).
        """
        import secrets
        from src.utils.expiry import calculate_expiry, validate_expiry_duration
        
        # Validate expiry duration
        if expiry_duration and not validate_expiry_duration(expiry_duration):
            raise ValueError(
                f"Invalid expiry_duration: {expiry_duration}. "
                f"Must be one of: 30d, 90d, 180d, or null"
            )
        
        raw_key = f"df_{secrets.token_urlsafe(32)}"
        key_hash = self._hash_key(raw_key)
        
        # Calculate expiry
        expires_at = calculate_expiry(expiry_duration)
        
        await self._ensure_initialized()
        pool = await PostgresPoolManager.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO api_keys (key_hash, name, tenant_id, integration_name, tier, scopes, user_id, expires_at, expiry_duration) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                key_hash, name, tenant_id, integration_name, tier, json.dumps(scopes or []), 
                uuid.UUID(user_id) if user_id else None, expires_at, expiry_duration
            )
        
        return raw_key

    async def list_keys(self) -> List[Dict]:
        """List metadata for all API keys."""
        from src.utils.expiry import days_remaining, is_expired
        
        await self._ensure_initialized()
        pool = await PostgresPoolManager.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, integration_name, tier, scopes, tenant_id, is_active, created_at, last_used_at, user_id, expires_at, expiry_duration "
                "FROM api_keys ORDER BY created_at DESC"
            )
            
            results = []
            for row in rows:
                result = dict(row)
                # Add expiry-related fields
                result["expires_at"] = row["expires_at"].isoformat() if row["expires_at"] else None
                result["is_expired"] = is_expired(row["expires_at"])
                result["days_remaining"] = days_remaining(row["expires_at"])
                results.append(result)
            
            return results

    async def list_user_keys(self, user_id: str) -> List[Dict]:
        """List API keys owned by a specific user."""
        from src.utils.expiry import days_remaining, is_expired
        
        await self._ensure_initialized()
        pool = await PostgresPoolManager.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, integration_name, tier, scopes, tenant_id, is_active, created_at, last_used_at, expires_at, expiry_duration "
                "FROM api_keys WHERE user_id = $1 ORDER BY created_at DESC",
                uuid.UUID(user_id)
            )
            
            results = []
            for row in rows:
                result = dict(row)
                # Add expiry-related fields
                result["expires_at"] = row["expires_at"].isoformat() if row["expires_at"] else None
                result["is_expired"] = is_expired(row["expires_at"])
                result["days_remaining"] = days_remaining(row["expires_at"])
                results.append(result)
            
            return results

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

    async def get_key_usage_status(self, api_key_id: str, tier: str, hourly_override: Optional[int] = None, monthly_override: Optional[int] = None) -> Dict[str, Any]:
        """Get current rate limit usage status for an API key."""
        try:
            from src.core.rate_limiter import rate_limiter
            return await rate_limiter.get_usage(api_key_id, tier, hourly_override, monthly_override)
        except Exception as e:
            logger.error(f"Failed to get usage status for key {api_key_id}: {e}")
            # Fallback limits
            tier_limits = {
                "free": {"hourly": 50, "monthly": 500},
                "pro": {"hourly": 500, "monthly": 20000},
                "enterprise": {"hourly": 2000, "monthly": None},
            }
            limits = tier_limits.get(tier, tier_limits["free"])
            return {
                "hourly_used": 0,
                "hourly_limit": hourly_override or limits["hourly"],
                "monthly_used": 0,
                "monthly_limit": monthly_override or limits["monthly"],
                "hourly_reset_at": None,
                "monthly_reset_at": None,
            }

# Global instance
api_key_store = APIKeyStore()
