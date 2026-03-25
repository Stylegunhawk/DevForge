"""Query expansion for improved retrieval recall.

Phase 12A Day 3-4: Intent-Aware Query Expansion
- Intent-specific structured prompts
- Keyword-based fallback (no LLM required)
- Hard timeout protection (5s)
- Quality metrics tracking
"""

import asyncio
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Intent-specific structured prompts
DEBUG_EXPANSION_PROMPT = """Generate {count} focused variations of this debugging query.

Original: {query}

Requirements:
- Variation focusing on error causes
- Variation focusing on debugging steps
- Each variation on a new line
- Minimum 5 words per variation
- No numbering or bullets

Variations:
"""

EXPLAIN_EXPANSION_PROMPT = """Generate {count} diverse variations to understand this concept.

Original: {query}

Requirements:
- Implementation details perspective
- Conceptual overview perspective
- Architecture/design perspective
- Best practices perspective
- Each variation on a new line
- Minimum 5 words per variation
- No numbering or bullets

Variations:
"""

CODE_SEARCH_EXPANSION_PROMPT = """Generate {count} code search variations.

Original: {query}

Requirements:
- Specific implementation focus
- Example usage focus
- Related patterns or interface focus
- Each variation on a new line
- Minimum 5 words per variation
- No numbering or bullets

Example:
Original: authentication token verification
Variations:
how is verify_token implemented structurally
verify_token usage examples in middleware
authentication token verification interface and abstraction

Variations:
"""

API_REFERENCE_EXPANSION_PROMPT = """Generate {count} API reference variations.

Original: {query}

Requirements:
- API documentation focus
- Parameter/response focus
- Each variation on a new line
- Minimum 5 words per variation
- No numbering or bullets

Variations:
"""

TROUBLESHOOT_EXPANSION_PROMPT = """Generate {count} troubleshooting variations.

Original: {query}

Requirements:
- Solution-oriented focus
- Workaround focus
- Root cause focus
- Each variation on a new line
- Minimum 5 words per variation
- No numbering or bullets

Variations:
"""

# Prompt mapping
EXPANSION_PROMPTS = {
    "debug": DEBUG_EXPANSION_PROMPT,
    "explain": EXPLAIN_EXPANSION_PROMPT,
    "code_search": CODE_SEARCH_EXPANSION_PROMPT,
    "api_reference": API_REFERENCE_EXPANSION_PROMPT,
    "troubleshoot": TROUBLESHOOT_EXPANSION_PROMPT
}

# Keyword fallback suffixes
FALLBACK_SUFFIXES = {
    "debug": ["error causes", "debugging steps", "troubleshooting guide"],
    "explain": ["implementation details", "concept overview", "architecture design", "best practices"],
    "code_search": ["implementation example", "code usage", "pattern examples"],
    "api_reference": ["API documentation", "endpoint reference"],
    "troubleshoot": ["solution workaround", "fix steps", "problem resolution"]
}


@dataclass
class ExpansionResult:
    """Query expansion result with metadata."""
    original_query: str
    expanded_queries: List[str]  # Includes original
    intent: str
    method: str  # "llm" or "keyword"
    latency_ms: float
    count: int


