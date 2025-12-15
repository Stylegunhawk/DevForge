"""Retrieval module for hybrid search.

Phase 11.2 Day 3: BM25 + Vector Hybrid Search
- BM25 keyword index
- Reciprocal Rank Fusion (RRF)
- Graceful fallback to vector-only
"""

from .bm25_index import BM25Index
from .hybrid_retriever import HybridRetriever

__all__ = ["BM25Index", "HybridRetriever"]
