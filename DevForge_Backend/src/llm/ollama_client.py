"""Simple Ollama client for LLM generation."""

import logging
import httpx

logger = logging.getLogger(__name__)

OLLAMA_HOST = "http://localhost:11434"


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
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{OLLAMA_HOST}/api/generate",
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
