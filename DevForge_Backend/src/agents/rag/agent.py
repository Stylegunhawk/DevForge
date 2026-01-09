"""RAG agent with LangGraph-based workflow for document ingestion and retrieval.

Phase 3.1: ChromaDB implementation with async document processing.
Supports PDF, Markdown, TXT, and DOCX file formats.
"""

import logging
import asyncio
import time
from typing import List, Literal, Optional, TypedDict, Dict
from pathlib import Path

from langgraph.graph import END, StateGraph
from cachetools import TTLCache
from src.agents.rag.graph.code_graph import CodeGraph
import json
from src.core.config import settings
from src.tools.rag.tools import (
    generate_response,
    ingest_documents,
    retrieve_docs,
)
# Note: Reranker is lazy-loaded inside RAGAgent
from src.agents.rag.context_shaper import ContextShaper

logger = logging.getLogger(__name__)


class RAGState(TypedDict):
    """State for RAG agent graph."""

    query: str  # User search query
    file_paths: Optional[List[str]]  # Optional: Documents to ingest first
    top_k: int  # Number of results to return
    embed_model: str  # Embedding model name
    backend: str  # Vector store backend ("chroma" or "qdrant")
    score_threshold: float  # Minimum similarity score
    documents: Optional[List[dict]]  # Retrieved documents
    context: Optional[str]  # Concatenated context from documents
    response: Optional[str]  # LLM-generated response
    error: Optional[str]  # Error message if any
    
    # ✅ ADDED: Carry tenant context in state
    tenant_id: Optional[str] 
    collection_name: Optional[str]


async def ingest_node(state: RAGState) -> RAGState:
    """Ingest documents into vector store if file_paths provided."""
    file_paths = state.get("file_paths")
    embed_model = state.get("embed_model", settings.RAG_EMBED_MODEL)
    backend = state.get("backend", settings.VECTOR_BACKEND)
    chunk_size = settings.RAG_CHUNK_SIZE
    chunk_overlap = settings.RAG_CHUNK_OVERLAP
    
    # ✅ FIX: Extract tenant info from state
    tenant_id = state.get("tenant_id", "default")
    collection_name = state.get("collection_name", f"user_{tenant_id}")

    logger.info(
        f"Ingesting {len(file_paths)} documents",
        extra={"file_count": len(file_paths), "embed_model": embed_model, "backend": backend},
    )

    import uuid
    batch_id = str(uuid.uuid4())

    try:
        # Update tools.ingest_documents to accept collection if not already
        result = await ingest_documents(
            file_paths=file_paths,
            file_id=batch_id,
            embed_model=embed_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            backend=backend,
            tenant_id=tenant_id,           # Pass explicitly
            collection_name=collection_name # Pass explicitly
        )

        if not result.get("success"):
            error_msg = result.get("error", "Document ingestion failed")
            logger.warning(f"Ingestion completed with errors: {error_msg}")
            return {**state, "error": error_msg}

        return {**state, "error": None}

    except Exception as e:
        logger.error(f"Ingest node failed: {e}", exc_info=True)
        return {**state, "error": f"Ingestion failed: {str(e)}"}


