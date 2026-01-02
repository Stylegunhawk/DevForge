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
from typing import List, Dict, Optional, Any, Tuple

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
        detected_language: str = None,
        skill_level: str = "intermediate",
        detected_libraries: List[str] = None,
        secondary_languages: List[str] = None
    ) -> LLMCheatsheetResponse:
        """
        Execute generation pipeline: Search -> Generate -> Validate -> Retry.
        
        Raises:
            ValidationError: If validation fails twice.
            Exception: For API errors.
        """
        detected_libraries = detected_libraries or []
        secondary_languages = secondary_languages or []
        
        # CRITICAL: Enforce language contract - no defaulting
        if not detected_language:
            raise ValueError("detected_language is required - cannot default to any language")
        
        logger.info(f"🎯 LLM Language Contract: Generating {detected_language.upper()} cheatsheet")
        
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
            search_context=search_results,
            secondary_languages=secondary_languages
        )
        
        # Step 3: Call LLM
        logger.info(f"Calling LLM ({self.model})")
        raw_markdown = await self._call_llm(system_prompt, user_query)
        
        # Step 4: Validation
        validation = self.validator.validate(
            raw_markdown, user_query, detected_language, allowed_secondary_languages=secondary_languages
        )
        
        # Step 4b: Post-Generation Language Contract Verification
        # Defense-in-depth: Explicitly check language contract was honored
        if validation.passed:
            contract_check = self._verify_language_contract(
                raw_markdown, detected_language
            )
            if contract_check:
                # Contract violation detected even though other validation passed
                validation.passed = False
                validation.errors.append(contract_check)
                logger.warning(f"Language contract violation: {contract_check}")
        
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
                    corrected_markdown, user_query, detected_language, allowed_secondary_languages=secondary_languages
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
    
    def _verify_language_contract(
        self,
        markdown: str,
        expected_language: str
    ) -> Optional[str]:
        """Verify that LLM honored the language contract.
        
        This is a post-generation check to catch cases where LLM
        generated valid content but in the wrong language.
        
        Args:
            markdown: Generated markdown content
            expected_language: Language that should have been generated
            
        Returns:
            Error message if contract violated, None if honored
        """
        code_blocks = self._extract_code_blocks(markdown)
        
        if not code_blocks:
            return None  # No code blocks to verify
        
        expected_lower = expected_language.lower()
        auxiliary_langs = {"bash", "shell", "sh", "json", "yaml", "toml", "text", ""}
        
        # Extract primary code block languages (non-auxiliary)
        block_langs = [lang.lower().strip() for lang, _ in code_blocks if lang]
        primary_langs = [lang for lang in block_langs if lang not in auxiliary_langs]
        
        # Count target language blocks
        target_count = primary_langs.count(expected_lower)
        
        # Check for common wrong language (Python)
        if expected_lower != "python" and "python" in primary_langs:
            python_count = primary_langs.count("python")
            if python_count > target_count:
                return (
                    f"LLM violated language contract: Generated {python_count} Python blocks "
                    f"but only {target_count} {expected_language} blocks. "
                    f"This is a critical bug - user requested {expected_language}."
                )
        
        return None
    
    def _extract_code_blocks(self, markdown: str) -> List[Tuple[str, str]]:
        """Extract code blocks as (language, code) tuples."""
        import re
        pattern = r'```(\w+)?\n(.*?)```'
        matches = re.findall(pattern, markdown, re.DOTALL)
        return [(lang or "text", code.strip()) for lang, code in matches]

    def _build_system_prompt(
        self,
        topic: str,
        code_context: str,
        language: str,
        skill: str,
        libraries: List[str],
        search_context: List[Any],
        secondary_languages: List[str] = None
    ) -> str:
        """Construct the prompt with optional search context."""
        secondary_languages = secondary_languages or []
        
        search_text = ""
        if search_context:
            search_text = "## LATEST DOCUMENTATION CONTEXT\n"
            for res in search_context[:3]:
                search_text += f"- Source ({res.title}): {res.description}\n"
        
        secondary_context_rule = ""
        if secondary_languages:
            secondary_context_rule = f"""
2. You may use Secondary Languages ({', '.join(secondary_languages)}) ONLY for specific supporting sections (like 'Interop', 'Setup', or 'Database connections').
   - Keep interactions in secondary languages minimal and focused on the Primary Language.
   - The majority of code MUST be in {language} (Primary Language).
"""
        
        return f"""You are an expert technical writer creating programming cheatsheets.

## 🚨 CRITICAL LANGUAGE CONSTRAINT 🚨
**PRIMARY LANGUAGE: {language.upper()}**
{f"SECONDARY LANGUAGES ALLOWED: {', '.join(secondary_languages)}" if secondary_languages else ""}

PROMPT RULES:
1. Primary Language: {language}. You may use {', '.join(secondary_languages) if secondary_languages else 'no secondary languages'} ONLY for interop examples. The majority of code MUST be {language}.
{secondary_context_rule}
3. All code blocks using the Primary Language MUST use ```{language} syntax.
4. Do NOT default to Python or any other language unless explicitly listed as permitted.
5. If you cannot generate valid {language} code, state this explicitly.
6. The user requested {language} - honor this contract absolutely.

## TASK
Create a comprehensive {skill}-level cheatsheet for: {topic}

## CONTEXT
Target Language: {language} ← THIS IS MANDATORY
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
Brief introduction to {language}.

### 2. Installation/Setup (if applicable)
Command to install packages for {language}.

### 3. Core Concepts ({skill})
Explain key {language} concepts and interactions.

### 4. Common Patterns
Provide 5-7 copy-pasteable {language} code examples.
Each example must include:
- Title
- Code block (```{language} ... ``` ← USE THIS EXACT LANGUAGE TAG)
- Brief explanation

### 5. Quick Reference Table
| {language} syntax | description |
|--------|-------------|

### 6. Best Practices & Gotchas
Specific to {language}.

## QUALITY RULES
1. **Language Authority**: Code must be {language} (or allowed secondary languages).
2. **Valid Syntax**: All code must be syntactically valid.
3. **Real Imports**: Do NOT invent libraries. Use standard or detected libs for {language}.
4. **No Placeholders**: Use real variable names appropriate for {language} (e.g. `user_id`, not `foo`).
5. **Modern APIs**: Use current {language} syntax (refer to Documentation Context if available).

Generate the {language} cheatsheet now."""

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
        
        # Check if language mismatch was detected
        language_error = None
        for error in errors:
            if "Language" in error or "language" in error:
                language_error = error
                break
        
        feedback_prompt = f"""
## CRITICAL: PREVIOUS OUTPUT FAILED VALIDATION
Your previous attempt had the following errors:
{chr(10).join(f'- {e}' for e in errors)}

## INSTRUCTION
Regenerate the cheatsheet fixing ALL errors above.
"""
        
        if language_error:
            # Add specific language guidance
            feedback_prompt += f"""

⚠️  LANGUAGE MISMATCH DETECTED ⚠️
You generated code in the WRONG language.
{language_error}

You MUST use the EXACT language specified in the original prompt.
Do NOT default to Python or any other language.
"""
        else:
            feedback_prompt += """
Ensure code syntax is perfect and all imports are real.
"""
        
        feedback_prompt += f"""

## PREVIOUS FAILED OUTPUT (Reference)
{failed_output[:500]}...
"""
        
        # Combine prompt
        full_prompt = f"{original_prompt}\n{feedback_prompt}\nQuery: {user_query}"
        
        return await generate_text(full_prompt, model=self.model, max_tokens=config.LLM_CHEATSHEET_MAX_TOKENS)
