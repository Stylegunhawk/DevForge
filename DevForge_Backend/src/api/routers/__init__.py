"""API routers for MCP endpoints (gateway and manifest).

Handles tool discovery via manifest and tool execution via gateway.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.schemas import GatewayRequest, GatewayResponse
from src.core.utils import track_performance

# Import agents
from src.agents.datagen.agent import datagen_agent
from src.agents.rag.agent import rag_agent_invoke
from src.agents.github.agent import github_agent_invoke
from src.agents.reranker import rerank_docs_invoke
from src.agents.prompt_refiner.agent import refine_prompt_invoke
from src.agents.cheatsheet.agent import generate_cheatsheet_invoke



# Import Phase 2 specialized tools
from src.tools.changelog import generate_changelog_invoke
from src.tools.ci_diagnostics import analyze_ci_failure_invoke
from src.tools.scaffold import scaffold_repository_invoke

# Import RAG models for type hints
from src.api.rag_models import IngestAsyncRequest, IngestAsyncResponse, TaskStatusResponse

# Import job queue for async operations
from src.core.jobs import get_job_queue

router = APIRouter()
mcp_router = APIRouter()

# Map tool names to agent invoke functions
SUPPORTED_TOOLS = {
    "generate_data": datagen_agent,
    "retrieve_docs": rag_agent_invoke,
    "github_operation": github_agent_invoke,
    "rerank_docs": rerank_docs_invoke,
    "refine_prompt": refine_prompt_invoke,
    "generate_cheatsheet": generate_cheatsheet_invoke,
    # Phase 2: Specialized GitHub Tools
    "generate_changelog": generate_changelog_invoke,
    "analyze_ci_failure": analyze_ci_failure_invoke,
    "scaffold_repository": scaffold_repository_invoke,
}


# Job status endpoint for async operations
@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get status of async job
    
    Returns:
        Job status including progress, result, and ETA
    """
    job_queue = get_job_queue()
    job = await job_queue.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JSONResponse(content=job.to_dict())


# Phase 10.1: Async RAG Endpoints
# ARCHITECTURE COMPLIANCE (see docs/rag_architecture.md):
# ✅ NO /rag/graph/context endpoint (forbidden)
# ✅ Delegates to RAGAgent via Celery tasks

@router.post("/rag/ingest-async")
async def ingest_documents_async(request: IngestAsyncRequest) -> IngestAsyncResponse:
    """
    Queue documents for async ingestion via Celery.
    
    ARCHITECTURE: Calls async_ingest_documents Celery task → RAGAgent.
    
    Args:
        request: IngestAsyncRequest with file_paths and collection_name
    
    Returns:
        IngestAsyncResponse with task_id for tracking
    """
    from src.workers.tasks.rag_tasks import async_ingest_documents
    
    logging.info(
        f"Queueing async ingestion: {len(request.file_paths)} files",
        extra={"collection": request.collection_name, "files": len(request.file_paths)}
    )
    
    # Queue Celery task
    task = async_ingest_documents.delay(
        file_paths=request.file_paths,
        collection_name=request.collection_name,
        embed_model=request.embed_model,
    )
    
    logging.info(f"Task queued: {task.id}")
    
    return IngestAsyncResponse(
        task_id=task.id,
        status="queued",
        collection=request.collection_name,
        total_files=len(request.file_paths),
    )


