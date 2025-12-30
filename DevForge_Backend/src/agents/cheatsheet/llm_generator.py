"""Production-grade LLM cheatsheet generator with web search and hard validation.

Orchestrates the LLM generation process:
1. Determines if web search is needed (for up-to-date info)
2. Executes targeted searches if enabled
3. Constructs comprehensive prompt with context
4. Generates content using Claude
5. Validates output (Hard Fail policy)
6. Retries once with feedback if validation fails
"""

import os
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from src.llm.ollama_client import generate_text

from src.agents.cheatsheet.validators import CheatsheetValidator, ValidationResult
from src.agents.cheatsheet.brave_search import BraveSearchClient
from src.agents.cheatsheet.search_strategy import SearchQueryStrategy
from src.agents.cheatsheet.config import config

logger = logging.getLogger(__name__)


@dataclass
class LLMCheatsheetResponse:
    """Structured response from LLM generator."""
    markdown: str
    language: str
    skill_level: str
    detected_libraries: List[str]
    
    # Metadata for transparency
    generation_method: str = "llm_primary"  # "llm_primary", "llm_with_search"
    llm_generated: bool = True
    web_search_used: bool = False
    sources: List[str] = field(default_factory=list)
    
    # Quality metrics
    validation_score: float = 0.0
    quality_indicators: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    routing_reason: str = ""


class ValidationError(Exception):
    """Raised when LLM output fails validation after retries."""
    def __init__(self, message, errors, original_output, corrected_output=None):
        super().__init__(message)
        self.errors = errors
        self.original_output = original_output
        self.corrected_output = corrected_output


