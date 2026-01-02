"""RAG agent with LangGraph-based workflow for document ingestion and retrieval.

Phase 3.1: ChromaDB implementation with async document processing.
Supports PDF, Markdown, TXT, and DOCX file formats.
"""

import logging
import time
from typing import List, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from src.core.config import settings
from src.tools.rag.tools import (
    generate_response,
    ingest_documents,
    retrieve_docs,
)
from src.agents.reranker import Reranker

# Initialize reranker globally
try:
    reranker = Reranker()
except Exception as e:
    logger.warning(f"Failed to initialize Reranker: {e}. Reranking will be disabled.")
    reranker = None

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


async def ingest_node(state: RAGState) -> RAGState:
    """Ingest documents into vector store if file_paths provided.

    Args:
        state: RAG state with file_paths

    Returns:
        Updated state with ingestion result (or error)
    """
    file_paths = state.get("file_paths")
    embed_model = state.get("embed_model", settings.RAG_EMBED_MODEL)
    backend = state.get("backend", settings.VECTOR_BACKEND)
    chunk_size = settings.RAG_CHUNK_SIZE
    chunk_overlap = settings.RAG_CHUNK_OVERLAP

    logger.info(
        f"Ingesting {len(file_paths)} documents",
        extra={"file_count": len(file_paths), "embed_model": embed_model, "backend": backend},
    )

    try:
        result = await ingest_documents(
            file_paths=file_paths,
            embed_model=embed_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            backend=backend,
        )

        if not result.get("success"):
            error_msg = result.get("error", "Document ingestion failed")
            logger.warning(f"Ingestion completed with errors: {error_msg}")
            return {
                **state,
                "error": error_msg,
            }

        logger.info(
            f"Ingestion successful: {result['documents_processed']} documents, {result['chunks_created']} chunks",
            extra={
                "documents_processed": result["documents_processed"],
                "chunks_created": result["chunks_created"],
            },
        )

        return {
            **state,
            "error": None,  # Clear any previous errors
        }

    except Exception as e:
        logger.error(
            f"Ingest node failed: {e}",
            extra={"error": str(e), "file_count": len(file_paths) if file_paths else 0},
            exc_info=True,
        )
        return {
            **state,
            "error": f"Ingestion failed: {str(e)}",
        }


async def retrieve_node(state: RAGState) -> RAGState:
    """Retrieve relevant documents via semantic search.

    Args:
        state: RAG state with query

    Returns:
        Updated state with documents and context
    """
    query = state.get("query", "")
    top_k = state.get("top_k", settings.RAG_TOP_K)
    embed_model = state.get("embed_model", settings.RAG_EMBED_MODEL)
    backend = state.get("backend", settings.VECTOR_BACKEND)
    score_threshold = state.get("score_threshold", settings.RAG_SCORE_THRESHOLD)

    logger.info(
        f"Retrieving documents: query='{str(query)[:50]}...', top_k={top_k}",
        extra={"query_preview": str(query)[:50], "top_k": top_k},
    )

    try:
        # PHASE 12A: Use shared RAGAgent instance for persistent analytics
        agent = get_shared_rag_agent()
        
        retrieval_result = await agent.retrieve_with_reranking(
            query=query,
            top_k=top_k,
            use_reranking=True,
            use_cache=True,
            use_hybrid=False  # Hybrid requires init_bm25() first
        )
        
        # Extract documents from the result
        documents = retrieval_result.get("documents", [])
        
        # Convert ChunkResult objects to dict format if needed
        formatted_documents = []
        for doc in documents:
            if hasattr(doc, 'content'):
                # ChunkResult object
                formatted_documents.append({
                    "id": doc.id,
                    "content": doc.content,
                    "metadata": doc.metadata,
                    "score": getattr(doc, 'rerank_score', getattr(doc, 'score', 0.0))
                })
            else:
                # Already a dict
                formatted_documents.append(doc)

        if not formatted_documents:
            logger.warning("No documents retrieved (empty result or below threshold)")
            return {
                **state,
                "documents": [],
                "context": "",
                "error": None,
            }

        # Concatenate document content into context
        context = "\n\n".join([f"[{i+1}] {doc['content']}" for i, doc in enumerate(formatted_documents)])

        logger.info(
            f"Retrieved {len(formatted_documents)} documents ({len(context)} characters)",
            extra={"documents_count": len(formatted_documents), "context_length": len(context)},
        )

        return {
            **state,
            "documents": formatted_documents,
            "context": context,
            "error": None,
        }

    except Exception as e:
        logger.error(
            f"Retrieve node failed: {e}",
            extra={"error": str(e), "query_preview": str(query)[:50]},
            exc_info=True,
        )
        return {
            **state,
            "error": f"Retrieval failed: {str(e)}",
            "documents": None,
            "context": None,
        }


