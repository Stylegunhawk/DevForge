"""Domain detector for intelligent routing between template and LLM paths.

This module determines whether a cheatsheet request should use:
- Fast template path (stable libraries, known languages)
- LLM path (unsupported languages, fast-evolving libraries)

Critical: This is routing logic only - does NOT generate content.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DomainDetector:
    """Determines if a request should use LLM vs Template path.
    
    Philosophy: Template-first for speed and reliability, LLM for coverage.
    """
    
    # Languages without template support (require LLM)
    UNSUPPORTED_LANGUAGES = {
        "sql": ["select", "join", "where", "insert", "update", "delete", "from", "group by"],
        "rust": ["fn ", "impl ", "trait ", "cargo", "struct ", "enum ", "mut ", "pub "],
        "go": ["func ", "package ", "import ", "go ", "defer ", "chan ", "goroutine"],
        "ruby": ["puts ", "require ", ".each", ".map", ".select", "def ", "end", "class ", "module ", "do ", "end"],
        "toml": ["[package]", "[dependencies]", "name =", "version =", "[tool]"],
        "yaml": ["apiversion:", "kind:", "metadata:", "spec:", "deployment:", "service:"],
        "dockerfile": ["from ", "run ", "cmd ", "expose ", "env ", "workdir"],
        "nginx": ["server {", "location ", "proxy_pass", "upstream"],
        "bash": ["#!/bin/bash", "if [", "for ", "while ", "case ", "esac"],
    }
    
    # Libraries that change frequently (prefer LLM for latest syntax)
    FAST_EVOLVING_LIBS = [
        # AI/ML frameworks (rapid iteration)
        "langchain",
        "langgraph", 
        "llama-index",
        "autogen",
        "crewai",
        "instructor",
        "pydantic-ai",
        
        # Modern JS frameworks (frequent breaking changes)
        "nextjs",
        "next",
        "remix",
        "astro",
        "bun",
        "deno",
        "vite",
        "svelte",
        "solid",
        
        # Emerging tools
        "vercel",
        "cloudflare-workers",
        "supabase",
    ]
    
    # Recency keywords indicating "latest version" request
    LATEST_KEYWORDS = [
        "latest", "new", "modern", "2024", "2025", "current", 
        "updated", "recent", "v0.", "v1.", "newest"
    ]
    
    def should_use_llm(
        self,
        query: str,
        code_context: str,
        detected_libraries: list[str],
        language: str
    ) -> tuple[bool, str]:
        """Determine if request should route to LLM path.
        
        Decision tree:
        1. Check for unsupported language (SQL, Rust, etc.)
        2. Check for fast-evolving library with code context
        3. Check for explicit "latest" request
        4. Check if templates are missing
        5. Default: Use template (safe, fast)
        
        Args:
            query: User's input query/description
            code_context: User's code snippet (if provided)
            detected_libraries: Libraries found in code
            language: Programming language
            
        Returns:
            Tuple of (should_use_llm, reason_string)
            
        Examples:
            >>> should_use_llm("sql basics", "", [], "sql")
            (True, "unsupported_language:sql")
            
            >>> should_use_llm("", "from langchain import...", ["langchain"], "python")
            (True, "fast_evolving_lib:langchain")
            
            >>> should_use_llm("", "import pandas", ["pandas"], "python")
            (False, "template_available")
        """
        
        # Normalize inputs
        query_lower = query.lower() if query else ""
        code_lower = code_context.lower() if code_context else ""
        language_lower = language.lower() if language else ""
        
        # Check 1: Unsupported language detection
        unsupported_lang, confidence = self._detect_unsupported(
            query_lower, 
            code_lower, 
            language_lower
        )
        
        # Route to LLM if unsupported language detected
        # Lower threshold to 1 for explicit language match (confidence=10) or keyword match
        if unsupported_lang and (confidence >= 1 or language_lower in self.UNSUPPORTED_LANGUAGES):
            logger.info(f"Routing to LLM: Unsupported language '{unsupported_lang}' "
                       f"(confidence: {confidence}, explicit: {language_lower in self.UNSUPPORTED_LANGUAGES})")
            return True, f"unsupported_language:{unsupported_lang}"
        
        # Check 2: Fast-evolving library with code context
        # Only trigger if user provided actual code (shows intent)
        if code_context and len(code_context) > 20:
            for lib in detected_libraries:
                lib_lower = lib.lower()
                if any(fast_lib in lib_lower for fast_lib in self.FAST_EVOLVING_LIBS):
                    logger.info(f"Routing to LLM: Fast-evolving library '{lib}' "
                               f"with code context ({len(code_context)} chars)")
                    return True, f"fast_evolving_lib:{lib}"
        
        # Check 3: Explicit latest/recent request
        if self._has_latest_signal(query_lower):
            logger.info(f"Routing to LLM: Explicit recency request detected")
            # If user wants latest, even for stable libs, honor it
            target_lib = detected_libraries[0] if detected_libraries else language
            return True, f"explicit_latest_request:{target_lib}"
        
        # Check 4: No template exists
        # This checks if we have high-quality templates for detected libraries
        if detected_libraries and not self._has_template(detected_libraries):
            logger.info(f"Routing to LLM: No template for libraries: {detected_libraries}")
            return True, f"no_template_available:{detected_libraries[0]}"
        
        # Default: Use template (fast, reliable, cheap)
        logger.info(f"Routing to Template: Language '{language}' has templates, "
                   f"libraries: {detected_libraries}")
        return False, "template_available"
    
    def _detect_unsupported(
        self, 
        query: str, 
        code: str, 
        explicit_language: str
    ) -> tuple[Optional[str], int]:
        """Detect if query/code is for an unsupported language.
        
        Returns:
            Tuple of (language_name, keyword_match_count)
            Returns (None, 0) if no unsupported language detected
        """
        # Combine query and code for keyword analysis
        text = f"{query} {code}"
        
        # Check explicit language first (highest confidence)
        if explicit_language in self.UNSUPPORTED_LANGUAGES:
            # User explicitly requested unsupported language
            return explicit_language, 10  # Very high confidence
        
        # Check for keyword patterns
        best_match = None
        best_count = 0
        
        for lang, keywords in self.UNSUPPORTED_LANGUAGES.items():
            match_count = sum(1 for kw in keywords if kw in text)
            
            if match_count > best_count:
                best_count = match_count
                best_match = lang
        
        return best_match, best_count
    
    def _has_latest_signal(self, query: str) -> bool:
        """Check if user is asking for latest/current version.
        
        Examples: "latest langchain", "python 2024", "new syntax"
        """
        return any(keyword in query for keyword in self.LATEST_KEYWORDS)
    
    def _has_template(self, libraries: list[str]) -> bool:
        """Check if high-quality templates exist for detected libraries.
        
        Checks enhanced_templates.py to see if libraries have comprehensive
        templates (not just stubs).
        
        Args:
            libraries: List of library names
            
        Returns:
            True if at least one library has a full template
        """
        try:
            from src.agents.cheatsheet.enhanced_templates import LIBRARY_SECTIONS
            from src.agents.cheatsheet.config import config
            
            for lib in libraries:
                lib_lower = lib.lower()
                
                # Check config first - FULLY_TEMPLATED_LIBS are guaranteed good
                if lib_lower in [l.lower() for l in config.FULLY_TEMPLATED_LIBS]:
                    logger.debug(f"Library '{lib}' is fully templated (config)")
                    return True
                
                # Check LIBRARY_SECTIONS
                if lib_lower in LIBRARY_SECTIONS:
                    template = LIBRARY_SECTIONS[lib_lower]
                    
                    # Check for any skill level
                    for level in ['beginner', 'intermediate', 'expert']:
                        if level in template:
                            section = template[level]
                            examples = section.get('examples', [])
                            
                            # Comprehensive check: Must have real code, not stubs
                            has_real_code = False
                            for ex in examples:
                                code = ex.get('code', '')
                                
                                # Check if code is substantial AND not a stub
                                if len(code) > 50:
                                    # Check for stub markers
                                    is_stub = (
                                        'will be enriched' in code.lower() or
                                        'this section will' in code.lower() or
                                        '# placeholder' in code.lower() or
                                        '# stub' in code.lower()
                                    )
                                    
                                    if not is_stub:
                                        has_real_code = True
                                        break
                            
                            if has_real_code:
                                logger.debug(f"Template found for '{lib}' at '{level}' level")
                                return True
            
            logger.debug(f"No comprehensive templates for: {libraries}")
            return False
            
        except ImportError as e:
            logger.error(f"Failed to import templates: {e}")
            # Fail safe: assume template exists (use existing path)
            return True
