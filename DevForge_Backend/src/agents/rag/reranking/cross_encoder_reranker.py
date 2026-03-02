"""Cross-encoder reranker implementation.

TECHNICAL DETAILS (Phase 11 Refinement):
- Sigmoid normalization: raw logits → [0, 1]
- Two-level content truncation (chars → tokens)
- Async-safe inference via asyncio.to_thread
- Score reset to prevent state leakage
"""

import math
import asyncio
import logging
from typing import List, Optional
from sentence_transformers import CrossEncoder

from .base_reranker import BaseReranker
from src.storage.base_store import ChunkResult
from src.core.config import settings

logger = logging.getLogger(__name__)


class CrossEncoderReranker(BaseReranker):
    """
    Cross-encoder reranker using sentence-transformers.
    
    Model: cross-encoder/ms-marco-MiniLM-L-6-v2
    - 6-layer MiniLM (22.7M parameters)
    - CPU-friendly (~100-150ms for 30 candidates)
    - Proven SOTA for passage ranking
    """
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize cross-encoder reranker.
        
        Args:
            model_name: HuggingFace model identifier
        
        Memory: ~200MB in RAM after loading
        Latency: ~150ms for 30 candidates (CPU)
        """
        self.model_name = model_name or settings.RERANK_MODEL
        self.model = CrossEncoder(
            self.model_name,
            max_length=512,  # Token limit for model
            device='cpu'      # CPU-only (portable)
        )
        
        logger.info(f"CrossEncoderReranker initialized: {model_name}")
    
    @staticmethod
    def normalize_score(raw_score: float) -> float:
        """
        Normalize raw logits using sigmoid to [0, 1] range.
        
        CrossEncoder.predict() returns unbounded logits (typically [-10, 10]).
        Sigmoid normalization: 1 / (1 + exp(-score))
        
        This makes thresholds stable and interpretable:
        - 0.5 = neutral (logit = 0)
        - 0.7+ = relevant (logit > 1)
        - 0.3 = threshold for "somewhat relevant"
        
        Args:
            raw_score: Raw logit from cross-encoder
        
        Returns:
            Normalized score in [0, 1]
        """
        return 1 / (1 + math.exp(-raw_score))
    
    async def rerank(
        self,
        query: str,
        chunks: List[ChunkResult],
        top_k: int = 5
    ) -> List[ChunkResult]:
        """
        Rerank chunks using cross-encoder semantic scoring.
        
        Process:
        1. Reset scores (prevent state leakage)
        2. Build query-document pairs
        3. Batch inference (async-safe)
        4. Normalize scores with sigmoid
        5. Sort by normalized score
        
        Args:
            query: User query string
            chunks: Candidate chunks from vector search
            top_k: Number of top results to return
        
        Returns:
            Reranked chunks with normalized scores
        """
        if not chunks:
            return []
        
        # CRITICAL: Reset scores to prevent state leakage across requests
        for chunk in chunks:
            chunk.rerank_score = 0.0
        
        # Build query-document pairs
        # Two-level truncation:
        # 1. Pre-truncate to 2048 chars (~512 tokens, rough 4:1 ratio)
        #    - Reduces data sent to model
        # 2. Model internally truncates to max_length=512 tokens
        #    - Ensures compatibility with positional embeddings
        pairs = [(query, chunk.content[:2048]) for chunk in chunks]
        
        # Batch inference (async-safe via thread pool)
        # asyncio.to_thread prevents blocking the event loop
        raw_scores = await asyncio.to_thread(self.model.predict, pairs)
        
        # Normalize and attach scores
        for chunk, raw_score in zip(chunks, raw_scores):
            chunk.rerank_score = self.normalize_score(float(raw_score))
        
        # Sort by normalized score (descending)
        ranked = sorted(chunks, key=lambda c: c.rerank_score, reverse=True)
        
        logger.debug(f"Reranked {len(chunks)} chunks, returning top {top_k}")
        
        return ranked[:top_k]
    
    def apply_code_boost(self, chunks: List[ChunkResult]) -> List[ChunkResult]:
        """
        Apply code-aware score boosting based on chunk type.
        
        ARCHITECTURE (Phase 11 Day 3):
        - Boosts function chunks (1.2x)
        - Boosts class chunks (1.15x)
        - Neutral for imports (1.0x)
        - Reduces text chunks (0.95x)
        
        This prioritizes executable code entities for code queries.
        
        Args:
            chunks: Chunks with rerank_score already set
        
        Returns:
            Same chunks with boosted scores (mutates in place)
        """
        from src.core.config import settings
        
        for chunk in chunks:
            chunk_type = chunk.metadata.get("chunk_type", "text")
            
            # Apply boost based on chunk type
            if chunk_type == "function":
                chunk.rerank_score *= settings.BOOST_FUNCTION  # 1.2x
            elif chunk_type == "class":
                chunk.rerank_score *= settings.BOOST_CLASS    # 1.15x
            elif chunk_type == "import":
                chunk.rerank_score *= settings.BOOST_IMPORT   # 1.0x (no change)
            else:  # text, markdown, etc.
                chunk.rerank_score *= settings.BOOST_TEXT     # 0.95x
        
        logger.debug(f"Applied code-aware boosting to {len(chunks)} chunks")
        return chunks
