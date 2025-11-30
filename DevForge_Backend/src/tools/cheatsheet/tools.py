"""Helper tools for cheat sheet agent."""

import re
from typing import Optional

def detect_language_from_code(code: str) -> str:
    """
    Detect programming language from code snippet using simple heuristics.
    """
    code = code.strip()
    
    # Python
    if re.search(r'def\s+\w+\s*\(|import\s+\w+|from\s+\w+\s+import|print\(', code):
        return "python"
        
    # JavaScript/TypeScript
    if re.search(r'function\s+\w+\s*\(|const\s+\w+\s*=|let\s+\w+\s*=|console\.log\(', code):
        if re.search(r':\s*\w+(\[\])?\s*[=,)]|interface\s+\w+', code):
            return "typescript"
        return "javascript"
        
    # Default fallback
    return "python"

def format_code_block(code: str, language: str) -> str:
    """Format code into a markdown block."""
    return f"```{language}\n{code}\n```"
