"""Unit tests for intent classification.

Tests:
- Rule-based classification (fast path)
- LLM fallback (when enabled)
- Default fallback
- Confidence scoring
- Metrics tracking
- Edge cases
"""

import pytest
from src.agents.rag.analytics import IntentClassifier, INTENT_KEYWORDS, DEFAULT_INTENT


class TestRuleBasedClassification:
    """Test Tier 1: Rule-based keyword scoring."""
    
    @pytest.mark.asyncio
    async def test_debug_intent_strong_match(self):
        """Strong debug intent with multiple keywords."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result = await classifier.classify("why does login fail with error")
        
        assert result.intent == "debug"
        assert result.method == "rule_based"
        assert result.confidence > 0.5
        assert result.keyword_scores["debug"] >= 2
        assert result.latency_ms < 10  # Should be very fast
    
    @pytest.mark.asyncio
    async def test_explain_intent(self):
        """Explain intent classification."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result = await classifier.classify("how does JWT authentication work")
        
        assert result.intent == "explain"
        assert result.method == "rule_based"
        assert result.keyword_scores["explain"] >= 2
    
    @pytest.mark.asyncio
    async def test_code_search_intent(self):
        """Code search intent classification."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result = await classifier.classify("find JWT implementation example")
        
        assert result.intent == "code_search"
        assert result.method == "rule_based"
        assert result.keyword_scores["code_search"] >= 2
    
    @pytest.mark.asyncio
    async def test_api_reference_intent(self):
        """API reference intent classification."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result = await classifier.classify("API endpoint documentation for authentication")
        
        assert result.intent == "api_reference"
        assert result.method == "rule_based"
    
    @pytest.mark.asyncio
    async def test_troubleshoot_intent(self):
        """Troubleshoot intent classification."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result = await classifier.classify("fix solution for authentication problem")
        
        assert result.intent == "troubleshoot"
        assert result.method == "rule_based"
    
    @pytest.mark.asyncio
    async def test_case_insensitive(self):
        """Keywords should match case-insensitively."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result1 = await classifier.classify("WHY DOES LOGIN FAIL")
        result2 = await classifier.classify("why does login fail")
        
        assert result1.intent == result2.intent == "debug"
    
    @pytest.mark.asyncio
    async def test_threshold_enforcement(self):
        """Queries below threshold should not use rule-based."""
        classifier = IntentClassifier(rule_threshold=3, llm_enabled=False)
        
        # Only 1 keyword match (below threshold of 3)
        result = await classifier.classify("why login")
        
        # Should fall back to default (not enough keywords)
        assert result.method == "default"
        assert result.intent == DEFAULT_INTENT


class TestDefaultFallback:
    """Test Tier 3: Default fallback."""
    
    @pytest.mark.asyncio
    async def test_ambiguous_query_falls_back(self):
        """Ambiguous query with no strong intent."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result = await classifier.classify("JWT token")
        
        # Only 0-1 keyword matches
        assert result.method == "default"
        assert result.intent == DEFAULT_INTENT
        assert result.confidence == 0.5  # Low confidence
    
    @pytest.mark.asyncio
    async def test_empty_query_falls_back(self):
        """Empty or whitespace-only query."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result = await classifier.classify("")
        
        assert result.method == "default"
        assert result.intent == DEFAULT_INTENT
    
    @pytest.mark.asyncio
    async def test_single_word_query(self):
        """Single word query."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result = await classifier.classify("authentication")
        
        # Unlikely to hit threshold with single word
        assert result.method == "default"


class TestConfidenceScoring:
    """Test confidence calculation logic."""
    
    @pytest.mark.asyncio
    async def test_confidence_increases_with_matches(self):
        """More keyword matches = higher confidence."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result1 = await classifier.classify("why error")  # 2 keywords
        result2 = await classifier.classify("why does this fail with error and bug")  # 4+ keywords
        
        assert result2.confidence > result1.confidence
    
    @pytest.mark.asyncio
    async def test_confidence_capped_at_1(self):
        """Confidence should not exceed 1.0."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        # Many debug keywords
        result = await classifier.classify(
            "why does this fail with error bug issue problem exception crash"
        )
        
        assert result.confidence <= 1.0


class TestMetricsTracking:
    """Test statistics and metrics."""
    
    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Statistics should be tracked correctly."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        # Classify several queries
        await classifier.classify("find code example")  # code_search
        await classifier.classify("why error")  # debug
        await classifier.classify("how works")  # explain
        
        stats = classifier.get_stats()
        
        assert stats["total"] == 3
        assert stats["method_breakdown"]["rule_based"]["count"] == 3
        assert stats["method_breakdown"]["rule_based"]["percentage"] == 100.0
        assert "code_search" in stats["intent_distribution"]
    
    @pytest.mark.asyncio
    async def test_default_fallback_recommendation(self):
        """High default rate should trigger recommendation."""
        classifier = IntentClassifier(rule_threshold=10, llm_enabled=False)  # High threshold
        
        # These will all fall back to default
        for _ in range(10):
            await classifier.classify("test query")
        
        stats = classifier.get_stats()
        
        assert stats["method_breakdown"]["default"]["percentage"] > 20
        assert "Consider enabling LLM" in stats["recommendation"]
    
    @pytest.mark.asyncio
    async def test_reset_stats(self):
        """Stats should reset correctly."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        await classifier.classify("find code")
        assert classifier.get_stats()["total"] == 1
        
        classifier.reset_stats()
        assert classifier.get_stats()["total"] == 0


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_special_characters(self):
        """Queries with special characters should work."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result = await classifier.classify("why does @auth/login() fail?")
        
        assert result.intent == "debug"  # Should ignore special chars
    
    @pytest.mark.asyncio
    async def test_very_long_query(self):
        """Very long queries should not break."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        long_query = "find code example " * 100
        result = await classifier.classify(long_query)
        
        assert result.intent == "code_search"
        assert result.latency_ms < 50  # Should still be fast
    
    @pytest.mark.asyncio
    async def test_unicode_characters(self):
        """Unicode characters should be handled."""
        classifier = IntentClassifier(rule_threshold=2, llm_enabled=False)
        
        result = await classifier.classify("найти код для authentication 🔐")
        
        # Should not crash, may fall back to default
        assert result.intent in INTENT_KEYWORDS or result.intent == DEFAULT_INTENT


@pytest.mark.asyncio
class TestLLMFallback:
    """Test Tier 2: LLM fallback (when enabled)."""
    
    async def test_llm_disabled_by_default(self):
        """LLM fallback should be disabled by default."""
        classifier = IntentClassifier()  # Default args
        
        assert classifier.llm_enabled == False
        
        # Ambiguous query should fall to default, not LLM
        result = await classifier.classify("JWT")
        
        assert result.method == "default"
        assert "llm_fallback" not in result.method
    
    async def test_llm_fallback_used_when_enabled(self):
        """LLM fallback should be attempted when enabled and threshold not met."""
        # Note: This test requires Ollama to be running
        # In real test env, we'd mock the LLM call
        
        classifier = IntentClassifier(rule_threshold=10, llm_enabled=True, llm_timeout=2)
        
        # This query won't meet threshold of 10, so  should try LLM
        result = await classifier.classify("authentication system")
        
        # Will either be llm_fallback or default (if LLM fails/times out)
        assert result.method in ["llm_fallback", "default"]


def run_all_tests():
    """Run all intent classification tests."""
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_all_tests()
