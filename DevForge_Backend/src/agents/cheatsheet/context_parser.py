"""Parse multi-block code context from frontend"""

import re
from typing import Dict


def parse_code_context(code_context: str) -> Dict:
    """
    Parse frontend's multi-block format.
    
    Input: "// javascript\ncode1\n\n---\n\n// javascript\ncode2"
    Output: {'blocks': [clean_code1, clean_code2], 'total_lines': N, 'has_multiple_blocks': bool, 'language_hints': ['javascript', 'javascript']}
    
    Args:
        code_context: Raw code context string from frontend
        
    Returns:
        Dictionary with parsed blocks, line count, multi-block flag, and language hints
    """
    # Handle empty/None
    if not code_context or code_context.strip() == '':
        return {
            'blocks': [],
            'total_lines': 0,
            'has_multiple_blocks': False,
            'language_hints': []
        }
    
    # Check for separator
    if '\n\n---\n\n' not in code_context:
        # Single block without separator
        lang_match = re.match(r'^//\s*(\w+)\s*\n', code_context)
        language_hint = lang_match.group(1).lower() if lang_match else None
        clean = re.sub(r'^//\s*\w+\s*\n', '', code_context, count=1).strip()
        return {
            'blocks': [clean] if clean else [],
            'total_lines': clean.count('\n') + 1 if clean else 0,
            'has_multiple_blocks': False,
            'language_hints': [language_hint] if language_hint else []
        }
    
    # Multi-block: split and clean
    raw_blocks = code_context.split('\n\n---\n\n')
    clean_blocks = []
    language_hints = []
    
    for block in raw_blocks:
        # Extract language hint before removing it
        lang_match = re.match(r'^//\s*(\w+)\s*\n', block)
        language_hint = lang_match.group(1).lower() if lang_match else None
        
        # Remove "// language" prefix
        clean = re.sub(r'^//\s*\w+\s*\n', '', block, count=1).strip()
        if clean:  # Skip empty blocks
            clean_blocks.append(clean)
            language_hints.append(language_hint)
    
    total_lines = sum(block.count('\n') + 1 for block in clean_blocks)
    
    return {
        'blocks': clean_blocks,
        'total_lines': total_lines,
        'has_multiple_blocks': len(clean_blocks) > 1,
        'language_hints': language_hints
    }
