"""Simplified unit tests for Phase 12A - no async complications."""

import pytest
from unittest.mock import MagicMock


# ============================================================
# RRF Fusion Tests (Simple, No External Deps)
# ============================================================

def test_rrf_deduplication():
    """RRF deduplicates by qualified_id."""
    from src.agents.rag.expansion import fuse_results_rrf
    
    # Create mock documents
    doc1 = MagicMock(qualified_id="file1::func1", id="1")
    doc2 = MagicMock(qualified_id="file2::func2", id="2")
    doc3 = MagicMock(qualified_id="file1::func1", id="1")  # Duplicate
    
    results_per_query = [
        [doc1, doc2],
        [doc3, doc2]  # doc3 is duplicate of doc1
    ]
    
    fused = fuse_results_rrf(results_per_query)
    
    # Should have only 2 unique docs
    assert len(fused) == 2
    ids = [doc.qualified_id for doc in fused]
    assert "file1::func1" in ids
    assert "file2::func2" in ids


def test_rrf_empty_input():
    """RRF handles empty input."""
    from src.agents.rag.expansion import fuse_results_rrf
    
    fused = fuse_results_rrf([])
    assert fused == []


def test_rrf_ranking():
    """RRF ranks docs appearing in multiple queries higher."""
    from src.agents.rag.expansion import fuse_results_rrf
    
    doc1 = MagicMock(qualified_id="doc1", id="1")
    doc2 = MagicMock(qualified_id="doc2", id="2")
    doc3 = MagicMock(qualified_id="doc3", id="3")
    
    # doc1 appears in all 3 queries (highest rank)
    results_per_query = [
        [doc1, doc2, doc3],
        [doc1, doc2],
        [doc1]
    ]
    
    fused = fuse_results_rrf(results_per_query)
    
    # doc1 should be first (highest RRF score)
    assert fused[0].qualified_id == "doc1"


def test_intent_keywords_defined():
    """Intent keywords are properly defined."""
    from src.agents.rag.analytics import INTENT_KEYWORDS
    
    assert "debug" in INTENT_KEYWORDS
    assert "explain" in INTENT_KEYWORDS
    assert "code_search" in INTENT_KEYWORDS
    assert len(INTENT_KEYWORDS["debug"]) > 0


def test_query_expander_keyword_fallback():
    """Query expander has keyword fallback."""
    from src.agents.rag.expansion import QueryExpander
    
    expander = QueryExpander()
    
    # Test keyword expansion (no LLM needed)
    variations = expander._expand_with_keywords("JWT auth", intent="debug", count=2)
    
    assert len(variations) == 2
    assert all("JWT auth" in v for v in variations)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
