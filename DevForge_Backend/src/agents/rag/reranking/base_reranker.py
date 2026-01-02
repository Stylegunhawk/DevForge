"""Base reranker interface for RAG.

ARCHITECTURE (Phase 11):
- Agent-internal component
- No new layers added
- Abstract interface for multiple reranker implementations
"""

from abc import ABC, abstractmethod
from typing import List
from src.storage.base_store import ChunkResult


class BaseReranker(ABC):
    """
    Abstract base class for reranking implementations.
    
    Rerankers improve retrieval quality by reordering initial vector
    search results using more sophisticated semantic similarity models.
    """
    
    @abstractmethod
    async def rerank(
        self,
        query: str,
        chunks: List[ChunkResult],
        top_k: int = 5
    ) -> List[ChunkResult]:
        """
        Rerank chunks by semantic relevance to query.
        
        Args:
            query: User query string
            chunks: Initial retrieval results from vector search
            top_k: Number of top results to return
        
        Returns:
            Reranked list of ChunkResult objects, sorted by relevance
        
        Note:
            Implementations must set chunk.rerank_score for each chunk
        """
        pass
