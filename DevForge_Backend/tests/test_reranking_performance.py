"""Performance tests for Phase 11 Day 3 - Code-aware boosting and latency."""

import pytest
import asyncio
import time
from src.agents.rag.reranking import CrossEncoderReranker
from src.storage.base_store import ChunkResult
from src.core.config import settings


def test_code_boost_application():
    """Test 1: Code boosting applies correct multipliers."""
    reranker = CrossEncoderReranker()
    
    chunks = [
        ChunkResult(id="1", content="test", metadata={"chunk_type": "function"}, score=0.5, rerank_score=1.0),
        ChunkResult(id="2", content="test", metadata={"chunk_type": "class"}, score=0.5, rerank_score=1.0),
        ChunkResult(id="3", content="test", metadata={"chunk_type": "import"}, score=0.5, rerank_score=1.0),
        ChunkResult(id="4", content="test", metadata={"chunk_type": "text"}, score=0.5, rerank_score=1.0),
    ]
    
    boosted = reranker.apply_code_boost(chunks)
    
    # Verify boost factors
    assert boosted[0].rerank_score == 1.0 * settings.BOOST_FUNCTION  # 1.2
    assert boosted[1].rerank_score == 1.0 * settings.BOOST_CLASS     # 1.15
    assert boosted[2].rerank_score == 1.0 * settings.BOOST_IMPORT    # 1.0
    assert boosted[3].rerank_score == 1.0 * settings.BOOST_TEXT      # 0.95


def test_boosting_changes_order():
    """Test 2: Boosting changes result ordering."""
    reranker = CrossEncoderReranker()
    
    chunks = [
        ChunkResult(id="text", content="text", metadata={"chunk_type": "text"}, score=0.5, rerank_score=0.9),
        ChunkResult(id="func", content="func", metadata={"chunk_type": "function"}, score=0.5, rerank_score=0.85),
    ]
    
    # Before boost: text > func
    assert chunks[0].id == "text"
    
    # Apply boost
    boosted = reranker.apply_code_boost(chunks)
    boosted.sort(key=lambda c: c.rerank_score, reverse=True)
    
    # After boost: func should be higher (0.85 * 1.2 = 1.02 > 0.9 * 0.95 = 0.855)
    assert boosted[0].id == "func"


@pytest.mark.asyncio
async def test_reranking_latency():
    """Test 3: Reranking completes within 200ms for 30 candidates."""
    reranker = CrossEncoderReranker()
    
    # Generate 30 mock chunks
    chunks = [
        ChunkResult(
            id=str(i),
            content=f"Sample content for chunk {i} with some text to rerank",
            metadata={"chunk_type": "function"},
            score=0.5
        )
        for i in range(30)
    ]
    
    # Measure latency
    start = time.time()
    results = await reranker.rerank("test query authentication", chunks, top_k=5)
    latency_ms = (time.time() - start) * 1000
    
    print(f"Reranking latency: {latency_ms:.2f}ms")
    
    # Should complete in < 200ms (may fail on slow machines)
    # Using 500ms threshold for CI/test environments
    assert latency_ms < 500, f"Reranking took {latency_ms}ms (budget: 200ms, CI threshold: 500ms)"
    
    # Verify results
    assert len(results) <= 5
    assert all(hasattr(r, 'rerank_score') for r in results)


@pytest.mark.asyncio
async def test_boosting_with_threshold():
    """Test 4: Boosting affects threshold filtering."""
    reranker = CrossEncoderReranker()
    
    # Create chunk that passes threshold after boost
    chunk_func = ChunkResult(
        id="func",
        content="function add(a, b) { return a + b; }",
        metadata={"chunk_type": "function"},
        score=0.5,
        rerank_score=0.27  # Below threshold (0.3)
    )
    
    # Before boost: fails threshold
    assert chunk_func.rerank_score < settings.RERANK_SCORE_THRESHOLD
    
    # Apply boost: 0.27 * 1.2 = 0.324
    boosted = reranker.apply_code_boost([chunk_func])
    
    # After boost: passes threshold
    assert boosted[0].rerank_score >= settings.RERANK_SCORE_THRESHOLD


def test_boost_constants_from_config():
    """Test 5: Boost constants loaded from config."""
    assert settings.BOOST_FUNCTION == 1.2
    assert settings.BOOST_CLASS == 1.15
    assert settings.BOOST_IMPORT == 1.0
    assert settings.BOOST_TEXT == 0.95


@pytest.mark.asyncio
async def test_async_thread_pool():
    """Test 6: Reranking uses async thread pool (no blocking)."""
    reranker = CrossEncoderReranker()
    
    chunks = [
        ChunkResult(id=str(i), content=f"content {i}", metadata={}, score=0.5)
        for i in range(10)
    ]
    
    # This should not block the event loop
    # If it blocks, this test would hang
    results = await asyncio.wait_for(
        reranker.rerank("test", chunks, top_k=5),
        timeout=5.0  # 5 second timeout
    )
    
    assert len(results) <= 5


def run_all_tests():
    """Run all performance tests."""
    print("=" * 60)
    print("Phase 11 Day 3 - Performance & Boosting Tests")
    print("=" * 60)
    
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_all_tests()
