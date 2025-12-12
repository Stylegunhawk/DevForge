"""DevForge Backend - FastAPI application entry point."""

import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.api.routers import router, mcp_router
from src.api.monitoring import router as monitoring_router  # Phase 3

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
    yield
    # Shutdown
    logger.info("DevForge shutting down...")


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

# Include API routers
app.include_router(router, prefix="/api")
app.include_router(mcp_router)  # MCP endpoints
app.include_router(monitoring_router)  # Phase 3: Observability


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        dict with status and uptime in seconds
    """
    uptime = time.time() - START_TIME
    return {"status": "ok", "uptime": round(uptime, 2)}


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

