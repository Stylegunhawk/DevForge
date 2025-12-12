"""Tests for performance optimization module.

Tests caching, timeouts, metrics tracking, and LLM batching.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from src.core.performance import (
    SimpleCache, CacheEntry, get_cache,
    cached, with_timeout, track_performance,
    LLMBatcher, PerformanceMetrics, get_metrics
)


class TestSimpleCache:
    """Test cache functionality"""
    
    @pytest.mark.asyncio
    async def test_cache_set_get(self):
        """Test basic cache set/get"""
        cache = SimpleCache()
        
        await cache.set("key1", "value1", ttl=60)
        value = await cache.get("key1")
        
        assert value == "value1"
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Test cache entry expiration"""
        cache = SimpleCache()
        
        await cache.set("key1", "value1", ttl=0)  # Immediate expiration
        await asyncio.sleep(0.1)
        
        value = await cache.get("key1")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_cache_delete(self):
        """Test cache deletion"""
        cache = SimpleCache()
        
        await cache.set("key1", "value1")
        await cache.delete("key1")
        
        value = await cache.get("key1")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test clearing all cache"""
        cache = SimpleCache()
        
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()
        
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
    
    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        """Test cleanup of expired entries"""
        cache = SimpleCache()
        
        await cache.set("key1", "value1", ttl=0)  # Expires immediately
        await cache.set("key2", "value2", ttl=3600)  # Long TTL
        
        await asyncio.sleep(0.1)
        await cache.cleanup_expired()
        
        # key1 should be cleaned, key2 should remain
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"


class TestCachedDecorator:
    """Test @cached decorator"""
    
    @pytest.mark.asyncio
    async def test_cached_function(self):
        """Test caching of function results"""
        call_count = 0
        
        @cached(ttl=60, key_prefix="test")
        async def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call - should execute function
        result1 = await expensive_function(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call - should use cache
        result2 = await expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Not incremented
        
        # Different argument - should execute again
        result3 = await expensive_function(10)
        assert result3 == 20
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_cached_respects_ttl(self):
        """Test cache respects TTL"""
        call_count = 0
        
        @cached(ttl=0, key_prefix="test")
        async def func():
            nonlocal call_count
            call_count += 1
            return "result"
        
        await func()
        await asyncio.sleep(0.1)
        await func()
        
        # Should call twice due to immediate expiration
        assert call_count == 2


class TestTimeoutDecorator:
    """Test @with_timeout decorator"""
    
    @pytest.mark.asyncio
    async def test_timeout_success(self):
        """Test function completes within timeout"""
        @with_timeout(1)
        async def quick_function():
            await asyncio.sleep(0.1)
            return "success"
        
        result = await quick_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_timeout_exceeded(self):
        """Test timeout raises TimeoutError"""
        @with_timeout(0.1)
        async def slow_function():
            await asyncio.sleep(1)
            return "should not reach"
        
        with pytest.raises(asyncio.TimeoutError):
            await slow_function()


class TestPerformanceMetrics:
    """Test performance metrics tracking"""
    
    @pytest.mark.asyncio
    async def test_record_metric(self):
        """Test recording metrics"""
        metrics = PerformanceMetrics()
        
        await metrics.record("test_metric", 100.5)
        await metrics.record("test_metric", 200.0)
        
        stats = await metrics.get_stats("test_metric")
        
        assert stats["count"] == 2
        assert stats["min"] == 100.5
        assert stats["max"] == 200.0
    
    @pytest.mark.asyncio
    async def test_metric_percentiles(self):
        """Test percentile calculations"""
        metrics = PerformanceMetrics()
        
        # Record 100 values
        for i in range(100):
            await metrics.record("test", float(i))
        
        stats = await metrics.get_stats("test")
        
        assert stats["p50"] == pytest.approx(50, abs=1)
        assert stats["p95"] == pytest.approx(95, abs=1)
        assert stats["p99"] == pytest.approx(99, abs=1)
    
    @pytest.mark.asyncio
    async def test_nonexistent_metric(self):
        """Test getting stats for nonexistent metric"""
        metrics = PerformanceMetrics()
        
        stats = await metrics.get_stats("nonexistent")
        
        assert stats == {}
    
    @pytest.mark.asyncio
    async def test_all_stats(self):
        """Test getting all metrics"""
        metrics = PerformanceMetrics()
        
        await metrics.record("metric1", 100)
        await metrics.record("metric2", 200)
        
        all_stats = await metrics.all_stats()
        
        assert "metric1" in all_stats
        assert "metric2" in all_stats


class TestTrackPerformanceDecorator:
    """Test @track_performance decorator"""
    
    @pytest.mark.asyncio
    async def test_tracks_duration(self):
        """Test performance tracking"""
        metrics = PerformanceMetrics()
        
        with patch('src.core.performance.get_metrics', return_value=metrics):
            @track_performance("test_operation")
            async def test_func():
                await asyncio.sleep(0.1)
                return "done"
            
            result = await test_func()
            
            assert result == "done"
            
            stats = await metrics.get_stats("test_operation")
            assert stats["count"] == 1
            assert stats["mean"] >= 100  # At least 100ms


class TestLLMBatcher:
    """Test LLM request batching"""
    
    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test batching multiple requests"""
        batcher = LLMBatcher(batch_size=3, max_wait_ms=100)
        
        # Mock the LLM call
        with patch.object(batcher, '_call_llm_single', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "response"
            
            # Add 3 requests (triggers batch)
            task1 = asyncio.create_task(batcher.add_request("prompt1"))
            task2 = asyncio.create_task(batcher.add_request("prompt2"))
            task3 = asyncio.create_task(batcher.add_request("prompt3"))
            
            results = await asyncio.gather(task1, task2, task3)
            
            assert len(results) == 3
            assert all(r == "response" for r in results)
            assert mock_llm.call_count == 3


class TestIntegration:
    """Integration tests for performance module"""
    
    @pytest.mark.asyncio
    async def test_cached_with_metrics(self):
        """Test combining caching and metrics"""
        call_count = 0
        
        @cached(ttl=60)
        @track_performance("combined_test")
        async def func(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call - cache miss
        result1 = await func(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call - cache hit
        result2 = await func(5)
        assert result2 == 10
        assert call_count == 1  # Still 1
        
        # Verify metrics tracked
        metrics = get_metrics()
        stats = await metrics.get_stats("combined_test")
        assert stats["count"] >= 1
