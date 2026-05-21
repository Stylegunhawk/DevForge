"""Tier configuration storage and management.

Handles dynamic tier limits, pricing, and expiry settings with Redis caching.
"""

import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timezone

from src.storage.db import PostgresPoolManager
from src.core.config import settings

logger = logging.getLogger(__name__)


class TierConfigStore:
    """Manages tier configuration with Redis caching."""
    
    CACHE_KEY = "tier_config:all"
    CACHE_TTL = 300  # 5 minutes
    
    def __init__(self):
        self._redis_initialized = False
        self.redis_client = None
    
    async def _ensure_redis(self):
        """Initialize Redis connection if available."""
        if not hasattr(self, '_redis_initialized'):
            try:
                import redis.asyncio as redis
                redis_url = getattr(settings, 'REDIS_URL', None)
                if redis_url:
                    self.redis_client = redis.Redis.from_url(
                        redis_url,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                    )
                    await self.redis_client.ping()
                    self._redis_initialized = True
                    logger.info("[TIER_CONFIG] Redis connection established")
                else:
                    self.redis_client = None
                    self._redis_initialized = False
            except Exception as e:
                logger.warning(f"[TIER_CONFIG] Redis unavailable: {e}")
                self.redis_client = None
                self._redis_initialized = False
    
    async def get_all_tiers(self) -> Dict[str, Any]:
        """
        Returns all tier configs as dict keyed by tier.
        Try Redis cache first, fall back to Postgres.
        """
        await self._ensure_redis()
        
        # Try Redis cache first
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(self.CACHE_KEY)
                if cached_data:
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"[TIER_CONFIG] Redis cache read failed: {e}")
        
        # Fall back to database
        try:
            pool = await PostgresPoolManager.get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        tier, 
                        hourly_limit, 
                        monthly_limit, 
                        cost_per_1k_tokens,
                        max_expiry_days,
                        tc.is_active,
                        tc.updated_at,
                        u.email as updated_by_email
                    FROM tier_config tc
                    LEFT JOIN users u ON tc.updated_by = u.id
                    WHERE tc.is_active = true
                    ORDER BY tier
                """)
                
                configs = {}
                for row in rows:
                    configs[row["tier"]] = {
                        "tier": row["tier"],
                        "hourly_limit": row["hourly_limit"],
                        "monthly_limit": row["monthly_limit"],
                        "cost_per_1k_tokens": float(row["cost_per_1k_tokens"]),
                        "max_expiry_days": row["max_expiry_days"],
                        "is_active": row["is_active"],
                        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                        "updated_by_email": row["updated_by_email"]
                    }
                
                # Update Redis cache
                if self.redis_client:
                    try:
                        await self.redis_client.setex(
                            self.CACHE_KEY,
                            self.CACHE_TTL,
                            json.dumps(configs)
                        )
                    except Exception as e:
                        logger.warning(f"[TIER_CONFIG] Redis cache write failed: {e}")
                
                return configs
                
        except Exception as e:
            logger.error(f"[TIER_CONFIG] Failed to load tier configs: {e}")
            # Return defaults on database failure
            return self._defaults_dict()
    
    async def get_tier(self, tier: str) -> Dict[str, Any]:
        """Get single tier config. Returns defaults if tier not found."""
        configs = await self.get_all_tiers()
        return configs.get(tier, self._defaults(tier))
    
    async def update_tier(
        self, 
        tier: str, 
        updates: Dict[str, Any],
        updated_by: str  # user_id
    ) -> Dict[str, Any]:
        """
        Update tier config in Postgres.
        Invalidate Redis cache.
        Returns updated config.
        """
        # Validate inputs
        if "hourly_limit" in updates:
            hourly_limit = updates["hourly_limit"]
            if not isinstance(hourly_limit, int) or hourly_limit < 1 or hourly_limit > 10000:
                raise ValueError("hourly_limit must be an integer between 1 and 10000")
        
        if "monthly_limit" in updates:
            monthly_limit = updates["monthly_limit"]
            if monthly_limit is not None:
                if not isinstance(monthly_limit, int) or monthly_limit < 1 or monthly_limit > 1000000:
                    raise ValueError("monthly_limit must be an integer between 1 and 1000000, or null")
        
        if "cost_per_1k_tokens" in updates:
            cost = updates["cost_per_1k_tokens"]
            if not isinstance(cost, (int, float)) or cost < 0.001 or cost > 1.0:
                raise ValueError("cost_per_1k_tokens must be between 0.001 and 1.0")
        
        if "max_expiry_days" in updates:
            max_days = updates["max_expiry_days"]
            if max_days not in (30, 90, 180):
                raise ValueError("max_expiry_days must be 30, 90, or 180")
        
        # Build update query
        set_clauses = []
        values = []
        param_idx = 1
        
        for field, value in updates.items():
            if field in ["hourly_limit", "monthly_limit", "cost_per_1k_tokens", "max_expiry_days"]:
                set_clauses.append(f"{field} = ${param_idx}")
                values.append(value)
                param_idx += 1
        
        if not set_clauses:
            raise ValueError("No valid fields to update")
        
        # Add updated_by
        set_clauses.append(f"updated_by = ${param_idx}")
        values.append(updated_by)
        param_idx += 1
        
        # Update database
        try:
            pool = await PostgresPoolManager.get_pool()
            async with pool.acquire() as conn:
                await conn.execute(f"""
                    UPDATE tier_config 
                    SET {', '.join(set_clauses)}
                    WHERE tier = ${param_idx}
                """, *values, tier)
                
                # Invalidate Redis cache
                if self.redis_client:
                    try:
                        await self.redis_client.delete(self.CACHE_KEY)
                    except Exception as e:
                        logger.warning(f"[TIER_CONFIG] Failed to invalidate cache: {e}")
                
                # Return updated config
                return await self.get_tier(tier)
                
        except Exception as e:
            logger.error(f"[TIER_CONFIG] Failed to update tier {tier}: {e}")
            raise
    
    def _defaults(self, tier: str) -> Dict[str, Any]:
        """Fallback hardcoded defaults if DB unavailable"""
        defaults = {
            "free": {
                "tier": "free",
                "hourly_limit": 50, 
                "monthly_limit": 500,
                "cost_per_1k_tokens": 0.010,
                "max_expiry_days": 180,
                "is_active": True,
                "updated_at": None,
                "updated_by_email": None
            },
            "pro": {
                "tier": "pro",
                "hourly_limit": 500,
                "monthly_limit": 20000,
                "cost_per_1k_tokens": 0.008,
                "max_expiry_days": 180,
                "is_active": True,
                "updated_at": None,
                "updated_by_email": None
            },
            "enterprise": {
                "tier": "enterprise",
                "hourly_limit": 2000,
                "monthly_limit": None,
                "cost_per_1k_tokens": 0.005,
                "max_expiry_days": 180,
                "is_active": True,
                "updated_at": None,
                "updated_by_email": None
            },
        }
        return defaults.get(tier, defaults["free"])
    
    def _defaults_dict(self) -> Dict[str, Any]:
        """Return all defaults as dict"""
        return {
            "free": self._defaults("free"),
            "pro": self._defaults("pro"),
            "enterprise": self._defaults("enterprise")
        }


# Global instance
tier_config_store = TierConfigStore()
