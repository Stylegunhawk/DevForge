"""Unit tests for Phase 11 reranking module."""

import pytest
import asyncio
from src.storage.base_store import ChunkResult


def test_base_reranker_import():
    """Test 1: Import BaseReranker."""
    from src.agents.rag.reranking import BaseReranker
    assert BaseReranker is not None


def test_cross_encoder_import():
    """Test 2: Import CrossEncoderReranker."""
    from src.agents.rag.reranking import CrossEncoderReranker
    assert CrossEncoderReranker is not None


def test_normalize_score():
    """Test 3: Sigmoid normalization function."""
    from src.agents.rag.reranking import CrossEncoderReranker
    
    # Neutral (logit = 0)
    assert abs(CrossEncoderReranker.normalize_score(0) - 0.5) < 0.01
    
    # Positive (logit = 1)
    normalized_positive = CrossEncoderReranker.normalize_score(1)
    assert normalized_positive > 0.7
    
    # Negative (logit = -1)
    normalized_negative = CrossEncoderReranker.normalize_score(-1)
    assert normalized_negative < 0.3
    
    # Extreme positive
    assert CrossEncoderReranker.normalize_score(10) > 0.99
    
    # Extreme negative
    assert CrossEncoderReranker.normalize_score(-10) < 0.01


@pytest.mark.asyncio
async def test_reranker_initialization():
    """Test 4: CrossEncoderReranker initializes correctly."""
    from src.agents.rag.reranking import CrossEncoderReranker
    
    reranker = CrossEncoderReranker()
    assert reranker.model is not None
    assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"


@pytest.mark.asyncio
async def test_rerank_sorts_correctly():
    """Test 5: Reranking sorts by relevance."""
    from src.agents.rag.reranking import CrossEncoderReranker
    
    reranker = CrossEncoderReranker()
    
    chunks = [
        ChunkResult(
            id="1",
            content="This is completely irrelevant random text about nothing",
            metadata={},
            score=0.9  # High vector score but irrelevant
        ),
        ChunkResult(
            id="2",
            content="JWT token authentication validation security implementation",
            metadata={},
            score=0.7  # Lower vector score but relevant
        ),
    ]
    
    results = await reranker.rerank("JWT authentication", chunks, top_k=2)
    
    # Relevant content should be ranked higher
    assert results[0].id == "2"
    assert results[0].rerank_score > results[1].rerank_score
    assert 0 <= results[0].rerank_score <= 1  # Normalized


@pytest.mark.asyncio
async def test_score_reset():
    """Test 6: Scores are reset before reranking."""
    from src.agents.rag.reranking import CrossEncoderReranker
    
    reranker = CrossEncoderReranker()
    
    # Create chunk with pre-existing rerank_score
    chunk = ChunkResult(
        id="1",
        content="test content",
        metadata={},
        score=0.5,
        rerank_score=0.99  # Old score from previous run
    )
    
    results = await reranker.rerank("test query", [chunk], top_k=1)
    
    # Score should have been reset and recalculated
    assert results[0].rerank_score != 0.99
    assert 0 <= results[0].rerank_score <= 1


@pytest.mark.asyncio
async def test_empty_chunks():
    """Test 7: Handle empty chunk list."""
    from src.agents.rag.reranking import CrossEncoderReranker
    
    reranker = CrossEncoderReranker()
    results = await reranker.rerank("test", [], top_k=5)
    
    assert results == []


@pytest.mark.asyncio
async def test_top_k_limit():
    """Test 8: Respects top_k limit."""
    from src.agents.rag.reranking import CrossEncoderReranker
    
    reranker = CrossEncoderReranker()
    
    chunks = [
        ChunkResult(id=str(i), content=f"content {i}", metadata={}, score=0.5)
        for i in range(10)
    ]
    
    results = await reranker.rerank("test", chunks, top_k=3)
    
    assert len(results) == 3


@pytest.mark.asyncio
async def test_content_truncation():
    """Test 9: Content is truncated correctly."""
    from src.agents.rag.reranking import CrossEncoderReranker
    
    reranker = CrossEncoderReranker()
    
    # Create chunk with very long content (>2048 chars)
    long_content = "x" * 5000
    chunk = ChunkResult(
        id="1",
        content=long_content,
        metadata={},
        score=0.5
    )
    
    # Should not raise error (content truncated internally)
    results = await reranker.rerank("test", [chunk], top_k=1)
    
    assert len(results) == 1
    assert results[0].rerank_score is not None


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Phase 11 Day 1 - Reranker Unit Tests")
    print("=" * 60)
    
    # Run with pytest
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_all_tests()
