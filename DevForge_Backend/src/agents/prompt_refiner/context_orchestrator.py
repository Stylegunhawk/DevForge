"""Context orchestrator for managing token budget.

Selects and assembles the most relevant context within token limits.
"""

import logging
from typing import Dict, Any, List
from src.agents.prompt_refiner.context_types import CodeContext

logger = logging.getLogger(__name__)


class ContextOrchestrator:
    """Orchestrates context assembly within token budget."""

    MAX_TOKENS = 4000  # Conservative limit for context
    CHARS_PER_TOKEN = 4  # Rough estimation

    def assemble_context(self, stack: Dict[str, Any], context: CodeContext) -> str:
        """Assemble final context string respecting token limits.
        
        Priority:
        1. Tech Stack Summary (High)
        2. Code Structure Summary (Medium)
        3. Recent Conversation (Low)
        
        Args:
            stack: Selected tech stack
            context: Unified CodeContext
            
        Returns:
            Formatted context string
        """
        parts = []
        current_chars = 0
        max_chars = self.MAX_TOKENS * self.CHARS_PER_TOKEN

        # 1. Tech Stack (Always include)
        stack_str = self._format_stack(stack)
        parts.append(stack_str)
        current_chars += len(stack_str)

        # 2. Code Structure (Include as much as possible)
        structure_str = self._format_structure(context)
        if current_chars + len(structure_str) < max_chars:
            parts.append(structure_str)
            current_chars += len(structure_str)
        else:
            # Truncate structure if needed
            available = max_chars - current_chars
            parts.append(structure_str[:available] + "...[TRUNCATED]")
            return "\n\n".join(parts)

        # 3. Recent Conversation (Fill remaining space)
        if context.recent_context:
            conv_str = f"RECENT CONVERSATION:\n{context.recent_context}"
            if current_chars + len(conv_str) < max_chars:
                parts.append(conv_str)
            else:
                available = max_chars - current_chars
                if available > 100:  # Only include if meaningful space remains
                    parts.append(conv_str[:available] + "...")

        return "\n\n".join(parts)

    def _format_stack(self, stack: Dict[str, Any]) -> str:
        """Format tech stack info."""
        lines = ["DETECTED TECH STACK:"]
        if stack.get("language"):
            lines.append(f"- Language: {stack['language']}")
        if stack.get("frameworks"):
            lines.append(f"- Frameworks: {', '.join(stack['frameworks'])}")
        if stack.get("database") and stack["database"] != "unknown":
            lines.append(f"- Database: {stack['database']}")
        return "\n".join(lines)

    def _format_structure(self, context: CodeContext) -> str:
        """Format code structure info."""
        lines = ["CODE STRUCTURE:"]
        if context.code_structure.classes:
            lines.append(f"- Classes: {', '.join(context.code_structure.classes)}")
        if context.code_structure.functions:
            lines.append(f"- Functions: {', '.join(context.code_structure.functions)}")
        if context.code_structure.conventions:
            lines.append(f"- Conventions: {context.code_structure.conventions}")
        return "\n".join(lines)
