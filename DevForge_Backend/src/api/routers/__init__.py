"""API routers for MCP endpoints (gateway and manifest).

Handles tool discovery via manifest and tool execution via gateway.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from src.agents.cheatsheet.agent import generate_cheatsheet_invoke
from src.agents.testgen.agent import generate_tests_invoke
from src.core.rate_limiter import rate_limiter
# Import agents
from src.agents.datagen.agent import datagen_agent
from src.agents.github.agent import github_agent_invoke
from src.agents.prompt_refiner.agent import refine_prompt_invoke

# Import RAG models for type hints
from src.api.rag_models import (
    IngestAsyncRequest,
    IngestAsyncResponse,
    TaskStatusResponse,
)
from src.core.config import settings

# Import job queue for async operations
from src.core.jobs import get_job_queue
from src.core.schemas import GatewayRequest, GatewayResponse
from src.core.utils import track_performance

# Import Phase 2 specialized tools
# from src.tools.changelog import generate_changelog_invoke
# from src.tools.ci_diagnostics import analyze_ci_failure_invoke
# from src.tools.scaffold import scaffold_repository_invoke

router = APIRouter()

# Map tool names to agent invoke functions
SUPPORTED_TOOLS = {
    "generate_data": datagen_agent,
    "github_operation": github_agent_invoke,
    "refine_prompt": refine_prompt_invoke,
    "generate_cheatsheet": generate_cheatsheet_invoke,
    "generate_tests": generate_tests_invoke,
    # Phase 2: Specialized GitHub Tools (Integrated into github_operation)
    # "generate_changelog": generate_changelog_invoke,
    # "analyze_ci_failure": analyze_ci_failure_invoke,
    # "scaffold_repository": scaffold_repository_invoke,
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
async def ingest_documents_async(http_req: Request, body: IngestAsyncRequest) -> IngestAsyncResponse:
    """
    Queue documents for async ingestion via Celery.

    Requires JWT auth (tenant_id extracted by JWTAuthMiddleware). The target
    collection is always derived from the authenticated tenant — the caller's
    collection_name field is ignored to prevent cross-tenant writes.

    ARCHITECTURE: Calls async_ingest_documents Celery task → RAGAgent.
    """
    from src.workers.tasks.rag_tasks import async_ingest_documents

    tenant_id = http_req.state.tenant_id
    collection_name = f"user_{tenant_id}"

    logging.info(
        f"Queueing async ingestion: {len(body.file_paths)} files",
        extra={"tenant": tenant_id, "collection": collection_name, "files": len(body.file_paths)},
    )

    task = async_ingest_documents.delay(
        file_paths=body.file_paths,
        collection_name=collection_name,
        embed_model=body.embed_model,
    )

    logging.info(f"Task queued: {task.id}")

    return IngestAsyncResponse(
        task_id=task.id,
        status="queued",
        collection=collection_name,
        total_files=len(body.file_paths),
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
                "code_graph": {"enabled": False},
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
                    "backend": stats.get("backend", "unknown"),
                }
            else:
                metrics["cache"] = {
                    "enabled": settings.ENABLE_QUERY_CACHE,
                    "hit_rate": 0.0,
                    "backend": "disabled",
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
                    "documents_indexed": bm25_stats.get("documents_indexed", 0),
                }
            else:
                metrics["hybrid_search"] = {
                    "enabled": settings.ENABLE_HYBRID_SEARCH,
                    "bm25_ready": False,
                    "documents_indexed": 0,
                }
        except Exception as e:
            logging.warning(f"Hybrid search metrics error: {e}")
            metrics["hybrid_search"] = {"enabled": False, "error": str(e)}

        # Reranking metrics
        try:
            metrics["reranking"] = {
                "enabled": settings.ENABLE_RERANKING,
                "model": settings.RERANK_MODEL if settings.ENABLE_RERANKING else None,
                "threshold": settings.RERANK_SCORE_THRESHOLD
                if settings.ENABLE_RERANKING
                else None,
            }
        except Exception as e:
            logging.warning(f"Reranking metrics error: {e}")
            metrics["reranking"] = {"enabled": False, "error": str(e)}

        # Code graph metrics
        try:
            if agent._code_graph:
                metrics["code_graph"] = {
                    "enabled": True,
                    "nodes": agent._code_graph.size(),
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
        return {"version": "11.2.0", "error": "metrics_unavailable", "message": str(e)}


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
                    "components": {},
                },
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
                # Access via property — triggers lazy-load if not yet initialised
                reranker_ok = agent.reranker is not None
                components["reranker"] = "ok" if reranker_ok else "not_loaded"
            else:
                components["reranker"] = "disabled"
                reranker_ok = True
        except Exception:
            components["reranker"] = "error"
            reranker_ok = True

        try:
            if settings.ENABLE_HYBRID_SEARCH:
                # BM25 is tenant-scoped and lazy-inits on first retrieval per tenant.
                # A fresh health-check agent has no tenant docs, so "not built yet" is normal.
                bm25_built = agent._bm25_index and agent._bm25_index.is_ready()
                components["bm25_index"] = "ok" if bm25_built else "ready_on_demand"
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
            content={"status": status, "version": "11.2.0", "components": components},
        )

    except Exception as e:
        logging.error(f"Critical error in /rag/health: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": "health_check_failed",
                "message": str(e),
            },
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
                "stats": stats,
            }
        else:
            return {"status": "disabled", "message": "Query cache is not enabled"}

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
            return {"status": "disabled", "message": "Hybrid search is not enabled"}

        # Admin route: isolate from user caching by instantiating directly
        agent = RAGAgent()

        if agent._bm25_index:
            await agent._bm25_index.rebuild(agent.vector_store)
            stats = agent._bm25_index.get_stats()

            return {
                "status": "rebuilt",
                "message": "BM25 index rebuilt successfully",
                "stats": stats,
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

        # Admin route: isolate from user caching by instantiating directly
        agent = RAGAgent()

        if not hasattr(agent, "_intent_classifier") or not agent._intent_classifier:
            return {
                "enabled": False,
                "message": "Intent classification not initialized",
            }

        stats = agent._intent_classifier.get_stats()

        return {"enabled": True, **stats}

    except Exception as e:
        logging.error(f"Failed to get fallback usage: {e}")
        return {"enabled": False, "error": str(e)}


@router.get("/rag/analytics/expansion-quality", tags=["rag", "analytics"])
async def get_expansion_quality():
    """Get query expansion quality metrics."""
    try:
        from src.agents.rag.agent import RAGAgent

        # Admin route: isolate from user caching by instantiating directly
        agent = RAGAgent()

        if not hasattr(agent, "_query_expander") or not agent._query_expander:
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
        from src.agents.rag.agent import RAGAgent

        # Admin route: isolate from user caching by instantiating directly
        agent = RAGAgent()

        if not hasattr(agent, "_intent_classifier") or not agent._intent_classifier:
            return {
                "enabled": False,
                "message": "Intent classification not initialized",
            }

        stats = agent._intent_classifier.get_stats()
        return {
            "enabled": True,
            "intent_distribution": stats.get("intent_distribution", {}),
            "method_breakdown": stats.get("method_breakdown", {}),
            "total_classifications": stats.get("total", 0),
        }
    except Exception as e:
        logging.error(f"Failed to get intent distribution: {e}")
        return {"enabled": False, "error": str(e)}


@router.get("/rag/analytics/cache-by-intent", tags=["rag", "analytics"])
async def get_cache_by_intent():
    """Get semantic cache effectiveness by intent."""
    try:
        from src.agents.rag.agent import RAGAgent

        # Admin route: isolate from user caching by instantiating directly
        agent = RAGAgent()

        if not hasattr(agent, "_semantic_cache") or not agent._semantic_cache:
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
            status_code=500, detail="Plugin manifest not found on server"
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logging.critical(f"Invalid manifest JSON: {e}")
        raise HTTPException(status_code=500, detail="Plugin manifest is invalid JSON")

    # Optional: validate expected LobeHub keys
    required_keys = {"identifier", "meta", "api"}
    missing = required_keys - manifest.keys()
    if missing:
        logging.critical(f"Manifest missing keys: {missing}")
        raise HTTPException(
            status_code=500, detail=f"Manifest missing required fields: {missing}"
        )

    logging.info(
        "LobeHub manifest served",
        extra={
            "identifier": manifest["identifier"],
            "api_count": len(manifest["api"]),
        },
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
        ],
    }


@router.post("/gateway")
async def gateway_endpoint(gateway_req: GatewayRequest, request: Request):
    """Universal gateway for all tools - simplified and cleaner"""
    tool_name = gateway_req.get_tool_name()
    args = gateway_req.arguments or {}
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

    api_key_id: Optional[str] = None  # bound inside the try; init here so the except handler can refer to it safely
    slot_acquired = False  # rate-limit slot — refunded via release() on any failure path
    try:
        # ------------------------------------------------------------------- #
        # Phase 4: Extract user_id and request context for analytics
        # ------------------------------------------------------------------- #
        user_id = getattr(request.state, "user_id", None)
        tenant_id = getattr(request.state, "tenant_id", "unknown")
        integration_name = getattr(request.state, "integration_name", "unknown")
        
        # ------------------------------------------------------------------- #
        # Rate Limiting Check (Phase 4)
        # ------------------------------------------------------------------- #
        api_key_id = getattr(request.state, "api_key_id", None)
        tier = getattr(request.state, "tier", "free")
        
        if api_key_id:
            allowed, limit_info = await rate_limiter.check_limits(
                api_key_id, 
                tier,
                hourly_override=getattr(request.state, "hourly_limit_override", None),
                monthly_override=getattr(request.state, "monthly_limit_override", None)
            )
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": "rate_limit_exceeded",
                        "message": f"Rate limit exceeded for {tier} tier",
                        "limit_info": {
                            "hourly_used": limit_info["hourly_used"],
                            "hourly_limit": limit_info["hourly_limit"],
                            "monthly_used": limit_info["monthly_used"],
                            "monthly_limit": limit_info["monthly_limit"],
                            "hourly_reset_at": limit_info["hourly_reset_at"],
                            "monthly_reset_at": limit_info["monthly_reset_at"],
                            **({"upgrade_url": settings.DASHBOARD_UPGRADE_URL}
                               if settings.DASHBOARD_UPGRADE_URL else {})
                        }
                    },
                    headers={
                        "X-RateLimit-Limit-Hourly": str(limit_info["hourly_limit"] or "unlimited"),
                        "X-RateLimit-Used-Hourly": str(limit_info["hourly_used"]),
                        "X-RateLimit-Reset-Hourly": limit_info["hourly_reset_at"],
                        "X-RateLimit-Limit-Monthly": str(limit_info["monthly_limit"] or "unlimited"),
                        "X-RateLimit-Used-Monthly": str(limit_info["monthly_used"]),
                        "Retry-After": limit_info["hourly_reset_at"],
                    }
                )
            slot_acquired = True

        # ------------------------------------------------------------------- #
        # Special handling for github_operation (v0.8 with context support)
        # ------------------------------------------------------------------- #
        if tool_name == "github_operation":
            query = args.get("query")
            if not query:
                error_msg = "github_operation requires 'query' parameter"
                # Scrub the github_token from args before logging — it's nested in `context`
                # and would otherwise leak into log handlers attached to the root logger.
                _safe_args = {
                    k: ({kk: vv for kk, vv in v.items() if kk != "github_token"}
                        if k == "context" and isinstance(v, dict) else v)
                    for k, v in (args or {}).items()
                }
                logging.error(error_msg, extra={"tool": tool_name, "args": _safe_args})
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "data": None,
                        "message": error_msg,
                    },
                )
            # v0.8: Support optional context parameter + per-user token
            context = args.get("context", {})
            # Strip token from context BEFORE any logging — never log raw tokens
            github_token = context.pop("github_token", None)

            logging.info(f"Calling {tool_name} for tenant {tenant_id} with query: {query[:100]}...")
            result = await agent_func(
                query=query, 
                context=context, 
                github_token=github_token,
                tenant_id=tenant_id,
                integration_name=integration_name,
                user_id=user_id  # NEW: Pass user_id to agent
            )
        else:
            logging.info(f"Calling {tool_name} for tenant {tenant_id} with args: {args}")
            result = await agent_func(
                args, 
                tenant_id=tenant_id, 
                integration_name=integration_name,
                user_id=user_id  # NEW: Pass user_id to agent
            )

        exec_time = time.time() - start_time

        # Extract data from result - handle different result structures
        result_data = result.get("data")
        if result_data is None:
            # If no 'data' key, use the entire result (minus metadata)
            result_data = {
                k: v
                for k, v in result.items()
                if k not in ["success", "tool", "format", "error", "execution_time"]
            }
            if not result_data:
                result_data = result  # Fallback to full result

        # Check if operation was successful
        success = result.get("success", True)  # Default to True if not specified
        error = result.get("error")

        if error:
            success = False
            message = f"{tool_name} execution failed: {error}"
            
            # Phase 2 & 4: Enhanced error feedback for GitHub permission issues
            is_github_tool = tool_name == "github_operation"
            is_permission_error = any(phrase in str(error).lower() for phrase in ["403", "permission denied", "bad credentials", "requires secondary factor"])
            
            if is_github_tool and is_permission_error:
                message += (
                    "\n\n💡 Tip: Check your GitHub Personal Access Token (PAT) in settings. "
                    "Ensure it has the required scopes (repo, admin:org, etc.) and is not expired."
                )
                
            logging.error(
                message,
                extra={"tool": tool_name, "error": error, "execution_time": exec_time},
            )
        else:
            message = f"{tool_name} executed successfully"

        logging.info(
            f"Tool {tool_name} executed successfully",
            extra={"tool": tool_name, "success": success, "execution_time": exec_time},
        )

        # ------------------------------------------------------------------- #
        # Phase 4: Rate-limit slot release on failure
        # ------------------------------------------------------------------- #
        # The slot was reserved atomically by rate_limiter.check_limits (Lua
        # acquire) at the top of this handler. On failure, refund the slot so
        # failed tool calls do not count against the user's quota.
        if not success and api_key_id:
            try:
                await rate_limiter.release(api_key_id)
            except Exception as e:
                logging.warning(f"Failed to release rate-limit slot: {e}")

        # ------------------------------------------------------------------- #
        # Phase 4: Async request logging for analytics
        # ------------------------------------------------------------------- #
        try:
            from src.workers.tasks.analytics_tasks import log_request_call
            from src.utils.sanitization import truncate_input
            
            input_summary = truncate_input(args)
            log_request_call.delay(
                user_id=user_id,
                tenant_id=tenant_id,
                integration_name=integration_name,
                tool_name=tool_name,
                input_summary=input_summary,
                success=success,
                duration_ms=int(exec_time * 1000)
            )
        except Exception as e:
            # Never block tool response for analytics logging
            logging.warning(f"Failed to queue analytics logging: {e}")

        # ------------------------------------------------------------------- #
        # Build response with rate limit headers
        # ------------------------------------------------------------------- #
        response_headers = {}
        if api_key_id:
            try:
                usage = await rate_limiter.get_usage(api_key_id, tier)
                response_headers = {
                    "X-RateLimit-Limit-Hourly": str(usage["hourly_limit"] or "unlimited"),
                    "X-RateLimit-Used-Hourly": str(usage["hourly_used"]),
                    "X-RateLimit-Reset-Hourly": usage["hourly_reset_at"],
                    "X-RateLimit-Limit-Monthly": str(usage["monthly_limit"] or "unlimited"),
                    "X-RateLimit-Used-Monthly": str(usage["monthly_used"]),
                }
            except Exception as e:
                logging.warning(f"Failed to get rate limit usage for headers: {e}")

        # Return standardized response format
        return JSONResponse(
            content={
                "success": success,
                "data": result_data,
                "message": message,
            },
            headers=response_headers
        )

    except Exception as e:
        exec_time = time.time() - start_time
        error_msg = f"{tool_name} execution error: {str(e)}"

        # Refund the rate-limit slot reserved earlier so a raised exception
        # does not consume the user's quota. Guarded by slot_acquired so we
        # never DECR a slot that was never acquired.
        if slot_acquired and api_key_id:
            try:
                await rate_limiter.release(api_key_id)
            except Exception as rel_e:
                logging.warning(f"Failed to release rate-limit slot after exception: {rel_e}")

        # Phase 2 & 4: Enhanced error feedback for GitHub permission issues
        is_github_tool = tool_name == "github_operation"
        is_permission_error = any(phrase in str(e).lower() for phrase in ["403", "permission denied", "bad credentials", "requires secondary factor"])
        
        if is_github_tool and is_permission_error:
            error_msg += (
                "\n\n💡 Tip: Check your GitHub Personal Access Token (PAT) in settings. "
                "Ensure it has the required scopes (repo, admin:org, etc.) and is not expired."
            )
            
        logging.error(
            error_msg,
            extra={"tool": tool_name, "error": str(e), "execution_time": exec_time},
            exc_info=True,
        )
        
        # ------------------------------------------------------------------- #
        # Phase 4: Log failed requests too
        # ------------------------------------------------------------------- #
        try:
            from src.workers.tasks.analytics_tasks import log_request_call
            from src.utils.sanitization import truncate_input
            
            input_summary = truncate_input(args)
            log_request_call.delay(
                user_id=getattr(request.state, "user_id", None),
                tenant_id=getattr(request.state, "tenant_id", "unknown"),
                integration_name=getattr(request.state, "integration_name", "unknown"),
                tool_name=tool_name,
                input_summary=input_summary,
                success=False,
                duration_ms=int(exec_time * 1000)
            )
        except Exception as log_e:
            # Never block tool response for analytics logging
            logging.warning(f"Failed to queue analytics logging for error: {log_e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "data": None,
                "message": error_msg,
            },
        )
