"""Base vector store interface for RAG.

ARCHITECTURE (see docs/rag_architecture.md):
- Abstract interface for all vector backends
- Agents call BaseVectorStore ONLY
- NO backend internals exposed
- iter_chunk_metadata for derived state rebuild
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, AsyncIterator
from dataclasses import dataclass


@dataclass
class ChunkResult:
    """Result from vector search."""
    
    id: str
    content: str
    metadata: Dict
    score: Optional[float] = None
    rerank_score: Optional[float] = None  # Phase 11: Reranking score
    is_graph_expansion: bool = False     # Phase 12A: Graph-injected chunk


class BaseVectorStore(ABC):
    """
    Abstract base class for vector storage backends.
    
    Implementations: ChromaVectorStore, PgVectorStore
    """
    
    @abstractmethod
    async def add_chunks(
        self,
        chunks: List[Dict],
        embeddings: List,
    ) -> int:
        """
        Add chunks with embeddings to the store.
        
        Args:
            chunks: List of chunk dicts with content and metadata
            embeddings: List of embedding vectors
        
        Returns:
            Number of chunks added
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> List[ChunkResult]:
        """
        Search for similar chunks.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results
            score_threshold: Minimum similarity score
        
        Returns:
            List of matching chunks
        """
        pass
    
    @abstractmethod
    async def get_chunk_by_qualified_id(
        self,
        qid: str,
        tenant_id: str = "default",
        collection_name: Optional[str] = None
    ) -> Optional[ChunkResult]:
        """
        Get a specific chunk by qualified ID (file::entity).
        
        ARCHITECTURE: Used by graph expansion to fetch related chunks.
        
        Args:
            qid: Qualified ID (file::entity format)
            tenant_id: Tenant context for data isolation
            collection_name: Optional explicit collection name
        
        Returns:
            Chunk if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def iter_chunk_metadata(
        self,
        batch_size: int = 500,
        tenant_id: str = "default",
        collection_name: Optional[str] = None
    ) -> AsyncIterator[List[Dict]]:
        """
        Iterate over chunk metadata in batches.
        
        ARCHITECTURE: Used ONLY for derived state rebuild (code graph).
        Does NOT return embeddings or full content, only metadata.
        
        Args:
            batch_size: Number of chunks per batch
            tenant_id: Tenant context for data isolation
            collection_name: Optional explicit collection name
        
        Yields:
            Batches of metadata dictionaries
        """
        pass
    
    @abstractmethod
    async def delete_by_source(self, source: str) -> int:
        """
        Delete all chunks from a source file.
        
        Args:
            source: Source file path
        
        Returns:
            Number of chunks deleted
        """
        pass
    
    @abstractmethod
    async def count(self) -> int:
        """
        Get total number of chunks in store.
        
        Returns:
            Chunk count
        """
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all chunks from the store."""
        pass
        
    @abstractmethod
    async def delete_by_file_id(self, file_id: str, tenant_id: str = "default", collection_name: Optional[str] = None) -> int:
        """
        Delete all chunks for a specific file by its ID.
        
        Args:
            file_id: File UUID
            tenant_id: Tenant context for data isolation
            collection_name: Optional explicit collection name
            
        Returns:
            Number of chunks deleted
        """
        pass
        
    @abstractmethod
    async def delete_collection(self, tenant_id: str, collection_name: str) -> int:
        """
        Dev-only: Drop all vectors for a tenant collection.
        """
        pass
    
    @abstractmethod
    async def get_chunks_by_file_id(
        self,
        file_id: str,
        limit: int = 5,
        offset: int = 0
    ) -> List[ChunkResult]:
        """
        Get all chunks for a specific file, ordered by chunk_index.
        
        Args:
            file_id: File UUID
            limit: Number of chunks to return
            offset: Offset for pagination
            
        Returns:
            List of matching chunks ordered by index
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if vector store is healthy and accessible.
        
        Phase 11.2: Used by /rag/health endpoint.
        
        Returns:
            True if store is accessible, False otherwise
        """
        pass
