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
        self.text_fallback = TextChunker()
        self.supported_languages = set()
        self._check_parser_availability()
    
    def _check_parser_availability(self):
        """Check which languages are available via tree-sitter-languages."""
        try:
            from tree_sitter_languages import get_parser
            
            # Test each language
            for lang in ['python', 'javascript', 'typescript']:
                try:
                    _ = get_parser(lang)
                    self.supported_languages.add(lang)
                    logger.info(f"{lang.capitalize()} parser available")
                except Exception as e:
                    logger.warning(f"{lang.capitalize()} parser unavailable: {e}")
        except ImportError as e:
            logger.warning(f"tree-sitter-languages not available: {e}")
    
    def is_supported(self, file_path: str) -> bool:
        """Check if file extension is supported."""
        ext = Path(file_path).suffix.lower()
        lang = SUPPORTED_LANGUAGES.get(ext)
        return lang in self.supported_languages
    
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
        
        if not language or language not in self.supported_languages:
            logger.info(f"Unsupported language for {file_path}, using text chunking")
            return self.text_fallback.chunk(content, file_path)
        
        logger.info(f"Starting AST parsing for {file_path} (language: {language}, size: {len(content)} bytes)")
        try:
            chunks = self._chunk_with_ast(content, file_path, language)
            
            # CRITICAL FIX: Fallback if AST finds nothing but file is not empty
            # Prevents silent data loss for top-level code (scripts, configs)
            if not chunks and content.strip():
                logger.warning(f"AST parsing found 0 entities for {file_path}, falling back to text chunking")
                return self.text_fallback.chunk(content, file_path)
            
            return chunks
        except Exception as e:
            # Enhanced logging: Show exception type and input preview for debugging
            input_preview = content[:200].replace('\n', '\\n')
            logger.warning(
                f"AST parsing failed for {file_path} ({type(e).__name__}: {e}). "
                f"Input preview: {input_preview}... Falling back to text chunking."
            )
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
        # Normalize input: Strip UTF-8 BOM and invisible Unicode characters
        # Fix for AST parsing failures caused by BOM markers (\ufeff) or zero-width chars
        # that break Tree-sitter parsing even though the Python syntax is valid
        original_len = len(content)
        normalized_content = content.lstrip('\ufeff').replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
        
        # Log normalization details if any characters were stripped
        if len(normalized_content) != original_len:
            stripped = original_len - len(normalized_content)
            logger.info(f"Stripped {stripped} invisible char(s) from {file_path}")
        
        # Show content preview for debugging
        content_preview = normalized_content[:100].replace('\n', '\\n')
        logger.debug(f"Content preview for {file_path}: {content_preview}...")        
        # Tree-sitter API: Use tree_sitter_languages wrapper for compatibility
        # Fix: tree-sitter 0.21.3 + tree-sitter-python 0.25 require proper Language wrapping
        # Direct Parser(lang) fails with "Parsing failed" - use get_parser instead
        from tree_sitter_languages import get_parser
        
        parser = get_parser(language)
        logger.debug(f"Parsing {file_path} with tree-sitter-languages parser for {language}")
        try:
            tree = parser.parse(bytes(normalized_content, 'utf8'))
            root = tree.root_node
            logger.debug(f"Parse successful for {file_path}, root node type: {root.type}")
        except Exception as parse_error:
            logger.error(f"Tree-sitter parse() failed for {file_path}: {type(parse_error).__name__}: {parse_error}")
            raise
        
        chunks = []
        lines = normalized_content.split('\n')
        
        # Extract imports
        imports = self._extract_imports(root, normalized_content, file_path, language)
        if imports:
            chunks.extend(imports)
        
        # Extract functions and classes
        entities = self._extract_entities(root, normalized_content, file_path, language, lines)
        chunks.extend(entities)
        
        logger.info(f"✅ AST chunking successful: {len(chunks)} chunks from {file_path} (imports: {len(imports)}, entities: {len(entities)})")
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
            # Get language object for querying
            from tree_sitter_languages import get_language
            lang_obj = get_language(language)
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
            # Get language object for querying
            from tree_sitter_languages import get_language
            lang_obj = get_language(language)
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
            
            # Get language object for querying
            from tree_sitter_languages import get_language
            lang_obj = get_language(language)
            query = lang_obj.query(query_str)
            captures = query.captures(node)
            
            for call_node, _ in captures:
                call_name = content[call_node.start_byte:call_node.end_byte]
                calls.add(call_name)
        
        except Exception as e:
            logger.debug(f"Call extraction failed: {e}")
        
        return list(calls)