@router.get("/rag/task/{task_id}")
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    Get status of async RAG ingestion task.
    
    Args:
        task_id: Celery task ID
    
    Returns:
        TaskStatusResponse with current status and progress
    """
    from src.workers.celery_app import app
    
    # Get task result from Celery backend
    result = app.AsyncResult(task_id)
    
    # Build response based on task state
    response_data = {
        "task_id": task_id,
        "status": result.status,  # PENDING, PROGRESS, SUCCESS, FAILURE
    }
    
    if result.status == "PROGRESS":
        # Progress metadata from task.update_state()
        response_data["progress"] = result.info
    elif result.status == "SUCCESS":
        response_data["result"] = result.result
    elif result.status == "FAILURE":
        response_data["error"] = str(result.info)
    
    logging.info(f"Task status: {task_id} → {result.status}")
    
    return TaskStatusResponse(**response_data)


# ============================================================
# Phase 11.2 Day 4: Observability Endpoints
# ============================================================

@router.get("/rag/metrics", tags=["rag", "observability"])
async def get_rag_metrics():
    """
    Get RAG system metrics (Prometheus-compatible).
    
    CRITICAL: This endpoint MUST NEVER throw exceptions.
    Missing components return default values (0.0, false, null).
    
    Returns:
        Metrics dictionary with version, cache, hybrid_search, reranking, code_graph
    """
    try:
        from src.agents.rag.agent import RAGAgent
        from src.core.config import settings
        
        # Get or create RAG agent instance
        try:
            agent = RAGAgent()
        except Exception as e:
            logger.error(f"Failed to get RAGAgent for metrics: {e}")
            return {
                "version": "11.2.0",
                "error": "agent_unavailable",
                "cache": {"enabled": False},
                "hybrid_search": {"enabled": False},
                "reranking": {"enabled": False},
                "code_graph": {"enabled": False}
            }
        
        # Build metrics with safe defaults
        metrics = {"version": "11.2.0"}
        
        # Cache metrics
        try:
            if agent._query_cache:
                stats = agent._query_cache.get_stats()
                metrics["cache"] = {
                    "enabled": settings.ENABLE_QUERY_CACHE,
                    "hit_rate": stats.get("hit_rate", 0.0),
                    "hits": stats.get("hits", 0),
                    "misses": stats.get("misses", 0),
                    "memory_size": stats.get("memory_size", 0),
                    "backend": stats.get("backend", "unknown")
                }
            else:
                metrics["cache"] = {
                    "enabled": settings.ENABLE_QUERY_CACHE,
                    "hit_rate": 0.0,
                    "backend": "disabled"
                }
        except Exception as e:
            logging.warning(f"Cache metrics error: {e}")
            metrics["cache"] = {"enabled": False, "error": str(e)}
        
        # Hybrid search metrics
        try:
            if agent._bm25_index:
                bm25_stats = agent._bm25_index.get_stats()
                metrics["hybrid_search"] = {
                    "enabled": settings.ENABLE_HYBRID_SEARCH,
                    "bm25_ready": bm25_stats.get("ready", False),
                    "documents_indexed": bm25_stats.get("documents_indexed", 0)
                }
            else:
                metrics["hybrid_search"] = {
                    "enabled": settings.ENABLE_HYBRID_SEARCH,
                    "bm25_ready": False,
                    "documents_indexed": 0
                }
        except Exception as e:
            logging.warning(f"Hybrid search metrics error: {e}")
            metrics["hybrid_search"] = {"enabled": False, "error": str(e)}
        
        # Reranking metrics
        try:
            metrics["reranking"] = {
                "enabled": settings.ENABLE_RERANKING,
                "model": settings.RERANK_MODEL if settings.ENABLE_RERANKING else None,
                "threshold": settings.RERANK_SCORE_THRESHOLD if settings.ENABLE_RERANKING else None
            }
        except Exception as e:
            logging.warning(f"Reranking metrics error: {e}")
            metrics["reranking"] = {"enabled": False, "error": str(e)}
        
        # Code graph metrics
        try:
            if agent._code_graph:
                metrics["code_graph"] = {
                    "enabled": True,
                    "nodes": agent._code_graph.size()
                }
            else:
                metrics["code_graph"] = {"enabled": False, "nodes": 0}
        except Exception as e:
            logging.warning(f"Code graph metrics error: {e}")
            metrics["code_graph"] = {"enabled": False, "error": str(e)}
        
        return metrics
    
    except Exception as e:
        # Top-level safety: NEVER throw
        logging.error(f"Critical error in /rag/metrics: {e}")
        return {
            "version": "11.2.0",
            "error": "metrics_unavailable",
            "message": str(e)
        }


@router.get("/rag/health", tags=["rag", "observability"])
async def rag_health_check():
    """
    RAG system health check.
    
    Returns:
        200 with status "healthy" if all critical components OK
        200 with status "degraded" if some components down
        503 with status "unhealthy" if critical failure
    """
    try:
        from src.agents.rag.agent import RAGAgent
        from src.core.config import settings
        
        try:
            agent = RAGAgent()
        except Exception as e:
            logging.error(f"Failed to get RAGAgent for health check: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "error": "agent_init_failed",
                    "components": {}
                }
            )
        
        components = {}
        
        # Vector store health (CRITICAL)
        try:
            vector_ok = await agent.vector_store.health_check()
            components["vector_store"] = "ok" if vector_ok else "down"
        except Exception as e:
            logging.error(f"Vector store health check failed: {e}")
            components["vector_store"] = "error"
            vector_ok = False
        
        # Optional components
        try:
            if settings.ENABLE_RERANKING:
                reranker_ok = agent._reranker is not None
                components["reranker"] = "ok" if reranker_ok else "not_loaded"
            else:
                components["reranker"] = "disabled"
                reranker_ok = True
        except Exception:
            components["reranker"] = "error"
            reranker_ok = True
        
        try:
            if settings.ENABLE_HYBRID_SEARCH:
                bm25_ok = agent._bm25_index and agent._bm25_index.is_ready()
                components["bm25_index"] = "ok" if bm25_ok else "not_ready"
            else:
                components["bm25_index"] = "disabled"
        except Exception:
            components["bm25_index"] = "error"
        
        # Determine status
        if vector_ok:
            status = "healthy"
            code = 200
        else:
            status = "unhealthy"
            code = 503
        
        return JSONResponse(
            status_code=code,
            content={
                "status": status,
                "version": "11.2.0",
                "components": components
            }
        )
    
    except Exception as e:
        logging.error(f"Critical error in /rag/health: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": "health_check_failed",
                "message": str(e)
            }
        )


@router.post("/rag/cache/clear", tags=["rag", "admin"])
async def clear_query_cache():
    """
    Clear RAG query cache (admin endpoint).
    
    WARNING: Add authentication in production.
    """
    try:
        from src.agents.rag.agent import RAGAgent
        
        agent = RAGAgent()
        
        if agent._query_cache:
            await agent._query_cache.clear()
            stats = agent._query_cache.get_stats()
            return {
                "status": "cleared",
                "message": "Query cache cleared successfully",
                "stats": stats
            }
        else:
            return {
                "status": "disabled",
                "message": "Query cache is not enabled"
            }
    
    except Exception as e:
        logging.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/bm25/rebuild", tags=["rag", "admin"])
async def rebuild_bm25_index():
    """
    Rebuild BM25 index (admin endpoint).
    
    Use after large ingestion batches.
    WARNING: Add authentication in production.
    """
    try:
        from src.agents.rag.agent import RAGAgent
        from src.core.config import settings
        
        if not settings.ENABLE_HYBRID_SEARCH:
            return {
                "status": "disabled",
                "message": "Hybrid search is not enabled"
            }
        
        agent = RAGAgent()
        
        if agent._bm25_index:
            await agent._bm25_index.rebuild(agent.vector_store)
            stats = agent._bm25_index.get_stats()
            
            return {
                "status": "rebuilt",
                "message": "BM25 index rebuilt successfully",
                "stats": stats
            }
        else:
            raise HTTPException(status_code=400, detail="BM25 index is not initialized")
    
    except Exception as e:
        logging.error(f"Failed to rebuild BM25 index: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Phase 12A Day 1: Intent Classification Analytics
# ============================================================

@router.get("/rag/analytics/fallback-usage", tags=["rag", "analytics"])
async def get_fallback_usage():
    """
    Get intent classification fallback usage statistics.
    
    Helps determine when to enable LLM features.
    
    Returns:
        Fallback method breakdown and recommendations
    """
    try:
        from src.agents.rag.agent import RAGAgent
        
        agent = RAGAgent()
        
        if not hasattr(agent, '_intent_classifier') or not agent._intent_classifier:
            return {
                "enabled": False,
                "message": "Intent classification not initialized"
            }
        
        stats = agent._intent_classifier.get_stats()
        
        return {
            "enabled": True,
            **stats
        }
    
    except Exception as e:
        logging.error(f"Failed to get fallback usage: {e}")
        return {
            "enabled": False,
            "error": str(e)
        }


@router.get("/rag/analytics/expansion-quality", tags=["rag", "analytics"])
async def get_expansion_quality():
    """Get query expansion quality metrics."""
    try:
        from src.agents.rag.agent import get_rag_agent
        agent = get_rag_agent()
        
        if not hasattr(agent, '_query_expander') or not agent._query_expander:
            return {"enabled": False, "message": "Query expansion not initialized"}
        
        stats = agent._query_expander.get_stats()
        return {"enabled": True, **stats}
    except Exception as e:
        logging.error(f"Failed to get expansion quality: {e}")
        return {"enabled": False, "error": str(e)}


@router.get("/rag/analytics/intent-distribution", tags=["rag", "analytics"])
async def get_intent_distribution():
    """Get intent classification distribution."""
    try:
        from src.agents.rag.agent import get_rag_agent
        agent = get_rag_agent()
        
        if not hasattr(agent, '_intent_classifier') or not agent._intent_classifier:
            return {"enabled": False, "message": "Intent classification not initialized"}
        
        stats = agent._intent_classifier.get_stats()
        return {
            "enabled": True,
            "intent_distribution": stats.get("intent_distribution", {}),
            "method_breakdown": stats.get("method_breakdown", {}),
            "total_classifications": stats.get("total", 0)
        }
    except Exception as e:
        logging.error(f"Failed to get intent distribution: {e}")
        return {"enabled": False, "error": str(e)}


@router.get("/rag/analytics/cache-by-intent", tags=["rag", "analytics"])
async def get_cache_by_intent():
    """Get semantic cache effectiveness by intent."""
    try:
        from src.agents.rag.agent import get_rag_agent
        agent = get_rag_agent()
        
        if not hasattr(agent, '_semantic_cache') or not agent._semantic_cache:
            return {"enabled": False, "message": "Semantic cache not initialized"}
        
        stats = agent._semantic_cache.get_stats()
        return {"enabled": True, **stats}
    except Exception as e:
        logging.error(f"Failed to get cache by intent: {e}")
        return {"enabled": False, "error": str(e)}



@router.get("/manifests/devforge.json")
async def get_manifest():
    """
    Serve the LobeHub plugin manifest.

    This endpoint MUST return a LobeHub-compliant schema.
    It must never silently fall back to a different manifest format.
    """
    manifest_path = settings.MANIFEST_DIR / "devforge.json"

    if not manifest_path.exists():
        logging.critical(f"Manifest file missing: {manifest_path}")
        raise HTTPException(
            status_code=500,
            detail="Plugin manifest not found on server"
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logging.critical(f"Invalid manifest JSON: {e}")
        raise HTTPException(
            status_code=500,
            detail="Plugin manifest is invalid JSON"
        )

    # Optional: validate expected LobeHub keys
    required_keys = {"identifier", "meta", "api"}
    missing = required_keys - manifest.keys()
    if missing:
        logging.critical(f"Manifest missing keys: {missing}")
        raise HTTPException(
            status_code=500,
            detail=f"Manifest missing required fields: {missing}"
        )

    logging.info(
        "LobeHub manifest served",
        extra={
            "identifier": manifest["identifier"],
            "api_count": len(manifest["api"]),
        }
    )

    return JSONResponse(
        content=manifest,
        headers={"Content-Type": "application/json"},
    )


def _generate_default_manifest() -> dict:
    """Generate default manifest structure if static file is missing."""
    return {
        "name": "devforge",
        "version": "0.1.0",
        "description": "DevForge AI-powered developer tools",
        "schema_version": "v1",
        "gateway": settings.gateway_url,
        "tools": [
            {
                "name": "generate_data",
                "description": "Generate realistic mock CSV/JSON data using Faker and Pandas. Supports custom fields and formats.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rows": {
                            "type": "integer",
                            "description": "Number of rows to generate",
                            "default": 100,
                            "minimum": 1,
                            "maximum": 10000,
                        },
                        "format": {
                            "type": "string",
                            "description": "Output format",
                            "enum": ["csv", "json"],
                            "default": "json",
                        },
                        "fields": {
                            "type": "array",
                            "description": "Custom fields to generate (e.g., ['name', 'email', 'phone']). If omitted, generates common fields.",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["rows"],
                },
            }
        ]
    }


@router.post("/gateway")
async def gateway_endpoint(request: GatewayRequest):
    """Universal gateway for all tools - simplified and cleaner"""
    tool_name = request.get_tool_name()
    args = request.arguments or {}
    start_time = time.time()

    if tool_name not in SUPPORTED_TOOLS:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "data": None,
                "message": f"Tool '{tool_name}' not found. Available tools: {list(SUPPORTED_TOOLS.keys())}",
            },
        )

    agent_func = SUPPORTED_TOOLS[tool_name]

    try:
        # ------------------------------------------------------------------- #
        # Special handling for github_operation (v0.8 with context support)
        # ------------------------------------------------------------------- #
        if tool_name == "github_operation":
            query = args.get("query")
            if not query:
                error_msg = "github_operation requires 'query' parameter"
                logging.error(error_msg, extra={"tool": tool_name, "args": args})
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "data": None,
                        "message": error_msg,
                    },
                )
            
            # v0.8: Support optional context parameter
            context = args.get("context", {})
            
            logging.info(f"Calling {tool_name} with query: {query[:100]}...")
            result = await agent_func(query=query, context=context)
        else:
            logging.info(f"Calling {tool_name} with args: {args}")
            result = await agent_func(args)          # ← dict, no extra parsing

        exec_time = time.time() - start_time

        # Extract data from result - handle different result structures
        result_data = result.get("data")
        if result_data is None:
            # If no 'data' key, use the entire result (minus metadata)
            result_data = {k: v for k, v in result.items() if k not in ["success", "tool", "format", "error", "execution_time"]}
            if not result_data:
                result_data = result  # Fallback to full result

        # Check if operation was successful
        success = result.get("success", True)  # Default to True if not specified
        error = result.get("error")

        if error:
            success = False
            message = f"{tool_name} execution failed: {error}"
            logging.error(message, extra={"tool": tool_name, "error": error, "execution_time": exec_time})
        else:
            message = f"{tool_name} executed successfully"

        logging.info(
            f"Tool {tool_name} executed successfully",
            extra={"tool": tool_name, "success": success, "execution_time": exec_time},
        )

        # Return standardized response format
        return JSONResponse(
            content={
                "success": success,
                "data": result_data,
                "message": message,
            },
        )

    except Exception as e:
        exec_time = time.time() - start_time
        error_msg = f"{tool_name} execution error: {str(e)}"
        logging.error(
            error_msg,
            extra={"tool": tool_name, "error": str(e), "execution_time": exec_time},
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "data": None,
                "message": error_msg,
            },
        )

# Replace the mcp_endpoint function in src/api/routers.py

@mcp_router.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    MCP Protocol endpoint (JSON-RPC 2.0).
    
    Handles:
    - initialize: Server capabilities handshake
    - initialized: Notification after initialization
    - tools/list: List available tools
    - tools/call: Execute a tool
    - resources/list: List available resources
    - prompts/list: List available prompts
    """
    start_time = time.time()
    
    try:
        body = await request.body()
        body_str = body.decode("utf-8") if body else ""
        
        # Enhanced logging for traffic visibility
        client_host = request.client.host if request.client else "unknown"
        logging.info(
            f"MCP Request [{client_host}]",
            extra={
                "method": request.method,
                "url": str(request.url),
                "client_host": client_host,
                "body_length": len(body_str),
                "body_preview": body_str[:200] if body_str else None,
            }
        )
        
        # Handle empty body
        if not body:
            logging.warning("MCP endpoint received empty body")
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": "Parse error: Empty request body"
                    }
                }
            )
        
        # Parse JSON
        try:
            payload = json.loads(body_str)
        except json.JSONDecodeError as e:
            logging.error(f"MCP endpoint JSON decode error: {e}", extra={"body": body_str[:500]})
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
            )
        
        # Validate JSON-RPC version
        if payload.get("jsonrpc") != "2.0":
            logging.warning(f"Invalid JSON-RPC version: {payload.get('jsonrpc')}")
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request: jsonrpc must be '2.0'"
                    }
                }
            )
        
        method = payload.get("method")
        req_id = payload.get("id")
        params = payload.get("params", {})
        
        # Enhanced logging with request details
        logging.info(
            f"MCP method: {method}",
            extra={
                "method": method,
                "request_id": req_id,
                "params_keys": list(params.keys()) if isinstance(params, dict) else None,
                "is_notification": req_id is None,
            }
        )
        
        # Handle initialize
        if method == "initialize":
            client_info = params.get("clientInfo", {})
            logging.info(
                "MCP initialize request received",
                extra={
                    "client_name": client_info.get("name"),
                    "client_version": client_info.get("version"),
                }
            )
            
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "DevForge",
                        "version": "0.7.0"
                    },
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                        "prompts": {},
                    }
                }
            }
            
            exec_time = time.time() - start_time
            logging.info(
                "MCP initialize response",
                extra={
                    "execution_time": exec_time,
                    "capabilities": ["tools", "resources", "prompts"],
                }
            )
            
            return JSONResponse(content=response)
        
        # Handle initialized notification (no response needed)
        if method == "initialized":
            logging.info("MCP initialized notification received")
            # Notifications don't require a response
            return JSONResponse(status_code=200, content={})
        
        # Handle tools/list
        if method == "tools/list":
            logging.info("MCP tools/list request received")
            tools = []
            for name, func in SUPPORTED_TOOLS.items():
                # Build input schema based on tool
                input_schema = _get_tool_schema(name)
                
                tools.append({
                    "name": name,
                    "description": func.__doc__.strip() if func.__doc__ else f"{name} tool",
                    "inputSchema": input_schema
                })
            
            exec_time = time.time() - start_time
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": tools}
            }
            
            logging.info(
                "MCP tools/list response",
                extra={
                    "tools_count": len(tools),
                    "execution_time": exec_time,
                    "tool_names": [t["name"] for t in tools],
                }
            )
            
            return JSONResponse(content=response)
        
        # Handle resources/list
        if method == "resources/list":
            logging.info("MCP resources/list request received")
            
            # Return empty resources list for now
            resources = []
            
            exec_time = time.time() - start_time
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"resources": resources}
            }
            
            logging.info(
                "MCP resources/list response",
                extra={
                    "resources_count": len(resources),
                    "execution_time": exec_time,
                }
            )
            
            return JSONResponse(content=response)
        
        # Handle prompts/list
        if method == "prompts/list":
            logging.info("MCP prompts/list request received")
            
            # Return empty prompts list for now
            prompts = []
            
            exec_time = time.time() - start_time
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"prompts": prompts}
            }
            
            logging.info(
                "MCP prompts/list response",
                extra={
                    "prompts_count": len(prompts),
                    "execution_time": exec_time,
                }
            )
            
            return JSONResponse(content=response)
        
        # Handle tools/call
        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            logging.info(
                f"MCP tools/call request",
                extra={
                    "tool_name": tool_name,
                    "arguments_keys": list(arguments.keys()) if isinstance(arguments, dict) else None,
                    "arguments_preview": json.dumps(arguments)[:200] if arguments else None,
                }
            )
            
            if not tool_name:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32602,
                        "message": "Invalid params: 'name' is required"
                    }
                }
                logging.warning("MCP tools/call: missing tool name")
                return JSONResponse(status_code=400, content=error_response)
            
            if tool_name not in SUPPORTED_TOOLS:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32602,
                        "message": f"Tool not found: {tool_name}"
                    }
                }
                logging.warning(
                    "MCP tools/call: tool not found",
                    extra={
                        "tool_name": tool_name,
                        "available_tools": list(SUPPORTED_TOOLS.keys()),
                    }
                )
                return JSONResponse(status_code=400, content=error_response)
            
            # Call the tool via gateway
            try:
                tool_start_time = time.time()
                gateway_req = GatewayRequest(apiName=tool_name, arguments=arguments)
                gateway_response = await gateway(gateway_req)
                tool_exec_time = time.time() - tool_start_time
                
                # Extract response body
                response_body = json.loads(gateway_response.body.decode())
                
                # Return MCP-formatted response
                exec_time = time.time() - start_time
                mcp_response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(response_body, indent=2)
                            }
                        ]
                    }
                }
                
                logging.info(
                    "MCP tools/call response",
                    extra={
                        "tool_name": tool_name,
                        "success": response_body.get("success", False),
                        "tool_execution_time": tool_exec_time,
                        "total_execution_time": exec_time,
                        "response_size": len(json.dumps(response_body)),
                    }
                )
                
                return JSONResponse(content=mcp_response)
            
            except Exception as e:
                exec_time = time.time() - start_time
                error_response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }
                
                logging.error(
                    "MCP tools/call error",
                    extra={
                        "tool_name": tool_name,
                        "error": str(e),
                        "execution_time": exec_time,
                    },
                    exc_info=True
                )
                
                return JSONResponse(status_code=500, content=error_response)
        
        # Unknown method
        exec_time = time.time() - start_time
        error_response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }
        
        logging.warning(
            "MCP unknown method",
            extra={
                "method": method,
                "execution_time": exec_time,
            }
        )
        
        return JSONResponse(status_code=400, content=error_response)
    
    except Exception as e:
        exec_time = time.time() - start_time
        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }
        
        logging.error(
            "MCP endpoint unhandled error",
            extra={
                "error": str(e),
                "execution_time": exec_time,
            },
            exc_info=True
        )
        
        return JSONResponse(status_code=500, content=error_response)


