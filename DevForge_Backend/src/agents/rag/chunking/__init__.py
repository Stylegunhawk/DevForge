"""Chunking module for Phase 10.1 code-aware document processing."""

from .base_chunker import BaseChunker, ChunkMetadata
from .text_chunker import TextChunker

__all__ = ["BaseChunker", "ChunkMetadata", "TextChunker"]

# Code chunker will be added after tree-sitter is installed
try:
    from .code_chunker import CodeChunker
    __all__.append("CodeChunker")
except ImportError:
    CodeChunker = None
