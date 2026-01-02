"""Text-based chunker with overlap for fallback.

ARCHITECTURE: Fallback when AST parsing fails or unsupported language.
"""

import logging
from pathlib import Path
from typing import List, Dict

from .base_chunker import BaseChunker, ChunkMetadata

logger = logging.getLogger(__name__)


class TextChunker(BaseChunker):
    """Simple text-based chunker with overlap."""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        Initialize text chunker.
        
        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def is_supported(self, file_path: str) -> bool:
        """Text chunker supports all files."""
        return True
    
    def chunk(self, content: str, file_path: str) -> List[Dict]:
        """
        Chunk text with overlap.
        
        Args:
            content: Document content
            file_path: Source file path
        
        Returns:
            List of text chunks with metadata
        """
        if not content:
            return []
        
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_size = 0
        chunk_num = 0
        start_line = 0
        
        for line_num, line in enumerate(lines, 1):
            line_len = len(line) + 1  # +1 for newline
            
            # Check if adding this line would exceed chunk size
            if current_size + line_len > self.chunk_size and current_chunk:
                # Create chunk from accumulated lines
                chunk_content = '\n'.join(current_chunk)
                chunk_num += 1
                
                metadata = ChunkMetadata(
                    chunk_type="text",
                    name=f"chunk_{chunk_num}",
                    language=self._detect_language(file_path),
                    source=file_path,
                    start_line=start_line,
                    end_line=line_num - 1,
                )
                
                chunks.append(self._create_chunk_dict(chunk_content, metadata))
                
                # Keep overlap lines
                overlap_lines = self._get_overlap_lines(current_chunk)
                current_chunk = overlap_lines
                current_size = sum(len(line) + 1 for line in current_chunk)
                start_line = line_num - len(overlap_lines)
            
            current_chunk.append(line)
            current_size += line_len
        
        # Add final chunk
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            chunk_num += 1
            
            metadata = ChunkMetadata(
                chunk_type="text",
                name=f"chunk_{chunk_num}",
                language=self._detect_language(file_path),
                source=file_path,
                start_line=start_line,
                end_line=len(lines),
            )
            
            chunks.append(self._create_chunk_dict(chunk_content, metadata))
        
        logger.info(f"Text chunking: {len(chunks)} chunks from {file_path}")
        return chunks
    
    def _get_overlap_lines(self, lines: List[str]) -> List[str]:
        """Get overlap lines from chunk."""
        overlap_size = 0
        overlap_lines = []
        
        # Take lines from end until we reach overlap size
        for line in reversed(lines):
            overlap_size += len(line) + 1
            if overlap_size > self.chunk_overlap:
                break
            overlap_lines.insert(0, line)
        
        return overlap_lines
    
    def _detect_language(self, file_path: str) -> str:
        """Detect language from file extension."""
        ext = Path(file_path).suffix.lower()
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.jsx': 'javascript',
            '.md': 'markdown',
            '.txt': 'text',
        }
        return lang_map.get(ext, 'text')
