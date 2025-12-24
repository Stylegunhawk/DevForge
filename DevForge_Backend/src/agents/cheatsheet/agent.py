"""Enhanced cheatsheet agent with context awareness"""

import logging
import time
from typing import Dict, Any, Optional, List

from src.agents.cheatsheet.context_parser import parse_code_context
from src.agents.cheatsheet.library_detector import detect_libraries
from src.agents.cheatsheet.complexity_scorer import calculate_complexity
from src.agents.cheatsheet.section_selector import select_sections
from src.agents.cheatsheet.quick_reference import generate_quick_reference
from src.tools.cheatsheet.tools import detect_language_from_code

# Enrichment imports
# Enrichment imports
from src.agents.cheatsheet.enrichment_detector import should_enrich_sections
from src.agents.cheatsheet.section_enricher import SectionEnricher
from src.agents.cheatsheet.enhanced_templates import LIBRARY_SECTIONS
from src.agents.cheatsheet.config import config
from src.agents.cheatsheet.promotion_tracker import tracker as promotion_tracker

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CheatsheetAgent:
    """Generate context-aware programming cheatsheets"""
    
    def __init__(self):
        self.enricher = None  # Lazy initialization
    
    def generate(self, arguments: dict) -> dict:
        """
        Main generation logic with context awareness.
        
        Args:
            arguments: {
                'language': Optional[str],
                'skill_level': str,
                'code_context': Optional[str],
                'conversation_history': Optional[str]
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
        start_time = time.time()
        
        # Extract parameters
        explicit_language = arguments.get('language')
        skill_level = arguments.get('skill_level', 'beginner')
        code_context = arguments.get('code_context', '')
        conversation_history = arguments.get('conversation_history', '')
        
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
        
        # 6. LLM Enrichment (Optional)
        enrichment_decision = should_enrich_sections(
            detected_libraries=detected_libraries,
            code_context=code_context,
            conversation_history=conversation_history,
            supported_libraries=list(LIBRARY_SECTIONS.keys())
        )
        
        enriched_section_titles = []
        
        if enrichment_decision['enrich']:
            logger.info(f"Enrichment triggered: {enrichment_decision['reason']}")
            
            # Lazy init enricher
            if not self.enricher:
                try:
                    self.enricher = SectionEnricher()
                except Exception as e:
                    logger.error(f"Enricher init failed: {e}")
                    enrichment_decision['enrich'] = False
            
            if self.enricher:
                target_libraries = enrichment_decision.get('target_libraries', [])
                sections_enriched_count = 0
                max_sections = config.MAX_ENRICHED_SECTIONS
                
                # Invariant 3 check: Record initial structure state
                initial_section_count = len(sections)
                
                # Iterate and enrich in-place using Index Mutation (Invariant 1)
                for i in range(len(sections)):
                    # Invariant 2: Cap enrichment fan-out
                    if sections_enriched_count >= max_sections:
                        logger.info(f"Enrichment cap reached ({max_sections}). Stopping.")
                        break
                        
                    section = sections[i]
                    source_lib = section.get('source_library')
                    
                    # Invariant 4: Stable section matching (metadata only)
                    if source_lib and source_lib in target_libraries:
                        logger.info(f"Enrichment Candidate [{source_lib}]: {section['title']}")
                        
                        try:
                            # Invariant 1: Mandatory index-based mutation
                            sections[i] = self.enricher.enrich_section(
                                base_section=section,
                                user_code=code_context,
                                library=source_lib,
                                conversation=conversation_history
                            )
                            
                            # Validation: Check if enrichment happened
                            if 'llm_enrichment' in sections[i]:
                                enriched_section_titles.append(section['title'])
                                sections_enriched_count += 1
                                
                                # Phase B: Template Promotion Tracking
                                promotion_tracker.record_enrichment(source_lib, section['title'])
                                
                        except Exception as e:
                            logger.error(f"Failed to enrich section {section['title']}: {e}")
                            
                # Invariant 3 & 5: Assert structural integrity
                # LLM/Enricher must NOT add/remove sections from the list
                if len(sections) != initial_section_count:
                    logger.critical("Invariant Violation: Section count changed during enrichment!")
                    # Just logging critical for now, but in strict mode could raise
        
        # 7. Assemble markdown
        markdown = self._assemble_markdown(
            language=language_key,
            skill_level=skill_level,
            sections=sections
        )
        
        # 8. Generate quick reference
        quick_ref = generate_quick_reference(
            language=language_key,
            skill_level=skill_level,
            detected_libraries=detected_libraries
        )
        
        full_markdown = markdown + '\n' + quick_ref
        
        # 9. Return enhanced response
        supported_libs = [lib for lib in detected_libraries if lib in LIBRARY_SECTIONS]
        elapsed_ms = int((time.time() - start_time) * 1000)
        
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
                'sections': [{'title': s['title']} for s in sections],
                'enrichment': {
                    'enabled': enrichment_decision['enrich'],
                    'reason': enrichment_decision.get('reason'),
                    'enriched_sections': enriched_section_titles,
                    'target_libraries': enrichment_decision.get('target_libraries', []),
                    # Phase B Telemetry
                    'confidence': enrichment_decision.get('confidence', 0.0),
                    'promotable': any(
                        promotion_tracker.should_promote(lib, title)
                        for lib in enrichment_decision.get('target_libraries', [])
                        for title in enriched_section_titles
                    )
                },
                'method': 'enriched' if enriched_section_titles else 'template',
                'response_time_ms': elapsed_ms
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
            
            # LLM Enrichment
            if 'llm_enrichment' in section:
                lines.append(section['llm_enrichment'])
                lines.append("")  # Spacing
            
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
