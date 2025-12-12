"""Performance and observability monitoring endpoints.

Provides real-time metrics, health checks, and performance statistics.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter
from datetime import datetime

from src.core.performance import get_metrics, get_cache
from src.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint
    
    Returns:
        Health status and basic system info
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "0.8.0",
        "environment": "production" if settings.ENVIRONMENT == "production" else "development"
    }


@router.get("/metrics")
async def get_performance_metrics() -> Dict[str, Any]:
    """Get performance metrics
    
    Returns:
        Performance statistics for all tracked metrics
    """
    metrics = get_metrics()
    stats = await metrics.all_stats()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "metrics": stats
    }


@router.get("/metrics/{metric_name}")
async def get_metric_stats(metric_name: str) -> Dict[str, Any]:
    """Get statistics for specific metric
    
    Args:
        metric_name: Name of metric
        
    Returns:
        Metric statistics (min, max, mean, percentiles)
    """
    metrics = get_metrics()
    stats = await metrics.get_stats(metric_name)
    
    if not stats:
        return {
            "error": f"Metric '{metric_name}' not found",
            "available_metrics": list(metrics.metrics.keys())
        }
    
    return {
        "metric": metric_name,
        "timestamp": datetime.now().isoformat(),
        "stats": stats
    }


@router.get("/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics
    
    Returns:
        Cache size and hit/miss ratios
    """
    cache = get_cache()
    
    # Count entries
    total_entries = len(cache._cache)
    
    # Clean up expired entries
    await cache.cleanup_expired()
    
    active_entries = len(cache._cache)
    expired_cleaned = total_entries - active_entries
    
    return {
        "timestamp": datetime.now().isoformat(),
        "total_entries": active_entries,
        "expired_cleaned": expired_cleaned,
        "cache_enabled": True
    }


@router.post("/cache/clear")
async def clear_cache() -> Dict[str, Any]:
    """Clear all cache entries
    
    Returns:
        Confirmation message
    """
    cache = get_cache()
    await cache.clear()
    
    logger.info("Cache manually cleared")
    
    return {
        "success": True,
        "message": "Cache cleared successfully",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/performance/summary")
async def performance_summary() -> Dict[str, Any]:
    """Get comprehensive performance summary
    
    Returns:
        Performance summary with key metrics
    """
    metrics = get_metrics()
    all_stats = await metrics.all_stats()
    
    # Calculate summary statistics
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_metrics_tracked": len(all_stats),
        "key_metrics": {}
    }
    
    # Extract key metrics
    for metric_name, stats in all_stats.items():
        if stats:
            summary["key_metrics"][metric_name] = {
                "count": stats.get("count", 0),
                "p95_ms": round(stats.get("p95", 0), 2),
                "p99_ms": round(stats.get("p99", 0), 2),
                "mean_ms": round(stats.get("mean", 0), 2)
            }
    
    return summary


@router.get("/config")
async def get_configuration() -> Dict[str, Any]:
    """Get current configuration (sanitized)
    
    Returns:
        Current GitOps configuration (no secrets)
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "gitops": {
            "storage": settings.GITOPS_STORAGE,
            "fuzzy_search_enabled": settings.GITOPS_ENABLE_FUZZY_SEARCH,
            "commit_gen_enabled": settings.GITOPS_ENABLE_COMMIT_GEN,
            "log_parsing_enabled": settings.GITOPS_ENABLE_LOG_PARSING,
            "async_jobs_enabled": settings.GITOPS_ENABLE_ASYNC_JOBS,
            "confidence_gating_enabled": settings.GITOPS_ENABLE_CONFIDENCE_GATING,
            "fuzzy_threshold": settings.GITOPS_FUZZY_THRESHOLD,
            "commit_confidence_threshold": settings.GITOPS_COMMIT_CONFIDENCE_THRESHOLD,
            "auto_fix_threshold": settings.GITOPS_AUTO_FIX_THRESHOLD,
            "repo_cache_ttl": settings.GITOPS_REPO_CACHE_TTL,
            "session_ttl": settings.GITOPS_SESSION_TTL,
            "max_sync_work_units": settings.MAX_SYNC_WORK_UNITS
        },
        "version": "0.8.0"
    }
