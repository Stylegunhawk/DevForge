"""Simple tests for semantic cache (no external deps)."""

import pytest
import numpy as np
from unittest.mock import AsyncMock
from src.agents.rag.cache.semantic_cache import SemanticCache, CachedQuery


def test_cached_query_similarity():
    """Test similarity calculation between embeddings."""
    # Create embeddings
    emb1 = np.array([1.0, 0.0, 0.0])
    emb2 = np.array([1.0, 0.0, 0.0])  # Identical
    emb3 = np.array([0.0, 1.0, 0.0])  # Orthogonal
    
    cached = CachedQuery(
        query="test",
        intent="debug",
        embedding=emb1,
        results={},
        timestamp=0.0
    )
    
    # Identical embeddings = similarity 1.0
    assert abs(cached.similarity(emb2) - 1.0) < 0.001
    
    # Orthogonal embeddings = similarity 0.0
    assert abs(cached.similarity(emb3) - 0.0) < 0.001


@pytest.mark.asyncio
async def test_semantic_cache_miss_empty():
    """Semantic cache miss when cache is empty."""
    cache = SemanticCache(similarity_threshold=0.92)
    
    result = await cache.get("test query", intent="debug")
    
    assert result is None
    assert cache.get_stats()["hits"] == 0
    assert cache.get_stats()["misses"] == 1


@pytest.mark.asyncio
async def test_semantic_cache_set_and_get():
    """Set and retrieve from semantic cache."""
    cache = SemanticCache(similarity_threshold=0.9)
    
    # Set a query
    await cache.set(
        query="authentication error",
        intent="debug",
        results={"documents": ["doc1", "doc2"]}
    )
    
    # Get similar query (same query, should hit)
    result = await cache.get("authentication error", intent="debug")
    
    assert result is not None
    assert result["documents"] == ["doc1", "doc2"]
    assert cache.get_stats()["hits"] == 1


@pytest.mark.asyncio
async def test_semantic_cache_intent_separation():
    """Cache entries are separated by intent."""
    cache = SemanticCache()
    
    # Cache same query with different intents
    await cache.set("JWT auth", intent="debug", results={"type": "debug"})
    await cache.set("JWT auth", intent="explain", results={"type": "explain"})
    
    # Retrieve with specific intent
    result_debug = await cache.get("JWT auth", intent="debug")
    result_explain = await cache.get("JWT auth", intent="explain")
    
    assert result_debug["type"] == "debug"
    assert result_explain["type"] == "explain"


@pytest.mark.asyncio
async def test_semantic_cache_lru_eviction():
    """LRU eviction when cache is full."""
    cache = SemanticCache(max_size_per_intent=2)
    
    # Fill cache for debug intent
    await cache.set("query1", intent="debug", results={"id": 1})
    await cache.set("query2", intent="debug", results={"id": 2})
    await cache.set("query3", intent="debug", results={"id": 3})  # Should evict query1
    
    # query1 should be evicted
    result1 = await cache.get("query1", intent="debug")
    result3 = await cache.get("query3", intent="debug")
    
    assert result1 is None  # Evicted
    assert result3 is not None  # Still in cache


def test_semantic_cache_stats():
    """Cache statistics tracking."""
    cache = SemanticCache()
    
    cache._hits = 10
    cache._misses = 5
    
    stats = cache.get_stats()
    
    assert stats["hits"] == 10
    assert stats["misses"] == 5
    assert stats["hit_rate"] == 10 / 15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
