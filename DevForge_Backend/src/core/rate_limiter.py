"""Tier-based rate limiting for DevForge API.

Uses Redis for atomic counters with PostgreSQL fallback for monthly tracking.
Implements hourly and monthly token limits per tier.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Tuple, Any
import uuid

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from src.storage.db import PostgresPoolManager
from src.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Tier-based rate limiting using Redis and PostgreSQL."""
    
    def __init__(self):
        self.redis_client = None
        self._redis_initialized = False
    
    async def _get_limits(
        self, 
        tier: str,
        hourly_override: Optional[int] = None,
        monthly_override: Optional[int] = None
    ) -> Dict[str, Optional[int]]:
        """Get limits from DB config with overrides"""
        try:
            from src.storage.tier_config_store import tier_config_store
            config = await tier_config_store.get_tier(tier)
            
            return {
                # Override takes priority over tier default
                "hourly": hourly_override or config["hourly_limit"],
                "monthly": monthly_override or config["monthly_limit"]
            }
        except Exception as e:
            logger.warning(f"[RATE_LIMIT] Failed to get tier limits for {tier}: {e}")
            # Fail open with conservative defaults (ignore overrides if DB unavailable)
            return {"hourly": hourly_override or 50, "monthly": monthly_override or 500}
    
    async def _ensure_redis(self):
        """Initialize Redis connection if not already done."""
        if not self._redis_initialized and REDIS_AVAILABLE:
            try:
                redis_url = getattr(settings, 'REDIS_URL', None)
                if not redis_url:
                    logger.warning("[RATE_LIMIT] REDIS_URL not configured")
                    return
                
                self.redis_client = redis.Redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                # Test connection
                await self.redis_client.ping()
                self._redis_initialized = True
                logger.info("[RATE_LIMIT] Redis connection established")
            except Exception as e:
                logger.warning(f"[RATE_LIMIT] Redis unavailable: {e}")
                self.redis_client = None
                self._redis_initialized = False
    
    def _hourly_key(self, api_key_id: str, now: datetime) -> str:
        """Generate Redis key for hourly rate limiting."""
        hour_str = now.strftime("%Y-%m-%d-%H")
        return f"ratelimit:hourly:{api_key_id}:{hour_str}"
    
    def _monthly_key(self, api_key_id: str, now: datetime) -> str:
        """Generate Redis key for monthly rate limiting."""
        month_str = now.strftime("%Y-%m")
        return f"ratelimit:monthly:{api_key_id}:{month_str}"
    
    def _next_hour_reset(self, now: datetime) -> str:
        """Get ISO timestamp for next hour reset."""
        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return next_hour.isoformat()
    
    def _next_month_reset(self, now: datetime) -> str:
        """Get ISO timestamp for next month reset."""
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            next_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return next_month.isoformat()
    
    def _seconds_until_end_of_month(self, now: datetime) -> int:
        """Calculate seconds until end of current month."""
        if now.month == 12:
            end_of_month = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_of_month = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
        return int((end_of_month - now).total_seconds())
    
    async def _sync_monthly_from_db(self, api_key_id: str, now: datetime):
        """Sync monthly usage from PostgreSQL to Redis."""
        if not self.redis_client:
            return
        
        try:
            month_str = now.strftime("%Y-%m")
            pool = await PostgresPoolManager.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT tokens_used FROM monthly_usage WHERE api_key_id = $1 AND year_month = $2",
                    uuid.UUID(api_key_id), month_str
                )
                
                if row and row["tokens_used"] > 0:
                    monthly_key = self._monthly_key(api_key_id, now)
                    # Set the value in Redis with TTL
                    ttl = self._seconds_until_end_of_month(now)
                    await self.redis_client.setex(monthly_key, ttl, row["tokens_used"])
                    logger.info(f"[RATE_LIMIT] Synced monthly usage from DB: {row['tokens_used']} tokens for key {api_key_id}")
        except Exception as e:
            logger.error(f"[RATE_LIMIT] Failed to sync monthly usage from DB: {e}")
    
    async def _persist_monthly_to_db(self, api_key_id: str, month_str: str, tokens_used: int):
        """Persist monthly usage to PostgreSQL."""
        try:
            pool = await PostgresPoolManager.get_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO monthly_usage (api_key_id, year_month, tokens_used, last_updated)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                    ON CONFLICT (api_key_id, year_month)
                    DO UPDATE SET 
                        tokens_used = monthly_usage.tokens_used + EXCLUDED.tokens_used,
                        last_updated = CURRENT_TIMESTAMP
                """, uuid.UUID(api_key_id), month_str, tokens_used)
        except Exception as e:
            logger.error(f"[RATE_LIMIT] Failed to persist monthly usage to DB: {e}")
    
    async def check_and_increment(
        self, 
        api_key_id: str, 
        tier: str, 
        tokens_used: int,
        hourly_override: Optional[int] = None,
        monthly_override: Optional[int] = None
    ) -> Dict[str, Any]:
        """Check limits and increment counters after request completes."""
        await self._ensure_redis()
        
        now = datetime.now(timezone.utc)
        limits = await self._get_limits(tier, hourly_override, monthly_override)
        
        result = {
            "success": True,
            "hourly_used": 0,
            "hourly_limit": limits["hourly"],
            "monthly_used": 0,
            "monthly_limit": limits["monthly"],
            "hourly_reset_at": self._next_hour_reset(now),
            "monthly_reset_at": self._next_month_reset(now),
        }
        
        try:
            if self.redis_client:
                # Use Redis pipeline for atomic operations
                pipe = self.redis_client.pipeline()
                
                # Hourly counter
                hourly_key = self._hourly_key(api_key_id, now)
                pipe.incrby(hourly_key, tokens_used)
                pipe.expire(hourly_key, 3600)  # 1 hour TTL
                
                # Monthly counter
                monthly_key = self._monthly_key(api_key_id, now)
                pipe.incrby(monthly_key, tokens_used)
                pipe.expire(monthly_key, self._seconds_until_end_of_month(now))
                
                # Execute pipeline
                pipeline_results = await pipe.execute()
                hourly_result, monthly_result = pipeline_results[0], pipeline_results[1]
                
                result["hourly_used"] = hourly_result
                result["monthly_used"] = monthly_result
                
                # Persist monthly to DB (async, don't wait)
                month_str = now.strftime("%Y-%m")
                try:
                    await self._persist_monthly_to_db(api_key_id, month_str, tokens_used)
                except Exception as e:
                    logger.error(f"[RATE_LIMIT] Failed to persist monthly usage: {e}")
                
            else:
                # Fallback to DB only (no Redis)
                logger.warning("[RATE_LIMIT] Redis unavailable, using DB fallback")
                # For now, just return success without tracking
                # In production, you might want to implement DB-only tracking
                
        except Exception as e:
            logger.error(f"[RATE_LIMIT] Error in check_and_increment: {e}")
            # Fail open - don't block requests due to rate limiter errors
        
        return result
    
    async def get_usage(
        self, 
        api_key_id: str, 
        tier: str,
        hourly_override: Optional[int] = None,
        monthly_override: Optional[int] = None
    ) -> Dict[str, Any]:
        """Returns current usage without incrementing."""
        await self._ensure_redis()
        
        now = datetime.now(timezone.utc)
        limits = await self._get_limits(tier, hourly_override, monthly_override)
        
        result = {
            "hourly_used": 0,
            "hourly_limit": limits["hourly"],
            "monthly_used": 0,
            "monthly_limit": limits["monthly"],
            "hourly_reset_at": self._next_hour_reset(now),
            "monthly_reset_at": self._next_month_reset(now),
        }
        
        try:
            if self.redis_client:
                # Try Redis first
                hourly_key = self._hourly_key(api_key_id, now)
                monthly_key = self._monthly_key(api_key_id, now)
                
                hourly_used = await self.redis_client.get(hourly_key)
                monthly_used = await self.redis_client.get(monthly_key)
                
                if hourly_used:
                    result["hourly_used"] = int(hourly_used)
                if monthly_used:
                    result["monthly_used"] = int(monthly_used)
                else:
                    # If no monthly data in Redis, sync from DB
                    await self._sync_monthly_from_db(api_key_id, now)
                    monthly_used = await self.redis_client.get(monthly_key)
                    if monthly_used:
                        result["monthly_used"] = int(monthly_used)
            else:
                # Fallback to DB for monthly usage
                month_str = now.strftime("%Y-%m")
                pool = await PostgresPoolManager.get_pool()
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT tokens_used FROM monthly_usage WHERE api_key_id = $1 AND year_month = $2",
                        uuid.UUID(api_key_id), month_str
                    )
                    if row:
                        result["monthly_used"] = row["tokens_used"]
                
        except Exception as e:
            logger.error(f"[RATE_LIMIT] Error in get_usage: {e}")
        
        return result
    
    async def check_limits(
        self, 
        api_key_id: str, 
        tier: str,
        hourly_override: Optional[int] = None,
        monthly_override: Optional[int] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if current usage already exceeds limits."""
        usage = await self.get_usage(api_key_id, tier, hourly_override, monthly_override)
        
        # Check hourly limit
        hourly_exceeded = usage["hourly_limit"] is not None and usage["hourly_used"] >= usage["hourly_limit"]
        
        # Check monthly limit
        monthly_exceeded = usage["monthly_limit"] is not None and usage["monthly_used"] >= usage["monthly_limit"]
        
        is_allowed = not (hourly_exceeded or monthly_exceeded)
        
        return is_allowed, usage


# Global rate limiter instance
rate_limiter = RateLimiter()