async def generate_node(state: RAGState) -> RAGState:
    """Generate LLM response based on retrieved context.

    Args:
        state: RAG state with query and context

    Returns:
        Updated state with generated response
    """
    query = state.get("query", "")
    context = state.get("context", "")

    logger.info(
        f"Generating response: query='{str(query)[:50]}...', context_length={len(context)}",
        extra={"query_preview": str(query)[:50], "context_length": len(context)},
    )

    try:
        if not context or context.strip() == "":
            logger.warning("Empty context, generating fallback response")
            return {
                **state,
                "response": "I don't have enough information to answer that question. No relevant documents were found.",
                "error": None,
            }

        response = await generate_response(query=query, context=context)

        logger.info(
            f"Response generated successfully ({len(response)} characters)",
            extra={"response_length": len(response)},
        )

        return {
            **state,
            "response": response,
            "error": None,
        }

    except Exception as e:
        logger.error(
            f"Generate node failed: {e}",
            extra={"error": str(e), "query_preview": str(query)[:50]},
            exc_info=True,
        )
        return {
            **state,
            "error": f"Response generation failed: {str(e)}",
            "response": None,
        }


async def error_node(state: RAGState) -> RAGState:
    """Handle errors and format error message.

    Args:
        state: RAG state with error

    Returns:
        Updated state with formatted error response
    """
    error = state.get("error", "Unknown error occurred")
    logger.error(f"RAG agent error: {error}", extra={"error": error})

    return {
        **state,
        "response": f"Error: {error}",
    }


def should_ingest(state: RAGState) -> Literal["ingest", "retrieve"]:
    """Determine if ingestion step should run.

    Args:
        state: RAG state

    Returns:
        "ingest" if file_paths provided, "retrieve" otherwise
    """
    file_paths = state.get("file_paths")
    if file_paths and len(file_paths) > 0:
        return "ingest"
    return "retrieve"


def check_error(state: RAGState) -> Literal["error_node", "continue"]:
    """Check if error occurred and route accordingly.

    Args:
        state: RAG state

    Returns:
        "error_node" if error exists, "continue" otherwise
    """
    error = state.get("error")
    if error:
        return "error_node"
    return "continue"


