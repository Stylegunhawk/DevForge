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
        expected_language: str = None
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
        """Validate syntax of code blocks. Currently supports Python."""
        errors = []
        
        for i, (lang, code) in enumerate(code_blocks):
            # Normalize language tag
            lang_lower = (lang or "").lower()
            
            # Check if block matches expected language (if provided)
            # We don't fail if language doesn't match, as cheatsheets might include bash/json etc.
            
            if lang_lower in ["python", "py"]:
                try:
                    ast.parse(code)
                except SyntaxError as e:
                    # Line number in error is relative to the code block
                    errors.append(
                        f"Syntax error in code block {i+1} (line {e.lineno}): {e.msg}"
                    )
                except Exception as e:
                    errors.append(f"Validation error in code block {i+1}: {str(e)}")
                    
        return errors

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
