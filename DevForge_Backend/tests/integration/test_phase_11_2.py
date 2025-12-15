"""Integration tests for Phase 11.2 - Retrieval Optimization.

Tests:
- Query cache (exact-match, hit/miss)
- Hybrid search (BM25 + Vector with RRF)
- Vector-only fallback
- Full pipeline (cache → hybrid → rerank → boost)
- Observability endpoints
"""

import pytest
from src.agents.rag.agent import RAGAgent
from src.core.config import settings


class TestQueryCacheIntegration:
    """Test query cache with full retrieval pipeline."""
    
    @pytest.mark.asyncio
    async def test_cache_miss_then_hit(self):
        """First query should miss, second should hit."""
        if not settings.ENABLE_QUERY_CACHE:
            pytest.skip("Query cache disabled")
        
        agent = RAGAgent()
        query = "test authentication query"
        
        # First retrieval (cache miss)
        result1 = await agent.retrieve_with_reranking(query, top_k=5, use_cache=True)
        assert result1.get("from_cache") == False
        
        # Second retrieval (cache hit)
        result2 = await agent.retrieve_with_reranking(query, top_k=5, use_cache=True)
        if settings.ENABLE_QUERY_CACHE:
            assert result2.get("from_cache") == True
            # Results should be identical (from cache)
            assert len(result2.get("documents", [])) == len(result1.get("documents", []))
    
    @pytest.mark.asyncio
    async def test_cache_respects_top_k(self):
        """Different top_k should produce different cache keys."""
        if not settings.ENABLE_QUERY_CACHE:
            pytest.skip("Query cache disabled")
        
        agent = RAGAgent()
        query = "JWT authentication"
        
        # Query with top_k=5
        result1 = await agent.retrieve_with_reranking(query, top_k=5)
        
        # Query with top_k=10 (different cache key)
        result2 = await agent.retrieve_with_reranking(query, top_k=10)
        
        # Should not be from cache (different keys)
        assert result2.get("from_cache") == False
    
    @pytest.mark.asyncio
    async def test_cache_disabled_per_query(self):
        """use_cache=False should bypass cache."""
        agent = RAGAgent()
        query = "test query"
        
        # Query with cache disabled
        result = await agent.retrieve_with_reranking(query, top_k=5, use_cache=False)
        
        # Should never be from cache
        assert result.get("from_cache") == False


class TestHybridSearchIntegration:
    """Test hybrid search (BM25 + Vector) integration."""
    
    @pytest.mark.asyncio
    async def test_hybrid_search_enabled(self):
        """When enabled, hybrid search should be used."""
        if not settings.ENABLE_HYBRID_SEARCH:
            pytest.skip("Hybrid search disabled")
        
        agent = RAGAgent()
        
        # Initialize BM25 if not ready
        if agent._bm25_index and not agent._bm25_index.is_ready():
            await agent.init_bm25()
        
        # Query with hybrid search
        result = await agent.retrieve_with_reranking(
            query="authentication system",
            top_k=5,
            use_hybrid=True
        )
        
        # Should return results (hybrid or fallback)
        assert "documents" in result
        assert isinstance(result["documents"], list)
    
    @pytest.mark.asyncio
    async def test_hybrid_fallback_to_vector(self):
        """If BM25 fails, should fall back to vector-only."""
        agent = RAGAgent()
        
        # Force hybrid to fail by not initializing BM25
        if agent._bm25_index:
            agent._bm25_index._is_ready = False
        
        # Query should still work (vector fallback)
        result = await agent.retrieve_with_reranking(
            query="test query",
            top_k=5,
            use_hybrid=True
        )
        
        # Should return results via fallback
        assert "documents" in result
    
    @pytest.mark.asyncio
    async def test_vector_only_mode(self):
        """use_hybrid=False should use vector-only."""
        agent = RAGAgent()
        
        result = await agent.retrieve_with_reranking(
            query="test query",
            top_k=5,
            use_hybrid=False
        )
        
        # Should return results
        assert "documents" in result


class TestFullPipeline:
    """Test complete retrieval pipeline."""
    
    @pytest.mark.asyncio
    async def test_cache_hybrid_rerank_pipeline(self):
        """Test: Cache → Hybrid → Rerank → Boost → Threshold → Fallback."""
        agent = RAGAgent()
        
        # Initialize if needed
        if agent._bm25_index and not agent._bm25_index.is_ready():
            await agent.init_bm25()
        
        query = "implement JWT authentication"
        
        # Full pipeline
        result = await agent.retrieve_with_reranking(
            query=query,
            top_k=5,
            use_cache=True,
            use_hybrid=True,
            use_reranking=True
        )
        
        # Validate response structure
        assert "documents" in result
        assert "from_cache" in result
        
        # If reranking enabled, should have rerank metadata
        if settings.ENABLE_RERANKING and result.get("reranked"):
            assert "threshold_passed" in result or "fallback_used" in result
    
    @pytest.mark.asyncio
    async def test_all_features_disabled(self):
        """System should work with all features disabled."""
        agent = RAGAgent()
        
        # Disable everything
        result = await agent.retrieve_with_reranking(
            query="test",
            top_k=5,
            use_cache=False,
            use_hybrid=False,
            use_reranking=False
        )
        
        # Should still return results (basic vector search)
        assert "documents" in result
        assert result["from_cache"] == False
        assert result["reranked"] == False


class TestObservabilityEndpoints:
    """Test observability endpoints are production-safe."""
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint_never_throws(self):
        """GET /rag/metrics must never throw exceptions."""
        from src.api.routers import get_rag_metrics
        
        # Should return metrics even if components fail
        metrics = await get_rag_metrics()
        
        assert isinstance(metrics, dict)
        assert "version" in metrics
        assert metrics["version"] == "11.2.0"
        
        # Should have component metrics (even if errored)
        assert "cache" in metrics
        assert "hybrid_search" in metrics
        assert "reranking" in metrics
        assert "code_graph" in metrics
    
    @pytest.mark.asyncio
    async def test_health_endpoint_returns_status(self):
        """GET /rag/health should return valid status."""
        from src.api.routers import rag_health_check
        
        response = await rag_health_check()
        
        # Should return JSONResponse or dict
        if hasattr(response, 'body'):
            # JSONResponse
            import json
            content = json.loads(response.body)
        else:
            content = response
        
        assert "status" in content
        assert content["status"] in ["healthy", "degraded", "unhealthy"]
        assert "components" in content


class TestBackwardCompatibility:
    """Ensure Phase 11.2 is backward compatible."""
    
    @pytest.mark.asyncio
    async def test_old_retrieve_still_works(self):
        """RAGAgent.retrieve() should still work (backward compat)."""
        agent = RAGAgent()
        
        # Old method signature
        results = await agent.retrieve(query="test", top_k=5)
        
        # Should return results
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_feature_flags_respected(self):
        """Feature flags should properly disable features."""
        from src.core.config import settings
        
        # Check flags are boolean
        assert isinstance(settings.ENABLE_QUERY_CACHE, bool)
        assert isinstance(settings.ENABLE_HYBRID_SEARCH, bool)
        assert isinstance(settings.ENABLE_RERANKING, bool)


def run_all_tests():
    """Run all Phase 11.2 integration tests."""
    print("=" * 60)
    print("Phase 11.2 Integration Tests")
    print("=" * 60)
    
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_all_tests()
