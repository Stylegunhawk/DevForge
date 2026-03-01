"""Intent classification for RAG queries.

Phase 12A Day 1: 3-Tier Intent Classification
- Tier 1: Rule-based keyword scoring (<5ms, 95% coverage)
- Tier 2: LLM fallback (150-300ms, OPTIONAL, disabled by default)
- Tier 3: Default fallback (code_search, 0ms)

Architecture:
- Production-safe: LLM disabled by default
- Hard timeouts on LLM calls
- Comprehensive logging for future optimization
"""

import asyncio
import logging
from typing import Optional, Tuple, Dict
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


# Intent taxonomy with keywords
INTENT_KEYWORDS = {
    "code_search": [
        "find", "show", "get", "search", "implementation", "example",
        "code for", "function", "class", "method", "where is", "locate"
    ],
    "debug": [
        "why", "error", "bug", "fail", "fails", "failed", "broken",
        "issue", "wrong", "not working", "exception", "crash", "problem"
    ],
    "explain": [
        "how", "what", "explain", "understand", "concept", "works",
        "architecture", "overview", "guide", "tutorial", "learn"
    ],
    "api_reference": [
        "api", "endpoint", "reference", "documentation", "docs",
        "parameters", "response", "request", "spec", "schema"
    ],
    "troubleshoot": [
        "fix", "solve", "resolve", "solution", "workaround",
        "repair", "correct", "remedy", "address"
    ]
}

DEFAULT_INTENT = "code_search"


@dataclass
class IntentResult:
    """Intent classification result with metadata."""
    intent: str
    confidence: float
    method: str  # "rule_based", "llm_fallback", "default"
    keyword_scores: Dict[str, int]
    latency_ms: float


