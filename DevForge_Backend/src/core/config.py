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
    GITHUB_MODEL: str = "qwen3-coder:480b-cloud"

    # Phase 3: Premium reasoning model
    PREMIUM_MODEL: str = "deepseek-v3.1:671b-cloud"

    # Phase 3: Embedding model
    EMBEDDING_MODEL: str = "bge-m3"

    # Optional: GitHub Integration (Phase 3)
    GITHUB_TOKEN: str | None = None

    # Optional: Database (Future phases)
    DATABASE_URL: str | None = None

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

