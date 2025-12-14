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
        f"Retrieving documents: query='{query[:50]}...', top_k={top_k}",
        extra={"query_preview": query[:50], "top_k": top_k},
    )

    try:
        documents = await retrieve_docs(
            query=query,
            top_k=top_k,
            embed_model=embed_model,
            backend=backend,
            score_threshold=score_threshold,
        )

        if not documents:
            logger.warning("No documents retrieved (empty result or below threshold)")
            return {
                **state,
                "documents": [],
                "context": "",
                "error": None,
            }

        # Rerank documents if reranker is available
        if reranker:
            try:
                # Rerank and take top_k (retrieval might return more, or we refine the order)
                # Note: retrieve_docs already limits to top_k, but we might want to retrieve more then rerank?
                # For now, we just re-order the retrieved docs.
                documents = await reranker.rerank(
                    query=query,
                    documents=documents,
                    top_k=top_k,
                    key=lambda x: x.get("content", "")
                )
                logger.info("Documents reranked successfully")
            except Exception as e:
                logger.error(f"Reranking failed, using original order: {e}")

        # Concatenate document content into context
        context = "\n\n".join([f"[{i+1}] {doc['content']}" for i, doc in enumerate(documents)])

        logger.info(
            f"Retrieved {len(documents)} documents ({len(context)} characters)",
            extra={"documents_count": len(documents), "context_length": len(context)},
        )

        return {
            **state,
            "documents": documents,
            "context": context,
            "error": None,
        }

    except Exception as e:
        logger.error(
            f"Retrieve node failed: {e}",
            extra={"error": str(e), "query_preview": query[:50]},
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
        f"Generating response: query='{query[:50]}...', context_length={len(context)}",
        extra={"query_preview": query[:50], "context_length": len(context)},
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
            extra={"error": str(e), "query_preview": query[:50]},
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

    logger.info(f"RAG agent invoked: query='{query[:100]}...', file_paths={file_paths}")

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
        
        logger.info(f"RAGAgent initialized: collection={collection_name}")
    
    @property
    def code_graph(self):
        """
        Lazy-initialized code graph.
        
        ARCHITECTURE: Derived state, rebuilt from chunk metadata.
        No persistence, instance-scoped only.
        """
        if self._code_graph is None:
            from src.agents.rag.graph import CodeGraph
            
            self._code_graph = CodeGraph()
            
            # ARCHITECTURE COMPLIANCE: Rebuild from vector store metadata
            # Uses BaseVectorStore.iter_chunk_metadata() abstraction
            import asyncio
            
            async def rebuild():
                """Rebuild graph from existing chunks."""
                count = 0
                try:
                    async for batch in self.vector_store.iter_chunk_metadata(batch_size=500):
                        # Convert metadata list to chunk format expected by graph
                        chunks = [{"metadata": meta} for meta in batch]
                        self._code_graph.add_chunks_batch(chunks)
                        count += len(batch)
                    
                    logger.info(f"Graph rebuilt: {count} chunks → {self._code_graph.size()} nodes")
                except Exception as e:
                    logger.warning(f"Graph rebuild failed: {e}")
            
            # Run rebuild asynchronously (non-blocking)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # In async context, schedule task
                    asyncio.create_task(rebuild())
                else:
                    # In sync context, run to completion
                    loop.run_until_complete(rebuild())
            except RuntimeError:
                # No event loop, create one
                asyncio.run(rebuild())
            
            logger.info("CodeGraph initialized (rebuilding from vector store)")
        
        return self._code_graph
    
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

