"""Formatter for cheat sheets."""

from jinja2 import Template
from src.tools.cheatsheet.templates import CHEATSHEET_TEMPLATE

class CheatsheetFormatter:
    """Formats cheat sheet content into Markdown."""
    
    def format_markdown(self, data: dict) -> str:
        """
        Format the cheat sheet data into a markdown string.
        
        Args:
            data: Dictionary containing:
                - language
                - skill_level
                - sections (list of dicts with title, content)
                - quick_refs (list of dicts with task, code)
        """
        template = Template(CHEATSHEET_TEMPLATE)
        return template.render(
            language=data.get("language", "Unknown"),
            skill_level=data.get("skill_level", "beginner"),
            sections=data.get("sections", []),
            quick_refs=data.get("quick_refs", [])
        )
