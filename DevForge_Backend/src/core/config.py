"""Configuration management for DevForge Backend.

Loads environment variables and provides settings singleton.
"""

import os
from functools import lru_cache
from typing import List, Optional, Dict

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
    VECTOR_BACKEND: str = "chroma"  # Options: chroma (default), qdrant
    CHROMA_PERSIST_DIR: str = "./data/chromadb"
    CHROMA_COLLECTION: str = "devforge_docs"
    RAG_EMBED_MODEL: str = "nomic-embed-text"  # Primary for RAG
    RAG_EMBED_MODEL_FALLBACK: str = "bge-m3"  # Fallback if nomic unavailable
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 5
    RAG_SCORE_THRESHOLD: float = 0.0  # Set to 0 to accept all results; ChromaDB L2 scores are small

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
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300  # 5 minutes
    CELERY_TASK_TIME_LIMIT: int = 360  # 6 minutes hard limit

    # Phase 10.1: pgvector Configuration
    POSTGRES_URL: str = "postgresql://devforge:devforge123@localhost:5432/devforge"
    PG_VECTOR_DIMENSION: int = 768  # nomic-embed-text dimension
    USE_PGVECTOR: bool = False  # Feature flag, ChromaDB default
    PGVECTOR_FALLBACK_TO_CHROMA: bool = True  # Graceful degradation

    # Phase 10.1: Code Graph Configuration
    ENABLE_CODE_GRAPH: bool = True
    GRAPH_CONTEXT_DEPTH: int = 2  # BFS depth for related functions
    GRAPH_MAX_CONTEXT_CHUNKS:int = 3  # Limit per expanded function
    
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
    INTENT_RULE_BASED_THRESHOLD: int = 2  # Min keyword matches for confident classification
    INTENT_LLM_FALLBACK: bool = False  # DISABLED by default (production-safe)
    INTENT_LLM_TIMEOUT: int = 3  # Hard timeout for LLM calls (seconds)
    DEFAULT_INTENT: str = "code_search"  # Fallback intent
    
    # Phase 12A Day 3-4: Query Expansion
    ENABLE_QUERY_EXPANSION: bool = True
    EXPANSION_LLM_MODEL: str = "llama3.2"
    EXPANSION_TIMEOUT: int = 5  # Hard timeout for LLM calls (seconds)
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