class QueryExpander:
    """
    Intent-aware query expansion with LLM + keyword fallback.
    
    Production defaults:
    - LLM timeout: 5s
    - Keyword fallback if LLM fails
    - Intent-specific expansion counts
    """
    
    def __init__(
        self,
        llm_timeout: int = 5,
        llm_model: Optional[str] = None,
        expansion_counts: Optional[Dict[str, int]] = None
    ):
        """
        Initialize query expander.
        
        Args:
            llm_timeout: Hard timeout for LLM calls (seconds)
            llm_model: LLM model to use
            expansion_counts: Expansion count per intent
        """
        from src.core.config import settings
        self.llm_timeout = llm_timeout
        self.llm_model = llm_model or settings.DEFAULT_MODEL
        
        # Default expansion counts per intent
        self.expansion_counts = expansion_counts or {
            "debug": 2,
            "explain": 4,
            "code_search": 3,
            "api_reference": 2,
            "troubleshoot": 3
        }
        
        # Metrics
        self._total_expansions = 0
        self._llm_successes = 0
        self._llm_failures = 0
        self._keyword_fallbacks = 0
        
        logger.info(
            f"QueryExpander initialized (timeout={llm_timeout}s, "
            f"model={llm_model})"
        )
    
    async def expand(
        self,
        query: str,
        intent: str,
        count: Optional[int] = None
    ) -> ExpansionResult:
        """
        Expand query with intent-aware variations.
        
        Flow:
        1. Try LLM expansion (with timeout)
        2. Fallback to keyword expansion if LLM fails
        3. Always include original query first
        
        Args:
            query: Original query
            intent: Intent classification result
            count: Number of variations (default from expansion_counts)
        
        Returns:
            ExpansionResult with queries and metadata
        """
        import time
        start_time = time.perf_counter()
        
        # Get expansion count for intent
        if count is None:
            count = self.expansion_counts.get(intent, 3)
        
        # Always include original query
        queries = [query]
        
        # Try LLM expansion
        llm_variations = await self._expand_with_llm(query, intent, count)
        
        if llm_variations:
            queries.extend(llm_variations)
            method = "llm"
            self._llm_successes += 1
        else:
            # Fallback to keyword expansion
            keyword_variations = self._expand_with_keywords(query, intent, count)
            queries.extend(keyword_variations)
            method = "keyword"
            self._keyword_fallbacks += 1
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        self._total_expansions += 1
        
        result = ExpansionResult(
            original_query=query,
            expanded_queries=queries,
            intent=intent,
            method=method,
            latency_ms=latency_ms,
            count=len(queries) - 1  # Exclude original
        )
        
        logger.debug(
            f"Query expanded: {count} variations ({method}, "
            f"intent={intent}, latency={latency_ms:.2f}ms)"
        )
        
        return result
    
    async def _expand_with_llm(
        self,
        query: str,
        intent: str,
        count: int
    ) -> Optional[List[str]]:
        """
        LLM-based expansion with timeout and structured parsing.
        
        Args:
            query: Original query
            intent: Intent classification
            count: Number of variations
        
        Returns:
            List of variations or None if failed/timeout
        """
        try:
            # Get intent-specific prompt
            prompt_template = EXPANSION_PROMPTS.get(
                intent,
                CODE_SEARCH_EXPANSION_PROMPT  # Default
            )
            
            prompt = prompt_template.format(query=query, count=count)
            
            # Import LLM client
            from src.llm.ollama_client import generate_text
            
            # Timeout-bound LLM call
            response = await asyncio.wait_for(
                generate_text(prompt, model=self.llm_model, max_tokens=200),
                timeout=self.llm_timeout
            )
            
            # Parse structured output
            variations = self._parse_variations(response, count)
            
            if variations:
                logger.info(
                    f"[ISSUE-2-VERIFY] LLM expansion success: {len(variations)} variations "
                    f"(intent={intent}). Variations: {variations}"
                )
                return variations
            else:
                logger.warning(f"LLM returned no valid variations (intent={intent})")
                return None
        
        except asyncio.TimeoutError:
            logger.warning(
                f"LLM expansion timeout after {self.llm_timeout}s "
                f"(intent={intent})"
            )
            self._llm_failures += 1
            return None
        
        except Exception as e:
            logger.error(f"LLM expansion failed: {e} (intent={intent})")
            self._llm_failures += 1
            return None
    
    def _parse_variations(self, response: str, count: int) -> List[str]:
        """
        Parse LLM response into variations.
        
        Args:
            response: Raw LLM response
            count: Expected number of variations
        
        Returns:
            List of valid variations
        """
        # Split by newlines
        lines = response.strip().split('\n')
        
        # Filter and clean
        variations = []
        for line in lines:
            cleaned = line.strip()
            
            # Remove numbering/bullets (strips leading digits, dots, dashes, etc.)
            cleaned = cleaned.lstrip('0123456789.-) ')
            
            # Phase 2 Refinement: Lower threshold to 2 words + add safety guards
            # - Must be at least 2 words (covers "pgvector implementation")
            # - Must be at least 10 chars (skips noise like "Here:")
            # - Must not start with common list markers or quotes
            is_valid = (
                len(cleaned.split()) >= 2 and 
                len(cleaned) > 10 and 
                not cleaned.startswith(("-", '"', "•")) and
                not (cleaned and cleaned[0].isdigit())
            )
            
            if is_valid:
                variations.append(cleaned)
            
            # Cap at requested count
            if len(variations) >= count:
                break
        
        return variations
    
    def _expand_with_keywords(
        self,
        query: str,
        intent: str,
        count: int
    ) -> List[str]:
        """
        Keyword-based expansion fallback (no LLM required).
        
        Args:
            query: Original query
            intent: Intent classification
            count: Number of variations
        
        Returns:
            List of keyword-based variations
        """
        suffixes = FALLBACK_SUFFIXES.get(
            intent,
            ["implementation", "example", "guide"]  # Default
        )
        
        # Generate variations by appending suffixes
        variations = [
            f"{query} {suffix}"
            for suffix in suffixes[:count]
        ]
        
        logger.debug(
            f"Keyword fallback expansion: {len(variations)} variations "
            f"(intent={intent})"
        )
        
        return variations
    
    def get_stats(self) -> Dict:
        """
        Get expansion statistics.
        
        Returns:
            Stats dict with success rates and methods
        """
        if self._total_expansions == 0:
            return {
                "total": 0,
                "llm_success_rate": 0.0,
                "keyword_fallback_rate": 0.0,
                "recommendation": "No expansions yet"
            }
        
        llm_rate = self._llm_successes / self._total_expansions
        keyword_rate = self._keyword_fallbacks / self._total_expansions
        
        # Recommendation
        if keyword_rate > 0.8:
            recommendation = (
                f"LLM rarely succeeding ({llm_rate:.1%}), "
                f"check Ollama availability or disable expansion"
            )
        elif llm_rate > 0.8:
            recommendation = "LLM expansion working well"
        else:
            recommendation = f"Mixed mode: {llm_rate:.1%} LLM, {keyword_rate:.1%} keyword"
        
        return {
            "total": self._total_expansions,
            "llm_successes": self._llm_successes,
            "llm_failures": self._llm_failures,
            "keyword_fallbacks": self._keyword_fallbacks,
            "llm_success_rate": llm_rate,
            "keyword_fallback_rate": keyword_rate,
            "recommendation": recommendation
        }
    
    def reset_stats(self):
        """Reset statistics (for testing)."""
        self._total_expansions = 0
        self._llm_successes = 0
        self._llm_failures = 0
        self._keyword_fallbacks = 0
