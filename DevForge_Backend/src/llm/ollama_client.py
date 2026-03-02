"""Simple Ollama client for LLM generation."""

import logging
import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

# Removed hardcoded OLLAMA_HOST, dynamically loading from settings when used


async def generate_text(prompt: str, model: str = "gpt-oss:20b-cloud", max_tokens: int = 100) -> str:
    """
    Generate text using Ollama API.
    
    Args:
        prompt: Input prompt
        model: Model name (default: cloud model)
        max_tokens: Max tokens to generate
    
    Returns:
        Generated text or empty string on error
    """
    try:
        headers = {"Authorization": f"Bearer {settings.OLLAMA_API_KEY}"} if settings.OLLAMA_API_KEY else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_HOST}/api/generate",
                headers=headers,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
    
    except Exception as e:
        logger.warning(f"Ollama generation failed: {e}, returning empty string")
        return ""
