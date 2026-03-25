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
        Ensures metadata chunk_id is used as the database primary key.
        """
        import uuid
        from langchain_core.documents import Document
        
        documents = []
        ids = []
        
        for c in chunks:
            metadata = c.get("metadata", {})
            # Extract ID from metadata or fallback
            chunk_id = metadata.get("chunk_id") or str(uuid.uuid4())
            
            # Ensure chunk_id is in metadata for search alignment
            metadata["chunk_id"] = chunk_id
            
            doc = Document(
                page_content=c["content"],
                metadata=metadata
            )
            documents.append(doc)
            ids.append(chunk_id)
        
        # Add to Chroma with explicit IDs
        if documents:
            await asyncio.to_thread(
                self.client.add_documents, 
                documents=documents, 
                ids=ids
            )
        
        logger.debug(f"Added {len(chunks)} chunks to ChromaDB (IDs synchronized)")
        return len(chunks)
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> List[ChunkResult]:
        """
        Search for similar chunks in ChromaDB (Direct Collection Access).
        """
        # Direct query to underlying Chroma collection
        # This guarantees we get scores and metadata without wrapper issues
        results = await asyncio.to_thread(
            self._collection.query,
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        chunk_results = []
        
        # Check if we got results
        if not results or not results["ids"]:
            return []
            
        # Parse standard Chroma results structure (list of lists)
        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]
        
        for i in range(len(ids)):
            dist = distances[i]
            
            # Chroma returns DISTANCE (lower is better).
            # We need SIMILARITY (higher is better).
            # Simple conversion for L2 distance: similarity = 1 / (1 + distance)
            # OR just pass the raw distance if your agent handles it (our agent does).
            
            # Let's verify threshold
            # If threshold is 0.0, we accept everything.
            
            # Construct ChunkResult
            chunk_results.append(ChunkResult(
                id=ids[i],
                content=documents[i],
                metadata=metadatas[i] or {},
                score=dist, # Pass raw distance, agent handles normalization
            ))
            
        return chunk_results
        
    async def get_chunk_by_qualified_id(
        self,
        qid: str,
        tenant_id: str = "default",
        collection_name: Optional[str] = None
    ) -> Optional[ChunkResult]:
        """
        Get chunk by qualified ID (file::entity).
        
        ARCHITECTURE: Used by graph expansion.
        
        Args:
            qid: Qualified ID (file::entity)
            tenant_id: Tenant context for data isolation
            collection_name: Optional explicit collection name
        
        Returns:
            ChunkResult if found, None otherwise
        """
        if "::" not in qid:
            return None

        # Parse QID properly taking into account new and old formats
        if qid.count("::") == 1:
            file_path, entity_name = qid.split("::", 1)
            tenant = tenant_id
        else:
            tenant, rest = qid.split("::", 1)
            file_path, entity_name = rest.rsplit("::", 1)

        # Query ChromaDB by metadata
        results = await asyncio.to_thread(
            self._collection.get,
            where={
                "$and": [
                    {"source": {"$eq": file_path}},
                    {"name": {"$eq": entity_name}},
                    {"tenant_id": {"$eq": tenant}},
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
    
    async def iter_chunk_metadata(
        self,
        batch_size: int = 500,
        tenant_id: str = "default",
        collection_name: Optional[str] = None
    ) -> AsyncIterator[List[Dict]]:
        """
        Iterate over chunk metadata in batches.
        
        ARCHITECTURE: Used ONLY for graph rebuild. NO embeddings returned.
        
        Args:
            batch_size: Chunks per batch
            tenant_id: Tenant context for data isolation
            collection_name: Optional explicit collection name
        
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
            
            # Filter by tenant_id in metadata (additional safety)
            filtered = [m for m in metadatas if m.get("tenant_id") == tenant_id]
            if filtered:
                yield filtered
            
            # Check if we've reached the end
            if len(metadatas) < batch_size:
                break
            
            offset += batch_size
    
    async def delete_by_source(self, source: str, tenant_id: str = "default", collection_name: Optional[str] = None) -> int:
        """
        Delete all chunks from a source file (tenant-scoped).
        
        Args:
            source: Source file path
            tenant_id: Tenant context for data isolation
            collection_name: Optional explicit collection name
        
        Returns:
            Number of chunks deleted
        """
        # Get IDs to delete (with tenant scoping)
        results = await asyncio.to_thread(
            self._collection.get,
            where={
                "$and": [
                    {"source": {"$eq": source}},
                    {"tenant_id": {"$eq": tenant_id}}
                ]
            },
            include=[],  # Only need IDs
        )
        
        ids = results.get("ids", [])
        
        if ids:
            await asyncio.to_thread(self._collection.delete, ids=ids)
            logger.info(f"Deleted {len(ids)} chunks from {source} (tenant={tenant_id})")
        
        return len(ids)

    async def delete_by_file_id(self, file_id: str, tenant_id: str = "default", collection_name: Optional[str] = None) -> int:
        """
        Delete all chunks for a specific file by its ID (tenant-scoped).
        
        Args:
            file_id: File UUID
            tenant_id: Tenant context for data isolation
            collection_name: Optional explicit collection name
            
        Returns:
            Number of chunks deleted
        """
        # Get IDs to delete (with tenant scoping)
        results = await asyncio.to_thread(
            self._collection.get,
            where={
                "$and": [
                    {"file_id": {"$eq": file_id}},
                    {"tenant_id": {"$eq": tenant_id}}
                ]
            },
            include=[],  # Only need IDs
        )
        
        ids = results.get("ids", [])
        
        if ids:
            await asyncio.to_thread(self._collection.delete, ids=ids)
            logger.info(f"Deleted {len(ids)} orphaned chunks for file_id={file_id} (tenant={tenant_id})")
        
        return len(ids)

    async def delete_collection(self, tenant_id: str, collection_name: str) -> int:
        """Dev-only: Drop all vectors for a tenant collection."""
        results = await asyncio.to_thread(
            self._collection.get,
            where={"tenant_id": {"$eq": tenant_id}},
            include=[],
        )
        ids = results.get("ids", [])
        if ids:
            await asyncio.to_thread(self._collection.delete, ids=ids)
            logger.warning(f"DEV PURGE: Deleted {len(ids)} chunks for tenant={tenant_id}")
        return len(ids)

    async def get_chunks_by_file_id(
        self,
        file_id: str,
        limit: int = 5,
        offset: int = 0
    ) -> List[ChunkResult]:
        """
        Retrieve chunks for a specific file from Chroma, ordered by chunk_index.
        """
        results = await asyncio.to_thread(
            self._collection.get,
            where={"file_id": {"$eq": file_id}},
            limit=limit,
            offset=offset,
            include=["metadatas", "documents"]
        )
        
        chunk_results = []
        if not results or not results["ids"]:
            return []
            
        ids = results["ids"]
        documents = results["documents"]
        metadatas = results["metadatas"]
        
        for i in range(len(ids)):
            chunk_results.append(ChunkResult(
                id=ids[i],
                content=documents[i],
                metadata=metadatas[i] or {},
                score=None
            ))
            
        # Sort by chunk_index manually if Chroma doesn't support complex ordering in .get()
        # Chroma .get() results are usually returned in insertion order or index order, 
        # but chunk_index is safer.
        chunk_results.sort(key=lambda x: int(x.metadata.get("chunk_index", 0)))
        
        return chunk_results
    
    async def count(self) -> int:
        """Get total number of chunks."""
        result = await asyncio.to_thread(self._collection.count)
        return result
    
    async def clear(self) -> None:
        """Clear all chunks from collection."""
        await asyncio.to_thread(self._collection.delete, where={})
        logger.info(f"Cleared collection: {self.collection_name}")
    
    async def health_check(self) -> bool:
        """
        Check if ChromaDB backend is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try to get collection count
            count = await asyncio.to_thread(self._collection.count)
            return count is not None
        except Exception as e:
            logger.error(f"ChromaDB health check failed: {e}")
            return False
