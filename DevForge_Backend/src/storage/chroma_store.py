"""ChromaDB vector store implementation.

ARCHITECTURE (see docs/rag_architecture.md):
- Wraps existing ChromaDB usage
- Implements BaseVectorStore interface
- iter_chunk_metadata for graph rebuild (NO embeddings)
- Backward compatible with existing data
"""

import logging
import asyncio
from typing import List, Dict, Optional, AsyncIterator
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.embeddings import OllamaEmbeddings

from .base_store import BaseVectorStore, ChunkResult
from src.core.config import settings

logger = logging.getLogger(__name__)


class ChromaVectorStore(BaseVectorStore):
    """
    ChromaDB implementation of BaseVectorStore.
    
    Wraps LangChain Chroma client with standardized interface.
    """
    
    def __init__(self, collection_name: str = "devforge_docs", embed_model: Optional[str] = None):
        """
        Initialize ChromaDB vector store.
        
        Args:
            collection_name: Name of the collection
            embed_model: Embedding model name
        """
        self.collection_name = collection_name
        self.embed_model = embed_model or settings.RAG_EMBED_MODEL
        
        # Initialize embeddings
        self.embeddings = OllamaEmbeddings(
            model=self.embed_model,
            base_url=settings.OLLAMA_HOST,
        )
        
        # Initialize Chroma
        persist_directory = str(Path(settings.CHROMA_PERSIST_DIR) / collection_name)
        self.client = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_directory,
        )
        
        # Access underlying collection for advanced operations
        self._collection = self.client._collection
        
        logger.info(f"ChromaVectorStore initialized: {collection_name}")
    
    async def add_chunks(self, chunks: List[Dict], embeddings: List) -> int:
        """
        Add chunks with embeddings to ChromaDB.
        
        Args:
            chunks: List of dicts with 'content' and 'metadata'
            embeddings: List of embedding vectors
        
        Returns:
            Number of chunks added
        """
        # Convert to LangChain Document format
        from langchain_core.documents import Document
        
        documents = [
            Document(page_content=c["content"], metadata=c.get("metadata", {}))
            for c in chunks
        ]
        
        # Add to Chroma (synchronous operation)
        await asyncio.to_thread(self.client.add_documents, documents)
        
        logger.debug(f"Added {len(chunks)} chunks to ChromaDB")
        return len(chunks)
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> List[ChunkResult]:
        """
        Search for similar chunks in ChromaDB.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results
            score_threshold: Minimum similarity score
        
        Returns:
            List of ChunkResult objects
        """
        # Chroma uses cosine similarity (higher = more similar)
        # LangChain returns (Document, score) tuples
        results = await asyncio.to_thread(
            self.client.similarity_search_with_score,
            query="",  # We're using embedding directly
            k=top_k,
        )
        
        # Filter and convert to ChunkResult
        chunk_results = []
        for doc, score in results:
            if score >= score_threshold:
                chunk_results.append(ChunkResult(
                    id=doc.metadata.get("id", "unknown"),
                    content=doc.page_content,
                    metadata=doc.metadata,
                    score=score,
                ))
        
        return chunk_results
    
    async def get_chunk_by_qualified_id(self, qid: str) -> Optional[ChunkResult]:
        """
        Get chunk by qualified ID (file::entity).
        
        ARCHITECTURE: Used by graph expansion.
        
        Args:
            qid: Qualified ID (file::entity)
        
        Returns:
            ChunkResult if found, None otherwise
        """
        # Parse QID
        if "::" not in qid:
            logger.warning(f"Invalid QID format: {qid}")
            return None
        
        file_path, entity_name = qid.split("::", 1)
        
        # Query ChromaDB by metadata
        results = await asyncio.to_thread(
            self._collection.get,
            where={
                "$and": [
                    {"source": {"$eq": file_path}},
                    {"name": {"$eq": entity_name}},
                ]
            },
            limit=1,
            include=["metadatas", "documents"],
        )
        
        if not results or not results["documents"]:
            return None
        
        # Return first match
        return ChunkResult(
            id=results["ids"][0] if results["ids"] else qid,
            content=results["documents"][0],
            metadata=results["metadatas"][0],
            score=None,
        )
    
    async def iter_chunk_metadata(self, batch_size: int = 500) -> AsyncIterator[List[Dict]]:
        """
        Iterate over chunk metadata in batches.
        
        ARCHITECTURE: Used ONLY for graph rebuild. NO embeddings returned.
        
        Args:
            batch_size: Chunks per batch
        
        Yields:
            Batches of metadata dictionaries
        """
        offset = 0
        
        while True:
            # Get batch from ChromaDB (synchronous operation)
            batch = await asyncio.to_thread(
                self._collection.get,
                offset=offset,
                limit=batch_size,
                include=["metadatas"],  # CRITICAL: NO embeddings
            )
            
            metadatas = batch.get("metadatas", [])
            
            if not metadatas:
                break
            
            logger.debug(f"iter_chunk_metadata: yielding batch of {len(metadatas)}")
            yield metadatas
            
            # Check if we've reached the end
            if len(metadatas) < batch_size:
                break
            
            offset += batch_size
    
    async def delete_by_source(self, source: str) -> int:
        """
        Delete all chunks from a source file.
        
        Args:
            source: Source file path
        
        Returns:
            Number of chunks deleted
        """
        # Get IDs to delete
        results = await asyncio.to_thread(
            self._collection.get,
            where={"source": {"$eq": source}},
            include=[],  # Only need IDs
        )
        
        ids = results.get("ids", [])
        
        if ids:
            await asyncio.to_thread(self._collection.delete, ids=ids)
            logger.info(f"Deleted {len(ids)} chunks from {source}")
        
        return len(ids)
    
    async def count(self) -> int:
        """Get total number of chunks."""
        result = await asyncio.to_thread(self._collection.count)
        return result
    
    async def clear(self) -> None:
        """Clear all chunks from collection."""
        await asyncio.to_thread(self._collection.delete, where={})
        logger.info(f"Cleared collection: {self.collection_name}")
