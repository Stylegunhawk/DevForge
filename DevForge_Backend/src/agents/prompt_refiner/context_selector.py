"""Context selector for deterministic tech stack selection.

Prioritizes explicit project files over conversation history to resolve conflicts.
"""

import logging
from typing import Dict, Any, Optional
from src.agents.prompt_refiner.context_types import CodeContext

logger = logging.getLogger(__name__)


class ContextSelector:
    """Selects the definitive tech stack from available context sources."""

    def select_stack(self, context: CodeContext) -> Dict[str, Any]:
        """Select the tech stack based on priority rules.
        
        Priority:
        1. Dependency Analysis (if available) - Hard evidence
        2. Code Structure (imports/classes) - Strong evidence
        3. Conversation History - Soft evidence
        
        Args:
            context: Unified CodeContext object
            
        Returns:
            Dictionary with selected language, frameworks, and database
        """
        selected_stack = {
            "language": "unknown",
            "frameworks": [],
            "database": "unknown",
            "source": "unknown"
        }
        
        # 1. Check Dependency Analysis (if we had it attached to context)
        # Note: In this phase, we assume dependency info might be merged into context.frameworks
        # or we rely on code structure if explicit deps aren't there yet.
        
        # 2. Check Code Structure (Imports are strong indicators)
        code_lang = context.detected_language
        if code_lang and code_lang != "unknown":
            selected_stack["language"] = code_lang
            selected_stack["source"] = "code_analysis"
        
        # Infer frameworks from imports/classes
        code_frameworks = self._infer_frameworks_from_code(context)
        if code_frameworks:
            selected_stack["frameworks"].extend(code_frameworks)
            selected_stack["source"] = "code_analysis"

        # 3. Check Conversation (Fill gaps or override if empty)
        conv_lang = self._infer_language_from_conversation(context)
        if selected_stack["language"] == "unknown" and conv_lang:
            selected_stack["language"] = conv_lang
            selected_stack["source"] = "conversation"
            
        if not selected_stack["frameworks"]:
            selected_stack["frameworks"] = context.conversation.technologies
            if selected_stack["frameworks"]:
                selected_stack["source"] = "conversation"
        
        # Deduplicate
        selected_stack["frameworks"] = sorted(list(set(selected_stack["frameworks"])))
        
        logger.info(
            "Selected tech stack",
            extra={
                "stack": selected_stack,
                "context_has_code": bool(context.code_structure.classes),
                "context_has_conv": bool(context.conversation.technologies)
            }
        )
        
        return selected_stack

    def _infer_frameworks_from_code(self, context: CodeContext) -> list:
        """Infer frameworks based on imports and class names."""
        frameworks = []
        imports = " ".join(context.code_structure.imports).lower()
        
        if "fastapi" in imports:
            frameworks.append("FastAPI")
        if "flask" in imports:
            frameworks.append("Flask")
        if "django" in imports:
            frameworks.append("Django")
        if "react" in imports:
            frameworks.append("React")
            
        return frameworks

    def _infer_language_from_conversation(self, context: CodeContext) -> Optional[str]:
        """Guess language from conversation keywords."""
        techs = [t.lower() for t in context.conversation.technologies]
        if "python" in techs or "fastapi" in techs or "django" in techs:
            return "python"
        if "javascript" in techs or "react" in techs or "node" in techs:
            return "javascript"
        if "typescript" in techs:
            return "typescript"
        return None
