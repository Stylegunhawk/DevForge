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

config = EnrichmentConfig()
