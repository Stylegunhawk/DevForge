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
                
                # DEBUG: Log metadata before storing
                logger.info(f"[STORE_DEBUG] Before pg_vector storage: type(meta.get('calls'))={type(meta.get('calls'))}, calls={meta.get('calls')}")
                logger.info(f"[STORE_DEBUG] Full metadata: {meta}")
                
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
    
    def _ensure_list_types(self, metadata: Dict) -> Dict:
        """
        Ensure calls and imports fields are always List[str], not str.
        
        This fixes the issue where PostgreSQL returns these fields as strings
        like "['func1', 'func2']" instead of proper lists.
        """
        # Process calls field
        calls = metadata.get("calls", [])
        if isinstance(calls, str):
            try:
                # Try to parse as JSON list
                parsed_calls = json.loads(calls)
                if isinstance(parsed_calls, list):
                    metadata["calls"] = [str(item) for item in parsed_calls]
                else:
                    metadata["calls"] = []
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, check if it's a single item string
                calls_stripped = calls.strip()
                if calls_stripped.startswith('[') and calls_stripped.endswith(']'):
                    # Try to eval Python list representation (safe since we control content)
                    try:
                        import ast
                        parsed_calls = ast.literal_eval(calls_stripped)
                        if isinstance(parsed_calls, list):
                            metadata["calls"] = [str(item) for item in parsed_calls]
                        else:
                            metadata["calls"] = []
                    except (ValueError, SyntaxError):
                        metadata["calls"] = []
                else:
                    # Single string, wrap in list
                    metadata["calls"] = [calls_stripped] if calls_stripped else []
        
        # Process imports field
        imports = metadata.get("imports", [])
        if isinstance(imports, str):
            try:
                # Try to parse as JSON list
                parsed_imports = json.loads(imports)
                if isinstance(parsed_imports, list):
                    metadata["imports"] = [str(item) for item in parsed_imports]
                else:
                    metadata["imports"] = []
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, check if it's a single item string
                imports_stripped = imports.strip()
                if imports_stripped.startswith('[') and imports_stripped.endswith(']'):
                    # Try to eval Python list representation (safe since we control content)
                    try:
                        import ast
                        parsed_imports = ast.literal_eval(imports_stripped)
                        if isinstance(parsed_imports, list):
                            metadata["imports"] = [str(item) for item in parsed_imports]
                        else:
                            metadata["imports"] = []
                    except (ValueError, SyntaxError):
                        metadata["imports"] = []
                else:
                    # Single string, wrap in list
                    metadata["imports"] = [imports_stripped] if imports_stripped else []
        
        return metadata

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
        tenant_id: str = "default",
        collection_name: Optional[str] = None,
        file_ids: Optional[List[str]] = None,
    ) -> List[ChunkResult]:
        """Search for similar chunks using Cosine Distance with tenant filtering."""
        conn = await self._get_conn()
        try:
            collection = collection_name or self.collection_name

            # Cosine distance operator is <=>
            # Similarity = 1 - Distance
            if file_ids:
                query = f"""
                    SELECT chunk_id, content, metadata, 1 - (embedding <=> $1) as similarity
                    FROM {self.table_name}
                    WHERE tenant_id = $2
                      AND collection_name = $3
                      AND metadata->>'file_id' = ANY($4)
                    ORDER BY embedding <=> $1
                    LIMIT $5;
                """
                bind_params = (query_embedding, tenant_id, collection, file_ids, top_k)
            else:
                query = f"""
                    SELECT chunk_id, content, metadata, 1 - (embedding <=> $1) as similarity
                    FROM {self.table_name}
                    WHERE tenant_id = $2
                      AND collection_name = $3
                    ORDER BY embedding <=> $1
                    LIMIT $4;
                """
                bind_params = (query_embedding, tenant_id, collection, top_k)

            logger.info(f"PgVector Executing search STRICT: tenant={tenant_id}, collection={collection}, top_k={top_k}, file_ids={file_ids}")

            rows = await conn.fetch(query, *bind_params)
            
            logger.info(f"PgVector Rows found: {len(rows)}")
            
            results = []
            for row in rows:
                metadata = json.loads(row["metadata"])
                
                # FIX: Ensure calls/imports are always List[str], not str
                metadata = self._ensure_list_types(metadata)
                
                # DEBUG: Log metadata after retrieval
                logger.info(f"[RETRIEVE_DEBUG] After pg_vector retrieval: type(metadata.get('calls'))={type(metadata.get('calls'))}, calls={metadata.get('calls')}")
                
                results.append(ChunkResult(
                    id=row["chunk_id"],
                    content=row["content"],
                    metadata=metadata,
                    score=float(row["similarity"])
                ))
            
            return results
            
        finally:
            await conn.close()

    async def get_chunk_by_qualified_id(
        self,
        qid: str,
        tenant_id: str = "default",
        collection_name: Optional[str] = None
    ) -> Optional[ChunkResult]:
        """Get chunk by qualified ID (file::entity) via metadata."""
        if "::" not in qid:
            return None
            
        # Parse QID properly taking into account new and old formats
        if qid.count("::") == 1:
            file_path, entity_name = qid.split("::", 1)
            tenant = tenant_id
        else:
            tenant, rest = qid.split("::", 1)
            file_path, entity_name = rest.rsplit("::", 1)

        collection = collection_name or self.collection_name
        
        conn = await self._get_conn()
        try:
            # Query JSONB metadata
            query = f"""
                SELECT chunk_id, content, metadata
                FROM {self.table_name}
                WHERE metadata->>'source' = $1 
                  AND metadata->>'name' = $2
                  AND tenant_id = $3
                  AND collection_name = $4
                LIMIT 1;
            """
            
            row = await conn.fetchrow(query, file_path, entity_name, tenant, collection)
            
            if row:
                metadata = json.loads(row["metadata"])
                
                # FIX: Ensure calls/imports are always List[str], not str
                metadata = self._ensure_list_types(metadata)
                
                return ChunkResult(
                    id=row["chunk_id"],
                    content=row["content"],
                    metadata=metadata,
                    score=None
                )
            return None
            
        finally:
            await conn.close()

    async def iter_chunk_metadata(
        self,
        batch_size: int = 500,
        tenant_id: str = "default",
        collection_name: Optional[str] = None
    ) -> AsyncIterator[List[Dict]]:
        """Iterate over chunk metadata (NO embeddings/content)."""
        conn = await self._get_conn()
        try:
            collection = collection_name or self.collection_name
            # Use a server-side cursor for efficiency
            async with conn.transaction():
                cursor = await conn.cursor(
                    f"SELECT metadata FROM {self.table_name} "
                    f"WHERE tenant_id = $1 AND collection_name = $2 "
                    f"ORDER BY created_at",
                    tenant_id,
                    collection
                )
                
                while True:
                    rows = await cursor.fetch(batch_size)
                    if not rows:
                        break
                    
                    # Process metadata with safe list type conversion
                    processed_metas = []
                    for row in rows:
                        metadata = json.loads(row["metadata"])
                        # FIX: Ensure calls/imports are always List[str], not str
                        metadata = self._ensure_list_types(metadata)
                        processed_metas.append(metadata)
                    
                    yield processed_metas
                    
                    # DEBUG: Log first metadata in batch for graph building
                    if processed_metas:
                        first_meta = processed_metas[0]
                        logger.info(f"[ITER_DEBUG] For graph building: type(first_meta.get('calls'))={type(first_meta.get('calls'))}, calls={first_meta.get('calls')}")
                    
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

    async def delete_by_file_id(
        self,
        file_id: str,
        tenant_id: str = "default",
        collection_name: Optional[str] = None
    ) -> int:
        """Delete all chunks for a given file_id."""
        conn = await self._get_conn()
        try:
            collection = collection_name or self.collection_name
            result = await conn.execute(
                f"DELETE FROM {self.table_name} "
                f"WHERE metadata->>'file_id' = $1 "
                f"AND tenant_id = $2 "
                f"AND collection_name = $3",
                file_id, tenant_id, collection
            )
            deleted = int(result.split()[-1])
            logger.info(f"delete_by_file_id: deleted {deleted} chunks for file_id={file_id}")
            return deleted
        finally:
            await conn.close()

    async def delete_collection(self, tenant_id: str, collection_name: str) -> int:
        """Dev-only: Drop all vectors for a tenant collection."""
        conn = await self._get_conn()
        try:
            result = await conn.execute(
                f"DELETE FROM {self.table_name} "
                f"WHERE tenant_id = $1 "
                f"AND collection_name = $2",
                tenant_id, collection_name
            )
            deleted = int(result.split()[-1])
            logger.warning(f"DEV PURGE: Deleted {deleted} chunks for tenant={tenant_id}, collection={collection_name}")
            return deleted
        finally:
            await conn.close()

    async def get_chunks_by_file_id(
        self,
        file_id: str,
        limit: int = 5,
        offset: int = 0
    ) -> List[ChunkResult]:
        """
        Retrieve chunks for a specific file from PostgreSQL, ordered by chunk_index.
        """
        conn = await self._get_conn()
        try:
            # SQL filtering on JSONB metadata
            query = f"""
                SELECT chunk_id, content, metadata
                FROM {self.table_name}
                WHERE metadata->>'file_id' = $1
                ORDER BY (metadata->>'chunk_index')::int ASC
                LIMIT $2 OFFSET $3;
            """
            
            rows = await conn.fetch(query, file_id, limit, offset)
            
            results = []
            for row in rows:
                metadata = json.loads(row["metadata"])
                
                # FIX: Ensure calls/imports are always List[str], not str
                metadata = self._ensure_list_types(metadata)
                
                results.append(ChunkResult(
                    id=row["chunk_id"],
                    content=row["content"],
                    metadata=metadata,
                    score=None
                ))
            
            return results
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
