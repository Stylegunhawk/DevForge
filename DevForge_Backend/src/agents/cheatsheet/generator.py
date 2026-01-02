"""Content generator for cheat sheets."""

from typing import List, Dict, Any
from src.agents.cheatsheet.language_profiles import LANGUAGE_PROFILES

class CheatsheetGenerator:
    """Generates cheat sheet content based on language and skill level."""
    
    def get_topics(self, language: str, skill_level: str) -> List[str]:
        """Get topics for a specific language and skill level."""
        profile = LANGUAGE_PROFILES.get(language.lower())
        if not profile:
            return []
            
        return profile["topics"].get(skill_level, [])
        
    def generate_section_content(self, language: str, topic: str, skill_level: str) -> str:
        """
        Generate content for a specific section.
        In a real implementation, this might call an LLM.
        For now, we return structured placeholders based on the profile.
        """
        profile = LANGUAGE_PROFILES.get(language.lower())
        if not profile:
            return f"Content for {topic}"
            
        syntax = profile.get("syntax", {})
        
        # Simple template-based generation for demonstration
        if "Variable" in topic:
            return f"- Declaration: `{syntax.get('variable', 'var = val')}`\n- Types: int, float, string"
        elif "Function" in topic:
            return f"- Definition: `{syntax.get('function', 'def func():')}`\n- Call: `func()`"
        elif "Class" in topic:
            return f"- Definition: `{syntax.get('class', 'class MyClass:')}`"
        elif "Print" in topic or "Output" in topic:
            return f"- Output: `{syntax.get('print', 'print()')}`"
        else:
            return f"Key concepts for {topic} in {language} ({skill_level})."

    def generate_quick_ref(self, language: str) -> List[Dict[str, str]]:
        """Generate quick reference items."""
        profile = LANGUAGE_PROFILES.get(language.lower())
        if not profile:
            return []
            
        syntax = profile.get("syntax", {})
        return [
            {"task": "Print to console", "code": syntax.get("print", "")},
            {"task": "Define variable", "code": syntax.get("variable", "")},
            {"task": "Define function", "code": syntax.get("function", "")}
        ]
