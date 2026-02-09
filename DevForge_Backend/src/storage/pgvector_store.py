"""PosterSQL (pgvector) vector store implementation.

ARCHITECTURE (see docs/rag_architecture.md):
- Implements BaseVectorStore using asyncpg and pgvector
- Replaces ChromaDB for production scaling
- Compatible with all RAG endpoints (delete_by_source, etc.)
"""

import logging
import asyncio
import uuid
import json
from typing import List, Dict, Optional, AsyncIterator

import asyncpg
from pgvector.asyncpg import register_vector

from .base_store import BaseVectorStore, ChunkResult
from src.core.config import settings

logger = logging.getLogger(__name__)


class PgVectorStore(BaseVectorStore):
    """
    PostgreSQL (pgvector) implementation of BaseVectorStore.
    """

    def __init__(self, table_name: str = "rag_vectors", collection_name: str = "default"):
        """
        Initialize PgVector store.

        Args:
            table_name: Database table name for vectors
            collection_name: Tenant collection name for isolation
        """
        self.table_name = table_name
        self.collection_name = collection_name
        self.dsn = settings.POSTGRES_URL
        # Ensure dimension matches embedding model (e.g., nomic-embed-text=768)
        self.dimension = settings.PG_VECTOR_DIMENSION 
        
        # Initialize embeddings for query embedding generation
        from langchain_community.embeddings import OllamaEmbeddings
        self.embeddings = OllamaEmbeddings(
            model=settings.RAG_EMBED_MODEL,
            base_url=settings.OLLAMA_HOST,
        )

    async def _get_conn(self) -> asyncpg.Connection:
        """Get database connection and register vector type."""
        conn = await asyncpg.connect(self.dsn)
        try:
            await register_vector(conn)
        except ValueError:
            # Type 'vector' not found. Create extension and reconnect.
            logger.info("Vector type not found, creating extension...")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            await conn.close()
            # Reconnect to pick up the new type
            conn = await asyncpg.connect(self.dsn)
            await register_vector(conn)
            
        return conn

    async def _init_schema(self):
        """Initialize database schema (extension and table)."""
        conn = await self._get_conn()
        try:
            # Enable extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # Create table
            # ID: UUID primary key
            # chunk_id: External ID from logic (matches others)
            # content: Text content
            # metadata: JSONB for flexible querying
            # embedding: Vector with specific dimension
            # source: Extracted from metadata for fast delete operations
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id UUID PRIMARY KEY,
                    chunk_id TEXT UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    embedding vector({self.dimension}),
                    source TEXT,
                    tenant_id TEXT,
                    collection_name TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create HNSW index for faster search (approximate)
            # Note: Index creation can fail if table is empty, usually needs some data first.
            # We add IF NOT EXISTS but keeping it minimal for now.
            try:
                await conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS {self.table_name}_embedding_idx 
                    ON {self.table_name} 
                    USING hnsw (embedding vector_cosine_ops);
                """)
            except Exception as e:
                logger.warning(f"Could not create HNSW index (maybe empty table?): {e}")

            # Index for source deletion performance
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {self.table_name}_source_idx 
                ON {self.table_name} (source);
            """)
            
            # Index for tenant filtering performance
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {self.table_name}_tenant_idx 
                ON {self.table_name} (tenant_id, collection_name);
            """)

            logger.info(f"PgVector schema initialized for {self.table_name}")
            
        finally:
            await conn.close()

    async def add_chunks(self, chunks: List[Dict], embeddings: List) -> int:
        """Add chunks with embeddings to PostgreSQL."""
        if not chunks:
            return 0

        # Ensure schema exists (lazy init)
        await self._init_schema()
        
        conn = await self._get_conn()
        try:
            records = []
            for chunk, embedding in zip(chunks, embeddings):
                meta = chunk.get("metadata", {})
                chunk_id = meta.get("chunk_id") or str(uuid.uuid4())
                meta["chunk_id"] = chunk_id # Ensure synced
                
                # Extract source for the optimized column
                source = meta.get("source")
                
                # Extract tenant info
                tenant_id = meta.get("tenant_id", "default")
                collection = meta.get("collection_name") or self.collection_name
                
                records.append((
                    uuid.uuid4(),
                    chunk_id,
                    chunk["content"],
                    json.dumps(meta),
                    embedding,
                    source,
                    tenant_id,
                    collection
                ))

            # Bulk insert
            await conn.copy_records_to_table(
                self.table_name,
                records=records,
                columns=["id", "chunk_id", "content", "metadata", "embedding", "source", "tenant_id", "collection_name"],
                timeout=30
            )
            
            logger.debug(f"Added {len(chunks)} chunks to PgVector")
            return len(chunks)
            
        finally:
            await conn.close()

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
        tenant_id: str = "default",
        collection_name: Optional[str] = None,
    ) -> List[ChunkResult]:
        """Search for similar chunks using Cosine Distance with tenant filtering."""
        conn = await self._get_conn()
        try:
            collection = collection_name or self.collection_name
            
            # Cosine distance operator is <=>
            # Similarity = 1 - Distance
            query = f"""
                SELECT chunk_id, content, metadata, 1 - (embedding <=> $1) as similarity
                FROM {self.table_name}
                WHERE tenant_id = $2 
                  AND collection_name = $3
                ORDER BY embedding <=> $1
                LIMIT $4;
            """
            
            logger.info(f"PgVector Executing search STRICT: tenant={tenant_id}, collection={collection}, top_k={top_k}")
            
            rows = await conn.fetch(query, query_embedding, tenant_id, collection, top_k)
            
            logger.info(f"PgVector Rows found: {len(rows)}")
            
            results = []
            for row in rows:
                results.append(ChunkResult(
                    id=row["chunk_id"],
                    content=row["content"],
                    metadata=json.loads(row["metadata"]),
                    score=float(row["similarity"])
                ))
            
            return results
            
        finally:
            await conn.close()

    async def get_chunk_by_qualified_id(self, qid: str) -> Optional[ChunkResult]:
        """Get chunk by qualified ID (file::entity) via metadata."""
        if "::" not in qid:
            return None
            
        file_path, entity_name = qid.split("::", 1)
        
        conn = await self._get_conn()
        try:
            # Query JSONB metadata
            query = f"""
                SELECT chunk_id, content, metadata
                FROM {self.table_name}
                WHERE metadata->>'source' = $1 AND metadata->>'name' = $2
                LIMIT 1;
            """
            
            row = await conn.fetchrow(query, file_path, entity_name)
            
            if row:
                return ChunkResult(
                    id=row["chunk_id"],
                    content=row["content"],
                    metadata=json.loads(row["metadata"]),
                    score=None
                )
            return None
            
        finally:
            await conn.close()

    async def iter_chunk_metadata(self, batch_size: int = 500) -> AsyncIterator[List[Dict]]:
        """Iterate over chunk metadata (NO embeddings/content)."""
        conn = await self._get_conn()
        try:
            # Use a server-side cursor for efficiency
            async with conn.transaction():
                cursor = await conn.cursor(f"SELECT metadata FROM {self.table_name} ORDER BY created_at")
                
                while True:
                    rows = await cursor.fetch(batch_size)
                    if not rows:
                        break
                    
                    yield [json.loads(row["metadata"]) for row in rows]
                    
        finally:
            await conn.close()

    async def delete_by_source(self, source: str, tenant_id: str = "default", collection_name: Optional[str] = None) -> int:
        """Delete all chunks from a source file (tenant-scoped)."""
        conn = await self._get_conn()
        try:
            collection = collection_name or self.collection_name
            
            # Delete using optimized source column AND tenant filtering
            result = await conn.execute(
                f"DELETE FROM {self.table_name} WHERE source = $1 AND tenant_id = $2 AND collection_name = $3",
                source, tenant_id, collection
            )
            
            # Format is "DELETE X"
            count = int(result.split()[-1])
            logger.info(f"Deleted {count} chunks for {source} from PgVector (tenant={tenant_id}, collection={collection})")
            return count
            
        finally:
            await conn.close()

    async def count(self, tenant_id: str = "default", collection_name: Optional[str] = None) -> int:
        """Get total number of chunks (tenant-scoped)."""
        conn = await self._get_conn()
        try:
            collection = collection_name or self.collection_name
            count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {self.table_name} WHERE tenant_id = $1 AND collection_name = $2",
                tenant_id, collection
            )
            return count
        except Exception:
            return 0
        finally:
            await conn.close()

    async def clear(self) -> None:
        """Clear all chunks."""
        conn = await self._get_conn()
        try:
            await conn.execute(f"TRUNCATE TABLE {self.table_name}")
            logger.info("Cleared PgVector table")
        finally:
            await conn.close()

    async def health_check(self) -> bool:
        """Check if Postgres is accessible."""
        try:
            conn = await self._get_conn()
            await conn.execute("SELECT 1")
            await conn.close()
            return True
        except Exception as e:
            logger.error(f"PgVector health check failed: {e}")
            return False