def _get_tool_schema(tool_name: str) -> dict:
    """Generate JSON schema for tool parameters."""
    schemas = {
        "generate_data": {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "integer",
                    "description": "Number of rows to generate",
                    "minimum": 1,
                    "maximum": 10000
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "csv"],
                    "description": "Output format"
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Custom fields to generate"
                }
            },
            "required": ["rows"]
        },
        "retrieve_docs": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paths to documents"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results",
                    "default": 5
                }
            },
            "required": ["query"]
        },
        "github_operation": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language GitHub operation"
                }
            },
            "required": ["query"]
        },
        "rerank_docs": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query for reranking"
                },
                "documents": {
                    "type": "array",
                    "description": "Documents to rerank"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results"
                }
            },
            "required": ["query", "documents"]
        },
        "refine_prompt": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Prompt to refine"
                },
                "domain": {
                    "type": "string",
                    "enum": ["general", "image", "code", "rag", "llm"],
                    "description": "Domain"
                },
                "skill_level": {
                    "type": "string",
                    "enum": ["beginner", "intermediate", "expert"],
                    "description": "Skill level"
                }
            },
            "required": ["prompt"]
        },
        "generate_cheatsheet": {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "description": "Programming language"
                },
                "skill_level": {
                    "type": "string",
                    "enum": ["beginner", "intermediate", "expert"],
                    "description": "Skill level"
                },
                "code_context": {
                    "type": "string",
                    "description": "Code context"
                }
            },
            "required": ["language"]
        }
    }
    
    return schemas.get(tool_name, {
        "type": "object",
        "properties": {},
        "required": []
    })