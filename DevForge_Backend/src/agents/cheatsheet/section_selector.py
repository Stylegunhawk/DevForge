"""Select most relevant sections based on context"""

import logging
from typing import List, Dict
from .enhanced_templates import BASE_TEMPLATES, LIBRARY_SECTIONS

logger = logging.getLogger(__name__)


def select_sections(
    language: str,
    skill_level: str,
    detected_libraries: List[str],
    complexity_score: int
) -> List[Dict]:
    """
    Choose 5-7 most relevant sections.
    
    Priority:
    1. Library-specific sections (if detected)
    2. Complexity-appropriate base sections
    3. General language topics
    4. FALLBACK: Never return empty (use beginner basics)
    
    Args:
        language: Programming language (e.g., 'python')
        skill_level: 'beginner', 'intermediate', or 'expert'
        detected_libraries: List of detected library names
        complexity_score: Numeric complexity score
        
    Returns:
        List of section dictionaries with title, explanation, examples, etc.
        GUARANTEED: Never returns empty list.
    """
    sections = []
    
    # 1. Add library sections (highest priority)
    for lib in detected_libraries:
        if lib in LIBRARY_SECTIONS:
            lib_section = LIBRARY_SECTIONS[lib].get(skill_level)
            if lib_section:
                sections.append(lib_section)
                logger.info(f"Added library section: {lib} ({skill_level})")
            if len(sections) >= 3:  # Max 3 library sections
                break
    
    # 2. Get base sections for language/skill
    if language in BASE_TEMPLATES:
        base_sections = BASE_TEMPLATES[language].get(skill_level, {})
        
        # Choose topics - PRIORITY: strictly follow skill_level
        if skill_level == 'beginner':
            # Simple: fundamentals only
            priority = ['variables', 'control_flow', 'functions', 'basic_io']
        elif skill_level == 'intermediate':
            if language in ['javascript', 'typescript']:
                priority = ['async_flow', 'data_structures', 'modules', 'error_handling']
            else: # python default
                priority = ['data_structures', 'file_io', 'error_handling', 'modules']
        else:  # expert
            if language == 'typescript':
                priority = ['typing', 'decorators', 'generators', 'classes']
            elif language == 'javascript':
                priority = ['async_flow', 'classes', 'closures', 'event_loop']
            else: # python default
                priority = ['decorators', 'generators', 'context_managers', 'classes']
        
        # Add base sections until we have 5-7 total
        for topic in priority:
            if topic in base_sections and len(sections) < 7:
                sections.append(base_sections[topic])
                logger.info(f"Added base section: {topic}")
    
    # 3. SAFETY NET: Never return empty
    if not sections:
        logger.warning(f"No sections found for {language}/{skill_level}. "
                      f"Using fallback to Python beginner basics.")
        
        # Emergency fallback: Try requested language beginner first, then Python
        fallback_base = BASE_TEMPLATES.get(language, {}).get('beginner', {})
        if not fallback_base:
            fallback_base = BASE_TEMPLATES.get('python', {}).get('beginner', {})
            
        if fallback_base:
            # Take first 3 sections as minimal fallback
            # Generic keys often shared
            common_keys = ['variables', 'control_flow', 'functions']
            for key in common_keys:
                if key in fallback_base:
                    sections.append(fallback_base[key])
                    if len(sections) >= 3:
                        break
    
    return sections[:7]  # Hard limit of 7 sections