async def retrieve_node(state: RAGState) -> RAGState:
    """Retrieve relevant documents via semantic search."""
    query = state.get("query", "")
    top_k = state.get("top_k", settings.RAG_TOP_K)
    score_threshold = state.get("score_threshold", settings.RAG_SCORE_THRESHOLD)
    
    # ✅ FIX: Extract tenant info from state
    tenant_id = state.get("tenant_id", "default")
    collection_name = state.get("collection_name", f"user_{tenant_id}")

    logger.info(f"Retrieving documents: query='{str(query)[:50]}...', top_k={top_k}")

    try:
        # ✅ FIX: Use Factory Pattern with correct scope
        # Do NOT use get_shared_rag_agent()
        agent = get_rag_agent(tenant_id=tenant_id, collection_name=collection_name)
        
        retrieval_result = await agent.retrieve_with_reranking(
            query=query,
            top_k=top_k,
            use_reranking=True,
            use_cache=True,
            use_hybrid=False,
            score_threshold=score_threshold
        )
        
        # Extract documents from the result
        documents = retrieval_result.get("documents", [])
        
        # Normalize format
        formatted_documents = []
        for doc in documents:
            if hasattr(doc, 'content'):
                formatted_documents.append({
                    "id": doc.id,
                    "content": doc.content,
                    "metadata": doc.metadata,
                    "score": getattr(doc, 'rerank_score', getattr(doc, 'score', 0.0))
                })
            else:
                formatted_documents.append(doc)

        if not formatted_documents:
            return {**state, "documents": [], "context": "", "error": None}

        # Context formatting logic...
        context_parts = []
        for i, doc in enumerate(formatted_documents):
            is_graph = doc.get("metadata", {}).get("is_graph_expansion") or doc.get("is_graph_expansion")
            marker = "[GRAPH]" if is_graph else "[VECTOR]"
            context_parts.append(f"[{i+1}] {marker} {doc['content']}")
            
        context = "\n\n".join(context_parts)

        return {
            **state,
            "documents": formatted_documents,
            "context": context,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Retrieve node failed: {e}", exc_info=True)
        return {**state, "error": f"Retrieval failed: {str(e)}", "documents": None, "context": None}


async def generate_node(state: RAGState) -> RAGState:
    """Generate LLM response based on retrieved context."""
    query = state.get("query", "")
    context = state.get("context", "")

    try:
        if not context or context.strip() == "":
            return {
                **state,
                "response": "I don't have enough information to answer that question.",
                "error": None,
            }

        response = await generate_response(query=query, context=context)

        return {**state, "response": response, "error": None}

    except Exception as e:
        logger.error(f"Generate node failed: {e}", exc_info=True)
        return {**state, "error": f"Response generation failed: {str(e)}", "response": None}


async def error_node(state: RAGState) -> RAGState:
    error = state.get("error", "Unknown error occurred")
    logger.error(f"RAG agent error: {error}")
    return {**state, "response": f"Error: {error}"}


def should_ingest(state: RAGState) -> Literal["ingest", "retrieve"]:
    file_paths = state.get("file_paths")
    if file_paths and len(file_paths) > 0:
        return "ingest"
    return "retrieve"


def check_error(state: RAGState) -> Literal["error_node", "continue"]:
    if state.get("error"):
        return "error_node"
    return "continue"


def create_rag_graph():
    workflow = StateGraph(RAGState)
    workflow.add_node("ingest", ingest_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("error", error_node)

    workflow.set_conditional_entry_point(should_ingest, {"ingest": "ingest", "retrieve": "retrieve"})
    workflow.add_conditional_edges("ingest", check_error, {"error_node": "error", "continue": "retrieve"})
    workflow.add_conditional_edges("retrieve", check_error, {"error_node": "error", "continue": "generate"})
    workflow.add_conditional_edges("generate", check_error, {"error_node": "error", "continue": END})
    workflow.add_edge("error", END)
    
    return workflow.compile()


# ============================================================================
# PHASE 15: RAG AGENT FACTORY (MULTI-TENANT CACHE)
# ============================================================================

_agent_cache = TTLCache(maxsize=100, ttl=3600)

def get_rag_agent(tenant_id: str = "default", collection_name: Optional[str] = None) -> "RAGAgent":
    """
    Get or create a RAGAgent for a specific tenant/collection.
    Uses LRU/TTL cache to prevent re-initialization overhead.
    """
    # 1. Determine Scope
    if not collection_name:
        collection_name = f"user_{tenant_id}"
        
    # 2. Check Cache
    if collection_name in _agent_cache:
        return _agent_cache[collection_name]
    
    # 3. Create New Instance
    logger.info(f"Initializing new RAGAgent for collection: {collection_name}")
    agent = RAGAgent(collection_name=collection_name)
    agent.tenant_id = tenant_id 
    
    _agent_cache[collection_name] = agent
    return agent

# ✅ FIX: EXPORT ONLY WHAT IS NEEDED
__all__ = ["RAGAgent", "get_rag_agent", "rag_agent_invoke"]

# Export compiled RAG agent
rag_agent = create_rag_graph()


async def rag_agent_invoke(
    query: str,
    tenant_id: str = "default", # ✅ Added support for tenant ID
    file_paths: Optional[List[str]] = None,
    top_k: Optional[int] = None,
    embed_model: Optional[str] = None,
    backend: Optional[str] = None,
    score_threshold: Optional[float] = None,
) -> dict:
    """Convenience function to invoke RAG agent with a query."""
    start_time = time.time()

    initial_state: RAGState = {
        "query": query,
        "tenant_id": tenant_id, # ✅ Pass tenant ID to state
        "collection_name": f"user_{tenant_id}",
        "file_paths": file_paths,
        "top_k": top_k if top_k is not None else settings.RAG_TOP_K,
        "embed_model": embed_model if embed_model else settings.RAG_EMBED_MODEL,
        "backend": backend if backend else settings.VECTOR_BACKEND,
        "score_threshold": score_threshold if score_threshold is not None else settings.RAG_SCORE_THRESHOLD,
        "documents": None,
        "context": None,
        "response": None,
        "error": None,
    }

    try:
        final_state = await rag_agent.ainvoke(initial_state)
        # ... (rest of function logic remains same) ...
        # Standardizing return format...
        return _sanitize_json_values({
            "success": final_state.get("error") is None,
            "tool": "retrieve_docs",
            "data": {
                "response": final_state.get("response", ""),
                "documents": final_state.get("documents", []),
                "backend": settings.VECTOR_BACKEND,
            },
            "error": final_state.get("error")
        })

    except Exception as e:
        logger.error(f"RAG agent invocation failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


import math
def _sanitize_json_values(obj):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj): return 0.0
        return obj
    elif isinstance(obj, dict):
        return {k: _sanitize_json_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_json_values(i) for i in obj]
    return obj


class RAGAgent:
    """RAG Agent class for async task queue integration."""
    
    def __init__(self, collection_name: str = "devforge_docs"):
        self.collection_name = collection_name
        self.embed_model = settings.RAG_EMBED_MODEL
        self.backend = settings.VECTOR_BACKEND
        
        from src.storage.chroma_store import ChromaVectorStore
        self.vector_store = ChromaVectorStore(
            collection_name=collection_name,
            embed_model=self.embed_model
        )
        
        self._code_graph = None
        self._reranker = None
        self._query_cache = None
        self._bm25_index = None
        self._hybrid_retriever = None
        
        # ... (Rest of RAGAgent methods: init_graph, retrieve_with_reranking, etc. REMAIN SAME) ...
        # Just ensure retrieve_with_reranking is kept as you had it.
        
        # Phase 11.2: Initialize query cache
        if settings.ENABLE_QUERY_CACHE:
            redis_client = self._init_redis() if settings.REDIS_URL else None
            from src.agents.rag.cache import QueryCache
            self._query_cache = QueryCache(
                redis_client=redis_client,
                ttl=settings.QUERY_CACHE_TTL,
                max_size=settings.QUERY_CACHE_MAX_SIZE
            )
            logger.info("Query cache enabled")
        
        # Phase 11.2 Day 3: Initialize BM25 index (will be built on startup)
        if settings.ENABLE_HYBRID_SEARCH:
            from src.agents.rag.retrieval import BM25Index
            self._bm25_index = BM25Index()
            logger.info("Hybrid search enabled (BM25 index will be built on startup)")
        
        # Phase 12A Day 1: Initialize intent classifier
        self._intent_classifier = None
        if settings.ENABLE_INTENT_CLASSIFICATION:
            from src.agents.rag.analytics import IntentClassifier
            self._intent_classifier = IntentClassifier(
                rule_threshold=settings.INTENT_RULE_BASED_THRESHOLD,
                llm_enabled=settings.INTENT_LLM_FALLBACK,
                llm_timeout=settings.INTENT_LLM_TIMEOUT
            )
            logger.info("Intent classification enabled")
        
        # Phase 12A Day 2: Initialize query expander
        self._query_expander = None
        if settings.ENABLE_QUERY_EXPANSION:
            from src.agents.rag.expansion import QueryExpander
            self._query_expander = QueryExpander(
                llm_model=settings.EXPANSION_LLM_MODEL,  # Fixed: was model_name
                llm_timeout=settings.EXPANSION_TIMEOUT
            )
            logger.info("Query expansion enabled")
        
        # Phase 12A Day 3: Initialize semantic cache
        self._semantic_cache = None
        if settings.ENABLE_SEMANTIC_CACHE:
            from src.agents.rag.cache import SemanticCache
            from src.tools.rag.tools import get_embedding_model
            
            # Get actual embeddings object, not just the string name
            embeddings = get_embedding_model(settings.RAG_EMBED_MODEL)
            
            self._semantic_cache = SemanticCache(
                similarity_threshold=settings.SEMANTIC_CACHE_THRESHOLD,
                max_size_per_intent=settings.SEMANTIC_CACHE_MAX_SIZE_PER_INTENT,
                embed_model=embeddings  # Pass embeddings object
            )
            logger.info("Semantic cache enabled")
        
        # Phase 13: Initialize context shaper (deterministic dedup + ordering)
        self._context_shaper = ContextShaper(
            max_chunks=12,
            max_per_secondary_role=3
        )
        logger.info("Context shaper initialized")
        
        logger.info(f"RAGAgent initialized: collection={collection_name}")
    
    @property
    def code_graph(self):
        """
        Get code graph (must call init_graph() first).
        
        ARCHITECTURE: Derived state, rebuilt from chunk metadata.
        No persistence, instance-scoped only.
        
        Raises:
            RuntimeError: If graph not initialized
        """
        if self._code_graph is None:
            raise RuntimeError(
                "Code graph not initialized. Call 'await agent.init_graph()' first."
            )
        return self._code_graph
    
    async def init_graph(self):
        """
        Initialize code graph from cache or vector store metadata.
        
        ARCHITECTURE (Phase 16: Redis Caching):
        - Try Redis cache first (Fast)
        - Fallback to Chroma metadata rebuild (Slow)
        - Save to Redis on rebuild
        """
        if self._code_graph is not None:
            logger.info("Code graph already initialized")
            return
        

        
        # 0. Try Redis Cache
        cache_key = f"rag_graph:{self.collection_name}"
        redis_client = self._init_redis()
        
        if redis_client:
            try:
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    graph_dict = json.loads(cached_data)
                    self._code_graph = CodeGraph.from_dict(graph_dict)
                    logger.info(f"Graph loaded from cache: {self._code_graph.size()} nodes")
                    await redis_client.close()
                    return
            except Exception as e:
                logger.warning(f"Graph cache load failed: {e}")
        
        # 1. Fallback: Rebuild from Chroma
        logger.info("Building graph from vector store metadata (Cold Start)...")
        self._code_graph = CodeGraph()
        
        count = 0
        try:
            async for batch in self.vector_store.iter_chunk_metadata(batch_size=500):
                # Validate metadata hygiene
                valid_batch = []
                for meta in batch:
                    # FIX: Risk 1 - Metadata Integrity Check
                    if "source" not in meta or "name" not in meta:
                        # logger.debug(f"Skipping chunk (missing source/name): {meta.get('id', 'unknown')}")
                        continue
                    valid_batch.append({"metadata": meta})

                if valid_batch:
                    self._code_graph.add_chunks_batch(valid_batch)
                    count += len(valid_batch)
            
            logger.info(f"Graph initialized: {count} chunks → {self._code_graph.size()} nodes")
            
            # 2. Save to Cache
            if redis_client:
                try:
                    graph_dict = self._code_graph.to_dict()
                    await redis_client.set(cache_key, json.dumps(graph_dict), ex=3600) # 1 hr TTL
                    logger.info("Graph cached to Redis")
                    await redis_client.close()
                except Exception as e:
                    logger.warning(f"Graph cache save failed: {e}")
            
        except Exception as e:
            logger.warning(f"Graph rebuild failed: {e}, using empty graph")
            # Fallback: empty graph
            self._code_graph = CodeGraph()
            if redis_client:
                await redis_client.close()
    
    async def init_bm25(self):
        """
        Initialize BM25 index from vector store metadata.
        
        ARCHITECTURE (Phase 11.2 Day 3):
        - Proper async pattern (no blocking)
        - Called explicitly during startup
        - Builds from iter_chunk_metadata()
        - Graceful failure → hybrid search disabled
        
        Usage:
            agent = RAGAgent()
            await agent.init_bm25()  # Explicit async init
        """
        if not settings.ENABLE_HYBRID_SEARCH or not self._bm25_index:
            logger.info("Hybrid search disabled, skipping BM25 init")
            return
        
        if self._bm25_index.is_ready():
            logger.info("BM25 index already initialized")
            return
        
        try:
            # Build BM25 index from vector store
            await self._bm25_index.build(
                self.vector_store,
                batch_size=settings.BM25_INDEX_BATCH_SIZE
            )
            
            # Initialize hybrid retriever if BM25 ready
            if self._bm25_index.is_ready():
                from src.agents.rag.retrieval import HybridRetriever
                self._hybrid_retriever = HybridRetriever(
                    vector_store=self.vector_store,
                    bm25_index=self._bm25_index,
                    embeddings=self.embeddings
                )
                logger.info("Hybrid retriever initialized")
            else:
                logger.warning("BM25 index build failed, hybrid search disabled")
        
        except Exception as e:
            logger.error(f"BM25 initialization failed: {e}, hybrid search disabled")
            # Graceful failure: system will use vector-only
    
    def _init_redis(self):
        """
        Initialize Redis client for cache.
        
        Returns:
            Redis async client or None if initialization fails
        """
        try:
            import redis.asyncio as redis
            client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            logger.info(f"Redis client initialized: {settings.REDIS_URL}")
            return client
        except Exception as e:
            logger.warning(f"Redis init failed: {e}, will use in-memory cache")
            return None
    
    @property
    def reranker(self):
        """
        Lazy-load reranker on first use.
        
        ARCHITECTURE (Phase 11):
        - Agent-internal property
        - Loaded only if ENABLE_RERANKING=true
        - No persistence, instance-scoped
        """
        if self._reranker is None and settings.ENABLE_RERANKING:
            from src.agents.rag.reranking import CrossEncoderReranker
            self._reranker = CrossEncoderReranker(model_name=settings.RERANK_MODEL)
            logger.info("Reranker initialized (lazy)")
        return self._reranker
    
    async def ingest_document(
        self,
        file_path: str,
        file_id: str,
        tenant_id: str = "default",
        knowledge_id: Optional[str] = None,
        embed_model: Optional[str] = None,
        collection_name: Optional[str] = None,
    ) -> dict:
        """Ingest a single document into the vector store.
        
        This method is called by Celery tasks (NOT tools).
        
        Args:
            file_path: Path to document to ingest
            file_id: Unique ID for the file
            tenant_id: Tenant ID for isolation
            knowledge_id: Knowledge Base ID
            embed_model: Optional embedding model override
            collection_name: Optional target collection
        
        Returns:
            Dictionary with ingestion result
        """
        from src.tools.rag.tools import ingest_documents as _ingest_documents
        
        result = await _ingest_documents(
            file_paths=[file_path],
            file_id=file_id,
            tenant_id=tenant_id,
            knowledge_id=knowledge_id,
            embed_model=embed_model or self.embed_model,
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
            backend=self.backend,
            collection_name=collection_name or self.collection_name,
        )
        
        # FIX: Problem 1 - Graph Freshness
        # Invalidate graph so it rebuilds on next query with new data
        self._code_graph = None
        logger.info(
            f"Document ingested: {file_path}. Graph invalidated.",
            extra={"chunks": result.get("chunks_created", 0)}
        )
        
        return result
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[dict]:
        """Retrieve documents via semantic search.
        
        Args:
            query: Search query
            top_k: Number of results
        
        Returns:
            List of matching documents
        """
        # Phase 14: Use _vector_search directly (breaking circular dependency)
        return await self._vector_search(query=query, top_k=top_k)
    
    async def _vector_search(self, query: str, top_k: int, score_threshold: float = 0.0) -> List:
        """
        Vector-only search using ChromaVectorStore.
        
        Args:
            query: Search query
            top_k: Number of results
            score_threshold: Minimum similarity score (default: 0.0)
        
        Returns:
            List of search results (ChunkResult objects, NOT dicts)
        """
        # Phase 14: Direct store usage
        # Note: vector_store.search returns ChunkResult objects
        # We need to ensure callers handle objects (or convert them if needed)
        # Existing callers (retrieve_with_reranking) expect ChunkResult objects for reraking.
        
        # We need query embedding first?
        # ChromaVectorStore.search takes query_embedding.
        # But wait, helper implementation of ChromaVectorStore.search takes query_embedding.
        # Does it have a method for query string?
        # Looking at chroma_store.py: 
        # async def search(self, query_embedding: List[float], ...)
        
        # So we need to embed the query first.
        # self.vector_store.embeddings.embed_query(query)
        
        query_embedding = await asyncio.to_thread(
            self.vector_store.embeddings.embed_query,
            query
        )
        
        results = await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            score_threshold=score_threshold
        )
        
        return results

    
    async def retrieve_with_reranking(
        self,
        query: str,
        top_k: int = 5,
        use_reranking: bool = True,
        use_cache: bool = True,  # Phase 11.2 Day 1
        use_hybrid: bool = True,  # Phase 11.2 Day 3
        score_threshold: float = 0.0, # Added correct score threshold support
    ) -> dict:
        """
        Retrieve documents with optional hybrid search, caching, and reranking.
        
        ARCHITECTURE (Phase 11 + 11.2):
        - Optional query cache (exact-match)
        - Optional hybrid search (BM25 + Vector with RRF)
        - Two-stage retrieval: Initial search → Reranking
        - Mandatory fallback: Never returns zero results
        - Agent-internal: No API changes
        
        Args:
            query: Search query
            top_k: Number of results to return
            use_reranking: Enable reranking (respects ENABLE_RERANKING flag)
            use_cache: Enable cache lookup (respects ENABLE_QUERY_CACHE flag)
            use_hybrid: Enable hybrid search (respects ENABLE_HYBRID_SEARCH flag)
            score_threshold: Minimum similarity score filter
        
        Returns:
            Dictionary with documents and metadata
        """
        # Ensure query is a string
        query = str(query) if query else ""
        
        # [RAG-DEBUG] Pipeline entry log
        logger.info(
            f"[RAG-DEBUG] Pipeline START: query='{query[:60]}...', top_k={top_k}, "
            f"flags(SEMANTIC={settings.ENABLE_SEMANTIC_CACHE}, "
            f"EXACT={settings.ENABLE_QUERY_CACHE}, "
            f"EXPAND={settings.ENABLE_QUERY_EXPANSION}, "
            f"HYBRID={settings.ENABLE_HYBRID_SEARCH}, "
            f"RERANK={settings.ENABLE_RERANKING})"
        )
    
        # ========================================
        # PHASE 12A: Query Intelligence Pipeline
        # ========================================
        
        # Step 1: Intent Classification
        intent = "general"  # default
        if self._intent_classifier and settings.ENABLE_INTENT_CLASSIFICATION:
            try:
                classification_result = await self._intent_classifier.classify(query)
                # IntentResult is a dataclass, use attribute access
                intent = classification_result.intent if hasattr(classification_result, 'intent') else "general"
                confidence = classification_result.confidence if hasattr(classification_result, 'confidence') else 0.0
                logger.info(f"[PHASE 12A] Intent: {intent} (confidence: {confidence:.2f})")
            except Exception as e:
                logger.warning(f"Intent classification failed: {e}, using default='general'")
        
        # Step 2: Semantic Cache Check (intent-aware)
        if use_cache and self._semantic_cache and settings.ENABLE_SEMANTIC_CACHE:
            try:
                cached_result = await self._semantic_cache.get(query, intent)
                if cached_result:
                    logger.info(f"[PHASE 12A] ✅ SEMANTIC CACHE HIT (intent={intent})")
                    return {
                        **cached_result,
                        "from_semantic_cache": True,
                        "intent": intent,
                        "cache_type": "semantic"
                    }
                logger.debug(f"[PHASE 12A] Semantic cache miss (intent={intent})")
            except Exception as e:
                logger.warning(f"Semantic cache check failed: {e}")
        
        # Step 3: Query Expansion (intent-aware)
        expanded_queries = [query]  # default: just original query
        if self._query_expander and settings.ENABLE_QUERY_EXPANSION:
            try:
                expansion_result = await self._query_expander.expand(query, intent)
                # ExpansionResult is a dataclass, use attribute access
                if hasattr(expansion_result, 'success') and expansion_result.success:
                    expanded_queries = expansion_result.expanded_queries if hasattr(expansion_result, 'expanded_queries') else [query]
                    logger.info(f"[PHASE 12A] Query expanded: {len(expanded_queries)} queries")
                    for i, eq in enumerate(expanded_queries):
                        logger.debug(f"  [{i}] {eq[:60]}...")
            except Exception as e:
                logger.warning(f"Query expansion failed: {e}, using original query only")
        
        # ========================================
        # End of Phase 12A Query Intelligence
        # ========================================
    
        # Phase 11.2 Day 1: Check cache first
        if use_cache and self._query_cache and settings.ENABLE_QUERY_CACHE:
            from src.agents.rag.cache import cache_key_from_query
            
            cache_key = cache_key_from_query(query, top_k)
            cached = await self._query_cache.get(cache_key)
            
            if cached:
                logger.info(f"Query cache HIT: {str(query)[:50]}...")
                return {
                    **cached,
                    "from_cache": True,
                    "cache_key": cache_key
                }
        
        # Cache miss or disabled → proceed with retrieval
        
        # Phase 12A Step 4: Multi-Query Retrieval + Fusion (for expanded queries)
        initial_top_k = settings.VECTOR_SEARCH_CANDIDATES if (use_reranking and settings.ENABLE_RERANKING) else top_k
        
        if len(expanded_queries) > 1:
            # Multiple queries → retrieve for each and fuse
            from src.agents.rag.expansion import ResultFusion
            fusion = ResultFusion()
            
            all_results = []
            for eq in expanded_queries:
                # Use vector search for each expanded query, pass score_threshold
                eq_results = await self._vector_search(eq, initial_top_k, score_threshold)
                all_results.append(eq_results)
            
            # Fuse results using Reciprocal Rank Fusion
            initial_results = fusion.fuse(all_results, top_k=initial_top_k)
            logger.info(f"[PHASE 12A] Fused {len(expanded_queries)} result sets → {len(initial_results)} docs")
        
        # Phase 11.2 Day 3: Hybrid search (BM25 + Vector) or vector-only
        elif use_hybrid and self._hybrid_retriever and settings.ENABLE_HYBRID_SEARCH:
            # Ensure BM25 ready (lazy init if needed)
            if not self._bm25_index.is_ready():
                logger.warning("BM25 not ready, initializing...")
                await self.init_bm25()
            
            # Hybrid search with RRF fusion
            if self._hybrid_retriever:
                try:
                    initial_results = await self._hybrid_retriever.search(
                        query,
                        top_k=initial_top_k,
                        alpha=settings.HYBRID_ALPHA
                    )
                    logger.debug(f"Hybrid search returned {len(initial_results)} results")
                except Exception as e:
                    logger.error(f"Hybrid search failed: {e}, falling back to vector-only")
                    # Graceful fallback to vector search, pass threshold
                    initial_results = await self._vector_search(query, initial_top_k, score_threshold)
            else:
                # Hybrid not available, use vector, pass threshold
                initial_results = await self._vector_search(query, initial_top_k, score_threshold)
        else:
            # Vector-only search, pass threshold
            initial_results = await self._vector_search(query, initial_top_k, score_threshold)
 
        # Phase 12A: Graph Context Expansion (Before Reranking)
        if settings.ENABLE_CODE_GRAPH:
            try:
                # 1. Ensure graph is initialized (lazy load)
                if self._code_graph is None:
                    await self.init_graph()
                
                # 2. Prepare candidates (normalize to dicts)
                anchors = []
                for res in initial_results:
                    if hasattr(res, 'metadata'): 
                        anchors.append({
                            "metadata": res.metadata, 
                            "source": res.metadata.get("source"), 
                            "name": res.metadata.get("name")
                        })
                    else:
                        anchors.append(res)

                # 3. Expand using Strong Anchors
                # This calls your NEW _expand_with_graph_context method
                expanded_candidates = await self._expand_with_graph_context(anchors)
                
                # 4. Merge Candidates into Results for Reranking
                from src.storage.base_store import ChunkResult
                
                # Deduplicate
                seen_ids = {r.id for r in initial_results if hasattr(r, 'id')}
                seen_ids.update({r.get("id") for r in initial_results if isinstance(r, dict)})
                
                for cand in expanded_candidates:
                    cand_id = cand.get("id")
                    if cand_id and cand_id not in seen_ids:
                        # Convert to ChunkResult for Reranker compatibility
                        new_chunk = ChunkResult(
                            id=cand_id,
                            content=cand.get("content"),
                            metadata=cand.get("metadata"),
                            score=0.0 # Neutral score (Constraint C)
                        )
                        initial_results.append(new_chunk)
                        seen_ids.add(cand_id)
                        
            except Exception as e:
                logger.warning(f"Graph expansion failed: {e}")
        
        # If reranking disabled, return vector results
        if not use_reranking or not settings.ENABLE_RERANKING or self.reranker is None:
            result = {
                "documents": initial_results[:top_k],
                "reranked": False,
                "from_cache": False,
                "reason": "reranking_disabled" if not settings.ENABLE_RERANKING else "reranking_not_requested"
            }
            
            # Cache the result (exact-match cache)
            if use_cache and self._query_cache and settings.ENABLE_QUERY_CACHE:
                from src.agents.rag.cache import cache_key_from_query
                await self._query_cache.set(cache_key_from_query(query, top_k), result)
            
            # Phase 12A: Update semantic cache
            if use_cache and self._semantic_cache and settings.ENABLE_SEMANTIC_CACHE:
                try:
                    await self._semantic_cache.set(query, intent, result)
                    logger.debug(f"[PHASE 12A] Cached result for intent={intent}")
                except Exception as e:
                    logger.warning(f"Failed to update semantic cache: {e}")
            
            return result
        
        # Stage 2: Rerank candidates (precision)
        try:
            # Convert to ChunkResult format if needed
            from src.storage.base_store import ChunkResult
            
            # Ensure initial_results are ChunkResult objects
            if initial_results and not isinstance(initial_results[0], ChunkResult):
                # Convert dict format to ChunkResult
                chunk_candidates = [
                    ChunkResult(
                        id=r.get("id", str(i)),
                        content=r.get("content", r.get("page_content", "")),
                        metadata=r.get("metadata", {}),
                        score=r.get("score")
                    )
                    for i, r in enumerate(initial_results)
                ]
            else:
                chunk_candidates = initial_results
            
            # Rerank all candidates
            reranked = await self.reranker.rerank(query, chunk_candidates, top_k=top_k*2)
            
            # Phase 11 Day 3: Apply code-aware boosting
            boosted = self.reranker.apply_code_boost(reranked)
            # Re-sort after boosting
            boosted.sort(key=lambda c: c.rerank_score, reverse=True)
            
            # Apply threshold filter (after boosting)
            filtered = [c for c in boosted if c.rerank_score >= settings.RERANK_SCORE_THRESHOLD]
            
            # MANDATORY FALLBACK: Never return zero results
            if len(filtered) >= 3:
                # Case A: ≥3 pass threshold → return those
                final_results = filtered[:top_k]
                logger.info(f"Reranking: {len(filtered)} passed threshold, returning top {len(final_results)}")
                
                # Phase 13: Deterministic Context Shaping
                shaped_results = self._context_shaper.shape_context(final_results)
                
                result = {
                    "documents": shaped_results,
                    "reranked": True,
                    "threshold_passed": len(filtered),
                    "fallback_used": False,
                    "from_cache": False
                }
            
            elif len(filtered) > 0:
                # Case B: 1-2 pass threshold → blend with vector results
                logger.warning(f"Only {len(filtered)} results passed threshold, blending with vector")
                remaining = top_k - len(filtered)
                fallback = [c for c in chunk_candidates if c not in filtered][:remaining]
                final_results = filtered + fallback
                
                # Phase 13: Deterministic Context Shaping
                shaped_results = self._context_shaper.shape_context(final_results)
                
                result = {
                    "documents": shaped_results,
                    "reranked": True,
                    "threshold_passed": len(filtered),
                    "fallback_used": True,
                    "fallback_count": len(fallback),
                    "from_cache": False
                }
            
            else:
                # Case C: 0 pass threshold → return top vector results (safeguard)
                logger.warning("No results passed rerank threshold, using vector results")
                
                # Phase 13: Deterministic Context Shaping
                final_results = chunk_candidates[:top_k]
                shaped_results = self._context_shaper.shape_context(final_results)
                
                result = {
                    "documents": shaped_results,
                    "reranked": False,
                    "threshold_passed": 0,
                    "fallback_used": True,
                    "reason": "threshold_too_strict",
                    "from_cache": False
                }
            
            # Phase 11.2: Cache the final result (exact-match)
            if use_cache and self._query_cache and settings.ENABLE_QUERY_CACHE:
                from src.agents.rag.cache import cache_key_from_query
                await self._query_cache.set(cache_key_from_query(query, top_k), result)
            
            # Phase 12A: Update semantic cache
            if use_cache and self._semantic_cache and settings.ENABLE_SEMANTIC_CACHE:
                try:
                    await self._semantic_cache.set(query, intent, result)
                    logger.debug(f"[PHASE 12A] Cached reranked result for intent={intent}")
                except Exception as e:
                    logger.warning(f"Failed to update semantic cache: {e}")
            
            return result
        
        except Exception as e:
            logger.error(f"Reranking failed: {e}, falling back to vector results")
            result = {
                "documents": initial_results[:top_k],
                "reranked": False,
                "error": str(e),
                "fallback_used": True,
                "from_cache": False
            }
            
            # Cache even error fallback results
            if use_cache and self._query_cache and settings.ENABLE_QUERY_CACHE:
                from src.agents.rag.cache import cache_key_from_query
                await self._query_cache.set(cache_key_from_query(query, top_k), result)
            
            return result
    
    async def retrieve_with_context(
        self,
        query: str,
        top_k: int = 5,
        use_graph: bool = True,
    ) -> dict:
        """
        Retrieve documents with optional graph-based context expansion.
        
        ARCHITECTURE: Graph expansion is INTERNAL only.
        No API exposure, uses BFS traversal with depth limit.
        
        Args:
            query: Search query
            top_k: Number of initial results
            use_graph: Whether to expand context using code graph
        
        Returns:
            Dictionary with documents and (optionally) expanded context
        """
        # Get initial results using internal method to avoid circular dependency
        retrieval_result = await self.retrieve_with_reranking(
            query=query,
            top_k=top_k,
            score_threshold=settings.RAG_SCORE_THRESHOLD,
            use_reranking=True
        )
        initial_results = retrieval_result.get("documents", [])
        
        if not use_graph or not settings.ENABLE_CODE_GRAPH:
            return {
                "documents": initial_results,
                "expanded": False,
            }
        
        # FIX: Problem 2 - Legacy Safety
        # Normalize to dict before calling expander (prevent legacy crash)
        candidates = []
        for res in initial_results:
            if hasattr(res, 'metadata'): 
                candidates.append({
                    "metadata": res.metadata, 
                    "source": res.metadata.get("source"), 
                    "name": res.metadata.get("name")
                })
            else:
                candidates.append(res)

        # Expand with graph context
        expanded_results = await self._expand_with_graph_context(candidates)
        
        # Merge results (Legacy mode just appends)
        final_docs = initial_results + expanded_results

        return {
            "documents": final_docs,
            "expanded": True,
            "expansion_count": len(expanded_results),
        }
    
    async def _expand_with_graph_context(self, results: List[dict]) -> List[dict]:
        """
        Expand results using code graph (INTERNAL method).
        
        ARCHITECTURE:
        - Uses self.code_graph (instance property)
        - Calls BaseVectorStore abstraction ONLY
        - NEVER accesses vector_store internals
        
        Args:
            results: Initial search results (Strong Anchors)
        
        Returns:
            List of NEW related code chunks found via graph (Nominees)
        """
        expanded = [] # Return only the NEW chunks found via graph
        seen_qids = set()
        
        # Build QIDs from initial results (Anchors)
        for result in results:
            metadata = result.get("metadata", {})
            source = metadata.get("source", "")
            name = metadata.get("name", "")
            
            if source and name:
                qid = f"{source}::{name}"  # CRITICAL: :: separator
                seen_qids.add(qid)
        
        # Find related chunks via graph
        for result in results:
            metadata = result.get("metadata", {})
            source = metadata.get("source", "")
            name = metadata.get("name", "")
            
            if not source or not name:
                continue
            
            qid = f"{source}::{name}"
            
            # Constraint D: Respect Bounds (Depth & Max Chunks)
            related_qids = self.code_graph.get_related(
                qid,
                depth=settings.GRAPH_CONTEXT_DEPTH,
                max_results=settings.GRAPH_MAX_CONTEXT_CHUNKS,
            )
            
            # Fetch related chunks
            for related_qid in related_qids:
                if related_qid in seen_qids:
                    continue
                
                seen_qids.add(related_qid)
                
                # CRITICAL: Fetch actual code using the now-implemented storage method
                related_chunk = await self.vector_store.get_chunk_by_qualified_id(related_qid)
                
                if related_chunk:
                    # Constraint E: Fetch candidate, do not assume importance
                    chunk_dict = {
                        "id": related_chunk.id,
                        "content": related_chunk.content,
                        "metadata": related_chunk.metadata,
                        # Constraint C: Neutral placeholder score. 
                        # The Reranker will assign the real score later.
                        "score": 0.0, 
                        "is_graph_expansion": True
                    }
                    expanded.append(chunk_dict)
                    logger.debug(f"Graph expansion candidate: {related_qid}")

        logger.info(f"Graph expansion: {len(results)} anchors -> found {len(expanded)} new dependency chunks")
        return expanded


# ✅ DEPRECATED: get_shared_rag_agent is removed. Use get_rag_agent(tenant_id).

