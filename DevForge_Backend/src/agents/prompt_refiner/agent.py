"""Prompt Refiner Agent."""

import logging
import time
from typing import Any, Dict, Optional, List

from src.agents.prompt_refiner.domain_handlers import DOMAIN_CONFIGS
from src.agents.prompt_refiner.enhancer import PromptEnhancer
from src.agents.prompt_refiner.conversation_parser import ConversationParser
from src.agents.prompt_refiner.code_parser import CodeParser
from src.agents.prompt_refiner.context_types import CodeContext

logger = logging.getLogger(__name__)


class PromptRefinerAgent:
    """Agent for refining and optimizing user prompts."""

    def __init__(self):
        """Initialize the agent."""
        self.enhancer = PromptEnhancer()
        self.conversation_parser = ConversationParser()
        self.code_parser = CodeParser()

    async def refine(
        self,
        prompt: str,
        domain: str = "general",
        skill_level: str = "intermediate",
        file_context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        attached_files: Optional[List[str]] = None,
        project_files: Optional[Dict[str, str]] = None,
        tenant_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        user_id: str = None  # NEW: Phase 4 analytics support
    ) -> Dict[str, Any]:
        """Refine a user prompt.

        Args:
            prompt: Original user prompt.
            domain: Target domain (image, code, rag, llm).
            skill_level: User skill level.
            file_context: Optional context from files.
            conversation_history: Optional list of recent messages.
            attached_files: Optional list of code file contents.
            project_files: Optional dict of project files (requirements.txt, etc).

        Returns:
            Dictionary containing the refined prompt and metadata.
        """
        start_time = time.time()

        # Validate prompt
        if not prompt or not prompt.strip():
            logger.warning("refine_prompt called with empty prompt")
            return {
                "original_prompt": prompt or "",
                "refined_prompt": prompt or "",
                "domain": domain,
                "error": "Prompt is empty. Provide a non-empty prompt to refine.",
                "success": False,
            }

        # Validate domain
        if domain not in DOMAIN_CONFIGS and domain != "general":
            logger.warning(f"Unknown domain '{domain}', defaulting to 'general'")
            domain = "general"

        logger.info(
            f"Refining prompt for domain '{domain}'",
            extra={"prompt_length": len(prompt), "skill_level": skill_level},
        )

        try:
            # Gather context for code domain
            code_context = None
            if domain == "code" and (conversation_history or attached_files):
                code_context = self._gather_context(
                    conversation_history=conversation_history or [],
                    attached_files=attached_files or [],
                    file_context=file_context,
                )
                
                if code_context and code_context.has_context():
                    logger.info(
                        "Using context-aware refinement",
                        extra={
                            "technologies": code_context.conversation.technologies,
                            "classes": len(code_context.code_structure.classes),
                            "functions": len(code_context.code_structure.functions),
                        }
                    )
            
            # Enhance prompt
            enhancement_result = await self.enhancer.enhance(
                prompt=prompt,
                domain=domain,
                skill_level=skill_level,
                file_context=file_context,
                code_context=code_context,
                project_files=project_files,
                tenant_id=tenant_id,
                integration_name=integration_name,
                user_id=user_id  # NEW: Pass user_id to enhancer
            )

            execution_time = time.time() - start_time

            result = {
                "original_prompt": prompt,
                "refined_prompt": enhancement_result["refined_prompt"],
                "context_summary": enhancement_result.get("context_summary"),
                "chosen_stack": enhancement_result.get("chosen_stack"),
                "sanitization_log": enhancement_result.get("sanitization_log", []),
                "quality": enhancement_result.get("quality"),
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
    
    def _gather_context(
        self,
        conversation_history: List[Dict[str, str]],
        attached_files: List[str],
        file_context: Optional[str],
    ) -> CodeContext:
        """Gather context from conversation and code files.
        
        Args:
            conversation_history: Recent conversation messages
            attached_files: List of code file contents
            file_context: Optional additional file context
            
        Returns:
            CodeContext with parsed information
        """
        context = CodeContext()
        
        try:
            # Parse conversation history
            if conversation_history:
                context.conversation = self.conversation_parser.extract_context(
                    conversation_history
                )
                context.frameworks = context.conversation.technologies
                context.recent_context = self.conversation_parser._create_summary(
                    conversation_history, 
                    context.conversation.technologies
                )
            
            # Parse code files
            all_code = []
            if attached_files:
                all_code.extend(attached_files)
            if file_context:
                all_code.append(file_context)
            
            if all_code:
                # Combine and parse all code
                combined_code = "\n\n".join(all_code)
                context.code_structure = self.code_parser.parse_file(combined_code)
                context.detected_language = context.code_structure.language
            
        except Exception as e:
            logger.warning(f"Context gathering failed: {e}", exc_info=True)
        
        return context

# Global instance
prompt_refiner_agent = PromptRefinerAgent()

async def refine_prompt_invoke(
    arguments: dict,
    tenant_id: str = "unknown",
    integration_name: str = "unknown",
    user_id: str = None  # NEW: Phase 4 analytics support
) -> Dict[str, Any]:
    """Convenience function to invoke the prompt refiner agent.
    
    Matches the Gateway tool signature - accepts dict of arguments.
    
    Args:
        arguments: Dictionary containing prompt, domain, skill_level, file_context
    """
    result = await prompt_refiner_agent.refine(
        prompt=arguments.get("prompt"),
        domain=arguments.get("domain", "general"),
        skill_level=arguments.get("skill_level", "intermediate"),
        file_context=arguments.get("file_context"),
        conversation_history=arguments.get("conversation_history"),
        attached_files=arguments.get("attached_files"),
        project_files=arguments.get("project_files"),
        tenant_id=tenant_id,
        integration_name=integration_name,
        user_id=user_id  # NEW: Pass user_id to agent
    )
    
    # Format for Gateway response
    return {
        "success": result["success"],
        "tool": "refine_prompt",
        "data": {
            "refined_prompt": result["refined_prompt"],
            "context_summary": result.get("context_summary"),
            "chosen_stack": result.get("chosen_stack"),
            "sanitization_log": result.get("sanitization_log", []),
            "quality": result.get("quality"),
            "domain": result["domain"],
        },
        "execution_time": round(result.get("execution_time", 0), 4),
        "error": result.get("error"),
    }
