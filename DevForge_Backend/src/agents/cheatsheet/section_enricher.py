"""Add contextual tips to existing template sections using scoped LLM calls."""

import os
import logging
from typing import Dict, Optional, Any
from src.llm.ollama_client import generate_text
from .config import config

logger = logging.getLogger(__name__)

class SectionEnricher:
    """Enrich template sections with LLM-generated contextual tips."""
    
    def __init__(self):
        self.model = config.OLLAMA_MODEL
    
    async def enrich_section(
        self,
        base_section: Dict[str, Any],
        user_code: str,
        library: str = "",
        conversation: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add enrichment to ONE section.
        
        CRITICAL: Base structure MUST remain intact.
        Only adds 'llm_enrichment' key.
        
        Args:
            base_section: Template section with title, explanation, examples.
            user_code: User's actual code for context.
            library: Primary library being used (e.g. 'langchain').
            conversation: Optional conversation history.
        
        Returns:
            Original section dict + {'llm_enrichment': str} added.
        """
        # if not self.client:
        #     logger.debug("Enrichment skipped: No API key.")
        #     return base_section

        try:
            logger.info(f"Enriching section: title='{base_section.get('title')}' lib='{library}'")
            
            prompt = self._build_prompt(base_section, user_code, library, conversation)
            
            # Call Ollama
            enrichment_text = await generate_text(
                prompt=prompt,
                model=self.model,
                max_tokens=config.MAX_ENRICHMENT_TOKENS
            )
            
            if not enrichment_text:
                return base_section

            # Clean up: sometimes LLMs output Markdown fences around the whole thing
            enrichment_text = enrichment_text.strip()
            # If it starts with 'Here is...', strip that? Prompting should prevent it.
            
            logger.info(f"Enrichment success: {len(enrichment_text)} chars added.")
            
            return {
                **base_section,
                'llm_enrichment': enrichment_text,
                'enrichment_metadata': {
                    'tokens_used': 0, # Not available in simple generate_text
                    'library': library,
                    'model': self.model
                }
            }
            
        except Exception as e:
            logger.error(f"Enrichment failed for section '{base_section.get('title')}': {e}")
            # Graceful degradation - return original
            return base_section

    def _build_prompt(
        self,
        base_section: Dict[str, Any],
        user_code: str,
        library: str,
        conversation: Optional[str]
    ) -> str:
        """Build constrained prompt that preserves structure."""
        
        # Truncate contexts to fit context window safely and reduce noise
        safe_code = user_code[:1500] if user_code else ""
        safe_convo = conversation[-1000:] if conversation else ""
        
        section_title = base_section.get('title', 'Unknown Section')
        section_expl = base_section.get('explanation', '')
        
        prompt = f"""You are an expert developer assistant enriching a programming cheatsheet.

BASE SECTION (DO NOT MODIFY OR REPEAT):
Title: {section_title}
Explanation snippet: {section_expl[:200]}...

USER'S CODE TEXT:
```
{safe_code}
```
"""
        if safe_convo:
            prompt += f"""
CONVERSATION CONTEXT:
{safe_convo}
"""

        prompt += f"""
YOUR TASK:
For the library '{library}', look at the User's Code and the Base Section.
Add 2 specific items to help the user, focusing on MODERN/LATEST API usage (2024/2025 standards).

1. **Latest API Changes**: Brief note if syntax has changed recently (e.g. LangChain v0.1 vs v0.2).
2. **Debugging Tip**: Specific tip for the pattern seen in User's Code.

CONSTRAINTS:
- Output MUST be valid Markdown.
- DO NOT repeat the section title.
- DO NOT rewrite the explanation.
- Keep it under 150 words total.
- Use headers: `### Latest API Changes` and `### Debugging Tip`.
- If no specific relevant tip exists, provide a general best practice for '{library}'.

OUTPUT FORMAT:
### Latest API Changes
- [Note about versions/changes]

### Debugging Tip
- [Specific advice for the code pattern]
"""
        return prompt


