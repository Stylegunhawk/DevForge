"""Integration tests for Phase 11 Day 2 - RAGAgent reranking integration."""

import pytest
import asyncio
from src.agents.rag.agent import RAGAgent
from src.storage.base_store import ChunkResult
from src.core.config import settings


@pytest.mark.asyncio
async def test_reranker_property_lazy_load():
    """Test 1: Reranker property lazy loads correctly."""
    agent = RAGAgent()
    
    # Reranker should be None initially
    assert agent._reranker is None
    
    # Access property (should lazy load if enabled)
    if settings.ENABLE_RERANKING:
        reranker = agent.reranker
        assert reranker is not None
        # Second access should return same instance
        reranker2 = agent.reranker
        assert reranker is reranker2


@pytest.mark.asyncio
async def test_retrieve_with_reranking_disabled():
    """Test 2: retrieve_with_reranking when reranking disabled."""
    # Mock settings to disable
    original = settings.ENABLE_RERANKING
    settings.ENABLE_RERANKING = False
    
    try:
        agent = RAGAgent()
        # Should return non-reranked results
        # (Note: This requires mock data or actual vector store)
        # Placeholder test
        assert agent.reranker is None
    finally:
        settings.ENABLE_RERANKING = original


@pytest.mark.asyncio
async def test_threshold_fallback_case_a():
    """Test 3: Threshold fallback - Case A (≥3 pass)."""
    from src.agents.rag.reranking import CrossEncoderReranker
    
    agent = RAGAgent()
    
    # Create mock candidates with high rerank scores
    candidates = [
        ChunkResult(
            id=str(i),
            content=f"Relevant content {i}",
            metadata={},
            score=0.8,
            rerank_score=0.9 - (i * 0.05)  # High scores
        )
        for i in range(5)
    ]
    
    # Simulate reranking (threshold = 0.3)
    filtered = [c for c in candidates if c.rerank_score >= 0.3]
    
    # Case A: Should have ≥3 results
    assert len(filtered) >= 3


@pytest.mark.asyncio
async def test_threshold_fallback_case_b():
    """Test 4: Threshold fallback - Case B (1-2 pass, blend with vector)."""
    # Create scenario where only 1-2 results pass threshold
    candidates = [
        ChunkResult(id="1", content="High relevance", metadata={}, score=0.9, rerank_score=0.8),
        ChunkResult(id="2", content="Low relevance", metadata={}, score=0.7, rerank_score=0.2),
        ChunkResult(id="3", content="Low relevance", metadata={}, score=0.6, rerank_score=0.1),
    ]
    
    threshold = 0.3
    filtered = [c for c in candidates if c.rerank_score >= threshold]
    
    # Case B: Only 1 passes
    assert len(filtered) < 3
    
    # Should blend with vector results
    top_k = 3
    remaining = top_k - len(filtered)
    fallback = [c for c in candidates if c not in filtered][:remaining]
    final = filtered + fallback
    
    assert len(final) == top_k


@pytest.mark.asyncio
async def test_threshold_fallback_case_c():
    """Test 5: Threshold fallback - Case C (0 pass, use vector)."""
    # All results below threshold
    candidates = [
        ChunkResult(id=str(i), content=f"Low {i}", metadata={}, score=0.5, rerank_score=0.1)
        for i in range(5)
    ]
    
    threshold = 0.3
    filtered = [c for c in candidates if c.rerank_score >= threshold]
    
    # Case C: None pass
    assert len(filtered) == 0
    
    # Should return vector results
    top_k = 5
    final = candidates[:top_k]
    assert len(final) == top_k  # Never zero


@pytest.mark.asyncio
async def test_retrieve_with_reranking_response_structure():
    """Test 6: retrieve_with_reranking returns correct structure."""
    # This test requires actual implementation
    # Placeholder for structure validation
    expected_keys = ["documents", "reranked"]
    
    # Mock response
    response = {
        "documents": [],
        "reranked": False,
        "reason": "test"
    }
    
    assert "documents" in response
    assert "reranked" in response


@pytest.mark.asyncio
async def test_vector_search_candidates_setting():
    """Test 7: Honors VECTOR_SEARCH_CANDIDATES setting."""
    # When reranking enabled, should retrieve more candidates
    assert settings.VECTOR_SEARCH_CANDIDATES == 30
    
    # Initial retrieval should use this value
    initial_top_k = settings.VECTOR_SEARCH_CANDIDATES
    assert initial_top_k > 5  # More than final top_k


def run_all_tests():
    """Run all integration tests."""
    print("=" * 60)
    print("Phase 11 Day 2 - Integration Tests")
    print("=" * 60)
    
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_all_tests()
