"""Simple Ollama client for LLM generation."""

import logging
import httpx

logger = logging.getLogger(__name__)

OLLAMA_HOST = "http://localhost:11434"


async def generate_text(prompt: str, model: str = "gpt-oss:20b-cloud", max_tokens: int = 100) -> str:
    """
    Generate text using Ollama API with dynamic timeout.
    
    Args:
        prompt: Input prompt
        model: Model name
        max_tokens: Max tokens to generate
    
    Returns:
        Generated text
        
    Raises:
        RuntimeError: If generation fails
    """
    # Dynamic timeout: 0.5s per token + 30s buffer
    timeout = max(60.0, (max_tokens * 0.5) + 30)
    
    logger.info(f"Generating {max_tokens} tokens (timeout: {timeout}s)")
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
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
            
            generated = result.get("response", "")
            
            if not generated:
                raise RuntimeError("Ollama returned empty response")
            
            logger.info(f"✅ Generated {len(generated)} chars")
            return generated
    
    except httpx.TimeoutException:
        logger.error(f"❌ Timeout after {timeout}s")
        raise RuntimeError(f"Ollama timeout (>{timeout}s). Reduce max_tokens or use faster model.")
    
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ HTTP {e.response.status_code}")
        raise RuntimeError(f"Ollama API error: {e.response.status_code}")
    
    except Exception as e:
        logger.error(f"❌ {type(e).__name__}: {e}")
        raise RuntimeError(f"Ollama failed: {e}")
