"""Enhanced cheatsheet agent with context awareness"""

import logging
from typing import Dict, Any, Optional

from src.agents.cheatsheet.context_parser import parse_code_context
from src.agents.cheatsheet.library_detector import detect_libraries
from src.agents.cheatsheet.complexity_scorer import calculate_complexity
from src.agents.cheatsheet.section_selector import select_sections
from src.agents.cheatsheet.quick_reference import generate_quick_reference
from src.tools.cheatsheet.tools import detect_language_from_code

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CheatsheetAgent:
    """Generate context-aware programming cheatsheets"""
    
    def generate(self, arguments: dict) -> dict:
        """
        Main generation logic with context awareness.
        
        Args:
            arguments: {
                'language': Optional[str],
                'skill_level': str,
                'code_context': Optional[str]
            }
            
        Returns:
            {
                'success': bool,
                'language': str,
                'skill_level': str,
                'markdown': str,
                'data': {...}
            }
        """
        # Extract parameters
        explicit_language = arguments.get('language')
        skill_level = str(arguments.get('skill_level', 'beginner')).lower()
        code_context = arguments.get('code_context')
        
        logger.info(f"Request: language={explicit_language}, "
                   f"skill_level={skill_level}, "
                   f"has_context={bool(code_context)}")
        
        # 1. Parse code context
        parsed = None
        if code_context:
            parsed = parse_code_context(code_context)
            logger.info(f"Parsed: {len(parsed['blocks'])} blocks, "
                       f"{parsed['total_lines']} lines")
        
        # 2. Detect libraries
        detected_libraries = []
        if parsed and parsed['blocks']:
            detected_libraries = detect_libraries(parsed['blocks'])
            logger.info(f"Detected libraries: {detected_libraries}")
        
        # 3. Calculate complexity
        complexity = {'score': 0, 'suggested_level': 'beginner', 'features': {}}
        if parsed and parsed['blocks']:
            complexity = calculate_complexity(parsed['blocks'])
            logger.info(f"Complexity: score={complexity['score']}, "
                       f"suggested={complexity['suggested_level']}")
        
        # 4. Determine language (explicit param wins)
        language = None
        if explicit_language:
            language = explicit_language
            logger.info(f"Using explicit language: {language}")
        elif parsed and parsed['blocks']:
            language = detect_language_from_code(parsed['blocks'][0])
            logger.info(f"Auto-detected language: {language}")
        else:
            return {
                'success': False,
                'message': 'Must provide language or code_context',
                'hint': 'Add "language": "python" to your request'
            }
        
        # Validate language
        if not language:
            return {
                'success': False,
                'message': 'Could not detect language from code context',
                'hint': 'Provide explicit "language" parameter'
            }
        
        language_key = language.lower()
        
        # 5. Select sections
        sections = select_sections(
            language=language_key,
            skill_level=skill_level,
            detected_libraries=detected_libraries,
            complexity_score=complexity['score']
        )
        
        logger.info(f"Selected {len(sections)} sections")
        
        # 6. Assemble markdown
        markdown = self._assemble_markdown(
            language=language_key,
            skill_level=skill_level,
            sections=sections
        )
        
        # 7. Generate quick reference
        quick_ref = generate_quick_reference(
            language=language_key,
            skill_level=skill_level,
            detected_libraries=detected_libraries
        )
        
        # Combine markdown and quick reference
        full_markdown = markdown + '\n' + quick_ref
        
        # 8. Return enhanced response
        # Determine which detected libraries have template support
        supported_libs = [lib for lib in detected_libraries if lib in['pandas', 'fastapi', 'asyncio']]
        
        logger.info(f"Delivering skill: {skill_level} (Requested: {arguments.get('skill_level', 'beginner')})")
        
        return {
            'success': True,
            'language': language_key,
            'skill_level': skill_level,
            'markdown': full_markdown,
            'data': {
                'language': language_key.title(),
                'skill_level': skill_level,
                'detected_libraries': detected_libraries,
                'supported_libraries': supported_libs,
                'complexity_score': complexity['score'],
                'sections': [{'title': s['title']} for s in sections]
            }
        }
    
    def _assemble_markdown(
        self,
        language: str,
        skill_level: str,
        sections: list
    ) -> str:
        """Combine sections into final markdown"""
        lines = [f"# {language.title()} Cheat Sheet - {skill_level.title()}\n"]
        
        for i, section in enumerate(sections, 1):
            # Section header
            lines.append(f"\n## {i}. {section['title']}")
            lines.append(section['explanation'] + '\n')
            
            # Examples
            for example in section.get('examples', []):
                lines.append(f"### {example['title']}")
                lines.append(f"```{language}")
                lines.append(example['code'])
                lines.append("```\n")
            
            # Pitfalls
            if section.get('pitfalls'):
                lines.append("### Common Pitfalls")
                for pitfall in section['pitfalls']:
                    lines.append(f"- {pitfall}")
                lines.append("")
        
        return '\n'.join(lines)


# Global instance
cheatsheet_agent = CheatsheetAgent()


async def generate_cheatsheet_invoke(args: dict) -> dict:
    """Wrapper for MCP Gateway invocation (async wrapper for sync logic)"""
    result = cheatsheet_agent.generate(args)
    
    return {
        "success": result.get("success", False),
        "data": result,
        "format": "markdown"
    }
