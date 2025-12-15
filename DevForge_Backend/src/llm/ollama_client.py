# Stub LLM client for testing (when Ollama not available)

import logging

logger = logging.getLogger(__name__)


async def generate_text(prompt: str, model: str = "llama3.2", max_tokens: int = 100) -> str:
    """
    Stub LLM generation for testing.
    
    In production, this would call Ollama.
    For tests without Ollama, returns empty string.
    """
    logger.warning(f"LLM stub called (Oll

ama not available): model={model}")
    return ""
