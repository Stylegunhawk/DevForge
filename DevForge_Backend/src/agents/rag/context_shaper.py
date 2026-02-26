"""Deterministic RAG context shaper for deduplication, role assignment, and ordering.

ARCHITECTURE:
- Pure logic, no external dependencies (no DB, no LLM)
- Handles qualified ID deduplication (overloads, nested functions)
- Assigns exactly ONE primary entry role
- Deterministic ordering with stable tie-breaking
- Exposes roles in chunk metadata for API/LLM consumption
"""

import logging
from typing import List, Dict, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class ContextShaper:
    """Deterministic RAG context shaper with senior-level refinements.
    
    Features:
    - Qualified ID deduplication (handles overloads, nesting)
    - Single primary entry (exactly one anchor)
    - Stable ordering (deterministic tie-breaking)
    - Role exposure (attached to metadata)
    - Metadata provenance (preserves is_graph_expansion)
    """
    
    def __init__(self, max_chunks: int = 12, max_per_secondary_role: int = 3):
        """Initialize context shaper with limits.
        
        Args:
            max_chunks: Maximum total chunks to return
            max_per_secondary_role: Max chunks per dependency/supporting role
        """
        self.max_chunks = max_chunks
        self.max_per_secondary_role = max_per_secondary_role
    
    def shape_context(
        self,
        chunks: List,  # List of ChunkResult objects
        query_intent: str = "general"
    ) -> List:
        """Main shaping pipeline.
        
        Args:
            chunks: Raw chunks from retrieval/reranking
            query_intent: Query intent for context (future use)
        
        Returns:
            Shaped, deduplicated, role-assigned, ordered chunks
        """
        if not chunks:
            return []
        
        logger.info(f"Context shaping START: {len(chunks)} chunks")
        
        # Step A: Deduplicate by qualified ID with metadata provenance
        deduped = self._deduplicate(chunks)
        logger.info(
            f"After dedup: {len(deduped)} chunks ({len(chunks) - len(deduped)} dropped)"
        )
        
        # Step B: Assign roles (exactly one entry)
        with_roles = self._assign_roles(deduped)
        role_counts = defaultdict(int)
        for c in with_roles:
            role_counts[c.metadata.get("role", "unknown")] += 1
        logger.info(f"Roles assigned: {dict(role_counts)}")
        
        # Step C: Order deterministically
        ordered = self._order_chunks(with_roles)
        
        # Step D: Apply limits
        limited = self._apply_limits(ordered)
        logger.info(f"Context shaping DONE: {len(limited)} final chunks")
        
        return limited
    
    def _get_dedup_key(self, chunk) -> str:
        """Get deduplication key with qualified ID priority.
        
        Priority:
        1. qualified_id (if present) - e.g., "file.py::ClassName::method_name"
        2. (source, symbol_path) - fallback for nested symbols
        3. (file_id, name, type) - last resort
        
        Args:
            chunk: ChunkResult object
        
        Returns:
            Deduplication key string
        """
        metadata = chunk.metadata if hasattr(chunk, 'metadata') else {}
        
        # Priority 1: Use qualified_id if available (best)
        if "qualified_id" in metadata:
            return metadata["qualified_id"]
        
        # Priority 2: Build from source + symbol path
        source = metadata.get("source", "")
        name = metadata.get("name", "")
        if source and name:
            # Handle nested symbols (e.g., "Class.method")
            return f"{source}::{name}"
        
        # Priority 3: Fallback to tuple-based key
        file_id = metadata.get("file_id", "unknown")
        chunk_type = metadata.get("chunk_type", "text")
        chunk_id = getattr(chunk, 'id', 'unknown')
        return f"{file_id}::{name}::{chunk_type}::{chunk_id}"
    
    def _deduplicate(self, chunks: List) -> List:
        """Keep highest-scored instance per qualified ID with metadata provenance.
        
        CRITICAL: Preserve is_graph_expansion across duplicates.
        If ANY duplicate has is_graph_expansion=True, propagate to survivor.
        
        Args:
            chunks: List of ChunkResult objects
        
        Returns:
            Deduplicated list
        """
        groups = defaultdict(list)
        for chunk in chunks:
            key = self._get_dedup_key(chunk)
            groups[key].append(chunk)
        
        deduped = []
        for key, group in groups.items():
            # Keep highest scored chunk
            best = max(group, key=lambda c: getattr(c, 'rerank_score', None) or getattr(c, 'score', 0.0) or 0.0)
            
            # METADATA PROVENANCE: Merge critical flags
            # If ANY chunk in group was from graph expansion, preserve that
            if any(c.metadata.get("is_graph_expansion") for c in group):
                best.metadata["is_graph_expansion"] = True
            
            deduped.append(best)
        
        return deduped
    
    def _assign_roles(self, chunks: List) -> List:
        """Assign exactly ONE entry, rest are dependency/supporting.
        
        Rules:
        - Highest rerank_score → entry (primary anchor)
        - is_graph_expansion=True → dependency
        - Everything else → supporting
        
        Args:
            chunks: Deduplicated chunks
        
        Returns:
            Chunks with roles attached to metadata (sorted by score)
        """
        if not chunks:
            return []
        
        # Sort by score to find primary
        scored = sorted(
            chunks,
            key=lambda c: getattr(c, 'rerank_score', None) or getattr(c, 'score', 0.0) or 0.0,
            reverse=True
        )
        
        # EXACTLY ONE ENTRY (highest scored)
        if scored:
            scored[0].metadata["role"] = "entry"
        
        # Assign rest based on is_graph_expansion
        for chunk in scored[1:]:
            if chunk.metadata.get("is_graph_expansion"):
                chunk.metadata["role"] = "dependency"
            else:
                chunk.metadata["role"] = "supporting"
        
        # ✅ FIX: Return the sorted list 'scored', not the original 'chunks'
        return scored
        
    def _order_chunks(self, chunks: List) -> List:
        """Order chunks deterministically with stable tie-breaker.
        
        Sort key: (role_priority, -score, entity_name, qualified_id)
        
        Args:
            chunks: Role-assigned chunks
        
        Returns:
            Sorted chunk list
        """
        role_priority = {"entry": 1, "dependency": 2, "supporting": 3}
        
        return sorted(chunks, key=lambda c: (
            role_priority.get(c.metadata.get("role"), 999),  # Role first
            -(getattr(c, 'rerank_score', None) or getattr(c, 'score', 0.0) or 0.0),  # Score descending
            c.metadata.get("name", ""),  # Name ascending
            self._get_dedup_key(c)  # Qualified ID as tie-breaker
        ))
    
    def _apply_limits(self, chunks: List) -> List:
        """Apply max chunk limits per role.
        
        Args:
            chunks: Ordered chunks
        
        Returns:
            Limited chunk list
        """
        # Max total chunks
        if len(chunks) <= self.max_chunks:
            return chunks
        
        # Separate by role
        entry = [c for c in chunks if c.metadata.get("role") == "entry"]
        dependency = [c for c in chunks if c.metadata.get("role") == "dependency"]
        supporting = [c for c in chunks if c.metadata.get("role") == "supporting"]
        
        # Entry has no limit (always included)
        # Limit secondary roles
        limited = (
            entry +
            dependency[:self.max_per_secondary_role] +
            supporting[:self.max_per_secondary_role]
        )
        
        # Final hard limit
        return limited[:self.max_chunks]
