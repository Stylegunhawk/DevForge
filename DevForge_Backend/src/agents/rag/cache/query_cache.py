"""Query cache implementation with Redis and LRU fallback.

Phase 11.2: Exact-Match Query Cache
- Cache ONLY final retrieval results (post-rerank, post-graph)
- Never cache intermediate stages
- Graceful fallback: Redis failure → in-memory LRU
"""

from typing import Optional, Dict, Any
import json
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)


class QueryCache:
    """
    Exact-match query cache with optional Redis backend.
    
    Lifecycle:
    - Cache key = SHA256(normalized_query + "::" + top_k)
    - TTL = configurable (default 1 hour)
    - Invalidation = TTL expiry only (no manual invalidation per query)
    - Failures = never break retrieval (graceful fallback)
    
    Storage:
    - Primary: Redis (if available and configured)
    - Fallback: In-memory LRU (always available)
    """
    
    def __init__(
        self,
        redis_client=None,
        ttl: int = 3600,
        max_size: int = 1000
    ):
        """
        Initialize query cache.
        
        Args:
            redis_client: Optional Redis async client
            ttl: Cache TTL in seconds (default 1 hour)
            max_size: Max LRU cache size if no Redis (default 1000)
        """
        self.redis = redis_client
        self.ttl = ttl
        self.max_size = max_size
        
        # Fallback: In-memory LRU cache (always initialized)
        self._memory_cache: OrderedDict = OrderedDict()
        
        if not redis_client:
            logger.warning("Redis not available, using in-memory LRU cache only")
        else:
            logger.info(f"QueryCache initialized with Redis backend (TTL={ttl}s)")
        
        # Metrics
        self._hits = 0
        self._misses = 0
    
    async def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached query results.
        
        Flow:
        1. Try Redis (if available)
        2. Fallback to in-memory LRU
        3. Log hit/miss
        
        Args:
            cache_key: SHA256 hash from cache_key_from_query()
        
        Returns:
            Cached results dict or None if miss
        """
        try:
            # Try Redis first (if available)
            if self.redis:
                try:
                    cached_json = await self.redis.get(f"query_cache:{cache_key}")
                    if cached_json:
                        cached_result = json.loads(cached_json)
                        
                        # Invalidate if cached docs have no file_id (legacy cache entry)
                        # Guard: only validate if cached_result is a dict
                        if isinstance(cached_result, dict):
                            docs = cached_result.get("documents", [])
                            if docs and isinstance(docs[0], dict) and not docs[0].get("metadata", {}).get("file_id"):
                                logger.warning(f"Stale cache entry (no file_id) for key {cache_key[:12]} — invalidating")
                                await self.delete(cache_key)
                                return None
                            # Invalidate empty result sets (stale orphan-filtered results)
                            if not docs:
                                logger.warning(f"Empty cached result for key {cache_key[:12]} — invalidating")
                                await self.delete(cache_key)
                                return None
                            
                        self._hits += 1
                        logger.info(f"[RAG-DEBUG] ✅ EXACT CACHE HIT (Redis): {cache_key[:12]}...")
                        return cached_result
                except Exception as redis_err:
                    logger.warning(f"Redis get failed: {redis_err}, trying memory cache")
            
            # Fallback to in-memory LRU
            if cache_key in self._memory_cache:
                cached_result = self._memory_cache[cache_key]
                
                # Invalidate if cached docs have no file_id (legacy cache entry)
                # Guard: only validate if cached_result is a dict
                if isinstance(cached_result, dict):
                    docs = cached_result.get("documents", [])
                    if docs and isinstance(docs[0], dict) and not docs[0].get("metadata", {}).get("file_id"):
                        logger.warning(f"Stale memory cache entry (no file_id) for key {cache_key[:12]} — invalidating")
                        await self.delete(cache_key)
                        return None

                self._hits += 1
                # Move to end (LRU)
                self._memory_cache.move_to_end(cache_key)
                logger.info(f"[RAG-DEBUG] ✅ EXACT CACHE HIT (memory): {cache_key[:12]}...")
                return cached_result
            
            # Miss
            self._misses += 1
            logger.info(f"[RAG-DEBUG] ❌ EXACT CACHE MISS: {cache_key[:12]}...")
            return None
        
        except Exception as e:
            # CRITICAL: Cache failures must NEVER break retrieval
            logger.error(f"Cache get error: {e}, returning None")
            self._misses += 1
            return None
    
    async def set(self, cache_key: str, results: Dict[str, Any]):
        """
        Cache query results.
        
        Flow:
        1. Try Redis (if available)
        2. Always cache in-memory LRU (as backup)
        3. Apply LRU eviction if needed
        
        Args:
            cache_key: SHA256 hash
            results: Final retrieval results (post-rerank, post-graph)
        """
        try:
            # Try Redis with TTL
            if self.redis:
                try:
                    await self.redis.setex(
                        f"query_cache:{cache_key}",
                        self.ttl,
                        json.dumps(results, default=str)  # Handle non-serializable
                    )
                    logger.debug(f"Cache SET (Redis): {cache_key[:12]}...")
                except Exception as redis_err:
                    logger.warning(f"Redis set failed: {redis_err}, using memory only")
            
            # Always cache in-memory as fallback
            # LRU eviction if full
            if len(self._memory_cache) >= self.max_size:
                # Evict oldest (FIFO)
                evicted_key, _ = self._memory_cache.popitem(last=False)
                logger.debug(f"LRU evicted: {evicted_key[:12]}...")
            
            self._memory_cache[cache_key] = results
            logger.debug(f"Cache SET (memory): {cache_key[:12]}...")
        
        except Exception as e:
            # CRITICAL: Cache failures must NEVER break retrieval
            logger.error(f"Cache set error: {e}, continuing without cache")
    
    def get_hit_rate(self) -> float:
        """
        Calculate cache hit rate.
        
        Returns:
            Hit rate as float [0.0, 1.0]
        """
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total
    
    async def delete(self, cache_key: str):
        """
        Delete a specific cache entry from both Redis and memory.
        
        Args:
            cache_key: Cache key to delete
        """
        try:
            if self.redis:
                await self.redis.delete(f"query_cache:{cache_key}")
            
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
                
        except Exception as e:
            logger.error(f"Cache delete error: {e}")

    async def clear(self):
        """Clear all cache entries (both Redis and memory)."""
        try:
            if self.redis:
                # Delete all query_cache:* keys
                keys = await self.redis.keys("query_cache:*")
                if keys:
                    await self.redis.delete(*keys)
                    logger.info(f"Cleared {len(keys)} Redis cache entries")
            
            self._memory_cache.clear()
            logger.info("Memory cache cleared")
        
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
    
    def reset_metrics(self):
        """Reset hit/miss counters (for testing)."""
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with hits, misses, size, hit_rate
        """
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.get_hit_rate(),
            "memory_size": len(self._memory_cache),
            "backend": "redis" if self.redis else "memory_only"
        }
