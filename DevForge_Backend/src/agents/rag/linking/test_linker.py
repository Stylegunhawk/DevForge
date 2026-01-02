"""Test-source linking for RAG context enrichment.

ARCHITECTURE (see docs/rag_architecture.md):
- Metadata enrichment only
- NO graph modification
- NO vector store access
- NO persistence
- Agent-layer utility
"""

import logging
import re
from pathlib import Path
from typing import List, Set, Optional

logger = logging.getLogger(__name__)


# Test file patterns
TEST_PATTERNS = [
    r"test_.*\.py$",       # Python: test_foo.py
    r".*_test\.py$",       # Python: foo_test.py
    r".*\.spec\.ts$",      # TypeScript: foo.spec.ts
    r".*\.spec\.js$",      # JavaScript: foo.spec.js
    r".*\.test\.ts$",      # TypeScript: foo.test.ts
    r".*\.test\.js$",      # JavaScript: foo.test.js
    r".*\.test\.tsx$",     # React: foo.test.tsx
    r".*\.spec\.tsx$",     # React: foo.spec.tsx
]


class TestLinker:
    """
    Links test files to source files using patterns and imports.
    
    Strategy:
    1. Detect test files by filename pattern
    2. Extract imports from test content
    3. Infer source file from imports or filename similarity
    """
    
    def __init__(self):
        """Initialize test linker."""
        self.test_patterns = [re.compile(p) for p in TEST_PATTERNS]
        logger.debug("TestLinker initialized")
    
    def is_test_file(self, file_path: str) -> bool:
        """
        Check if file is a test file.
        
        Args:
            file_path: File path to check
        
        Returns:
            True if file matches test patterns
        """
        filename = Path(file_path).name
        return any(pattern.match(filename) for pattern in self.test_patterns)
    
    def infer_source_file(self, test_file_path: str, test_content: str) -> Optional[str]:
        """
        Infer source file from test file.
        
        Strategy:
        1. Extract imports from test content
        2. Look for local imports (not external packages)
        3. Fall back to filename similarity
        
        Args:
            test_file_path: Path to test file
            test_content: Content of test file
        
        Returns:
            Inferred source file path, or None
        """
        # Strategy 1: Extract imports
        imports = self._extract_imports(test_content, test_file_path)
        if imports:
            # Prefer the first local import
            return imports[0]
        
        # Strategy 2: Filename similarity
        return self._infer_from_filename(test_file_path)
    
    def _extract_imports(self, content: str, test_file_path: str) -> List[str]:
        """
        Extract local imports from test file.
        
        Args:
            content: Test file content
            test_file_path: Path to test file
        
        Returns:
            List of local import paths
        """
        imports = []
        test_path = Path(test_file_path)
        test_dir = test_path.parent
        
        # Python imports
        if test_path.suffix == ".py":
            # from foo import bar
            # import foo
            py_imports = re.findall(r"from\s+(\S+)\s+import|import\s+(\S+)", content)
            for match in py_imports:
                module = match[0] or match[1]
                # Skip external packages (no dots, or starts with common packages)
                if module and not module.startswith(("pytest", "unittest", "mock")):
                    # Convert module to file path
                    if "." in module:
                        # Relative import
                        parts = module.split(".")
                        inferred = test_dir / f"{parts[-1]}.py"
                    else:
                        inferred = test_dir / f"{module}.py"
                    
                    imports.append(str(inferred))
        
        # JavaScript/TypeScript imports
        elif test_path.suffix in (".js", ".ts", ".tsx", ".jsx"):
            # import foo from './foo'
            # import { bar } from '../src/bar'
            js_imports = re.findall(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", content)
            for imp in js_imports:
                # Skip node_modules
                if not imp.startswith((".", "/")):
                    continue
                
                # Resolve relative path
                if imp.startswith("."):
                    inferred = (test_dir / imp).resolve()
                    # Add extension if missing
                    if not inferred.suffix:
                        for ext in [".ts", ".tsx", ".js", ".jsx"]:
                            if (Path(str(inferred) + ext)).exists():
                                inferred = Path(str(inferred) + ext)
                                break
                    imports.append(str(inferred))
        
        logger.debug(f"Extracted {len(imports)} imports from {test_file_path}")
        return imports
    
    def _infer_from_filename(self, test_file_path: str) -> Optional[str]:
        """
        Infer source file from test filename.
        
        Examples:
            test_foo.py -> foo.py
            foo_test.py -> foo.py
            foo.spec.ts -> foo.ts
            foo.test.js -> foo.js
        
        Args:
            test_file_path: Path to test file
        
        Returns:
            Inferred source file path
        """
        test_path = Path(test_file_path)
        filename = test_path.name
        
        # Remove test patterns
        source_name = filename
        source_name = re.sub(r"^test_", "", source_name)
        source_name = re.sub(r"_test\.", ".", source_name)
        source_name = re.sub(r"\.spec\.", ".", source_name)
        source_name = re.sub(r"\.test\.", ".", source_name)
        
        # If no change, can't infer
        if source_name == filename:
            return None
        
        # Build source path
        source_path = test_path.parent / source_name
        
        logger.debug(f"Inferred source from filename: {test_file_path} -> {source_path}")
        return str(source_path)
    
    def enrich_chunk_metadata(self, chunks: List[dict], all_file_paths: List[str]) -> List[dict]:
        """
        Enrich chunks with test-source links.
        
        ARCHITECTURE: Metadata enrichment only, no graph/store modification.
        
        Args:
            chunks: List of chunk dictionaries
            all_file_paths: List of all file paths being ingested
        
        Returns:
            Enriched chunks with test_files metadata
        """
        # Build test -> source mapping
        test_to_source = {}
        for file_path in all_file_paths:
            if self.is_test_file(file_path):
                # For now, we don't have content here
                # Source inference happens during chunking
                pass
        
        # For each chunk, check if it's a source file with tests
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            source = metadata.get("source", "")
            
            if not source:
                continue
            
            # Find test files that reference this source
            test_files = []
            for test_path in all_file_paths:
                if not self.is_test_file(test_path):
                    continue
                
                # Simple filename-based matching for now
                inferred = self._infer_from_filename(test_path)
                if inferred and Path(inferred).resolve() == Path(source).resolve():
                    test_files.append(test_path)
            
            if test_files:
                metadata["test_files"] = test_files
                logger.info(f"Linked {len(test_files)} test(s) to {source}")
        
        return chunks


def link_test_to_source(
    test_file_path: str,
    test_content: str,
    linker: Optional[TestLinker] = None
) -> Optional[str]:
    """
    Convenience function to link a test file to its source.
    
    Args:
        test_file_path: Path to test file
        test_content: Content of test file
        linker: Optional TestLinker instance
    
    Returns:
        Inferred source file path, or None
    """
    if linker is None:
        linker = TestLinker()
    
    if not linker.is_test_file(test_file_path):
        return None
    
    return linker.infer_source_file(test_file_path, test_content)