class IntentClassifier:
    """
    3-tier intent classification system.
    
    Production defaults:
    - LLM fallback DISABLED
    - Rule-based threshold: 2 keywords
    - <5ms average latency
    """
    
    def __init__(
        self,
        rule_threshold: int = 2,
        llm_enabled: bool = False,
        llm_timeout: int = 3
    ):
        """
        Initialize intent classifier.
        
        Args:
            rule_threshold: Min keyword matches for confident classification
            llm_enabled: Enable LLM fallback (DISABLED by default)
            llm_timeout: Hard timeout for LLM calls (seconds)
        """
        self.rule_threshold = rule_threshold
        self.llm_enabled = llm_enabled
        self.llm_timeout = llm_timeout
        
        # Metrics tracking
        self._total_classifications = 0
        self._method_counts = defaultdict(int)
        self._intent_counts = defaultdict(int)
        
        if not llm_enabled:
            logger.info("IntentClassifier initialized (LLM fallback DISABLED)")
        else:
            logger.warning(
                f"IntentClassifier initialized (LLM fallback ENABLED, "
                f"timeout={llm_timeout}s)"
            )
    
    def _score_keywords(self, query: str) -> Dict[str, int]:
        """
        Score each intent by keyword matches.
        
        Args:
            query: User query (lowercased internally)
        
        Returns:
            {"debug": 3, "explain": 1, "code_search": 0, ...}
        """
        query_lower = query.lower()
        scores = {}
        
        for intent, keywords in INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            scores[intent] = score
        
        return scores
    
    async def classify(self, query: str) -> IntentResult:
        """
        Classify query intent using 3-tier system.
        
        Tier 1: Rule-based keyword scoring (FAST)
        Tier 2: LLM fallback (SLOW, OPTIONAL)
        Tier 3: Default fallback (INSTANT)
        
        Args:
            query: User query string
        
        Returns:
            IntentResult with intent, confidence, method, scores
        """
        import time
        start_time = time.perf_counter()
        
        # Tier 1: Rule-based keyword scoring
        keyword_scores = self._score_keywords(query)
        max_score = max(keyword_scores.values())
        
        if max_score >= self.rule_threshold:
            # Confident classification via keywords
            intent = max(keyword_scores, key=keyword_scores.get)
            confidence = min(max_score / 5.0, 1.0)  # Normalize
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            result = IntentResult(
                intent=intent,
                confidence=confidence,
                method="rule_based",
                keyword_scores=keyword_scores,
                latency_ms=latency_ms
            )
            
            # Update metrics
            self._total_classifications += 1
            self._method_counts["rule_based"] += 1
            self._intent_counts[intent] += 1
            
            # Log with score breakdown
            logger.debug(
                f"Intent classified: {intent} (rule-based, "
                f"confidence={confidence:.2f}, max_score={max_score}, "
                f"latency={latency_ms:.2f}ms, scores={keyword_scores})"
            )
            
            return result
        
        # Tier 2: LLM fallback (if enabled)
        if self.llm_enabled:
            llm_intent = await self._classify_with_llm(query)
            
            if llm_intent:
                confidence = 0.7  # Moderate confidence
                latency_ms = (time.perf_counter() - start_time) * 1000
                
                result = IntentResult(
                    intent=llm_intent,
                    confidence=confidence,
                    method="llm_fallback",
                    keyword_scores=keyword_scores,
                    latency_ms=latency_ms
                )
                
                # Update metrics
                self._total_classifications += 1
                self._method_counts["llm_fallback"] += 1
                self._intent_counts[llm_intent] += 1
                
                logger.info(
                    f"Intent classified: {llm_intent} (LLM fallback, "
                    f"confidence={confidence:.2f}, latency={latency_ms:.2f}ms)"
                )
                
                return result
        
        # Tier 3: Default fallback
        intent = DEFAULT_INTENT
        confidence = 0.5  # Low confidence
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        result = IntentResult(
            intent=intent,
            confidence=confidence,
            method="default",
            keyword_scores=keyword_scores,
            latency_ms=latency_ms
        )
        
        # Update metrics
        self._total_classifications += 1
        self._method_counts["default"] += 1
        self._intent_counts[intent] += 1
        
        logger.debug(
            f"Intent classified: {intent} (default fallback, "
            f"max_score={max_score} < threshold={self.rule_threshold}, "
            f"latency={latency_ms:.2f}ms)"
        )
        
        return result
    
    async def _classify_with_llm(self, query: str) -> Optional[str]:
        """
        LLM-based classification with hard timeout.
        
        Args:
            query: User query
        
        Returns:
            Intent string or None if timeout/failure
        """
        try:
            # Import here to avoid dependency if LLM disabled
            from src.llm.ollama_client import generate_text
            
            prompt = f"""Classify this query into ONE intent category.

Query: {query}

Categories:
- code_search: Finding specific code implementations
- debug: Investigating errors or bugs
- explain: Understanding concepts or how things work
- api_reference: API documentation lookup
- troubleshoot: Fixing problems or issues

Reply with ONLY the category name, nothing else.
Category:"""
            
            from src.core.config import settings
            
            # Timeout-bound LLM call
            response = await asyncio.wait_for(
                generate_text(prompt, model=settings.DEFAULT_MODEL, max_tokens=10),
                timeout=self.llm_timeout
            )
            
            # Validate response is a known intent
            intent = response.strip().lower()
            if intent in INTENT_KEYWORDS:
                return intent
            
            logger.warning(f"LLM returned invalid intent: {intent}")
            return None
        
        except asyncio.TimeoutError:
            logger.warning(
                f"Intent LLM timeout after {self.llm_timeout}s, "
                f"falling back to default"
            )
            return None
        
        except Exception as e:
            logger.error(f"Intent LLM failed: {e}, falling back to default")
            return None
    
    def get_stats(self) -> Dict:
        """
        Get classification statistics.
        
        Returns:
            Stats dict with method breakdown and recommendations
        """
        if self._total_classifications == 0:
            return {
                "total": 0,
                "method_breakdown": {},
                "intent_distribution": {},
                "recommendation": "No classifications yet"
            }
        
        method_pct = {
            method: (count / self._total_classifications) * 100
            for method, count in self._method_counts.items()
        }
        
        intent_pct = {
            intent: (count / self._total_classifications) * 100
            for intent, count in self._intent_counts.items()
        }
        
        # Recommendation logic
        default_pct = method_pct.get("default", 0)
        
        if not self.llm_enabled and default_pct > 20:
            recommendation = (
                f"Consider enabling LLM fallback: {default_pct:.1f}% "
                f"queries using default fallback"
            )
        elif self.llm_enabled and default_pct < 5:
            recommendation = (
                f"LLM fallback underutilized ({default_pct:.1f}% default rate), "
                f"consider disabling to reduce latency"
            )
        else:
            recommendation = "Classification performing well"
        
        return {
            "total": self._total_classifications,
            "method_breakdown": {
                "rule_based": {
                    "count": self._method_counts["rule_based"],
                    "percentage": method_pct.get("rule_based", 0)
                },
                "llm_fallback": {
                    "count": self._method_counts["llm_fallback"],
                    "percentage": method_pct.get("llm_fallback", 0)
                },
                "default": {
                    "count": self._method_counts["default"],
                    "percentage": method_pct.get("default", 0)
                }
            },
            "intent_distribution": intent_pct,
            "recommendation": recommendation,
            "llm_enabled": self.llm_enabled
        }
    
    def reset_stats(self):
        """Reset statistics (for testing)."""
        self._total_classifications = 0
        self._method_counts.clear()
        self._intent_counts.clear()
