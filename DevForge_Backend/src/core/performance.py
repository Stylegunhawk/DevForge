"""Performance optimization layer for DevForge GitOps.

Implements caching, request batching, and timeout handling for production deployment.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)


class CacheEntry:
    """Simple cache entry with TTL"""
    
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
    
    def is_expired(self) -> bool:
        """Check if entry has expired"""
        return datetime.now() > self.expires_at


class SimpleCache:
    """Thread-safe in-memory cache with TTL"""
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if expired/missing
        """
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            
            if entry.is_expired():
                del self._cache[key]
                return None
            
            return entry.value
    
    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: 1 hour)
        """
        async with self._lock:
            self._cache[key] = CacheEntry(value, ttl)
    
    async def delete(self, key: str):
        """Delete key from cache"""
        async with self._lock:
            self._cache.pop(key, None)
    
    async def clear(self):
        """Clear all cache entries"""
        async with self._lock:
            self._cache.clear()
    
    async def cleanup_expired(self):
        """Remove expired entries"""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")


# Global cache instance
_global_cache = SimpleCache()


def get_cache() -> SimpleCache:
    """Get global cache instance"""
    return _global_cache


def cached(ttl: int = 3600, key_prefix: str = ""):
    """Decorator for caching async function results
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
        
    Example:
        @cached(ttl=3600, key_prefix="repos")
        async def get_user_repos(user):
            return await fetch_repos(user)
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cache = get_cache()
            cached_value = await cache.get(cache_key)
            
            if cached_value is not None:
                logger.debug(f"Cache HIT: {cache_key[:50]}...")
                return cached_value
            
            # Cache miss - call function
            logger.debug(f"Cache MISS: {cache_key[:50]}...")
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


def with_timeout(timeout_seconds: int):
    """Decorator to add timeout to async functions
    
    Args:
        timeout_seconds: Timeout in seconds
        
    Raises:
        asyncio.TimeoutError: If function exceeds timeout
        
    Example:
        @with_timeout(10)
        async def slow_operation():
            await asyncio.sleep(20)  # Will timeout
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Function {func.__name__} exceeded timeout of {timeout_seconds}s"
                )
                raise
        
        return wrapper
    return decorator


class LLMBatcher:
    """Batch multiple LLM requests for efficiency"""
    
    def __init__(self, batch_size: int = 5, max_wait_ms: int = 100):
        """Initialize batcher
        
        Args:
            batch_size: Max requests per batch
            max_wait_ms: Max time to wait for batch to fill
        """
        self.batch_size = batch_size
        self.max_wait_ms = max_wait_ms
        self._queue: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
    
    async def add_request(self, prompt: str, **kwargs) -> Any:
        """Add request to batch
        
        Args:
            prompt: LLM prompt
            **kwargs: Additional LLM parameters
            
        Returns:
            LLM response
        """
        request = {
            "prompt": prompt,
            "kwargs": kwargs,
            "future": asyncio.Future()
        }
        
        async with self._lock:
            self._queue.append(request)
            
            # If batch full, process immediately
            if len(self._queue) >= self.batch_size:
                await self._process_batch()
        
        # Wait for result
        return await request["future"]
    
    async def _process_batch(self):
        """Process queued requests as batch"""
        if not self._queue:
            return
        
        batch = self._queue[:self.batch_size]
        self._queue = self._queue[self.batch_size:]
        
        logger.info(f"Processing LLM batch of {len(batch)} requests")
        
        # Process each request (in real implementation,would use batch API)
        for request in batch:
            try:
                # Placeholder - would call batch LLM API
                result = await self._call_llm_single(
                    request["prompt"],
                    **request["kwargs"]
                )
                request["future"].set_result(result)
            except Exception as e:
                request["future"].set_exception(e)
    
    async def _call_llm_single(self, prompt: str, **kwargs) -> str:
        """Call LLM for single request
        
        In production, this would use actual LLM client
        """
        # Placeholder implementation
        await asyncio.sleep(0.1)  # Simulate API call
        return f"Response to: {prompt[:50]}..."


class PerformanceMetrics:
    """Track performance metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()
    
    async def record(self, metric_name: str, value: float):
        """Record a metric value
        
        Args:
            metric_name: Name of metric
            value: Metric value
        """
        async with self._lock:
            if metric_name not in self.metrics:
                self.metrics[metric_name] = []
            
            self.metrics[metric_name].append(value)
            
            # Keep only last 1000 values
            if len(self.metrics[metric_name]) > 1000:
                self.metrics[metric_name] = self.metrics[metric_name][-1000:]
    
    async def get_stats(self, metric_name: str) -> Dict[str, float]:
        """Get statistics for a metric
        
        Args:
            metric_name: Name of metric
            
        Returns:
            Dict with min, max, mean, p50, p95, p99
        """
        async with self._lock:
            values = self.metrics.get(metric_name, [])
            
            if not values:
                return {}
            
            sorted_values = sorted(values)
            count = len(sorted_values)
            
            return {
                "count": count,
                "min": sorted_values[0],
                "max": sorted_values[-1],
                "mean": sum(sorted_values) / count,
                "p50": sorted_values[int(count * 0.5)],
                "p95": sorted_values[int(count * 0.95)],
                "p99": sorted_values[int(count * 0.99)],
            }
    
    async def all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all metrics"""
        stats = {}
        for metric_name in self.metrics:
            stats[metric_name] = await self.get_stats(metric_name)
        return stats


# Global metrics instance
_global_metrics = PerformanceMetrics()


def get_metrics() -> PerformanceMetrics:
    """Get global metrics instance"""
    return _global_metrics


def track_performance(metric_name: str):
    """Decorator to track function performance
    
    Args:
        metric_name: Name for the metric
        
    Example:
        @track_performance("github_api_call")
        async def fetch_repos():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                metrics = get_metrics()
                await metrics.record(metric_name, duration_ms)
                
                logger.debug(f"{metric_name}: {duration_ms:.2f}ms")
        
        return wrapper
    return decorator
