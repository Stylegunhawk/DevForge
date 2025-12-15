"""Semantic similarity cache for RAG queries.

Phase 12A Day 5-6: Intent-Aware Semantic Cache
- Embedding-based similarity search
- Intent-keyed cache (embedding, intent)
- Cosine similarity threshold (0.92)
- LRU eviction per intent
- Fallback to exact-match cache
- No external infrastructure required
"""

import logging
import numpy as np
from typing import Optional, Dict, List, Tuple, Any
from collections import OrderedDict
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class CachedQuery:
    """Cached query with embedding and results."""
    query: str
    intent: str
    embedding: np.ndarray
    results: Dict[str, Any]
    timestamp: float
    
    def similarity(self, other_embedding: np.ndarray) -> float:
        """Calculate cosine similarity with another embedding."""
        dot_product = np.dot(self.embedding, other_embedding)
        norm_a = np.linalg.norm(self.embedding)
        norm_b = np.linalg.norm(other_embedding)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)


class SemanticCache:
    """
    Intent-aware semantic cache using embedding similarity.
    
    Cache Structure:
    - Separate cache per intent
    - Each entry: (query, embedding, results)
    - Similarity threshold: 0.92 (default)
    - LRU eviction when full
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.92,
        max_size_per_intent: int = 100,
        embed_model=None
    ):
        """
        Initialize semantic cache.
        
        Args:
            similarity_threshold: Cosine similarity threshold for cache hit
            max_size_per_intent: Max cached queries per intent
            embed_model: Embedding model (if None, uses default)
        """
        self.similarity_threshold = similarity_threshold
        self.max_size_per_intent = max_size_per_intent
        self.embed_model = embed_model
        
        # Separate cache per intent
        self._caches: Dict[str, OrderedDict[str, CachedQuery]] = {}
        
        # Metrics
        self._hits = 0
        self._misses = 0
        self._similarity_scores: List[float] = []
        
        logger.info(
            f"SemanticCache initialized (threshold={similarity_threshold}, "
            f"max_size_per_intent={max_size_per_intent})"
        )
    
    async def get(
        self,
        query: str,
        intent: str,
        query_embedding: Optional[np.ndarray] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached results for semantically similar query.
        
        Args:
            query: User query
            intent: Intent classification
            query_embedding: Pre-computed embedding (optional)
        
        Returns:
            Cached results or None if no similar query found
        """
        logger.info(f"[RAG-DEBUG] SemanticCache.get() called: query='{query[:50]}...', intent={intent}")
        
        # Get or create intent-specific cache
        if intent not in self._caches:
            self._misses += 1
            logger.debug(f"Semantic cache MISS: no cache for intent={intent}")
            return None
        
        intent_cache = self._caches[intent]
        
        if not intent_cache:
            self._misses += 1
            logger.debug(f"Semantic cache MISS: empty cache for intent={intent}")
            return None
        
        # Get query embedding
        if query_embedding is None:
            query_embedding = await self._embed_query(query)
        
        # Find most similar cached query
        best_match = None
        best_similarity = 0.0
        
        for cached_query in intent_cache.values():
            similarity = cached_query.similarity(query_embedding)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = cached_query
        
        # Check threshold
        if best_match and best_similarity >= self.similarity_threshold:
            # Cache HIT
            self._hits += 1
            self._similarity_scores.append(best_similarity)
            
            # Move to end (LRU)
            intent_cache.move_to_end(best_match.query)
            
            logger.info(
                f"Semantic cache HIT: query='{query[:50]}...', "
                f"matched='{best_match.query[:50]}...', "
                f"similarity={best_similarity:.3f}, intent={intent}"
            )
            
            return best_match.results
        
        # Cache MISS
        self._misses += 1
        logger.debug(
            f"Semantic cache MISS: best_similarity={best_similarity:.3f} "
            f"< threshold={self.similarity_threshold} (intent={intent})"
        )
        
        return None
    
    async def set(
        self,
        query: str,
        intent: str,
        results: Dict[str, Any],
        query_embedding: Optional[np.ndarray] = None
    ):
        """
        Cache query results with embedding.
        
        Args:
            query: User query
            intent: Intent classification
            results: Final retrieval results (post-expansion, post-fusion)
            query_embedding: Pre-computed embedding (optional)
        """
        logger.info(f"[RAG-DEBUG] SemanticCache.set() called: query='{query[:50]}...', intent={intent}")
        
        # Get query embedding
        if query_embedding is None:
            query_embedding = await self._embed_query(query)
        
        # Get or create intent-specific cache
        if intent not in self._caches:
            self._caches[intent] = OrderedDict()
        
        intent_cache = self._caches[intent]
        
        # LRU eviction if full
        if len(intent_cache) >= self.max_size_per_intent:
            evicted_query, _ = intent_cache.popitem(last=False)
            logger.debug(
                f"Semantic cache eviction: query='{evicted_query[:30]}...', "
                f"intent={intent}"
            )
        
        # Cache query
        cached = CachedQuery(
            query=query,
            intent=intent,
            embedding=query_embedding,
            results=results,
            timestamp=time.time()
        )
        
        intent_cache[query] = cached
        
        logger.debug(
            f"Semantic cache SET: query='{query[:50]}...', intent={intent}, "
            f"cache_size={len(intent_cache)}"
        )
    
    async def _embed_query(self, query: str) -> np.ndarray:
        """
        Embed query using embedding model.
        
        Args:
            query: User query
        
        Returns:
            Query embedding as numpy array
        """
        try:
            if self.embed_model:
                # Use provided embedding model
                logger.info(f"[RAG-DEBUG] Using REAL embedding model for query: '{query[:50]}...'")
                embedding = await self.embed_model.embed_query(query)
                return np.array(embedding)
            else:
                # Fallback: simple hash-based pseudo-embedding (for testing)
                logger.info(f"[RAG-DEBUG] Using PSEUDO-EMBEDDING fallback for query: '{query[:50]}...'")
                return self._pseudo_embed(query)
        
        except Exception as e:
            logger.error(f"Embedding failed: {e}, using pseudo-embedding")
            return self._pseudo_embed(query)
    
    def _pseudo_embed(self, query: str) -> np.ndarray:
        """
        Simple pseudo-embedding for testing (hash-based).
        
        NOT for production! Just for testing without embedding model.
        """
        # Simple deterministic vector based on character frequencies
        vector = np.zeros(384)  # Small embedding dimension
        
        for i, char in enumerate(query.lower()[:384]):
            vector[i] = ord(char) / 255.0
        
        return vector
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get semantic cache statistics.
        
        Returns:
            Stats dict with hit rate, avg similarity, cache sizes
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        
        avg_similarity = (
            np.mean(self._similarity_scores) 
            if self._similarity_scores 
            else 0.0
        )
        
        cache_sizes = {
            intent: len(cache)
            for intent, cache in self._caches.items()
        }
        
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "avg_similarity": float(avg_similarity),
            "threshold": self.similarity_threshold,
            "cache_sizes": cache_sizes,
            "total_cached": sum(cache_sizes.values())
        }
    
    async def clear(self, intent: Optional[str] = None):
        """
        Clear cached queries.
        
        Args:
            intent: Clear specific intent cache, or all if None
        """
        if intent:
            if intent in self._caches:
                self._caches[intent].clear()
                logger.info(f"Cleared semantic cache for intent={intent}")
        else:
            self._caches.clear()
            logger.info("Cleared all semantic caches")
    
    def reset_metrics(self):
        """Reset hit/miss counters (for testing)."""
        self._hits = 0
        self._misses = 0
        self._similarity_scores.clear()
