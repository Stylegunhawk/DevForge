"""BM25 keyword search index.

Phase 11.2 Day 3: BM25 Index Manager
- Built from iter_chunk_metadata() (async-safe)
- Explicit initialization via init_bm25()
- Graceful failure mode (fallback to vector-only)
"""

import logging
from typing import List, Dict, Optional
import numpy as np
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class BM25Index:
    """
    BM25 keyword search index for hybrid retrieval.
    
    Lifecycle:
    - Built once during agent startup via init_bm25()
    - Rebuilds on demand after large ingestion
    - Uses iter_chunk_metadata() (NO asyncio.run())
    - Graceful failure → fallback to vector-only
    """
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize empty BM25 index."""
        self.tenant_id = tenant_id
        self.index: Optional[BM25Okapi] = None
        self.documents: List[Dict] = []  # Metadata only (no embeddings)
        self._is_ready = False
        logger.info("BM25Index created (not yet built)")
    
    async def build(
        self,
        vector_store,
        batch_size: int = 500,
        collection_name: Optional[str] = None
    ):
        """
        Build BM25 index from vector store metadata.
        
        ARCHITECTURE (Phase 11.2):
        - Uses iter_chunk_metadata() (async-safe)
        - NO asyncio.run() in property getter
        - Called explicitly during startup
        
        Args:
            vector_store: BaseVectorStore instance
            batch_size: Chunks per batch (default 500)
            collection_name: Optional explicit collection name
        
        Returns:
            None (sets self._is_ready on success)
        """
        logger.info(f"Building BM25 index from vector store for tenant {self.tenant_id}...")
        
        self.documents = []
        tokenized_corpus = []
        
        count = 0
        try:
            # Async-safe iteration over metadata with tenant filtering
            async for batch in vector_store.iter_chunk_metadata(
                batch_size=batch_size,
                tenant_id=self.tenant_id,
                collection_name=collection_name
            ):
                for meta in batch:
                    # Defense in depth: Verify tenant match
                    if meta.get("tenant_id", "default") != self.tenant_id:
                        continue

                    # Extract document content and metadata
                    doc = {
                        "qualified_id": meta.get("qualified_id", meta.get("id", f"unknown_{count}")),
                        "content": meta.get("content", ""),
                        "source": meta.get("source", ""),
                        "metadata": meta
                    }
                    self.documents.append(doc)
                    
                    # Tokenize for BM25 (simple whitespace split)
                    tokens = doc["content"].lower().split()
                    tokenized_corpus.append(tokens)
                    
                    count += 1
                
                if count % 1000 == 0:
                    logger.debug(f"BM25 indexing: {count} documents processed...")
            
            # Build BM25 index
            if tokenized_corpus:
                self.index = BM25Okapi(tokenized_corpus)
                self._is_ready = True
                logger.info(f"BM25 index built successfully: {count} documents indexed")
            else:
                logger.warning("No documents found for BM25 indexing")
                self._is_ready = False
        
        except Exception as e:
            logger.error(f"BM25 index build failed: {e}")
            self._is_ready = False
            # Graceful failure: system will fall back to vector-only
    
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        BM25 keyword search.
        
        Args:
            query: Search query string
            top_k: Number of results to return
        
        Returns:
            List of documents with bm25_score field
        """
        if not self._is_ready or not self.index:
            logger.warning("BM25 index not ready, returning empty results")
            return []
        
        # Tokenize query
        tokenized_query = query.lower().split()
        
        # Get BM25 scores for all documents
        scores = self.index.get_scores(tokenized_query)
        
        # Get top-k indices (descending order)
        top_indices = np.argsort(scores)[-top_k:][::-1]
        
        # Build results with scores
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only return actual matches
                doc = self.documents[idx].copy()
                doc["bm25_score"] = float(scores[idx])
                results.append(doc)
        
        logger.debug(f"BM25 search: {len(results)} results (top_k={top_k})")
        return results
    
    def is_ready(self) -> bool:
        """
        Check if BM25 index is ready for searching.
        
        Returns:
            True if index built successfully, False otherwise
        """
        return self._is_ready
    
    async def rebuild(self, vector_store):
        """
        Rebuild BM25 index.
        
        Use after large ingestion batches.
        
        Args:
            vector_store: BaseVectorStore instance
        """
        logger.info("Rebuilding BM25 index...")
        self._is_ready = False
        await self.build(vector_store)
    
    def get_stats(self) -> Dict:
        """
        Get index statistics.
        
        Returns:
            Dict with index stats
        """
        return {
            "ready": self._is_ready,
            "documents_indexed": len(self.documents),
            "index_type": "BM25Okapi"
        }
