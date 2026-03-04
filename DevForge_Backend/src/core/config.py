"""Configuration management for DevForge Backend.

Loads environment variables and provides settings singleton.
"""

import os
import re
import logging
from functools import lru_cache
from typing import List, Optional, Dict
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parents[2]
    MANIFEST_DIR: Path = BASE_DIR / "manifests"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_docker(self) -> bool:
        """Check if running inside Docker container."""
        return os.path.exists("/.dockerenv")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-correct Celery broker for local dev if it points to docker service
        if not self.is_docker:
            if self.CELERY_BROKER_URL and "redis:6379" in self.CELERY_BROKER_URL:
                self.CELERY_BROKER_URL = self.CELERY_BROKER_URL.replace("redis:6379", "localhost:6379")
            if self.CELERY_RESULT_BACKEND and "redis:6379" in self.CELERY_RESULT_BACKEND:
                self.CELERY_RESULT_BACKEND = self.CELERY_RESULT_BACKEND.replace("redis:6379", "localhost:6379")

        # Security validation for CORS
        if self.ENVIRONMENT.lower() == "production" and "localhost" in self.CORS_ORIGINS:
            import warnings
            warnings.warn("CRITICAL: Running in production environment but CORS_ORIGINS allows localhost!")

        # Validate Redis URL format if provided
        self._validate_redis_url()

        # Validate Postgres URL format if provided
        self._validate_postgres_url()

    def _validate_redis_url(self) -> None:
        """Validate Redis URL format and log warnings for common issues."""
        if not self.REDIS_URL:
            return

        # Valid Redis URL patterns
        valid_patterns = [
            r"^redis://[\w.-]+:\d+(/\d+)?$",  # redis://host:port/db
            r"^rediss://[\w.-]+:\d+(/\d+)?$",  # rediss:// (TLS)
            r"^redis://:[\w]+@[\w.-]+:\d+(/\d+)?$",  # redis://:password@host:port/db
        ]

        if not any(re.match(pattern, self.REDIS_URL) for pattern in valid_patterns):
            logger.warning(
                f"REDIS_URL format may be invalid: '{self.REDIS_URL}'. "
                "Expected format: redis://host:port/db or redis://:password@host:port/db"
            )

        # Warn about common issues
        if "localhost" in self.REDIS_URL and self.ENVIRONMENT.lower() == "production":
            logger.warning("REDIS_URL points to localhost in production environment!")

    def _validate_postgres_url(self) -> None:
        """Validate Postgres URL format and log warnings for common issues."""
        if not self.POSTGRES_URL:
            return

        # Valid Postgres URL patterns
        valid_patterns = [
            r"^postgresql://[\w.-]+:[\w.-]+@[\w.-]+:\d+/[\w.-]+$",  # postgresql://user:pass@host:port/db
            r"^postgresql://[\w.-]+@[\w.-]+:\d+/[\w.-]+$",  # postgresql://user@host:port/db (no password)
        ]

        if not any(re.match(pattern, self.POSTGRES_URL) for pattern in valid_patterns):
            logger.warning(
                f"POSTGRES_URL format may be invalid. "
                "Expected format: postgresql://user:password@host:port/database"
            )

        # Warn about common issues
        if "localhost" in self.POSTGRES_URL and self.ENVIRONMENT.lower() == "production":
            logger.warning("POSTGRES_URL points to localhost in production environment!")

    # Server Configuration
    PORT: int = 8000
    CORS_ORIGINS: str
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    # Ollama Configuration
    OLLAMA_HOST: str
    OLLAMA_API_KEY: str | None = None

    # Phase 1: Primary model for simple tasks
    DEFAULT_MODEL: str = "gpt-oss:20b-cloud"  # Use cloud to avoid memory issues

    # Phase 2: Supervisor router model
    SUPERVISOR_MODEL: str = "gpt-oss:20b-cloud"  # Use cloud to avoid memory issues

    # Phase 3: RAG models (both cloud)
    RAG_LOCAL_MODEL: str = "gpt-oss:20b-cloud"  # Use cloud
    RAG_CLOUD_MODEL: str = "gpt-oss:120b-cloud"

    # Phase 3: GitHub operations model
    GITHUB_MODEL: str = "gpt-oss:20b-cloud"

    # Phase 3: Premium reasoning model
    PREMIUM_MODEL: str = "deepseek-v3.1:671b-cloud"

    # Phase 3: Embedding model (existing, kept for Phase 1-2 compatibility)
    EMBEDDING_MODEL: str = "bge-m3"

    # Phase 3: RAG Configuration
    VECTOR_BACKEND: str = "postgres"  # Options: chroma, postgres
    CHROMA_PERSIST_DIR: str = "./data/chromadb"
    CHROMA_COLLECTION: str = "devforge_docs"
    RAG_EMBED_MODEL: str = "nomic-embed-text"  # Primary for RAG
    RAG_EMBED_MODEL_FALLBACK: str = "bge-m3"  # Fallback if nomic unavailable
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 5
    RAG_SCORE_THRESHOLD: float = 0.0  # Set to 0 to accept all results; ChromaDB L2 scores are small

    # Storage Configuration
    STORAGE_ROOT: str = "./data/uploads/users"
    FILE_BASE_URL: str

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

    # Phase 10.1: Celery Configuration
    CELERY_BROKER_URL: str | None = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str | None = "redis://localhost:6379/0"
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300  # 5 minutes
    CELERY_TASK_TIME_LIMIT: int = 360  # 6 minutes hard limit

    # Phase 10.1: pgvector Configuration
    POSTGRES_URL: str | None = None
    PG_VECTOR_DIMENSION: int = 768  # nomic-embed-text dimension
    USE_PGVECTOR: bool = False  # Feature flag, ChromaDB default
    PGVECTOR_FALLBACK_TO_CHROMA: bool = True  # Graceful degradation

    # Phase 10.1: Code Graph Configuration
    ENABLE_CODE_GRAPH: bool = True
    GRAPH_CONTEXT_DEPTH: int = 2  # BFS depth for related functions
    GRAPH_MAX_CONTEXT_CHUNKS:int = 3  # Limit per expanded function
    
    # Phase 12: RAG Configuration
    RAG_MAX_FILE_SIZE: int = 52428800  # 50MB default (52,428,800 bytes)
    
    # Phase 11: Reranking
    ENABLE_RERANKING: bool = True
    RERANK_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANK_SCORE_THRESHOLD: float = 0.3  # Normalized [0,1] via sigmoid
    VECTOR_SEARCH_CANDIDATES: int = 30   # Recall stage candidates
    
    # Phase 11: Code-aware boosting (Day 3)
    BOOST_FUNCTION: float = 1.2
    BOOST_CLASS: float = 1.15
    BOOST_IMPORT: float = 1.0
    BOOST_TEXT: float = 0.95
    
    # Phase 11.2: Query Cache (Exact-Match)
    ENABLE_QUERY_CACHE: bool = True
    QUERY_CACHE_TTL: int = 3600  # 1 hour
    QUERY_CACHE_MAX_SIZE: int = 1000  # In-memory LRU size
    REDIS_URL: Optional[str] = None  # Optional: "redis://localhost:6379/0"
    
    # Phase 11.2: Hybrid Search (BM25 + Vector)
    ENABLE_HYBRID_SEARCH: bool = True
    HYBRID_ALPHA: float = 0.5  # Vector weight (0.5 = 50%vector, 50% BM25)
    BM25_INDEX_BATCH_SIZE: int = 500
    
    # Phase 12A Day 1: Intent Classification
    ENABLE_INTENT_CLASSIFICATION: bool = True
    INTENT_RULE_BASED_THRESHOLD: int = 1  # Lowered from 2 for better detection
    INTENT_LLM_FALLBACK: bool = False  # DISABLED by default (production-safe)
    INTENT_LLM_TIMEOUT: int = 3  # Hard timeout for LLM calls (seconds)
    DEFAULT_INTENT: str = "code_search"  # Fallback intent
    
    # Phase 12A Day 3-4: Query Expansion
    ENABLE_QUERY_EXPANSION: bool = True
    EXPANSION_LLM_MODEL: str = "gpt-oss:20b-cloud"  # Use cloud model for expansion
    EXPANSION_TIMEOUT: int = 5  # Reduced for faster fallback to keywords
    EXPANSION_BY_INTENT: Dict[str, int] = {
        "debug": 2,
        "explain": 4,
        "code_search": 3,
        "api_reference": 2,
        "troubleshoot": 3
    }
    
    # Phase 12A Day 5-6: Semantic Cache
    ENABLE_SEMANTIC_CACHE: bool = True
    SEMANTIC_CACHE_THRESHOLD: float = 0.92  # Cosine similarity threshold
    SEMANTIC_CACHE_MAX_SIZE_PER_INTENT: int = 100  # Max cached queries per intent

    # Phase 1 (API Key Auth Phase): Security Configuration
    ADMIN_SECRET: str | None = None  # Protected admin endpoints
    API_KEY_CACHE_TTL: int = 300      # 5 minutes cache

    # Phase 3: Dashboard Authentication
    DASHBOARD_JWT_SECRET: str | None = None
    GOOGLE_DASHBOARD_CLIENT_ID: str | None = None
    GOOGLE_DASHBOARD_SECRET: str | None = None

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS comma-separated string into list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    GATEWAY_URL: str | None = None

    @property
    def gateway_url(self) -> str:
        """Generate gateway URL dynamically from PORT or use explicit setting."""
        if self.GATEWAY_URL:
            return self.GATEWAY_URL
        return f"http://localhost:{self.PORT}/api/gateway"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings singleton instance."""
    return Settings()


# Global settings instance
settings = get_settings()

