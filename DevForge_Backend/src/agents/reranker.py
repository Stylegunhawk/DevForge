"""Reranker agent for improving RAG retrieval relevance."""

import logging
from typing import List, Tuple, Dict, Any

from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)


class Reranker:
    """Reranks documents using a Cross-Encoder model."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """Initialize the reranker.

        Args:
            model_name: Name of the CrossEncoder model to use.
        """
        self.model_name = model_name
        try:
            # Initialize model on CPU by default to avoid VRAM issues with LLMs
            self.model = CrossEncoder(model_name)
            logger.info(f"Initialized Reranker with model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Reranker: {e}")
            raise

    async def rerank(self, query: str, documents: list, top_k: int = 5, key=lambda x: x) -> list:
        """Rerank a list of documents based on relevance to the query.

        Args:
            query: The search query.
            documents: List of documents (strings or objects) to rerank.
            top_k: Number of top documents to return.
            key: Function to extract text from document if it's an object.

        Returns:
            List of reranked documents (top_k).
        """
        if not documents:
            return []

        try:
            # Extract text using key function
            doc_texts = [key(doc) for doc in documents]
            
            # Create pairs for cross-encoder
            pairs = [[query, doc_text] for doc_text in doc_texts]

            # Predict scores
            scores = self.model.predict(pairs)

            # Combine original docs with scores
            doc_scores = list(zip(documents, scores))

            # Sort by score (descending)
            doc_scores.sort(key=lambda x: x[1], reverse=True)

            # Extract top_k documents
            top_docs = [doc for doc, score in doc_scores[:top_k]]

            logger.info(
                f"Reranked {len(documents)} documents, returning top {len(top_docs)}",
                extra={"query": query[:50], "top_score": float(doc_scores[0][1]) if doc_scores else 0},
            )

            return top_docs

        except Exception as e:
            logger.error(f"Reranking failed: {e}", exc_info=True)
            # Fallback: return original documents sliced
            return documents[:top_k]

# Global instance
reranker = Reranker()

async def rerank_docs_invoke(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper for MCP Gateway invocation.
    
    Args:
        args: Dictionary containing:
            - query: str
            - documents: List[str]
            - top_k: int (optional)
            
    Returns:
        Dictionary with success status and data.
    """
    query = args.get("query")
    documents = args.get("documents", [])
    top_k = args.get("top_k", 5)
    
    if not query or not documents:
        return {
            "success": False,
            "error": "Missing 'query' or 'documents' in arguments"
        }
        
    try:
        reranked_docs = await reranker.rerank(query, documents, top_k=top_k)
        return {
            "success": True,
            "data": {
                "documents": reranked_docs,
                "count": len(reranked_docs)
            },
            "format": "json"
        }
    except Exception as e:
        logger.error(f"Error in rerank_docs_invoke: {e}")
        return {
            "success": False,
            "error": str(e)
        }
