"""Simple Ollama client for LLM generation."""

import logging
import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

_DIRECT_OUTPUT_SYSTEM_PROMPT = (
    "Respond concisely and directly. "
    "Output only what is requested — no reasoning, no explanation, no preamble."
)


async def generate_text(
    prompt: str,
    model: str = "gpt-oss:20b-cloud",
    max_tokens: int = 100,
    system_prompt: str = _DIRECT_OUTPUT_SYSTEM_PROMPT,
) -> str:
    """
    Generate text using Ollama chat API.

    Uses /api/chat so thinking models (e.g. gpt-oss:120b-cloud) put their
    answer in message.content rather than the reasoning-only thinking field.

    Args:
        prompt: User prompt
        model: Model name
        max_tokens: Max tokens to generate
        system_prompt: System prompt (defaults to concise-output instruction)

    Returns:
        Generated text or empty string on error
    """
    try:
        headers = {"Authorization": f"Bearer {settings.OLLAMA_API_KEY}"} if settings.OLLAMA_API_KEY else {}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_HOST}/api/chat",
                headers=headers,
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7,
                    },
                },
            )
            response.raise_for_status()
            result = response.json()
            message = result.get("message", {})
            # content is the primary output; thinking models may leave it empty
            text = message.get("content", "")
            if not text:
                text = message.get("thinking", "")
            return text

    except Exception as e:
        logger.warning(f"Ollama generation failed: {e}, returning empty string")
        return ""
