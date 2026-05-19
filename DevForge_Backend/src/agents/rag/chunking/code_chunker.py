"""Code-aware chunker using Tree-sitter AST parsing.

ARCHITECTURE (see docs/rag_architecture.md):
- Extracts functions, classes, docstrings, imports
- Falls back to text chunking if parsing fails
- Stores metadata for graph reconstruction (Day 5)
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
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
                logger.warning(
                    f"[ISSUE-3-VERIFY] AST parsing found 0 entities for {file_path}, falling back to text chunking",
                    extra={"metric": "ast_fallback_count", "file": file_path}
                )
                fallback_chunks = self.text_fallback.chunk(content, file_path)
                for c in fallback_chunks:
                    c.setdefault("metadata", {})["ast_fallback"] = True
                return fallback_chunks
            
            return chunks
        except Exception as e:
            # Enhanced logging: Show exception type and input preview for debugging
            input_preview = content[:200].replace('\n', '\\n')
            logger.warning(
                f"[ISSUE-3-VERIFY] AST parsing failed for {file_path} ({type(e).__name__}: {e}). "
                f"Input preview: {input_preview}... Falling back to text chunking.",
                extra={"metric": "ast_fallback_count", "file": file_path}
            )
            fallback_chunks = self.text_fallback.chunk(content, file_path)
            for c in fallback_chunks:
                c.setdefault("metadata", {})["ast_fallback"] = True
            return fallback_chunks
    
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
            
            # DEBUG: Inspect AST structure
            logger.info(f"[AST_DEBUG] Root node type: {root.type}")
            logger.info(f"[AST_DEBUG] Root has children: {root.child_count > 0}")
            
            # Log first-level children
            if root.child_count > 0:
                child_types = []
                for i in range(root.child_count):
                    child = root.child(i)
                    child_types.append(child.type)
                logger.info(f"[AST_DEBUG] First-level children types: {child_types}")
            
            # Find and inspect function_definition nodes
            # self._debug_inspect_nodes(root, content, file_path)
            
        except Exception as parse_error:
            logger.error(f"Tree-sitter parse() failed for {file_path}: {type(parse_error).__name__}: {parse_error}")
            raise
        
        chunks = []
        lines = normalized_content.split('\n')
        
        # Extract imports
        imports = self._extract_imports(root, normalized_content, file_path, language)
        logger.info(f"[IMPORT_FLOW] Extracted {len(imports)} import chunks from {file_path}")
        if imports:
            chunks.extend(imports)
        
        # Extract imported names from import chunks for call extraction
        imported_names = set()
        logger.info(f"[IMPORT_DEBUG] Processing {len(imports)} import chunks")
        logger.info(f"[IMPORT_DEBUG] Before processing imports")
        
        for i, chunk in enumerate(imports):
            try:
                logger.info(f"[IMPORT_DEBUG] Chunk {i}: {chunk}")
                metadata = chunk.get('metadata', {})
                logger.info(f"[IMPORT_DEBUG] Chunk {i} metadata: {metadata}")
                
                # All chunks in 'imports' list are import chunks - no need for chunk_type check
                chunk_imports = metadata.get('imports', [])
                logger.info(f"[IMPORT_DEBUG] Chunk {i} imports field: {chunk_imports}")
                imported_names.update(chunk_imports)
                logger.info(f"[IMPORT_PROP_DEBUG] Import chunk imports: {chunk_imports}")
            except Exception as e:
                logger.error(f"[IMPORT_DEBUG] ERROR processing chunk {i}: {type(e).__name__}: {e}")
                raise
        
        logger.info(f"[IMPORT_DEBUG] After processing imports")
        logger.info(f"[IMPORT_DEBUG] Final imported_names: {imported_names}")
        
        # Extract functions and classes
        logger.info(f"[ENTITY_FLOW] About to extract entities with {len(imported_names)} imported names")
        entity_chunks, entities = self._extract_entities(root, normalized_content, file_path, language, lines, imported_names)
        chunks.extend(entity_chunks)
        
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

            # Collect all import nodes then emit ONE chunk per file.
            # Each import statement must not be its own chunk — that floods the
            # result set with low-signal lines and pushes class/function chunks
            # past the default chunksPerFile() window.
            import_nodes = [node for node, _ in captures]
            if not import_nodes:
                return []

            all_symbols: Set[str] = set()
            import_lines: List[str] = []
            for node in import_nodes:
                text = content[node.start_byte:node.end_byte]
                import_lines.append(text)
                all_symbols.update(self._extract_imported_symbols(text, language))

            combined_text = "\n".join(import_lines)
            first_node = import_nodes[0]
            last_node = import_nodes[-1]

            metadata = ChunkMetadata(
                chunk_type="import",
                name="imports",
                language=language,
                source=file_path,
                start_line=first_node.start_point[0] + 1,
                end_line=last_node.end_point[0] + 1,
                imports=list(all_symbols),
            )
            logger.info(f"[IMPORT_METADATA_DEBUG] Single import chunk: {len(import_nodes)} statements, {len(all_symbols)} symbols")
            chunks.append(self._create_chunk_dict(combined_text, metadata))

        except Exception as e:
            logger.debug(f"Import extraction failed: {e}")
        
        return chunks
    
    def _extract_entities(self, root, content: str, file_path: str, language: str, lines: List[str], imported_names: Set[str]) -> Tuple[List[Dict], Dict]:
        """Extract functions and classes."""
        chunks = []
        logger.info(f"[ENTITY_FLOW] Starting entity extraction with imported_names={imported_names}")
        
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
                    # Extract entity name using node.text (proper UTF-8 decoding)
                    try:
                        raw_name = node.text.decode('utf-8')
                    except (UnicodeDecodeError, AttributeError):
                        # Fallback to byte slicing if node.text fails
                        raw_name = content[node.start_byte:node.end_byte]
                    
                    clean_name = self._validate_and_clean_name(raw_name, node, capture_name, file_path)
                    
                    if clean_name:
                        # Find parent entity
                        parent = node.parent
                        if parent and parent.id in entities:
                            entities[parent.id]['name'] = clean_name
                            logger.info(f"[ENTITY_NAME] Extracted {capture_name}: '{clean_name}' from {file_path}")
                    else:
                        logger.warning(f"[ENTITY_NAME] Invalid name extracted: '{raw_name}' ({capture_name}) from {file_path}")
            
            # Create chunks for entities
            known_entities = set()
            
            # Use the passed imported_names instead of trying to build from empty chunks
            logger.info(f"[IMPORT_PASS_DEBUG] Using passed imported_names={imported_names}")
            
            # Aggregate all imports for debugging
            aggregated_imports = set(imported_names)
            logger.info(f"[IMPORT_AGG_DEBUG] aggregated_imports={aggregated_imports}")
            logger.info(f"[CALL_FLOW] About to process {len(entities)} entities for call extraction")
            
            # DEBUG: Check what entities actually contains
            logger.info(f"[ENTITY_DEBUG] entities type: {type(entities)}, len: {len(entities)}")
            if hasattr(entities, 'values'):
                logger.info(f"[ENTITY_DEBUG] entities has .values() method")
            else:
                logger.error(f"[ENTITY_DEBUG] CRITICAL: entities is {type(entities)}, not dict! Cannot call .values()")
            
            # First pass: collect all entity names into known_entities
            for entity_data in entities.values():
                if 'name' not in entity_data:
                    logger.warning(f"[ENTITY_NAME] Skipping entity without name in {file_path}")
                    continue
                name = entity_data['name']
                known_entities.add(name)
            
            # Second pass: extract calls with complete known_entities set
            logger.info(f"[CALL_FLOW] Starting second pass: call extraction for {len(entities)} entities")
            for entity_data in entities.values():
                if 'name' not in entity_data:
                    logger.warning(f"[ENTITY_NAME] Skipping entity without name in {file_path}")
                    continue
                
                node = entity_data['node']
                name = entity_data['name']
                entity_type = 'function' if entity_data['type'] == 'function' else 'class'
                
                # Final validation of entity name
                if not self._is_valid_entity_name(name):
                    logger.error(f"[ENTITY_NAME] CRITICAL: Invalid entity name '{name}' in {file_path} - SKIPPING")
                    continue
                
                logger.info(f"[ENTITY_NAME] Processing {entity_type}: '{name}' in {file_path}")
                
                # Extract entity text using node.text (proper UTF-8 decoding)
                try:
                    entity_text = node.text.decode('utf-8')
                except (UnicodeDecodeError, AttributeError):
                    # Fallback to byte slicing if node.text fails
                    entity_text = content[node.start_byte:node.end_byte]
                
                # Extract docstring
                docstring = self._extract_docstring(entity_text, language)
                
                # Extract instance type mapping if it's a class
                instance_type_map = {}
                if entity_type == "class":
                    instance_type_map = self._extract_instance_type_map(node, content, language)
                    if instance_type_map:
                        logger.info(f"[INSTANCE_MAP] Found {len(instance_type_map)} instance mappings in {name}")

                # Extract function calls with strict filtering
                logger.info(f"[CALL_ENTRY_DEBUG] About to call _extract_calls for {entity_type} '{name}' with {len(aggregated_imports)} imports")
                calls = self._extract_calls(node, content, language, known_entities, aggregated_imports, instance_type_map)
                
                # DEBUG: Log calls extraction
                logger.info(f"[CALLS_DEBUG] After _extract_calls(): type={type(calls)}, value={calls}")
                
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
                
                # DEBUG: Log types right after ChunkMetadata creation
                logger.info(f"[METADATA_CREATE_DEBUG] After ChunkMetadata creation - calls type: {type(metadata.calls)}, value: {metadata.calls}")
                
                # DEBUG: Log metadata before creating chunk dict
                chunk_dict = self._create_chunk_dict(entity_text, metadata)
                logger.info(f"[METADATA_DEBUG] Before storage: type(metadata.calls)={type(metadata.calls)}, metadata.calls={metadata.calls}")
                logger.info(f"[METADATA_DEBUG] Full metadata dict: {chunk_dict['metadata']}")
                
                chunks.append(chunk_dict)
        
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
        
        return chunks, entities
    
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
    
    def _extract_calls(self, node, content: str, language: str, known_entities: Set[str], imported_names: Set[str], instance_type_map: Optional[Dict[str, str]] = None) -> List[str]:
        """Extract function calls, strictly filtering to known entities and imported names."""
        calls = set()
        instance_type_map = instance_type_map or {}
        
        # DEBUG: Log filtering sets
        logger.info(f"[CALL_DEBUG] known_entities={known_entities}")
        logger.info(f"[CALL_DEBUG] imported_names={imported_names}")
        
        try:
            if language == 'python':
                # Full builtins set
                safety_blocklist = {
                    'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes', 'callable',
                    'chr', 'classmethod', 'compile', 'complex', 'delattr', 'dict', 'dir', 'divmod',
                    'enumerate', 'eval', 'exec', 'filter', 'float', 'format', 'frozenset', 'getattr',
                    'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int', 'isinstance',
                    'issubclass', 'iter', 'len', 'list', 'locals', 'map', 'max', 'memoryview', 'min',
                    'next', 'object', 'oct', 'open', 'ord', 'pow', 'print', 'property', 'range',
                    'repr', 'reversed', 'round', 'set', 'setattr', 'slice', 'sorted', 'staticmethod',
                    'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip',
                    # Generic method names
                    'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'index', 'count', 'sort',
                    'reverse', 'copy', 'split', 'join', 'strip', 'lstrip', 'rstrip', 'replace',
                    'find', 'rfind', 'startswith', 'endswith', 'lower', 'upper', 'title', 'capitalize',
                    'isalpha', 'isdigit', 'isalnum', 'isspace', 'istitle', 'isupper', 'islower',
                    'get', 'set', 'keys', 'values', 'items', 'update', 'pop', 'clear', 'copy',
                    'add', 'remove', 'discard', 'union', 'intersection', 'difference', 'symmetric_difference',
                    'issubset', 'issuperset', 'isdisjoint', 'update', 'intersection_update', 'difference_update',
                    'symmetric_difference_update', 'read', 'write', 'close', 'flush', 'seek', 'tell',
                    'fileno', 'isatty', 'truncate', 'writable', 'readable', 'seekable', 'closed',
                    'encode', 'decode', 'format', 'format_map', 'expandtabs', 'center', 'ljust', 'rjust',
                    'zfill', 'count', 'find', 'rfind', 'index', 'rindex', 'capitalize', 'casefold',
                    'title', 'swapcase', 'maketrans', 'translate', 'partition', 'rpartition'
                }
                
                # Captures: func() AND self.func() / obj.func()
                # Simplified query: capture only the call name, we will resolve base via AST walk
                query_str = """
                (call
                  function: (identifier) @call_name)
                (call
                  function: (attribute
                    attribute: (identifier) @call_name))
                """
            elif language in ('javascript', 'typescript'):
                # Safety blocklist for JavaScript/TypeScript
                safety_blocklist = {
                    'console', 'log', 'error', 'warn', 'info', 'debug',
                    # Generic method names
                    'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'index', 'count', 'sort',
                    'reverse', 'copy', 'split', 'join', 'strip', 'lstrip', 'rstrip', 'replace',
                    'find', 'rfind', 'startswith', 'endswith', 'lower', 'upper', 'title', 'capitalize',
                    'isalpha', 'isdigit', 'isalnum', 'isspace', 'istitle', 'isupper', 'islower',
                    'get', 'set', 'keys', 'values', 'items', 'update', 'pop', 'clear', 'copy',
                    'add', 'remove', 'discard', 'union', 'intersection', 'difference', 'symmetric_difference',
                    'issubset', 'issuperset', 'isdisjoint', 'update', 'intersection_update', 'difference_update',
                    'symmetric_difference_update', 'read', 'write', 'close', 'flush', 'seek', 'tell',
                    'fileno', 'isatty', 'truncate', 'writable', 'readable', 'seekable', 'closed',
                    'encode', 'decode', 'format', 'format_map', 'expandtabs', 'center', 'ljust', 'rjust',
                    'zfill', 'count', 'find', 'rfind', 'index', 'rindex', 'capitalize', 'casefold',
                    'title', 'swapcase', 'maketrans', 'translate', 'partition', 'rpartition'
                }
                
                # Captures: func() AND this.func() / obj.func()
                # Simplified query: capture only the call name, we will resolve base via AST walk
                query_str = """
                (call_expression
                  function: (identifier) @call_name)
                (call_expression
                  function: (member_expression
                    property: (property_identifier) @call_name))
                """
            else:
                return []
            
            # Get language object for querying
            from tree_sitter_languages import get_language
            lang_obj = get_language(language)
            query = lang_obj.query(query_str)
            captures = query.captures(node)
            
            for call_node, capture_name in captures:
                if capture_name != "call_name":
                    continue
                
                try:
                    call_name = call_node.text.decode('utf-8')
                except (UnicodeDecodeError, AttributeError):
                    call_name = content[call_node.start_byte:call_node.end_byte]
                
                # 1. Primary Check: Direct function calls or local imports
                # Priority: Known entities and imports always win
                if call_name in known_entities or call_name in imported_names:
                    if call_name not in safety_blocklist:
                        calls.add(call_name)
                        logger.debug(f"[CALL_ACCEPTED] {call_name}")
                        continue

                # 2. Instance Call Resolution: WALK UP the AST to find base
                # Patterns: self.x.method() or this.x.method()
                parent = call_node.parent
                base_name = None
                
                if language == 'python':
                    # self.model_router.invoke()
                    # (call function: (attribute object: (attribute object: (identifier) attribute: (identifier)) attribute: (identifier)))
                    if parent and parent.type == "attribute":
                        obj = parent.child_by_field_name("object")
                        if obj and obj.type == "attribute":
                            inner_obj = obj.child_by_field_name("object")
                            inner_attr = obj.child_by_field_name("attribute")
                            
                            if inner_obj:
                                try:
                                    inner_obj_text = inner_obj.text.decode('utf-8')
                                except:
                                    inner_obj_text = content[inner_obj.start_byte:inner_obj.end_byte]
                                    
                                if inner_obj_text in ("self", "cls"):
                                    if inner_attr:
                                        try:
                                            base_name = inner_attr.text.decode('utf-8')
                                        except:
                                            base_name = content[inner_attr.start_byte:inner_attr.end_byte]
                
                elif language in ('javascript', 'typescript'):
                    # this.model_router.invoke()
                    # (call_expression function: (member_expression object: (member_expression object: (this) property: (property_identifier)) property: (property_identifier)))
                    if parent and parent.type == "member_expression":
                        obj = parent.child_by_field_name("object")
                        if obj and obj.type == "member_expression":
                            inner_obj = obj.child_by_field_name("object")
                            inner_prop = obj.child_by_field_name("property")
                            
                            if inner_obj and inner_obj.type == "this":
                                if inner_prop:
                                    try:
                                        base_name = inner_prop.text.decode('utf-8')
                                    except:
                                        base_name = content[inner_prop.start_byte:inner_prop.end_byte]

                if base_name:
                    resolved_class = self._resolve_instance_calls(
                        base_name, instance_type_map, known_entities, imported_names, language
                    )
                    
                    if resolved_class and resolved_class not in safety_blocklist:
                        calls.add(resolved_class)
                        logger.info(f"[CALL_RESOLVED] {base_name}.{call_name} -> {resolved_class}")
                        continue
                
                # 3. Final Fallback: Keep the call if it's not blocked
                # This ensures we don't drop calls that didn't resolve but might be useful
                if call_name not in safety_blocklist and len(call_name) > 1:
                    # Optional: Add heuristic for external library calls if wanted, 
                    # but for now we follow the "don't add layer 3" rule.
                    # We only add it to 'calls' if it's already in known_entities/imports 
                    # (handled in step 1) or resolved (handled in step 2).
                    # Actually, the user says "do NOT drop call" if resolution fails, 
                    # but also says "KEEP import + local filtering". 
                    # I'll stick to the strict filtering requested: direct match or resolved instance.
                    pass
        
        except Exception as e:
            logger.debug(f"Call extraction failed: {e}")
        
        return list(calls)

    def _extract_instance_type_map(self, node, content: str, language: str) -> Dict[str, str]:
        """Extract mapping of instance variables to their types (classes)."""
        instance_map = {}
        
        try:
            if language == 'python':
                # self.x = Class()
                query_str = """
                (assignment
                  left: (attribute
                    object: (identifier) @self_obj
                    attribute: (identifier) @instance_name)
                  right: (call
                    function: (identifier) @class_name))
                """
            elif language in ('javascript', 'typescript'):
                # this.x = new Class()
                query_str = """
                (assignment_expression
                  left: (member_expression
                    object: (this) @this_obj
                    property: (property_identifier) @instance_name)
                  right: (new_expression
                    constructor: (identifier) @class_name))
                """
            else:
                return {}

            from tree_sitter_languages import get_language
            lang_obj = get_language(language)
            query = lang_obj.query(query_str)
            captures = query.captures(node)
            
            # Group by parent assignment node
            assignments = {}
            for cap_node, name in captures:
                parent = cap_node.parent
                while parent and parent.type not in ('assignment', 'assignment_expression'):
                    parent = parent.parent
                if not parent: continue
                
                if parent.id not in assignments:
                    assignments[parent.id] = {}
                assignments[parent.id][name] = cap_node

            for ass_id, caps in assignments.items():
                inst_node = caps.get("instance_name")
                class_node = caps.get("class_name")
                
                if inst_node and class_node:
                    try:
                        inst_name = inst_node.text.decode('utf-8')
                        cls_name = class_node.text.decode('utf-8')
                        instance_map[inst_name] = cls_name
                    except:
                        pass
                        
        except Exception as e:
            logger.debug(f"Instance map extraction failed: {e}")
            
        return instance_map

    def _resolve_instance_calls(self, instance_name: str, instance_map: Dict[str, str], known_entities: Set[str], imported_names: Set[str], language: str) -> Optional[str]:
        """Resolve instance variable to a class name using map or fallbacks."""
        # 1. Exact match from map
        if instance_name in instance_map:
            cls = instance_map[instance_name]
            if cls in known_entities or cls in imported_names:
                return cls

        # 2. Heuristic fallback: snake_case -> PascalCase or camelCase -> PascalCase
        # model_router -> ModelRouter
        # apiService -> ApiService
        parts = re.split(r'[_]', instance_name) if '_' in instance_name else re.findall(r'[a-zA-Z][^A-Z]*', instance_name)
        heuristic_name = "".join(p.capitalize() for p in parts if p)
        
        if heuristic_name in known_entities or heuristic_name in imported_names:
            return heuristic_name
            
        return None
    
    def _extract_imported_symbols(self, import_text: str, language: str) -> Set[str]:
        """Extract imported symbol names from import statement text."""
        imported_symbols = set()
        
        # DEBUG: Log exactly what import text we receive
        logger.info(f"[IMPORT_SYMBOL_DEBUG] Received import text: '{import_text}' (length: {len(import_text)})")
        
        try:
            if language == 'python':
                # Handle various import formats:
                # import module
                # import module as alias
                # import module1, module2
                # from module import name
                # from module import name as alias
                # from module import name1, name2
                # from module import *
                
                import re
                
                # from module import name1, name2 as alias2
                from_import_pattern = r'from\s+\S+\s+import\s+(.+)$'
                match = re.search(from_import_pattern, import_text.strip())
                if match:
                    imports_part = match.group(1)
                    # Handle "import *" - skip as it doesn't give us specific names
                    if '*' not in imports_part:
                        # Split by commas and process each
                        for part in imports_part.split(','):
                            part = part.strip()
                            # Handle "name as alias"
                            if ' as ' in part:
                                name = part.split(' as ')[0].strip()
                            else:
                                name = part
                            imported_symbols.add(name)
                
                # import module1, module2 as alias2
                import_pattern = r'import\s+(.+)$'
                match = re.search(import_pattern, import_text.strip())
                if match:
                    imports_part = match.group(1)
                    # Split by commas and process each
                    for part in imports_part.split(','):
                        part = part.strip()
                        # Handle "module as alias"
                        if ' as ' in part:
                            module_name = part.split(' as ')[0].strip()
                        else:
                            module_name = part
                        # For direct imports, the module name is what we might call
                        imported_symbols.add(module_name)
            
            elif language in ('javascript', 'typescript'):
                # Handle JS/TS import formats:
                # import name from 'module'
                # import { name1, name2 as alias2 } from 'module'
                # import * as alias from 'module'
                # import default_name, { name1, name2 } from 'module'
                
                import re
                
                # import { name1, name2 as alias2 } from 'module'
                named_import_pattern = r'import\s+.*?\{([^}]+)\}\s+from'
                match = re.search(named_import_pattern, import_text)
                if match:
                    imports_part = match.group(1)
                    for part in imports_part.split(','):
                        part = part.strip()
                        # Handle "name as alias"
                        if ' as ' in part:
                            name = part.split(' as ')[0].strip()
                        else:
                            name = part
                        # Remove "default" keyword if present
                        if name != 'default':
                            imported_symbols.add(name)
                
                # import name from 'module' (default import)
                default_import_pattern = r'import\s+(\w+)\s+from'
                match = re.search(default_import_pattern, import_text)
                if match:
                    imported_symbols.add(match.group(1))
        
        except Exception as e:
            logger.debug(f"Failed to extract imported symbols: {e}")
        
        return imported_symbols
    
    # _debug_inspect_nodes removed
    
    def _validate_and_clean_name(self, raw_name: str, node, capture_name: str, file_path: str) -> Optional[str]:
        """
        Validate and clean extracted entity name.
        
        Ensures:
        - Name is a valid identifier (letters, numbers, underscores)
        - Name is not empty or just symbols
        - Name has reasonable length
        """
        if not raw_name:
            logger.warning(f"[ENTITY_NAME] Empty name extracted for {capture_name} in {file_path}")
            return None
        
        # Strip whitespace and common invalid characters
        clean_name = raw_name.strip()
        
        # Remove surrounding quotes if present
        if (clean_name.startswith('"') and clean_name.endswith('"')) or \
           (clean_name.startswith("'") and clean_name.endswith("'")):
            clean_name = clean_name[1:-1]
        
        # Validate name pattern (Python identifier rules)
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', clean_name):
            logger.warning(f"[ENTITY_NAME] Invalid identifier pattern: '{clean_name}' (raw: '{raw_name}') for {capture_name} in {file_path}")
            return None
        
        # Check for minimum length
        if len(clean_name) < 1:
            logger.warning(f"[ENTITY_NAME] Name too short: '{clean_name}' for {capture_name} in {file_path}")
            return None
        
        # Check for maximum reasonable length
        if len(clean_name) > 100:
            logger.warning(f"[ENTITY_NAME] Name too long ({len(clean_name)} chars): '{clean_name[:50]}...' for {capture_name} in {file_path}")
            return None
        
        # Reject single character names that are just symbols
        if len(clean_name) == 1 and clean_name in '[]{}(),;:`"\'r':
            logger.warning(f"[ENTITY_NAME] Single symbol character: '{clean_name}' for {capture_name} in {file_path}")
            return None
        
        return clean_name
    
    def _is_valid_entity_name(self, name: str) -> bool:
        """
        Final validation of entity name before processing.
        
        Returns True if name is valid, False otherwise.
        """
        if not name or not isinstance(name, str):
            return False
        
        # Must be a valid identifier
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            return False
        
        # Must not be just symbols
        if len(name) == 1 and name in '[]{}(),;:`"\'r':
            return False
        
        # Must have reasonable length
        if len(name) < 1 or len(name) > 100:
            return False
        
        return True
