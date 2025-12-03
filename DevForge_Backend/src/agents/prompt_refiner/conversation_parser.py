"""Conversation parser for extracting context from chat history.

Analyzes conversation messages to extract technologies, project type, and preferences.
"""

import re
import logging
from typing import List, Dict, Any

from src.agents.prompt_refiner.context_types import ConversationContext

logger = logging.getLogger(__name__)


class ConversationParser:
    """Parse conversation history to extract project context."""
    
    # Technology keywords and their categories
    TECH_KEYWORDS = {
        # Python frameworks
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
        "pyramid": "Pyramid",
        
        # JavaScript frameworks
        "react": "React",
        "vue": "Vue.js",
        "angular": "Angular",
        "next": "Next.js",
        "express": "Express.js",
        "nest": "NestJS",
        
        # Databases
        "postgresql": "PostgreSQL",
        "postgres": "PostgreSQL",
        "mysql": "MySQL",
        "mongodb": "MongoDB",
        "redis": "Redis",
        "sqlite": "SQLite",
        
        # ORMs
        "sqlalchemy": "SQLAlchemy",
        "prisma": "Prisma",
        "mongoose": "Mongoose",
        
        # Other
        "typescript": "TypeScript",
        "graphql": "GraphQL",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "aws": "AWS",
        "gcp": "Google Cloud",
    }
    
    # Project type patterns
    PROJECT_PATTERNS = {
        r"(rest|api|backend|server)": "REST API",
        r"(frontend|ui|spa|web app)": "Frontend Application",
        r"(full.?stack)": "Full-Stack Application",
        r"(cli|command.?line|tool)": "CLI Tool",
        r"(microservice)": "Microservice",
        r"(library|package|sdk)": "Library/SDK",
    }
    
    def extract_context(self, messages: List[Dict[str, str]]) -> ConversationContext:
        """Extract context from conversation messages.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            
        Returns:
            ConversationContext with extracted information
        """
        if not messages:
            return ConversationContext()
        
        # Limit to last 5 messages
        recent_messages = messages[-5:] if len(messages) > 5 else messages
        
        # Combine all message content
        combined_text = " ".join(
            msg.get("content", "") 
            for msg in recent_messages 
            if msg.get("content")
        ).lower()
        
        # Extract technologies
        technologies = self._extract_technologies(combined_text)
        
        # Identify project type
        project_type = self._identify_project_type(combined_text)
        
        # Extract recent work
        recent_work = self._extract_recent_work(recent_messages)
        
        # Detect preferences
        preferences = self._detect_preferences(combined_text)
        
        # Create summary for recent context
        recent_context = self._create_summary(recent_messages, technologies)
        
        context = ConversationContext(
            project_type=project_type,
            technologies=technologies,
            recent_work=recent_work,
            preferences=preferences,
        )
        
        logger.info(
            f"Extracted conversation context",
            extra={
                "project_type": project_type,
                "tech_count": len(technologies),
                "technologies": technologies[:5],
            }
        )
        
        return context
    
    def _extract_technologies(self, text: str) -> List[str]:
        """Extract mentioned technologies from text."""
        found_tech = set()
        
        for keyword, tech_name in self.TECH_KEYWORDS.items():
            if keyword in text:
                found_tech.add(tech_name)
        
        return sorted(list(found_tech))
    
    def _identify_project_type(self, text: str) -> str:
        """Identify project type from conversation."""
        for pattern, project_type in self.PROJECT_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                return project_type
        
        return "Unknown"
    
    def _extract_recent_work(self, messages: List[Dict[str, str]]) -> List[str]:
        """Extract mentions of recent work/features."""
        work_patterns = [
            r"(created?|built|implemented|added|developed)\s+(\w+(?:\s+\w+){0,3})",
            r"(working on|building)\s+(\w+(?:\s+\w+){0,3})",
        ]
        
        recent_work = []
        
        for msg in messages:
            content = msg.get("content", "")
            for pattern in work_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    work_item = match.group(2).strip()
                    if len(work_item) > 3:  # Filter out very short matches
                        recent_work.append(work_item)
        
        return recent_work[:5]  # Limit to 5 items
    
    def _detect_preferences(self, text: str) -> Dict[str, Any]:
        """Detect coding preferences from conversation."""
        preferences = {}
        
        # Async preference
        if "async" in text or "await" in text or "asyncio" in text:
            preferences["async"] = True
        
        # Testing preference
        if "test" in text or "pytest" in text or "jest" in text:
            preferences["testing"] = True
        
        # Type hints preference
        if "type hint" in text or "mypy" in text or "typescript" in text:
            preferences["type_hints"] = True
        
        return preferences
    
    def _create_summary(self, messages: List[Dict[str, str]], technologies: List[str]) -> str:
        """Create a brief summary of recent conversation."""
        if not messages:
            return ""
        
        # Get last user message
        user_messages = [m for m in messages if m.get("role") == "user"]
        last_user_msg = user_messages[-1].get("content", "") if user_messages else ""
        
        tech_str = ", ".join(technologies[:3]) if technologies else "general development"
        
        summary = f"Working with {tech_str}."
        if last_user_msg:
            summary += f" Recent focus: {last_user_msg[:100]}..."
        
        return summary
