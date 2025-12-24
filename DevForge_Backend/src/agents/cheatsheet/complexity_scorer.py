"""Calculate code complexity score"""

import re
from typing import List, Dict


def calculate_complexity(code_blocks: List[str]) -> Dict:
    """
    Score code complexity based on language features.
    
    Returns:
        {
            'score': 35,
            'suggested_level': 'intermediate',
            'features': {...}
        }
    
    Args:
        code_blocks: List of code strings to analyze
        
    Returns:
        Dictionary with complexity score, suggested level, and feature counts
    """
    # Handle empty input
    if not code_blocks or all(not b.strip() for b in code_blocks):
        return {
            'score': 0,
            'suggested_level': 'beginner',
            'features': {}
        }
    
    combined_code = '\n'.join(code_blocks)
    
    # Count language features
    features = {
        'imports': len(re.findall(r'^\s*(?:import|from)\s+\w+', combined_code, re.M)),
        'functions': len(re.findall(r'^\s*def\s+\w+', combined_code, re.M)),
        'classes': len(re.findall(r'^\s*class\s+\w+', combined_code, re.M)),
        'async_functions': len(re.findall(r'async\s+def', combined_code)),
        'decorators': len(re.findall(r'^\s*@\w+', combined_code, re.M)),
        'comprehensions': len(re.findall(r'\[.+for\s+.+in\s+.+\]', combined_code)),
        'context_managers': len(re.findall(r'with\s+.+as\s+', combined_code)),
        'type_hints': len(re.findall(r':\s*(?:int|str|float|bool|list|dict|Optional|Union|List|Dict)\b', combined_code)),
        'lambda': len(re.findall(r'lambda\s+', combined_code)),
        'generators': len(re.findall(r'\(.+for\s+.+in\s+.+\)', combined_code)),
    }
    
    # Weighted scoring
    score = (
        features['imports'] * 2 +
        features['functions'] * 3 +
        features['classes'] * 5 +
        features['async_functions'] * 8 +
        features['decorators'] * 5 +
        features['comprehensions'] * 3 +
        features['context_managers'] * 6 +
        features['type_hints'] * 4 +
        features['lambda'] * 2 +
        features['generators'] * 4
    )
    
    # Ensure non-negative
    score = max(0, score)
    
    # Determine suggested level
    if score < 10:
        suggested_level = 'beginner'
    elif score < 30:
        suggested_level = 'intermediate'
    else:
        suggested_level = 'expert'
    
    return {
        'score': score,
        'suggested_level': suggested_level,
        'features': features
    }
