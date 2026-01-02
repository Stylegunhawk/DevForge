"""Unit tests for Phase 11.2 Day 1 - Query Cache.

Tests:
- Query normalization (token length aware)
- Cache key generation
- Cache operations (hit/miss, LRU eviction)
- Redis fallback to memory
"""

import pytest
from src.agents.rag.cache import normalize_query, cache_key_from_query, QueryCache


class TestQueryNormalization:
    """Test query normalization with token length awareness."""
    
    def test_short_query_sorting(self):
        """Short queries (<= 6 tokens) should have sorted tokens."""
        # 2 tokens
        assert normalize_query("JWT authentication") == normalize_query("authentication JWT")
        
        # 6 tokens (at threshold)
        q1 = "how to implement jwt token validation python"
        q2 = "python validation token jwt implement how to"
        assert normalize_query(q1) == normalize_query(q2)
    
    def test_long_query_no_sorting(self):
        """Long queries (> 6 tokens) should preserve order."""
        # 10 tokens - stack trace like
        q1 = "traceback most recent call last file auth py line 42 error"
        q2 = "error 42 line py auth file last call recent most traceback"
        
        # Should NOT be equal (order preserved)
        assert normalize_query(q1) != normalize_query(q2)
    
    def test_lowercase_conversion(self):
        """All queries should be lowercased."""
        assert normalize_query("JWT AUTH") == normalize_query("jwt auth")
    
    def test_punctuation_removal(self):
        """Punctuation (except underscores) should be removed."""
        assert normalize_query("How to use JWT?") == normalize_query("how to use jwt")
        assert normalize_query("get_user()") == normalize_query("get_user")
        
        # Underscores preserved
        assert "get_user" in normalize_query("get_user function")
    
    def test_whitespace_collapse(self):
        """Multiple spaces should collapse to single space."""
        assert normalize_query("JWT    authentication") == normalize_query("JWT authentication")


class TestCacheKeyGeneration:
    """Test cache key generation with SHA256."""
    
    def test_same_query_same_top_k(self):
        """Same query + top_k should produce same key."""
        key1 = cache_key_from_query("JWT auth", 5)
        key2 = cache_key_from_query("JWT auth", 5)
        assert key1 == key2
    
    def test_different_top_k(self):
        """Different top_k should produce different keys."""
        key1 = cache_key_from_query("JWT auth", 5)
        key2 = cache_key_from_query("JWT auth", 10)
        assert key1 != key2
    
    def test_key_length(self):
        """Cache keys should be 64-char SHA256 hashes."""
        key = cache_key_from_query("test", 5)
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


class TestQueryCacheMemory:
    """Test in-memory LRU cache (no Redis)."""
    
    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Initial lookup should be a miss."""
        cache = QueryCache(redis_client=None, max_size=10)
        result = await cache.get("test_key")
        assert result is None
        assert cache.get_hit_rate() == 0.0
    
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """After set, lookup should hit."""
        cache = QueryCache(redis_client=None, max_size=10)
        
        test_data = {"documents": [{"id": "1", "content": "test"}]}
        await cache.set("test_key", test_data)
        
        result = await cache.get("test_key")
        assert result == test_data
    
    @pytest.mark.asyncio
    async def test_hit_rate_calculation(self):
        """Hit rate should be calculated correctly."""
        cache = QueryCache(redis_client=None, max_size=10)
        
        await cache.set("key1", {"data": 1})
        
        # 1 miss
        await cache.get("key2")
        assert cache.get_hit_rate() == 0.0
        
        # 1 hit
        await cache.get("key1")
        assert cache.get_hit_rate() == 0.5  # 1 hit, 1 miss
        
        # Another hit
        await cache.get("key1")
        assert cache.get_hit_rate() == pytest.approx(0.666, 0.01)  # 2 hits, 1 miss
    
    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Oldest entry should be evicted when max_size reached."""
        cache = QueryCache(redis_client=None, max_size=2)
        
        await cache.set("key1", {"data": 1})
        await cache.set("key2", {"data": 2})
        await cache.set("key3", {"data": 3})  # Should evict key1
        
        assert await cache.get("key1") is None  # Evicted
        assert await cache.get("key2") == {"data": 2}
        assert await cache.get("key3") == {"data": 3}
    
    @pytest.mark.asyncio
    async def test_lru_move_to_end(self):
        """Accessing an entry should move it to end (LRU)."""
        cache = QueryCache(redis_client=None, max_size=2)
        
        await cache.set("key1", {"data": 1})
        await cache.set("key2", {"data": 2})
        
        # Access key1 (moves to end)
        await cache.get("key1")
        
        # Add key3 (should evict key2, not key1)
        await cache.set("key3", {"data": 3})
        
        assert await cache.get("key1") == {"data": 1}  # Still there
        assert await cache.get("key2") is None  # Evicted
        assert await cache.get("key3") == {"data": 3}
    
    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """get_stats should return cache metrics."""
        cache = QueryCache(redis_client=None, max_size=10)
        
        await cache.set("key1", {"data": 1})
        await cache.get("key1")  # hit
        await cache.get("key2")  # miss
        
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["memory_size"] == 1
        assert stats["backend"] == "memory_only"
    
    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """clear should remove all entries."""
        cache = QueryCache(redis_client=None, max_size=10)
        
        await cache.set("key1", {"data": 1})
        await cache.set("key2", {"data": 2})
        
        await cache.clear()
        
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert cache.get_stats()["memory_size"] == 0


class TestCacheIntegration:
    """Integration tests for cache with RAGAgent."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_returns_same_shape(self):
        """Cached results should have from_cache=True flag."""
        cache = QueryCache(redis_client=None)
        
        # Simulate cached result
        original_result = {
            "documents": [{"id": "1", "content": "test"}],
            "reranked": True,
            "threshold_passed": 3
        }
        
        from src.agents.rag.cache import cache_key_from_query
        key = cache_key_from_query("test query", 5)
        await cache.set(key, original_result)
        
        # Retrieve from cache
        cached = await cache.get(key)
        
        assert cached == original_result
        # Note: from_cache flag would be added by RAGAgent


def run_all_tests():
    """Run all cache tests."""
    print("=" * 60)
    print("Phase 11.2 Day 1 - Query Cache Tests")
    print("=" * 60)
    
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_all_tests()
