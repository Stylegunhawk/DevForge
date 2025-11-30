"""Prompt Refiner Agent."""

import logging
import time
from typing import Any, Dict, Optional

from src.agents.prompt_refiner.domain_handlers import DOMAIN_CONFIGS
from src.agents.prompt_refiner.enhancer import PromptEnhancer

logger = logging.getLogger(__name__)


class PromptRefinerAgent:
    """Agent for refining and optimizing user prompts."""

    def __init__(self):
        """Initialize the agent."""
        self.enhancer = PromptEnhancer()

    async def refine(
        self,
        prompt: str,
        domain: str = "general",
        skill_level: str = "intermediate",
        file_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Refine a user prompt.

        Args:
            prompt: Original user prompt.
            domain: Target domain (image, code, rag, llm).
            skill_level: User skill level.
            file_context: Optional context from files.

        Returns:
            Dictionary containing the refined prompt and metadata.
        """
        start_time = time.time()
        
        # Validate domain
        if domain not in DOMAIN_CONFIGS and domain != "general":
            logger.warning(f"Unknown domain '{domain}', defaulting to 'general'")
            domain = "general"

        logger.info(
            f"Refining prompt for domain '{domain}'",
            extra={"prompt_length": len(prompt), "skill_level": skill_level},
        )

        try:
            # Enhance prompt
            refined_prompt = await self.enhancer.enhance(
                prompt=prompt,
                domain=domain,
                skill_level=skill_level,
                file_context=file_context,
            )

            execution_time = time.time() - start_time

            result = {
                "original_prompt": prompt,
                "refined_prompt": refined_prompt,
                "domain": domain,
                "skill_level": skill_level,
                "execution_time": execution_time,
                "success": True,
            }
            
            return result

        except Exception as e:
            logger.error(f"Prompt refinement failed: {e}", exc_info=True)
            return {
                "original_prompt": prompt,
                "refined_prompt": prompt,  # Return original on error
                "domain": domain,
                "error": str(e),
                "success": False,
            }

# Global instance
prompt_refiner_agent = PromptRefinerAgent()

async def refine_prompt_invoke(
    prompt: str,
    domain: str = "general",
    skill_level: str = "intermediate",
    file_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience function to invoke the prompt refiner agent.
    
    Matches the Gateway tool signature.
    """
    result = await prompt_refiner_agent.refine(
        prompt=prompt,
        domain=domain,
        skill_level=skill_level,
        file_context=file_context,
    )
    
    # Format for Gateway response
    return {
        "success": result["success"],
        "tool": "refine_prompt",
        "data": {
            "refined_prompt": result["refined_prompt"],
            "domain": result["domain"],
        },
        "execution_time": round(result.get("execution_time", 0), 4),
        "error": result.get("error"),
    }
