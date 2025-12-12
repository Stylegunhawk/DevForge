"""Configuration management for DevForge Backend.

Loads environment variables and provides settings singleton.
"""

import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server Configuration
    PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    # Ollama Configuration
    OLLAMA_HOST: str = "http://localhost:11434"

    # Model Configuration (Exact names from ollama list)
    # Phase 1: Primary model for simple tasks
    DEFAULT_MODEL: str = "qwen3:4b"

    # Phase 2: Supervisor router model
    SUPERVISOR_MODEL: str = "deepseek-r1:8b"

    # Phase 3: RAG models
    RAG_LOCAL_MODEL: str = "gpt-oss:20b"
    RAG_CLOUD_MODEL: str = "gpt-oss:120b-cloud"

    # Phase 3: GitHub operations model
    GITHUB_MODEL: str = "gpt-oss:20b-cloud"

    # Phase 3: Premium reasoning model
    PREMIUM_MODEL: str = "deepseek-v3.1:671b-cloud"

    # Phase 3: Embedding model (existing, kept for Phase 1-2 compatibility)
    EMBEDDING_MODEL: str = "bge-m3"

    # Phase 3: RAG Configuration
    VECTOR_BACKEND: str = "chroma"  # Options: chroma (default), qdrant
    CHROMA_PERSIST_DIR: str = "./data/chromadb"
    CHROMA_COLLECTION: str = "devforge_docs"
    RAG_EMBED_MODEL: str = "nomic-embed-text"  # Primary for RAG
    RAG_EMBED_MODEL_FALLBACK: str = "bge-m3"  # Fallback if nomic unavailable
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 5
    RAG_SCORE_THRESHOLD: float = 0.5

    # Phase 3.1b: Qdrant Cloud Configuration
    QDRANT_URL: str | None = None  # e.g., https://xxx.europe-west3-0.gcp.cloud.qdrant.io
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION: str = "devforge_docs"

    # Optional: GitHub Integration (Phase 3)
    GITHUB_TOKEN: str | None = None
    GITHUB_USERNAME: str | None = None  # Optional: for display purposes

    # Optional: Database (Future phases)
    DATABASE_URL: str | None = None

    # GitOps v0.8 Configuration
    GITOPS_STORAGE: str = "memory"  # "memory" | "redis" | "postgres"
    GITOPS_ENABLE_FUZZY_SEARCH: bool = True
    GITOPS_FUZZY_THRESHOLD: float = 0.85
    GITOPS_ENABLE_COMMIT_GEN: bool = True
    GITOPS_ENABLE_WORKFLOWS: bool = True
    GITOPS_ENABLE_LOG_PARSING: bool = True
    GITOPS_ENABLE_ASYNC_JOBS: bool = True
    GITOPS_AUTO_CONFIRM: bool = False
    GITOPS_ENABLE_ROLLBACK: bool = True
    GITOPS_UNDO_WINDOW_MINUTES: int = 30
    GITOPS_REPO_CACHE_TTL: int = 3600  # 1 hour
    GITOPS_LLM_TIMEOUT: int = 10
    GITOPS_SESSION_TTL: int = 1800  # 30 minutes
    GITOPS_JOB_CLEANUP_HOURS: int = 24

    # Optional: Redis (only if GITOPS_STORAGE="redis")
    REDIS_URL: str | None = None

    # Auto-fix Policy (CI Diagnostics)
    GITOPS_AUTO_FIX_THRESHOLD: float = 0.95
    GITOPS_AUTO_FIX_TYPES: List[str] = ["format", "dependency_patch", "lint"]
    
    # Work unit thresholds for async fallback
    MAX_SYNC_WORK_UNITS: int = 50
    WORK_UNIT_TIMEOUT_SECONDS: int = 10

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS comma-separated string into list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def gateway_url(self) -> str:
        """Generate gateway URL dynamically from PORT."""
        # In production, this would use actual hostname from request
        return f"http://localhost:{self.PORT}/api/gateway"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings singleton instance."""
    return Settings()


# Global settings instance
settings = get_settings()

