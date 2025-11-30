"""Prompt enhancement logic using LLM."""

import logging
from typing import Optional

from src.agents.prompt_refiner.templates import TEMPLATES
from src.core.model_router import model_router

logger = logging.getLogger(__name__)


class PromptEnhancer:
    """Enhances prompts using LLM and domain-specific templates."""

    def __init__(self):
        """Initialize the enhancer."""
        pass

    async def enhance(
        self,
        prompt: str,
        domain: str = "general",
        skill_level: str = "intermediate",
        file_context: Optional[str] = None,
    ) -> str:
        """Enhance a prompt based on domain and context.

        Args:
            prompt: Original user prompt.
            domain: Target domain (image, code, rag, llm).
            skill_level: User skill level.
            file_context: Optional context from files.

        Returns:
            Refined prompt string.
        """
        try:
            # Select appropriate template
            template = TEMPLATES.get(domain, TEMPLATES["general"])

            # Format the prompt
            formatted_prompt = template.format(
                prompt=prompt,
                domain=domain,
                skill_level=skill_level,
                file_context=file_context or "None",
            )

            # Select model for refinement (using a capable model for instruction following)
            # Using 'routing' task profile usually gives a smart, fast model (e.g. deepseek-r1 or similar)
            # Or we can explicitly ask for a chat model.
            model_name = model_router.select_model_by_task("chat")
            chat_model = model_router.get_chat_model(model_name)

            logger.info(
                f"Enhancing prompt for domain '{domain}' using model '{model_name}'",
                extra={"original_length": len(prompt), "context_length": len(file_context) if file_context else 0},
            )

            # Invoke LLM
            response = await chat_model.ainvoke([{"role": "user", "content": formatted_prompt}])
            
            refined_prompt = response.content.strip() if hasattr(response, "content") else str(response).strip()

            logger.info(
                "Prompt enhanced successfully",
                extra={"refined_length": len(refined_prompt)},
            )

            return refined_prompt

        except Exception as e:
            logger.error(f"Prompt enhancement failed: {e}", exc_info=True)
            # Fallback: return original prompt
            return prompt