def create_rag_graph():
    """Create and compile the RAG workflow graph.

    Returns:
        Compiled LangGraph workflow
    """
    workflow = StateGraph(RAGState)

    # Add nodes
    workflow.add_node("ingest", ingest_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("error", error_node)

    # Set entry point with conditional routing
    workflow.set_conditional_entry_point(
        should_ingest,
        {
            "ingest": "ingest",
            "retrieve": "retrieve",
        },
    )

    # After ingestion, check for errors then route to retrieve
    workflow.add_conditional_edges(
        "ingest",
        check_error,
        {
            "error_node": "error",
            "continue": "retrieve",
        },
    )

    # After retrieval, check for errors then route to generate
    workflow.add_conditional_edges(
        "retrieve",
        check_error,
        {
            "error_node": "error",
            "continue": "generate",
        },
    )

    # After generation, check for errors then end
    workflow.add_conditional_edges(
        "generate",
        check_error,
        {
            "error_node": "error",
            "continue": END,
        },
    )

    # Error node leads to END
    workflow.add_edge("error", END)

    # Compile graph
    compiled_graph = workflow.compile()

    logger.info("RAG graph compiled successfully")
    return compiled_graph


# Export compiled RAG agent
rag_agent = create_rag_graph()


async def rag_agent_invoke(
    query: str,
    file_paths: Optional[List[str]] = None,
    top_k: Optional[int] = None,
    embed_model: Optional[str] = None,
    backend: Optional[str] = None,
    score_threshold: Optional[float] = None,
) -> dict:
    """Convenience function to invoke RAG agent with a query.

    Args:
        query: User search query
        file_paths: Optional list of file paths to ingest first
        top_k: Optional number of results (default: from settings)
        embed_model: Optional embedding model (default: from settings)
        backend: Optional vector backend (default: from settings)
        score_threshold: Optional similarity threshold (default: from settings)

    Returns:
        Dictionary matching GatewayResponse format:
            - success (bool)
            - tool (str): "retrieve_docs"
            - data (dict): {"response", "documents", "backend"}
            - execution_time (float)
            - error (str | None)
    """
    start_time = time.time()

    # Use defaults from settings if not provided
    initial_state: RAGState = {
        "query": query,
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

    logger.info(f"RAG agent invoked: query='{str(query)[:100]}...', file_paths={file_paths}")

    try:
        final_state = await rag_agent.ainvoke(initial_state)

        execution_time = time.time() - start_time

        # Check for errors
        error = final_state.get("error")
        success = error is None and final_state.get("response") is not None

        # Build response data
        response_data = {
            "response": final_state.get("response", ""),
            "documents": final_state.get("documents", []),
            "backend": final_state.get("backend", settings.VECTOR_BACKEND),
        }

        result = {
            "success": success,
            "tool": "retrieve_docs",
            "data": response_data,
            "execution_time": round(execution_time, 4),
            "error": error,
        }

        logger.info(
            f"RAG agent completed: success={success}, execution_time={execution_time:.2f}s",
            extra={
                "success": success,
                "execution_time": execution_time,
                "documents_count": len(response_data.get("documents", [])),
            },
        )

        return result

    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(
            f"RAG agent invocation failed: {e}",
            extra={"error": str(e), "execution_time": execution_time},
            exc_info=True,
        )
        return {
            "success": False,
            "tool": "retrieve_docs",
            "data": {
                "response": "",
                "documents": [],
                "backend": settings.VECTOR_BACKEND,
            },
            "execution_time": round(execution_time, 4),
            "error": f"RAG agent execution failed: {str(e)}",
        }


# Phase 10.1: RAGAgent class for Celery task compatibility
class RAGAgent:
    """RAG Agent class for async task queue integration.
    
    ARCHITECTURE (see docs/rag_architecture.md):
    - Each instance has its own graph (self._code_graph)
    - Graph is derived state, rebuilt from chunk metadata
    - NO global graph, NO persistence
    """
    
    def __init__(self, collection_name: str = "devforge_docs"):
        """Initialize RAG agent with collection scope.
        
        Args:
            collection_name: Target collection for documents
        """
        self.collection_name = collection_name
        self.embed_model = settings.RAG_EMBED_MODEL
        self.backend = settings.VECTOR_BACKEND
        
        # ARCHITECTURE: Use BaseVectorStore abstraction
        from src.storage.chroma_store import ChromaVectorStore
        self.vector_store = ChromaVectorStore(
            collection_name=collection_name,
            embed_model=self.embed_model
        )
        
        self._code_graph = None  # Instance-scoped, NOT global
        self._reranker = None  # Phase 11: Reranker (lazy load)
        self._query_cache = None  # Phase 11.2: Query cache
        self._bm25_index = None  # Phase 11.2 Day 3: BM25 index
        self._hybrid_retriever = None  # Phase 11.2 Day 3: Hybrid retriever
        
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
        Initialize code graph from vector store metadata.
        
        ARCHITECTURE (Phase 11.1 Fix):
        - Proper async pattern (no blocking in property)
        - Call once at agent startup
        - Rebuilds from iter_chunk_metadata()
        
        Usage:
            agent = RAGAgent()
            await agent.init_graph()  # Explicit async init
            graph = agent.code_graph  # Now safe
        """
        if self._code_graph is not None:
            logger.info("Code graph already initialized")
            return
        
        from src.agents.rag.graph import CodeGraph
        
        self._code_graph = CodeGraph()
        
        # Proper async rebuild from vector store metadata
        count = 0
        try:
            async for batch in self.vector_store.iter_chunk_metadata(batch_size=500):
                # Convert metadata list to chunk format
                chunks = [{"metadata": meta} for meta in batch]
                self._code_graph.add_chunks_batch(chunks)
                count += len(batch)
            
            logger.info(f"Graph initialized: {count} chunks → {self._code_graph.size()} nodes")
        except Exception as e:
            logger.warning(f"Graph rebuild failed: {e}, using empty graph")
            # Fallback: empty graph (graph expansion disabled)
            self._code_graph = CodeGraph()
    
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
        embed_model: Optional[str] = None,
    ) -> dict:
        """Ingest a single document into the vector store.
        
        This method is called by Celery tasks (NOT tools).
        
        Args:
            file_path: Path to document to ingest
            embed_model: Optional embedding model override
        
        Returns:
            Dictionary with ingestion result
        """
        from src.tools.rag.tools import ingest_documents as _ingest_documents
        
        result = await _ingest_documents(
            file_paths=[file_path],
            embed_model=embed_model or self.embed_model,
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
            backend=self.backend,
        )
        
        logger.info(
            f"Document ingested: {file_path}",
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
        from src.tools.rag.tools import retrieve_docs as _retrieve_docs
        
        return await _retrieve_docs(
            query=query,
            top_k=top_k,
            embed_model=self.embed_model,
            backend=self.backend,
            score_threshold=settings.RAG_SCORE_THRESHOLD,
        )
    
    async def _vector_search(self, query: str, top_k: int) -> List:
        """
        Vector-only search (helper for fallback).
        
        Args:
            query: Search query
            top_k: Number of results
        
        Returns:
            List of search results
        """
        from src.tools.rag.tools import retrieve_docs as _retrieve_docs
        
        return await _retrieve_docs(
            query=query,
            top_k=top_k,
            embed_model=self.embed_model,
            backend=self.backend,
            score_threshold=settings.RAG_SCORE_THRESHOLD,
        )
    
    async def retrieve_with_reranking(
        self,
        query: str,
        top_k: int = 5,
        use_reranking: bool = True,
        use_cache: bool = True,  # Phase 11.2 Day 1
        use_hybrid: bool = True  # Phase 11.2 Day 3
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
                # Use vector search for each expanded query
                eq_results = await self._vector_search(eq, initial_top_k)
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
                    # Graceful fallback to vector search
                    initial_results = await self._vector_search(query, initial_top_k)
            else:
                # Hybrid not available, use vector
                initial_results = await self._vector_search(query, initial_top_k)
        else:
            # Vector-only search
            initial_results = await self._vector_search(query, initial_top_k)
        
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
                result = {
                    "documents": final_results,
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
                result = {
                    "documents": final_results,
                    "reranked": True,
                    "threshold_passed": len(filtered),
                    "fallback_used": True,
                    "fallback_count": len(fallback),
                    "from_cache": False
                }
            
            else:
                # Case C: 0 pass threshold → return top vector results (safeguard)
                logger.warning("No results passed rerank threshold, using vector results")
                result = {
                    "documents": chunk_candidates[:top_k],
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
        from src.tools.rag.tools import retrieve_docs as _retrieve_docs
        
        # Get initial results
        initial_results = await _retrieve_docs(
            query=query,
            top_k=top_k,
            embed_model=self.embed_model,
            backend=self.backend,
            score_threshold=settings.RAG_SCORE_THRESHOLD,
        )
        
        if not use_graph or not settings.ENABLE_CODE_GRAPH:
            return {
                "documents": initial_results,
                "expanded": False,
            }
        
        # Expand with graph context
        expanded_results = await self._expand_with_graph_context(initial_results)
        
        return {
            "documents": expanded_results,
            "expanded": True,
            "expansion_count": len(expanded_results) - len(initial_results),
        }
    
    async def _expand_with_graph_context(self, results: List[dict]) -> List[dict]:
        """
        Expand results using code graph (INTERNAL method).
        
        ARCHITECTURE:
        - Uses self.code_graph (instance property)
        - Calls BaseVectorStore abstraction ONLY
        - NEVER accesses vector_store internals
        
        Args:
            results: Initial search results
        
        Returns:
            Extended list with related code chunks
        """
        expanded = list(results)
        seen_qids = set()
        
        # Build QIDs from initial results
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
            
            # Get related QIDs via BFS
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
                
                # CRITICAL: Use abstraction, NOT backend internals
                # For now, we need to add get_chunk_by_qid to BaseVectorStore
                # Placeholder: Log that we would fetch this chunk
                logger.debug(f"Would fetch related chunk: {related_qid}")
                
                # TODO: Implement get_chunk_by_qualified_id in BaseVectorStore
                # related_chunk = await self.vector_store.get_chunk_by_qualified_id(related_qid)
                # if related_chunk:
                #     expanded.append(related_chunk)
        
        logger.info(f"Graph expansion: {len(results)} → {len(expanded)} chunks")
        return expanded


# ========================================
# PHASE 12A: Shared Global RAGAgent Instance
# ========================================
# This single instance persists across all API requests,
# allowing analytics counters to accumulate properly
_shared_rag_agent: Optional[RAGAgent] = None


def get_shared_rag_agent() -> RAGAgent:
    """
    Get or create the shared RAGAgent instance.
    
    Returns:
        Shared RAGAgent instance with persistent analytics
    """
    global _shared_rag_agent
    if _shared_rag_agent is None:
        _shared_rag_agent = RAGAgent(collection_name=settings.CHROMA_COLLECTION)
        logger.info("[PHASE 12A] Created shared RAGAgent instance for analytics persistence")
    return _shared_rag_agent