class LLMCheatsheetGenerator:
    """Generates cheatsheets using LLM with validation and optional web search."""
    
    def __init__(
        self,
        validator: CheatsheetValidator,
        web_search_enabled: bool = True
    ):
        self.model = config.OLLAMA_MODEL
        
        self.validator = validator
        self.web_search_enabled = web_search_enabled
        self.search_client = BraveSearchClient()
        self.search_strategy = SearchQueryStrategy()

    async def generate(
        self,
        user_query: str,
        code_context: str = "",
        detected_language: str = "python",
        skill_level: str = "intermediate",
        detected_libraries: List[str] = None
    ) -> LLMCheatsheetResponse:
        """
        Execute generation pipeline: Search -> Generate -> Validate -> Retry.
        
        Raises:
            ValidationError: If validation fails twice.
            Exception: For API errors.
        """
        detected_libraries = detected_libraries or []
        
        # Ollama client is stateless (HTTP), no init check needed
        # if not self.client:
        #     raise Exception("LLM Client not initialized (missing API key)")

        # Step 1: Web Search (if needed)
        web_search_used = False
        search_results = []
        sources = []
        
        # Heuristic: Search if "latest" requested or fast-evolving libs present
        should_search = self._should_search(user_query, detected_libraries)
        
        if self.web_search_enabled and should_search:
            logger.info("Web search triggered for up-to-date context")
            try:
                # Generate targeted queries
                queries = self.search_strategy.build_queries(
                    user_query, detected_language, detected_libraries, skill_level
                )
                
                # Execute search (parallelize if multiple - keeping simple for now)
                for q in queries[:2]:  # Use top 2 queries
                    results = await self.search_client.search_docs(q, count=2)
                    search_results.extend(results)
                
                if search_results:
                    web_search_used = True
                    sources = [r.url for r in search_results]
                    
            except Exception as e:
                logger.error(f"Web search failed: {e}")
                # Continue without search
        
        # Step 2: Build System Prompt
        system_prompt = self._build_system_prompt(
            topic=user_query,
            code_context=code_context,
            language=detected_language,
            skill=skill_level,
            libraries=detected_libraries,
            search_context=search_results
        )
        
        # Step 3: Call LLM
        logger.info(f"Calling LLM ({self.model})")
        raw_markdown = await self._call_llm(system_prompt, user_query)
        
        # Step 4: Validation
        validation = self.validator.validate(
            raw_markdown, user_query, detected_language
        )
        
        retry_count = 0
        final_markdown = raw_markdown
        
        if not validation.passed:
            logger.warning(f"Optimization required: {validation.errors}")
            
            # Step 5: Retry with feedback (Once)
            retry_count = 1
            try:
                corrected_markdown = await self._retry_with_feedback(
                    system_prompt,
                    raw_markdown,
                    validation.errors,
                    user_query
                )
                
                # Re-validate
                validation_retry = self.validator.validate(
                    corrected_markdown, user_query, detected_language
                )
                
                if not validation_retry.passed:
                    # HARD FAIL - Do not ship invalid content
                    raise ValidationError(
                        "LLM output failed validation after retry",
                        errors=validation_retry.errors,
                        original_output=raw_markdown,
                        corrected_output=corrected_markdown
                    )
                
                final_markdown = corrected_markdown
                validation = validation_retry  # Update validation result
                logger.info("Validation passed after retry")
                
            except ValidationError:
                raise # Re-raise
            except Exception as e:
                logger.error(f"Retry failed: {e}")
                # If retry crashes, we must fail if original was invalid
                raise ValidationError(
                    "Retry mechanism failed",
                    errors=validation.errors,
                    original_output=raw_markdown
                )

        # Step 6: Return Response
        return LLMCheatsheetResponse(
            markdown=final_markdown,
            language=detected_language,
            skill_level=skill_level,
            detected_libraries=detected_libraries,
            generation_method="llm_with_search" if web_search_used else "llm_primary",
            llm_generated=True,
            web_search_used=web_search_used,
            sources=sources,
            validation_score=validation.quality_score,
            quality_indicators=validation.quality_indicators,
            retry_count=retry_count
        )

    def _should_search(self, query: str, libraries: List[str]) -> bool:
        """Decide if web search needed."""
        # Check explicit keywords
        keywords = ["latest", "new", "modern", "2024", "2025", "current", "version"]
        if any(k in query.lower() for k in keywords):
            return True
            
        # Check fast-evolving libs (import from config or detector?)
        # For simplicity, duplicate list or import
        from src.agents.cheatsheet.domain_detector import DomainDetector
        fast_libs = DomainDetector.FAST_EVOLVING_LIBS
        
        for lib in libraries:
            if any(fl in lib.lower() for fl in fast_libs):
                return True
                
        return False

    def _build_system_prompt(
        self,
        topic: str,
        code_context: str,
        language: str,
        skill: str,
        libraries: List[str],
        search_context: List[Any]
    ) -> str:
        """Construct the prompt with optional search context."""
        
        search_text = ""
        if search_context:
            search_text = "## LATEST DOCUMENTATION CONTEXT\n"
            for res in search_context[:3]:
                search_text += f"- Source ({res.title}): {res.description}\n"
        
        return f"""You are an expert technical writer creating programming cheatsheets.

## TASK
Create a comprehensive {skill}-level cheatsheet for: {topic}

## CONTEXT
Language: {language}
Skill Level: {skill}
Libraries Detected: {', '.join(libraries) if libraries else 'None'}
Code Context:
```
{code_context[:1000] if code_context else 'No code provided'}
```

{search_text}

## MANDATORY STRUCTURE (Markdown)
Your cheatsheet MUST include these sections in order:

### 1. Title & Quick Overview
Brief introduction.

### 2. Installation/Setup (if applicable)
Command to install packages.

### 3. Core Concepts ({skill})
Explain key interactions.

### 4. Common Patterns
Provide 5-7 copy-pasteable code examples.
Each example must include:
- Title
- Code block (```{language} ... ```)
- Brief explanation

### 5. Quick Reference Table
| syntax | description |
|--------|-------------|

### 6. Best Practices & Gotchas

## QUALITY RULES
1. **Valid Syntax**: All code must be syntactically valid {language}.
2. **Real Imports**: Do NOT invent libraries. Use standard or detected libs.
3. **No Placeholders**: Use real variable names (e.g. `user_id`, not `foo`).
4. **Modern APIs**: Use current syntax (refer to Documentation Context if available).

Generate the cheatsheet now."""

    async def _call_llm(self, prompt: str, user_query: str) -> str:
        """Call Ollama API."""
        full_prompt = f"{prompt}\n\nQuery: {user_query}"
        return await generate_text(full_prompt, model=self.model, max_tokens=config.LLM_CHEATSHEET_MAX_TOKENS)

    async def _retry_with_feedback(
        self,
        original_prompt: str,
        failed_output: str,
        errors: List[str],
        user_query: str
    ) -> str:
        """Retry generation with explicit error feedback."""
        feedback_prompt = f"""
## CRITICAL: PREVIOUS OUTPUT FAILED VALIDATION
Your previous attempt had the following errors:
{chr(10).join(f'- {e}' for e in errors)}

## INSTRUCTION
Regenerate the cheatsheet fixing ALL errors above.
Ensure code syntax is perfect and all imports are real.

## PREVIOUS FAILED OUTPUT (Ref)
{failed_output[:500]}...
"""
        # Combine prompt
        full_prompt = f"{original_prompt}\n{feedback_prompt}\nQuery: {user_query}"
        
        return await generate_text(full_prompt, model=self.model, max_tokens=config.LLM_CHEATSHEET_MAX_TOKENS)
