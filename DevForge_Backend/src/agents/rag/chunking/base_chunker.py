"""Base chunker interface for Phase 10.1 code-aware chunking.

ARCHITECTURE (see docs/rag_architecture.md):
- Chunkers are called BY agents, not exposed as tools
- Store metadata in chunk dict for graph reconstruction
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class ChunkMetadata:
    """Metadata for a document chunk."""
    
    chunk_type: str  # "function", "class", "text", "import"
    name: str  # Entity name or "chunk_N"
    language: Optional[str] = None  # "python", "javascript", etc.
    source: str = ""  # File path
    start_line: int = 0
    end_line: int = 0
    imports: List[str] = None  # Imported modules/functions
    calls: List[str] = None  # Functions called in this chunk
    docstring: Optional[str] = None
    
    def __post_init__(self):
        if self.imports is None:
            self.imports = []
        if self.calls is None:
            self.calls = []


class BaseChunker(ABC):
    """Abstract base class for document chunkers."""
    
    @abstractmethod
    def chunk(self, content: str, file_path: str) -> List[Dict]:
        """
        Chunk document content.
        
        Args:
            content: Document text content
            file_path: Source file path
        
        Returns:
            List of chunk dictionaries with metadata
        """
        pass
    
    @abstractmethod
    def is_supported(self, file_path: str) -> bool:
        """
        Check if this chunker supports the given file.
        
        Args:
            file_path: File path to check
        
        Returns:
            True if this chunker can handle the file
        """
        pass
    
    def _create_chunk_dict(self, content: str, metadata: ChunkMetadata) -> Dict:
        """
        Create standardized chunk dictionary.
        
        Args:
            content: Chunk content
            metadata: Chunk metadata
        
        Returns:
            Chunk dictionary with content and metadata
        """
        # DEBUG: Log types before creating dict
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[CHUNK_DICT_DEBUG] calls type: {type(metadata.calls)}, value: {metadata.calls}")
        logger.info(f"[CHUNK_DICT_DEBUG] imports type: {type(metadata.imports)}, value: {metadata.imports}")
        
        return {
            "content": content,
            "metadata": {
                "chunk_type": metadata.chunk_type,
                "name": metadata.name,
                "language": metadata.language,
                "source": metadata.source,
                "start_line": metadata.start_line,
                "end_line": metadata.end_line,
                "imports": metadata.imports,
                "calls": metadata.calls,
                "docstring": metadata.docstring,
            }
        }
