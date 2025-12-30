"""Configuration for cheatsheet enrichment."""
import os
from src.core.config import settings

class EnrichmentConfig:
    """Settings for LLM enrichment behavior."""
    
    # Feature flag (default: False for safety)
    # Controlled by env var ENABLE_LLM_ENRICHMENT via src.core.config if available,
    # or direct env var check as fallback.
    # Note: src.core.config doesn't have this field yet, so we use os.getenv for now
    # until we update the main settings class.
    ENABLED: bool = os.getenv('ENABLE_LLM_ENRICHMENT', 'false').lower() == 'true'
    
    # Fast-evolving libraries that need enrichment
    FAST_EVOLVING_LIBS = [
        'langchain',
        'langgraph', 
        'llama-index',
        'autogen',
        'crewai',
        'instructor',
        'pydantic-ai'
    ]
    
    # Libraries with FULL template coverage (skip enrichment)
    # These effectively disable enrichment even if detected, unless "latest" is explicitly requested
    FULLY_TEMPLATED_LIBS = [
        'pandas',
        'numpy',
        'fastapi',
        'flask',
        'asyncio',
        'sqlalchemy',
        # Phase C Safety: JS/TS libraries are fully templated
        'react',
        'express',
        'axios',
        'node'
    ]
    
    # Max tokens for enrichment (cost control)
    MAX_ENRICHMENT_TOKENS: int = 300
    
    # Max number of sections to enrich per request (Invariant 2: Cap enrichment fan-out)
    MAX_ENRICHED_SECTIONS: int = 2
    
    # Timeout for LLM calls (seconds) (converted to ms for internal logic if needed)
    ENRICHMENT_TIMEOUT_SECONDS: int = 5

    # --- Phase E: Hybrid LLM Configuration ---
    ENABLE_LLM_FALLBACK: bool = os.getenv('ENABLE_LLM_FALLBACK', 'true').lower() == 'true'
    ENABLE_WEB_SEARCH: bool = os.getenv('ENABLE_WEB_SEARCH', 'true').lower() == 'true'
    
    # LLM Settings
    OLLAMA_MODEL: str = os.getenv('OLLAMA_MODEL', 'gpt-oss:20b-cloud')
    LLM_CHEATSHEET_MAX_TOKENS: int = 4000
    LLM_CHEATSHEET_TEMPERATURE: float = 0.3
    
    # Validation Rules
    VALIDATION_MIN_LENGTH: int = 200
    VALIDATION_MIN_CODE_BLOCKS: int = 2

config = EnrichmentConfig()
