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


# Atomic INCR-and-check. Runs inside Redis (single-threaded), so the read of
# current usage and the increment happen as one indivisible step — closes the
# race where concurrent callers could all read used<limit and then all bump
# the counter past the limit.
#
# Args:
#   KEYS[1] = hourly key, KEYS[2] = monthly key
#   ARGV[1] = hourly_limit  (-1 means unlimited)
#   ARGV[2] = monthly_limit (-1 means unlimited)
#   ARGV[3] = hourly TTL seconds
#   ARGV[4] = monthly TTL seconds
# Returns: { allowed (1|0), hourly_used, monthly_used }
#   When allowed=0, neither counter was incremented.
#   When allowed=1, both counters were incremented by 1 and TTLs refreshed.
_ACQUIRE_LUA = """
local hl = tonumber(ARGV[1])
local ml = tonumber(ARGV[2])
local hu = tonumber(redis.call('GET', KEYS[1])) or 0
local mu = tonumber(redis.call('GET', KEYS[2])) or 0
if hl >= 0 and hu >= hl then
  return {0, hu, mu}
end
if ml >= 0 and mu >= ml then
  return {0, hu, mu}
end
local nh = redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
local nm = redis.call('INCR', KEYS[2])
redis.call('EXPIRE', KEYS[2], tonumber(ARGV[4]))
return {1, nh, nm}
"""


class RateLimiter:
    """Tier-based rate limiting using Redis and PostgreSQL."""

    def __init__(self):
        self.redis_client = None
        self._redis_initialized = False
        self._acquire_script = None  # cached redis-py Script object (EVALSHA-with-fallback)
    
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
        monthly_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        """DEPRECATED: no-op kept for back-compat with existing callers.

        Slot reservation now happens atomically inside ``check_limits`` via a
        Lua script, so calling this after a successful ``check_limits`` would
        double-count. New callers should drop the post-call invocation entirely
        and use ``release`` on the failure path instead.
        """
        del tokens_used
        return await self.get_usage(api_key_id, tier, hourly_override, monthly_override)

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
        monthly_override: Optional[int] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Atomically check the hourly + monthly limits and reserve a slot.

        Runs ``_ACQUIRE_LUA`` inside Redis: reads both counters, blocks if
        either is at its cap (no increment), otherwise INCRs both counters
        and refreshes their TTLs — all as one indivisible operation. This
        closes the read-then-increment race the older two-step pattern had.

        Returns:
            (allowed, usage). When False, no counter was incremented and the
            caller should reject the request. When True, both counters have
            already been bumped by 1 and the call should proceed; pair with
            ``release`` on the tool-failure path so failed calls do not
            consume quota.

        Fails open on Redis errors — don't lock users out on transient issues.
        """
        await self._ensure_redis()

        now = datetime.now(timezone.utc)
        limits = await self._get_limits(tier, hourly_override, monthly_override)
        usage: Dict[str, Any] = {
            "hourly_used": 0,
            "hourly_limit": limits["hourly"],
            "monthly_used": 0,
            "monthly_limit": limits["monthly"],
            "hourly_reset_at": self._next_hour_reset(now),
            "monthly_reset_at": self._next_month_reset(now),
        }

        if not self.redis_client:
            return True, usage

        try:
            if self._acquire_script is None:
                self._acquire_script = self.redis_client.register_script(_ACQUIRE_LUA)

            hourly_limit_arg = -1 if limits["hourly"] is None else int(limits["hourly"])
            monthly_limit_arg = -1 if limits["monthly"] is None else int(limits["monthly"])
            hourly_key = self._hourly_key(api_key_id, now)
            monthly_key = self._monthly_key(api_key_id, now)

            result = await self._acquire_script(
                keys=[hourly_key, monthly_key],
                args=[
                    hourly_limit_arg,
                    monthly_limit_arg,
                    3600,
                    self._seconds_until_end_of_month(now),
                ],
            )
            allowed = int(result[0]) == 1
            usage["hourly_used"] = int(result[1])
            usage["monthly_used"] = int(result[2])

            if allowed:
                # DB fallback source for the monthly counter (used when Redis dies).
                try:
                    await self._persist_monthly_to_db(api_key_id, now.strftime("%Y-%m"), 1)
                except Exception as e:
                    logger.error(f"[RATE_LIMIT] Failed to persist monthly usage: {e}")

            return allowed, usage
        except Exception as e:
            logger.error(f"[RATE_LIMIT] check_limits (atomic acquire) failed: {e}")
            return True, usage

    async def release(self, api_key_id: str) -> None:
        """Refund a previously-acquired slot.

        Call on the tool-failure path after a successful ``check_limits`` so
        failed calls do not count toward the user's limits. Best-effort:
        failures here are logged and swallowed.
        """
        await self._ensure_redis()
        if not self.redis_client:
            return
        now = datetime.now(timezone.utc)
        try:
            hourly_key = self._hourly_key(api_key_id, now)
            monthly_key = self._monthly_key(api_key_id, now)
            pipe = self.redis_client.pipeline()
            pipe.decr(hourly_key)
            pipe.decr(monthly_key)
            await pipe.execute()
        except Exception as e:
            logger.warning(f"[RATE_LIMIT] release failed: {e}")


# Global rate limiter instance
rate_limiter = RateLimiter()
