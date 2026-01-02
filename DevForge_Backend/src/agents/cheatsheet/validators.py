"""Production-grade validation for cheatsheets with HARD FAIL policy.

Philosophy: Better to fail loudly than ship garbage.
Validation checks include:
1. Minimum content length and structure
2. Code block presence and syntax validity (Python)
3. Hallucinated import detection
"""

import ast
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation attempt."""
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    quality_score: float = 0.0  # 0-100
    quality_indicators: Dict[str, Any] = field(default_factory=dict)


class CheatsheetValidator:
    """Production-grade validator for LLM-generated cheatsheets."""
    
    # Validation thresholds
    MIN_LENGTH = 200
    MAX_LENGTH = 15000
    MIN_CODE_BLOCKS = 2
    MIN_HEADINGS = 3
    
    # Known real packages (safe list to prevent hallucinations)
    # This list should be expanded or connected to a real package index in future
    KNOWN_PACKAGES = {
        # Standard Lib
        "os", "sys", "re", "json", "datetime", "collections", "itertools", 
        "functools", "math", "random", "time", "typing", "pathlib", "asyncio",
        "logging", "unittest", "argparse", "subprocess", "warnings", "abc",
        "contextlib", "copy", "dataclasses", "enum", "inspect", "io", "pickle",
        "platform", "shutil", "signal", "socket", "sqlite3", "string", "struct",
        "tempfile", "threading", "traceback", "uuid", "weakref", "xml", "csv",
        "email", "html", "http", "urllib", "zipfile", "gzip", "tarfile", "bz2",
        "glob", "hashlib", "hmac", "secrets", "ssl", "base64", "binascii",
        "calendar", "zoneinfo", "decimal", "fractions", "statistics", "textwrap",
        "unicodedata", "doctest", "pdb", "cProfile", "pstats", "timeit", "venv",
        
        # Data Science & ML
        "pandas", "numpy", "matplotlib", "seaborn", "scipy", "scikit-learn", 
        "sklearn", "tensorflow", "torch", "keras", "pytorch", "statsmodels", 
        "plotly", "bokeh", "altair", "streamlit", "gradio", "networkx",
        "pyspark", "polars", "dask", "jax", "xgboost", "lightgbm", "catboost",
        
        # Web & API
        "requests", "flask", "django", "fastapi", "aiohttp", "httpx", "urllib3",
        "uvicorn", "gunicorn", "starlette", "pydantic", "sqlalchemy", "alembic",
        "celery", "redis", "beautifulsoup4", "bs4", "selenium", "playwright",
        "scrapy", "lxml", "python-multipart", "jinja2", "werkzeug",
        
        # AI / LLM
        "openai", "anthropic", "langchain", "llama-index", "transformers", 
        "huggingface_hub", "tokenizers", "tiktoken", "cohere", "pinecone-client",
        "weaviate-client", "qdrant-client", "chromadb", "faiss", "sentence-transformers",
        "groq", "mistralai", "ollama", "instructor", "autogen", "crewai", "langgraph",
        
        # Utils & Dev
        "pytest", "black", "isort", "mypy", "ruff", "flake8", "pylint",
        "tox", "nox", "click", "typer", "rich", "tqdm", "pillow", "opencv-python",
        "cv2", "boto3", "google-cloud-storage", "azure-storage-blob",
        "pyyaml", "toml", "python-dotenv", "faker", "factory-boy", "freezegun"
    }

    def validate(
        self, 
        markdown: str, 
        original_query: str,
        expected_language: str = None,
        allowed_secondary_languages: List[str] = None
    ) -> ValidationResult:
        """
        Validate markdown content with checks for structure, syntax, and hallucinations.
        
        Args:
            markdown: The LLM generated markdown content
            original_query: The user's original query (for context)
            expected_language: The target programming language
            
        Returns:
            ValidationResult object
        """
        errors = []
        warnings = []
        indicators = {}
        
        # --- HARD CHECKS (Must Pass) ---
        
        # 1. Minimum content length
        if len(markdown) < self.MIN_LENGTH:
            errors.append(f"Content too short ({len(markdown)} < {self.MIN_LENGTH} chars)")
        
        # 2. Code blocks presence
        code_blocks = self._extract_code_blocks(markdown)
        indicators["code_blocks"] = len(code_blocks)
        
        if len(code_blocks) < self.MIN_CODE_BLOCKS:
            errors.append(f"Insufficient code examples ({len(code_blocks)} < {self.MIN_CODE_BLOCKS})")
        
        # 2b. CRITICAL: Language Mismatch Detection
        if expected_language:
            language_errors = self._validate_language_contract(
                code_blocks, expected_language, original_query, allowed_secondary_languages
            )
            if language_errors:
                errors.extend(language_errors)
                indicators["language_contract_honored"] = False
            else:
                indicators["language_contract_honored"] = True
            
        # 3. Structure (Headings)
        headings = re.findall(r'^#{1,3}\s+(.+)$', markdown, re.MULTILINE)
        indicators["headings"] = len(headings)
        
        if len(headings) < self.MIN_HEADINGS:
            errors.append(f"Poor structure: found {len(headings)} headings, required {self.MIN_HEADINGS}")
            
        # 4. Syntax Validation (CRITICAL)
        syntax_errors = self._validate_syntax(code_blocks, expected_language)
        if syntax_errors:
            errors.extend(syntax_errors)
            indicators["syntax_valid"] = False
        else:
            indicators["syntax_valid"] = True
            
        # 5. Hallucination Check (Python Imports)
        if expected_language and expected_language.lower() == "python":
            hallucinated = self._check_hallucinated_imports(markdown)
            if hallucinated:
                errors.append(f"Hallucinated imports detected: {', '.join(hallucinated)}")
                indicators["hallucinations"] = True
            else:
                indicators["hallucinations"] = False
        
        # --- SOFT CHECKS (Warnings) ---
        
        # 1. Maximum length
        if len(markdown) > self.MAX_LENGTH:
            warnings.append(f"Content very long ({len(markdown)} > {self.MAX_LENGTH} chars)")
            
        # 2. Reference Table
        has_table = '|' in markdown and '---' in markdown
        indicators["has_table"] = has_table
        if not has_table:
            warnings.append("No reference table included")
            
        # 3. Sufficient Examples
        if len(code_blocks) < 4:
            warnings.append("Consider adding more code examples")
            
        # Calculate Quality Score
        quality_score = self._calculate_quality(markdown, indicators)
        
        passed = len(errors) == 0
        
        return ValidationResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
            quality_score=quality_score,
            quality_indicators=indicators
        )

    
    def _validate_language_contract(
        self,
        code_blocks: List[Tuple[str, str]],
        expected_language: str,
        query: str,
        allowed_secondary_languages: List[str] = None
    ) -> List[str]:
        """Validate that generated code matches the requested language logic.
        
        Rules:
        1. Primary Language must be present.
        2. Primary Context Ratio: (Primary Blocks / Meaningful Blocks) >= 0.6.
           - Meaningful = Primary + Secondary + Wrong (Ignored: Bash, JSON, Text).
        3. All non-primary blocks MUST be in allowed_secondary_languages or auxiliary.
        """
        errors = []
        allowed_secondary_languages = allowed_secondary_languages or []
        expected_lower = expected_language.lower()
        
        # Normalize language aliases
        language_aliases = {
            "py": "python", "js": "javascript", "ts": "typescript", "rs": "rust",
            "go": "go", "golang": "go", "sh": "bash", "shell": "bash", "zsh": "bash"
        }
        
        def normalize(lang):
            return language_aliases.get(lang.lower().strip(), lang.lower().strip())
            
        expected_norm = normalize(expected_lower)
        secondary_norm = {normalize(l) for l in allowed_secondary_languages}
        
        # Auxiliary languages (Never count towards dominance checks)
        auxiliary_languages = {
            "bash", "shell", "sh", "zsh", "fish",
            "json", "yaml", "yml", "toml", "xml",
            "text", "txt", "markdown", "md", "",
            "html", "css", "scss", "ini", "cfg", "dockerfile"
        }
        
        # Counters
        primary_count = 0
        secondary_count = 0
        wrong_count = 0
        meaningful_blocks = 0
        wrong_languages_found = {}
        
        for lang, _ in code_blocks:
            norm_lang = normalize(lang)
            
            # Is it auxiliary?
            if norm_lang in auxiliary_languages:
                continue
                
            meaningful_blocks += 1
            
            if norm_lang == expected_norm:
                primary_count += 1
            elif norm_lang in secondary_norm:
                secondary_count += 1
            else:
                wrong_count += 1
                wrong_languages_found[norm_lang] = wrong_languages_found.get(norm_lang, 0) + 1

        # Check 1: Primary Presence
        # If there are meaningful blocks, we expect at least one primary block
        if meaningful_blocks > 0 and primary_count == 0:
             errors.append(
                f"❌ Language Contract Violation: No {expected_language} code blocks found. "
                f"Requested {expected_language}."
            )
            
        # Check 2: Unauthorized Languages
        if wrong_count > 0:
            errors.append(
                f"❌ Unauthorized Language Detected: found {', '.join(wrong_languages_found.keys())}. "
                f"Allowed: {expected_language} + {list(secondary_norm)}."
            )
            
        # Check 3: Primary Dominance (60% Rule)
        # Assert: Primary_Blocks / Meaningful_Blocks >= 0.60
        # 
        # Why skip for single-block inputs (meaningful_blocks < 2)?
        # - Single-block cheatsheets are often valid (e.g., "show me Rust basics")
        # - Enforcing 60% on 1 block would always pass (1/1 = 100%) or always fail (0/1 = 0%)
        # - The ratio is only meaningful when there are multiple blocks to compare
        # - This avoids false positives for legitimate single-language cheatsheets
        if meaningful_blocks >= 2:
            ratio = primary_count / meaningful_blocks
            if ratio < 0.6:
                errors.append(
                    f"❌ Primary Language Diluted: {expected_language} makes up only {ratio:.0%} of code examples. "
                    f"Must be at least 60% (found {primary_count}/{meaningful_blocks} primary blocks)."
                )
        
        return errors
    
    def _extract_code_blocks(self, markdown: str) -> List[Tuple[str, str]]:
        """Extract code blocks as (language, code) tuples."""
        pattern = r'```(\w+)?\n(.*?)```'
        matches = re.findall(pattern, markdown, re.DOTALL)
        return [(lang or "text", code.strip()) for lang, code in matches]

    def _validate_syntax(
        self, 
        code_blocks: List[Tuple[str, str]],
        expected_language: Optional[str]
    ) -> List[str]:
        """Validate syntax of code blocks. Supports multiple languages."""
        errors = []
        
        for i, (lang, code) in enumerate(code_blocks):
            # Normalize language tag
            lang_lower = (lang or "").lower()
            
            # Route to appropriate validator
            if lang_lower in ["python", "py"]:
                try:
                    ast.parse(code)
                except SyntaxError as e:
                    errors.append(
                        f"Syntax error in Python code block {i+1} (line {e.lineno}): {e.msg}"
                    )
                except Exception as e:
                    errors.append(f"Validation error in Python code block {i+1}: {str(e)}")
            
            elif lang_lower == "sql":
                if not self._has_sql_syntax(code):
                    errors.append(
                        f"Code block {i+1} marked as SQL but contains no SQL keywords. "
                        f"Expected SELECT, INSERT, UPDATE, DELETE, CREATE, etc."
                    )
            
            elif lang_lower in ["rust", "rs"]:
                if not self._has_rust_syntax(code):
                    errors.append(
                        f"Code block {i+1} marked as Rust but contains no Rust syntax. "
                        f"Expected fn, impl, struct, enum, pub, etc."
                    )
            
            elif lang_lower in ["go", "golang"]:
                if not self._has_go_syntax(code):
                    errors.append(
                        f"Code block {i+1} marked as Go but contains no Go syntax. "
                        f"Expected func, package, import, type, etc."
                    )
            
            # For other languages, skip syntax validation (graceful degradation)
            # We still enforce language presence via _validate_language_contract
                    
        return errors
    
    def _has_sql_syntax(self, code: str) -> bool:
        """Check for SQL syntax markers (case-insensitive)."""
        sql_keywords = [
            "SELECT", "FROM", "WHERE", "INSERT", "UPDATE", "DELETE", 
            "CREATE", "DROP", "ALTER", "JOIN", "GROUP BY", "ORDER BY",
            "HAVING", "UNION", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN"
        ]
        upper_code = code.upper()
        # Require at least one SQL keyword
        return any(keyword in upper_code for keyword in sql_keywords)
    
    def _has_rust_syntax(self, code: str) -> bool:
        """Check for Rust syntax patterns."""
        rust_patterns = [
            r'\bfn\s+\w+',          # Function declarations
            r'\bimpl\s+\w+',        # Implementations
            r'\bstruct\s+\w+',      # Struct definitions
            r'\benum\s+\w+',        # Enum definitions
            r'\bpub\s+',            # Public visibility
            r'\blet\s+mut\s+',      # Mutable variables
            r'\buse\s+\w+',         # Use statements
            r'->',                   # Return type syntax
            r'\bimpl\b',            # Trait implementations
            r'println!',            # Macros
            r'\blet\s+\w+',         # Variable declaration
            r'\bmatch\s+',          # Match expressions
            r'::',                  # Path separator
            r'&[a-zA-Z_]',          # References
            r'\bString\b',          # String type
            r'\bVec\b',             # Vec type
        ]
        # Require at least one Rust pattern
        return any(re.search(pattern, code) for pattern in rust_patterns)
    
    def _has_go_syntax(self, code: str) -> bool:
        """Check for Go syntax patterns."""
        go_patterns = [
            r'\bfunc\s+\w+',        # Function declarations
            r'\bpackage\s+\w+',     # Package declarations
            r'\bimport\s+["(]',     # Import statements
            r'\btype\s+\w+',        # Type definitions
            r'\bstruct\s*{',        # Struct literals
            r'\binterface\s*{',     # Interfaces
            r':=',                   # Short variable declaration
            r'\bgo\s+\w+',          # Goroutines
            r'\bchan\s+',           # Channels
            r'\bdefer\s+',          # Defer statements
            r'fmt\.',               # Standard library fmt
            r'\bmap\[',             # Map types
            r'\bslice\b',           # Slice mentions
            r'\bif\s+err\s*!=',     # Error handling pattern
        ]
        # Require at least one Go pattern
        return any(re.search(pattern, code) for pattern in go_patterns)

    def _check_hallucinated_imports(self, markdown: str) -> List[str]:
        """Check for potentially hallucinated Python imports."""
        # Regex to find 'import x' or 'from x import y'
        import_pattern = r'^\s*(?:from|import)\s+([\w\.]+)'
        
        # Find all code blocks to scan imports ONLY in code
        # We don't want to match prose that looks like imports
        code_blocks = self._extract_code_blocks(markdown)
        
        found_imports = set()
        for lang, code in code_blocks:
            if lang.lower() in ['python', 'py', '']:
                for line in code.split('\n'):
                    match = re.search(import_pattern, line)
                    if match:
                        found_imports.add(match.group(1).split('.')[0])
                        
        hallucinated = []
        for pkg in found_imports:
            # Skip private/internal modules
            if pkg.startswith('_'):
                continue
                
            if pkg not in self.KNOWN_PACKAGES:
                # Heuristic: If it looks like a real package but isn't in our list
                # and isn't very short (like 'a', 'b'), flag it.
                if len(pkg) > 2:
                    hallucinated.append(pkg)
                    
        return hallucinated

    def _calculate_quality(self, markdown: str, indicators: Dict[str, Any]) -> float:
        """Calculate a 0-100 quality score based on indicators."""
        score = 50.0  # Base score
        
        # Length bonus (max 10)
        length = len(markdown)
        if 500 <= length <= 5000:
            score += 10
        elif length > 5000:
            score += 5
            
        # Code blocks bonus (max 15)
        num_blocks = indicators.get("code_blocks", 0)
        score += min(num_blocks * 3, 15)
        
        # Structure bonus (max 10)
        num_headings = indicators.get("headings", 0)
        score += min(num_headings * 2, 10)
        
        # Table bonus (10)
        if indicators.get("has_table"):
            score += 10
            
        # Syntax validity bonus (15)
        if indicators.get("syntax_valid"):
            score += 15
        
        return min(max(score, 0), 100)
