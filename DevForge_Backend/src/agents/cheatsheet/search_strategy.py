"""Strategy for generating effective search queries.

Converts user intent + context into targeted search queries
to retrieve high-quality documentation.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


class SearchQueryStrategy:
    """Generates targeted search queries for documentation."""
    
    def build_queries(
        self,
        original_query: str,
        detected_language: str,
        detected_libraries: List[str],
        skill_level: str
    ) -> List[str]:
        """
        Build a list of search queries to fetch relevant documentation.
        
        Args:
            original_query: User's original request
            detected_language: Target language (e.g. 'python')
            detected_libraries: List of libraries in context
            skill_level: 'beginner', 'intermediate', 'expert'
            
        Returns:
            List of 1-3 query strings
        """
        queries = []
        
        # 1. Primary Query: Intent + Language
        # Clean up query
        base_query = original_query.strip()
        
        # If query is very short/vague, augment it
        if len(base_query.split()) < 3:
            queries.append(f"{base_query} {detected_language} cheatsheet")
        else:
            queries.append(f"{base_query} {detected_language}")
            
        # 2. Library specific (Highest Value)
        for lib in detected_libraries[:2]:  # Focus on top 2 libs
            # Add "latest" to capture recent changes for fast-evolving libs
            queries.append(f"{lib} latest documentation {detected_language}")
            
            # If specific task derived from query?
            # For now, generic doc search is safest
            
        # 3. Specific patterns based on skill level
        if skill_level == 'expert':
            queries.append(f"{detected_language} advanced patterns best practices")
        
        # Deduplicate and limit
        unique_queries = list(dict.fromkeys(queries))
        return unique_queries[:3]  # Max 3 queries per request
