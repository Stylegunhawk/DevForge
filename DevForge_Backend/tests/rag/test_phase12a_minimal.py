"""Minimal unit tests for Phase 12A components.

Tests work WITHOUT external dependencies:
- No Redis required
- No Chroma required
- No LLMs required (mocked)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.rag.analytics import IntentClassifier, INTENT_KEYWORDS
from src.agents.rag.expansion import QueryExpander, fuse_results_rrf


# ============================================================
# Intent Classification Tests
# ============================================================

class TestIntentClassifierBasic:
    """Basic intent classification tests (no external deps)."""
    
    @pytest.mark.asyncio
    async def test_rule_based_debug(self):
        """Debug intent via keywords."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result = await classifier.classify("why does this fail with error")
        
        assert result.intent == "debug"
        assert result.method == "rule_based"
        assert result.confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_rule_based_code_search(self):
        """Code search intent via keywords."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result = await classifier.classify("find implementation example")
        
        assert result.intent == "code_search"
        assert result.method == "rule_based"
    
    @pytest.mark.asyncio
    async def test_default_fallback(self):
        """Ambiguous query falls back to default."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result = await classifier.classify("JWT")
        
        assert result.method == "default"
        assert result.intent == "code_search"  # Default
        assert result.confidence == 0.5


# ============================================================
# Query Expansion Tests (Mocked LLM)
# ============================================================

class TestQueryExpanderMocked:
    """Query expander tests with mocked LLM."""
    
    @pytest.mark.asyncio
    async def test_keyword_fallback_expansion(self):
        """Keyword fallback works without LLM."""
        expander = QueryExpander(llm_timeout=1)
        
        # Mock LLM to always fail (triggers keyword fallback)
        import src.agents.rag.expansion.query_expander as exp_module
        original_expand = expander._expand_with_llm
        expander._expand_with_llm = AsyncMock(return_value=None)
        
        result = await expander.expand("authentication bug", intent="debug", count=2)
        
        assert len(result.expanded_queries) >= 1  # Original + variations
        assert result.original_query in result.expanded_queries
        assert result.method == "keyword"
        assert result.intent == "debug"
    
    def test_variation_parsing(self):
        """Parse LLM output correctly."""
        expander = QueryExpander()
        
        llm_output = """1. authentication error causes
2. - debugging authentication steps
authentication implementation example"""
        
        variations = expander._parse_variations(llm_output, count=3)
        
        # Should extract 3 valid variations (min 5 words each)
        assert len(variations) <= 3
        for var in variations:
            assert len(var.split()) >= 5
    
    def test_keyword_expansion_structure(self):
        """Keyword expansion generates correct structure."""
        expander = QueryExpander()
        
        variations = expander._expand_with_keywords("JWT auth", intent="debug", count=2)
        
        assert len(variations) == 2
        assert all("JWT auth" in v for v in variations)


# ============================================================
# Result Fusion Tests
# ============================================================

class TestRRFFusion:
    """RRF fusion tests (no external deps)."""
    
    def test_rrf_deduplication(self):
        """RRF deduplicates by qualified_id."""
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
    
    def test_rrf_empty_input(self):
        """RRF handles empty input."""
        fused = fuse_results_rrf([])
        assert fused == []
    
    def test_rrf_ranking(self):
        """RRF ranks docs appearing in multiple queries higher."""
        doc1 = MagicMock(qualified_id="doc1", id="1")
        doc2 = MagicMock(qualified_id="doc2", id="2")
        doc3 = MagicMock(qualified_id="doc3", id="3")
        
        # doc1 appears in all 3 queries (highest rank)
        # doc2 appears in 2 queries
        # doc3 appears in 1 query (lowest rank)
        results_per_query = [
            [doc1, doc2, doc3],
            [doc1, doc2],
            [doc1]
        ]
        
        fused = fuse_results_rrf(results_per_query)
        
        # doc1 should be first (highest RRF score)
        assert fused[0].qualified_id == "doc1"


#  ============================================================
# Integration: Intent → Expansion
# ============================================================

class TestIntentExpansionIntegration:
    """Test intent classification → expansion flow."""
    
    @pytest.mark.asyncio
    async def test_debug_intent_gets_2_expansions(self):
        """Debug intent should trigger 2-count expansion."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        expander = QueryExpander()
        
        # Classify
        intent_result = await classifier.classify("why login fails")
        assert intent_result.intent == "debug"
        
        # Expand with keyword fallback
        expander._expand_with_llm = AsyncMock(return_value=None)
        exp_result = await expander.expand(
            "why login fails",
            intent=intent_result.intent
        )
        
        # Should have 2 variations + original
        assert exp_result.count == 2
        assert len(exp_result.expanded_queries) == 3  # original + 2


def run_all_tests():
    """Run all Phase 12A unit tests."""
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_all_tests()
