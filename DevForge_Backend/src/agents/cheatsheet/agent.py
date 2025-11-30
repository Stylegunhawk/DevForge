from typing import List, Optional, Dict, Any
from src.agents.cheatsheet.generator import CheatsheetGenerator
from src.agents.cheatsheet.formatter import CheatsheetFormatter
from src.agents.cheatsheet.language_profiles import LANGUAGE_PROFILES
from src.tools.cheatsheet.tools import detect_language_from_code

class CheatsheetAgent:
    """Agent for generating dynamic cheat sheets."""
    
    def __init__(self):
        self.generator = CheatsheetGenerator()
        self.formatter = CheatsheetFormatter()
        
    async def generate(self,
        language: Optional[str] = None,
        skill_level: str = "beginner",
        code_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a cheat sheet.
        
        Args:
            language: Target programming language (optional if code_context provided)
            skill_level: Skill level (beginner, intermediate, expert)
            code_context: Optional code snippet to detect language
            
        Returns:
            Dictionary containing success status and generated content.
        """
        # 1. Detect language
        if not language and code_context:
            language = detect_language_from_code(code_context)
        
        if not language:
            language = "python"  # Default
            
        language_key = language.lower()
        
        # Get display name from profile
        profile = LANGUAGE_PROFILES.get(language_key)
        display_name = profile["name"] if profile else language.capitalize()
        
        # 2. Get topics and generate content
        topics = self.generator.get_topics(language_key, skill_level)
        sections = []
        
        for topic in topics:
            content = self.generator.generate_section_content(language_key, topic, skill_level)
            sections.append({"title": topic, "content": content})
            
        # 3. Get quick reference
        quick_refs = self.generator.generate_quick_ref(language_key)
        
        # 4. Format output
        data = {
            "language": display_name,
            "skill_level": skill_level,
            "sections": sections,
            "quick_refs": quick_refs
        }
        
        markdown_content = self.formatter.format_markdown(data)
        
        return {
            "success": True,
            "language": language_key,
            "skill_level": skill_level,
            "markdown": markdown_content,
            "data": data
        }

# Global instance
cheatsheet_agent = CheatsheetAgent()

async def generate_cheatsheet_invoke(args: dict) -> dict:
    """Wrapper for MCP Gateway invocation."""
    language = args.get("language")
    skill_level = args.get("skill_level", "beginner")
    code_context = args.get("code_context")
    
    result = await cheatsheet_agent.generate(
        language=language,
        skill_level=skill_level,
        code_context=code_context
    )
    
    return {
        "success": result["success"],
        "data": result,
        "format": "markdown"
    }
