"""Code-aware chunker using Tree-sitter AST parsing.

ARCHITECTURE (see docs/rag_architecture.md):
- Extracts functions, classes, docstrings, imports
- Falls back to text chunking if parsing fails
- Stores metadata for graph reconstruction (Day 5)
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Set
import re

from .base_chunker import BaseChunker, ChunkMetadata
from .text_chunker import TextChunker

logger = logging.getLogger(__name__)


# Language capability registry
SUPPORTED_LANGUAGES = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.jsx': 'javascript',
}


class CodeChunker(BaseChunker):
    """
    AST-based code chunker using Tree-sitter.
    
    Extracts:
    - Functions (with docstrings)
    - Classes (with methods)
    - Import statements
    - Function calls
    """
    
    def __init__(self):
        """Initialize code chunker with Tree-sitter parsers."""
        self.parsers = {}
        self.text_fallback = TextChunker()
        self._init_parsers()
    
    def _init_parsers(self):
        """Initialize Tree-sitter parsers for supported languages."""
        try:
            # Try to load language libraries (tree-sitter 0.25 API)
            try:
                import tree_sitter_python
                self.parsers['python'] = tree_sitter_python.language()
                logger.info("Python parser initialized")
            except Exception as e:
                logger.warning(f"Python parser failed: {e}")
            
            try:
                import tree_sitter_javascript
                self.parsers['javascript'] = tree_sitter_javascript.language()
                logger.info("JavaScript parser initialized")
            except Exception as e:
                logger.warning(f"JavaScript parser failed: {e}")
            
            try:
                import tree_sitter_typescript
                ts_lang = tree_sitter_typescript.language_typescript()
                self.parsers['typescript'] = ts_lang
                logger.info("TypeScript parser initialized")
            except Exception as e:
                logger.warning(f"TypeScript parser failed: {e}")
        
        except ImportError as e:
            logger.warning(f"Tree-sitter not available: {e}")
    
    def _create_parser(self, language):
        """
        Create parser for a language (tree-sitter 0.25 API).
        
        Note: In 0.25+, language objects are used directly, not via Parser.set_language().
        """
        return language  # Just return the language object
    
    def is_supported(self, file_path: str) -> bool:
        """Check if file extension is supported."""
        ext = Path(file_path).suffix.lower()
        return ext in SUPPORTED_LANGUAGES and SUPPORTED_LANGUAGES[ext] in self.parsers
    
    def chunk(self, content: str, file_path: str) -> List[Dict]:
        """
        Chunk code using AST parsing.
        
        Falls back to text chunking if parsing fails.
        
        Args:
            content: Code content
            file_path: Source file path
        
        Returns:
            List of code chunks with metadata
        """
        ext = Path(file_path).suffix.lower()
        language = SUPPORTED_LANGUAGES.get(ext)
        
        if not language or language not in self.parsers:
            logger.info(f"Unsupported language for {file_path}, using text chunking")
            return self.text_fallback.chunk(content, file_path)
        
        try:
            return self._chunk_with_ast(content, file_path, language)
        except Exception as e:
            logger.warning(f"AST parsing failed for {file_path}: {e}, falling back to text")
            return self.text_fallback.chunk(content, file_path)
    
    def _chunk_with_ast(self, content: str, file_path: str, language: str) -> List[Dict]:
        """
        Parse code with Tree-sitter and extract chunks.
        
        Args:
            content: Code content
            file_path: Source file path
            language: Programming language
        
        Returns:
            List of chunks (functions, classes, imports)
        """
        # Tree-sitter 0.25 API: Create Parser and parse with language
        from tree_sitter import Parser
        
        lang_obj = self.parsers[language]
        parser = Parser(lang_obj)
        tree = parser.parse(bytes(content, 'utf8'))
        root = tree.root_node
        
        chunks = []
        lines = content.split('\n')
        
        # Extract imports
        imports = self._extract_imports(root, content, file_path, language)
        if imports:
            chunks.extend(imports)
        
        # Extract functions and classes
        entities = self._extract_entities(root, content, file_path, language, lines)
        chunks.extend(entities)
        
        logger.info(f"AST chunking: {len(chunks)} chunks from {file_path}")
        return chunks
    
    def _extract_imports(self, root, content: str, file_path: str, language: str) -> List[Dict]:
        """Extract import statements."""
        chunks = []
        
        if language == 'python':
            query_str = """
            (import_statement) @import
            (import_from_statement) @import
            """
        elif language in ('javascript', 'typescript'):
            query_str = """
            (import_statement) @import
            """
        else:
            return []
        
        try:
            # Tree-sitter 0.25: language.query() directly
            lang_obj = self.parsers[language]
            query = lang_obj.query(query_str)
            captures = query.captures(root)
            
            for node, _ in captures:
                start_byte = node.start_byte
                end_byte = node.end_byte
                import_text = content[start_byte:end_byte]
                
                metadata = ChunkMetadata(
                    chunk_type="import",
                    name="imports",
                    language=language,
                    source=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                )
                
                chunks.append(self._create_chunk_dict(import_text, metadata))
        
        except Exception as e:
            logger.debug(f"Import extraction failed: {e}")
        
        return chunks
    
    def _extract_entities(self, root, content: str, file_path: str, language: str, lines: List[str]) -> List[Dict]:
        """Extract functions and classes."""
        chunks = []
        
        if language == 'python':
            query_str = """
            (function_definition
              name: (identifier) @func_name
            ) @function
            (class_definition
              name: (identifier) @class_name
            ) @class
            """
        elif language in ('javascript', 'typescript'):
            query_str = """
            (function_declaration
              name: (identifier) @func_name
            ) @function
            (class_declaration
              name: (identifier) @class_name
            ) @class
            """
        else:
            return []
        
        try:
            # Tree-sitter 0.25: language.query() directly
            lang_obj = self.parsers[language]
            query = lang_obj.query(query_str)
            captures = query.captures(root)
            
            # Group captures by entity
            entities = {}
            for node, capture_name in captures:
                if capture_name in ('function', 'class'):
                    entities[node.id] = {'node': node, 'type': capture_name}
                elif capture_name in ('func_name', 'class_name'):
                    # Find parent entity
                    parent = node.parent
                    if parent and parent.id in entities:
                        entities[parent.id]['name'] = content[node.start_byte:node.end_byte]
            
            # Create chunks for entities
            for entity_data in entities.values():
                if 'name' not in entity_data:
                    continue
                
                node = entity_data['node']
                name = entity_data['name']
                entity_type = 'function' if entity_data['type'] == 'function' else 'class'
                
                start_byte = node.start_byte
                end_byte = node.end_byte
                entity_text = content[start_byte:end_byte]
                
                # Extract docstring
                docstring = self._extract_docstring(entity_text, language)
                
                # Extract function calls
                calls = self._extract_calls(node, content, language)
                
                metadata = ChunkMetadata(
                    chunk_type=entity_type,
                    name=name,
                    language=language,
                    source=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    calls=calls,
                    docstring=docstring,
                )
                
                chunks.append(self._create_chunk_dict(entity_text, metadata))
        
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
        
        return chunks
    
    def _extract_docstring(self, entity_text: str, language: str) -> Optional[str]:
        """Extract docstring from function/class."""
        if language == 'python':
            # Look for triple-quoted string at start
            match = re.search(r'^\s*"""(.*?)"""|^\s*\'\'\'(.*?)\'\'\'', entity_text, re.DOTALL | re.MULTILINE)
            if match:
                return (match.group(1) or match.group(2)).strip()
        
        elif language in ('javascript', 'typescript'):
            # Look for JSDoc comment
            match = re.search(r'/\*\*(.*?)\*/', entity_text, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_calls(self, node, content: str, language: str) -> List[str]:
        """Extract function calls from entity."""
        calls = set()
        
        try:
            if language == 'python':
                query_str = "(call function: (identifier) @call_name)"
            elif language in ('javascript', 'typescript'):
                query_str = "(call_expression function: (identifier) @call_name)"
            else:
                return []
            
            # Tree-sitter 0.25: language.query() directly
            lang_obj = self.parsers[language]
            query = lang_obj.query(query_str)
            captures = query.captures(node)
            
            for call_node, _ in captures:
                call_name = content[call_node.start_byte:call_node.end_byte]
                calls.add(call_name)
        
        except Exception as e:
            logger.debug(f"Call extraction failed: {e}")
        
        return list(calls)
