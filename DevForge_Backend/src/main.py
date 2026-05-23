"""DevForge Backend - FastAPI application entry point."""

import time
import logging
from contextlib import asynccontextmanager
from pathlib import Path  # ✅ Added for robust path handling

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
# Ensure Celery app is loaded to apply broker config (prevents fallback to AMQP)
import src.workers.celery_app

from src.api.routers import router, mcp_router
from src.api.routers.rag import router as rag_router
from src.api.routers.auth import router as auth_router
from src.api.monitoring import router as monitoring_router  # Phase 3
from src.core.middleware import JWTAuthMiddleware
from src.core.api_key_middleware import APIKeyAuthMiddleware
from src.core.dashboard_middleware import DashboardAuthMiddleware
from src.api.routers.users import router as users_router
from src.api.routers.admin import router as admin_router
from src.storage.db import PostgresPoolManager

# Track application start time for uptime calculation
START_TIME = time.time()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("DevForge v0.8.0 starting up...")
    
    # Ensure data directory structure exists on startup
    Path("data/uploads").mkdir(parents=True, exist_ok=True)

    # Pre-load reranker model so first retrieval request doesn't pay model-load latency
    if settings.ENABLE_RERANKING:
        try:
            from src.agents.rag.reranking import CrossEncoderReranker
            CrossEncoderReranker(model_name=settings.RERANK_MODEL)
            logger.info("Reranker model pre-loaded at startup")
        except Exception as e:
            logger.warning(f"Reranker pre-load failed (will lazy-init on first use): {e}")

    yield
    # Shutdown
    logger.info("DevForge shutting down...")
    await PostgresPoolManager.close_pool()


# Create FastAPI app
app = FastAPI(
    title="DevForge Backend",
    description="FastAPI backend for AI-powered developer tools with intelligent GitHub automation",
    version="0.8.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add JWT auth middleware
app.add_middleware(JWTAuthMiddleware)

# Add API Key auth middleware (for /gateway and /mcp)
app.add_middleware(APIKeyAuthMiddleware)

# Add Dashboard auth middleware (for /api/users/* and /api/admin/*)
app.add_middleware(DashboardAuthMiddleware)

# Include API routers
app.include_router(router, prefix="/api")
app.include_router(auth_router, prefix="/api") # Auth routes (includes refresh)
app.include_router(users_router, prefix="/api") # User-scoped routes
app.include_router(rag_router, prefix="/api") # Lobe Chat RAG
app.include_router(mcp_router)  # MCP endpoints
app.include_router(monitoring_router)  # Phase 3: Observability
app.include_router(admin_router)  # API Key Management


# ============================================================================
# Static File Serving (Fixed for RAG File Previews)
# ============================================================================

# ✅ FIX: Mount the root 'data' directory to '/static'
# This ensures that a URL like: http://localhost:8000/static/uploads/users/dev_user_1/file.py
# Correctly maps to the file system: ./data/uploads/users/dev_user_1/file.py

data_dir = Path("data")
data_dir.mkdir(parents=True, exist_ok=True) # Double check creation

app.mount("/static", StaticFiles(directory=data_dir), name="static")


@app.get("/health")
async def health_check():
    """Unified health check endpoint combining API, Redis, and Vector DB status."""
    uptime = time.time() - START_TIME
    # 1. Check Vector Store (Postgres/Chroma)
    if settings.POSTGRES_URL is None:
        vector_status = "disabled"
    else:
        try:
            from src.api.routers import rag_health_check
            rag_health_response = await rag_health_check()
            import json
            rag_data = json.loads(rag_health_response.body.decode())
            components = rag_data.get("components", {})
            vector_status = components.get("vector_store", "error")
        except Exception as e:
            logger.error(f"Postgres health check failed: {e}")
            vector_status = "error"
    
    # 2. Check Redis
    if settings.REDIS_URL is None:
        redis_status = "disabled"
    else:
        redis_status = "error"
        try:
            from src.storage.redis_file_store import RedisFileStore
            redis_store = RedisFileStore()
            if await redis_store.client.ping():
                redis_status = "ok"
            else:
                redis_status = "down"
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            redis_status = "error"
        
    # 3. Determine overall status
    is_healthy = True
    if redis_status not in ("ok", "disabled"):
        is_healthy = False
    if vector_status not in ("ok", "disabled"):
        is_healthy = False
        
    status = "healthy" if is_healthy else "degraded"
    
    return {
        "status": status,
        "uptime": round(uptime, 2),
        "services": {
            "api": "ok",
            "redis": redis_status,
            "postgres": vector_status
        }
    }


@app.get("/")
async def root():
    """Root endpoint with API information.

    Returns:
        dict with welcome message and version
    """
    return {
        "message": "DevForge backend running",
        "version": "0.8.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True,
    )