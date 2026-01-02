"""Code parser for extracting structure from source files.

Uses AST parsing for Python and regex for other languages.
"""

import ast
import re
import logging
from typing import List, Dict, Any, Optional

from src.agents.prompt_refiner.context_types import CodeStructure

logger = logging.getLogger(__name__)


class CodeParser:
    """Parse code files to extract structure and conventions."""
    
    # Language detection patterns
    LANGUAGE_PATTERNS = {
        "python": r"(def |import |class |if __name__|print\(|from \w+ import)",
        "javascript": r"(function |const |let |var |=>|console\.log|require\()",
        "typescript": r"(interface |type |: string|: number|<T>|export )",
        "java": r"(public class |public static void|import java\.)",
        "go": r"(package |func |import \(|defer |go |fmt\.)",
        "rust": r"(fn |let mut|impl |pub |match |use |struct )",
    }
    
    def parse_file(self, file_content: str, language: Optional[str] = None) -> CodeStructure:
        """Parse code file and extract structure.
        
        Args:
            file_content: Source code content
            language: Optional language hint. If None, will auto-detect
            
        Returns:
            CodeStructure with extracted elements
        """
        if not file_content or not file_content.strip():
            return CodeStructure()
        
        # Detect language if not provided
        if not language:
            language = self._detect_language(file_content)
        
        # Parse based on language
        if language == "python":
            return self._parse_python(file_content)
        else:
            # Fallback to regex-based parsing
            return self._parse_generic(file_content, language)
    
    def _detect_language(self, code: str) -> str:
        """Detect programming language from code content."""
        for lang, pattern in self.LANGUAGE_PATTERNS.items():
            if re.search(pattern, code):
                return lang
        
        return "unknown"
    
    def _parse_python(self, code: str) -> CodeStructure:
        """Parse Python code using AST.
        
        Args:
            code: Python source code
            
        Returns:
            CodeStructure with extracted Python elements
        """
        structure = CodeStructure(language="python")
        
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            logger.warning(f"Python syntax error during parsing: {e}")
            return structure
        
        # Extract classes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                structure.classes.append(node.name)
            
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                # Check if it's a standalone function (not in a class)
                if not any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree)):
                    structure.functions.append(node.name)
                
                # Detect async pattern
                if isinstance(node, ast.AsyncFunctionDef) and "async" not in structure.patterns:
                    structure.patterns.append("async")
                
                # Detect decorators
                if node.decorator_list and "decorators" not in structure.patterns:
                    structure.patterns.append("decorators")
            
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                import_str = self._format_import(node)
                if import_str:
                    structure.imports.append(import_str)
        
        # Detect conventions
        structure.conventions = self._detect_python_conventions(structure)
        
        logger.info(
            f"Parsed Python code",
            extra={
                "classes": len(structure.classes),
                "functions": len(structure.functions),
                "imports": len(structure.imports),
                "patterns": structure.patterns,
            }
        )
        
        return structure
    
    def _format_import(self, node: ast.AST) -> Optional[str]:
        """Format import node as string."""
        try:
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
                return f"import {', '.join(names)}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]
                return f"from {module} import {', '.join(names)}"
        except Exception:
            return None
    
    def _detect_python_conventions(self, structure: CodeStructure) -> Dict[str, str]:
        """Detect Python coding conventions."""
        conventions = {}
        
        # Naming convention
        has_snake_case = any("_" in name for name in structure.functions + structure.classes)
        has_pascal_case = any(name[0].isupper() for name in structure.classes if name)
        
        if has_snake_case:
            conventions["naming"] = "snake_case"
        if has_pascal_case:
            conventions["class_naming"] = "PascalCase"
        
        # Async usage
        if "async" in structure.patterns:
            conventions["async_support"] = "yes"
        
        # Decorator usage
        if "decorators" in structure.patterns:
            conventions["uses_decorators"] = "yes"
        
        return conventions
    
    def _parse_generic(self, code: str, language: str) -> CodeStructure:
        """Parse code using regex for non-Python languages.
        
        Args:
            code: Source code
            language: Programming language
            
        Returns:
            CodeStructure with basic extraction
        """
        structure = CodeStructure(language=language)
        
        # JavaScript/TypeScript class detection
        if language in ["javascript", "typescript"]:
            # Classes
            class_matches = re.finditer(r"class\s+(\w+)", code)
            structure.classes = [m.group(1) for m in class_matches]
            
            # Functions
            func_patterns = [
                r"function\s+(\w+)",  # function name()
                r"const\s+(\w+)\s*=\s*(?:async\s*)?\(",  # const name = async (
                r"(\w+)\s*:\s*\([^)]*\)\s*=>",  # name: () =>
            ]
            for pattern in func_patterns:
                matches = re.finditer(pattern, code)
                structure.functions.extend([m.group(1) for m in matches])
            
            # Imports
            import_matches = re.finditer(r"import .+ from ['\"](.+)['\"]", code)
            structure.imports = [m.group(0) for m in import_matches]
            
            # Detect async
            if re.search(r"\basync\b", code):
                structure.patterns.append("async")
            
            # Detect conventions
            has_camel_case = any(re.match(r"[a-z]+[A-Z]", name) for name in structure.functions if name)
            if has_camel_case:
                structure.conventions["naming"] = "camelCase"
        
        logger.info(
            f"Parsed {language} code with regex",
            extra={
                "classes": len(structure.classes),
                "functions": len(structure.functions),
            }
        )
        
        return structure
    
    def detect_conventions(self, code_structure: CodeStructure) -> Dict[str, Any]:
        """Detect coding conventions from parsed structure.
        
        Args:
            code_structure: Parsed code structure
            
        Returns:
            Dictionary of detected conventions
        """
        return code_structure.conventions
