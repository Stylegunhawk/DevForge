"""Hybrid retriever combining BM25 keyword + Vector semantic search.

Phase 11.2 Day 3: Reciprocal Rank Fusion (RRF)
- Fuses BM25 (keyword) + Vector (semantic) results
- Deduplicates by qualified_id
- Configurable weighting (alpha parameter)
"""

import logging
from typing import List, Dict
from collections import defaultdict

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Hybrid retrieval using BM25 + Vector search with RRF fusion.
    
    Algorithm: Reciprocal Rank Fusion (RRF)
    - Score(doc) = α * (1/(k + rank_vector)) + (1-α) * (1/(k + rank_bm25))
    - k = RRF constant (default 60)
    - α = vector weight (default 0.5)
    """
    
    def __init__(self, vector_store, bm25_index, embeddings):
        """
        Initialize hybrid retriever.
        
        Args:
            vector_store: BaseVectorStore instance
            bm25_index: BM25Index instance
            embeddings: Embeddings model for query encoding
        """
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.embeddings = embeddings
        logger.info("HybridRetriever initialized")
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        alpha: float = 0.5,
        k: int = 60
    ) -> List[Dict]:
        """
        Hybrid search with RRF fusion.
        
        Args:
            query: Search query string
            top_k: Number of final results to return
            alpha: Vector weight (0.0-1.0, default 0.5)
                - 1.0 = vector only
                - 0.0 = BM25 only
                - 0.5 = equal weight
            k: RRF constant (default 60 from literature)
        
        Returns:
            List of deduplicated results with rrf_score
        """
        # Retrieve more candidates for better fusion
        candidate_multiplier = 3
        candidate_count = top_k * candidate_multiplier
        
        # Step 1: Vector semantic search
        query_embedding = await self.embeddings.aembed_query(query)
        vector_results = await self.vector_store.search(
            query_embedding,
            top_k=candidate_count
        )
        
        # Step 2: BM25 keyword search
        bm25_results = self.bm25_index.search(query, top_k=candidate_count)
        
        logger.debug(f"Hybrid search: {len(vector_results)} vector + {len(bm25_results)} BM25 candidates")
        
        # Step 3: Reciprocal Rank Fusion
        rrf_scores = defaultdict(float)
        doc_map = {}  # qid -> full document
        
        # Add vector scores (weighted by alpha)
        for rank, result in enumerate(vector_results, start=1):
            qid = result.metadata.get("qualified_id", result.id)
            rrf_scores[qid] += alpha * (1 / (k + rank))
            if qid not in doc_map:
                doc_map[qid] = result
        
        # Add BM25 scores (weighted by 1-alpha)
        for rank, result in enumerate(bm25_results, start=1):
            qid = result["qualified_id"]
            rrf_scores[qid] += (1 - alpha) * (1 / (k + rank))
            # If not already in doc_map, fetch full chunk
            if qid not in doc_map:
                # Use BM25 metadata (vector store fetch would be expensive)
                from src.storage.base_store import ChunkResult
                doc_map[qid] = ChunkResult(
                    id=qid,
                    content=result["content"],
                    metadata=result["metadata"],
                    score=None  # Will use rrf_score instead
                )
        
        # Step 4: Sort by RRF score (descending)
        sorted_qids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Step 5: Build final results (deduplicated, top-k)
        merged = []
        for qid, rrf_score in sorted_qids[:top_k]:
            doc = doc_map.get(qid)
            if doc:
                # Add RRF metadata
                if hasattr(doc, 'metadata'):
                    doc.metadata["rrf_score"] = rrf_score
                    doc.metadata["hybrid_search"] = True
                else:
                    doc["rrf_score"] = rrf_score
                    doc["hybrid_search"] = True
                
                merged.append(doc)
        
        logger.info(f"Hybrid search: {len(merged)} fused results (from {len(doc_map)} unique docs)")
        
        return merged
