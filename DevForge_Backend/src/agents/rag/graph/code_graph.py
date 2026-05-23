"""Code graph for context expansion.

ARCHITECTURE (see docs/rag_architecture.md):
- Derived state: Rebuilt from chunk metadata on first access
- Instance-scoped: Each RAGAgent has its own graph
- NO persistence: No pickle, no database, no cache files
- NO API exposure: Internal to retrieval only
- QID format: file::entity (double colon separator)
"""

import logging
from collections import defaultdict, deque
from typing import Dict, List, Set, Optional

logger = logging.getLogger(__name__)


class CodeGraph:
    """
    In-memory code dependency graph for context expansion.
    
    Nodes: Qualified IDs (file::entity)
    Edges: Function calls and imports
    """
    
    def __init__(self):
        """Initialize empty graph."""
        # Adjacency list: QID → Set[related QIDs]
        self._graph: Dict[str, Set[str]] = defaultdict(set)
        
        # Node metadata: QID → chunk metadata
        self._metadata: Dict[str, Dict] = {}
        
        logger.debug("CodeGraph initialized (empty)")
    
    def add_node(self, qid: str, **metadata) -> None:
        """
        Add a node to the graph.
        
        Args:
            qid: Qualified ID (tenant::file::entity)
            **metadata: Chunk metadata (chunk_type, name, calls, imports, etc.)
        """
        parts = qid.split("::")
        if len(parts) < 3:
            logger.warning(f"Invalid QID format (expected tenant::file::entity): {qid}")
            return
        
        tenant_id = parts[0]
        source = parts[1]
        
        # Initialize node if not exists
        if qid not in self._graph:
            self._graph[qid] = set()
        
        # Store metadata
        self._metadata[qid] = metadata
        
        # Add edges from metadata
        calls = metadata.get("calls", [])
        imports = metadata.get("imports", [])
        
        # DEBUG: Log before iteration in graph builder
        logger.info(f"[GRAPH_DEBUG] Before iteration: type(calls)={type(calls)}, calls={calls}")
        logger.info(f"[GRAPH_DEBUG] Before iteration: type(imports)={type(imports)}, imports={imports}")
        
        # Add call edges
        for call in calls:
            # Resolve simple names to full QIDs in same file
            if "::" in call:
                called_qid = call
            else:
                called_qid = f"{tenant_id}::{source}::{call}"
            self.add_edge(qid, called_qid, relation="calls")
        
        # Add import edges
        for imp in imports:
            if "::" in imp:
                self.add_edge(qid, imp, relation="imports")
            else:
                # Handle possible local imports
                called_qid = f"{tenant_id}::{source}::{imp}"
                self.add_edge(qid, called_qid, relation="imports")
    
    def add_edge(self, source_qid: str, target_qid: str, relation: str = "related") -> None:
        """
        Add a directed edge from source to target.
        
        Args:
            source_qid: Source qualified ID
            target_qid: Target qualified ID
            relation: Edge type (calls, imports, related)
        """
        if source_qid not in self._graph:
            self._graph[source_qid] = set()
        
        self._graph[source_qid].add(target_qid)
        
        # Also ensure target node exists
        if target_qid not in self._graph:
            self._graph[target_qid] = set()
    
    def add_chunks_batch(self, chunks: List[Dict], tenant_id: str = "default") -> None:
        """
        Add multiple chunks to the graph.
        
        Args:
            chunks: List of chunk dictionaries with metadata
            tenant_id: Tenant context for data isolation
        """
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            
            # Build QID from metadata
            source = metadata.get("source", "")
            name = metadata.get("name", "")
            # Extract tenant from metadata if not provided
            chunk_tenant = metadata.get("tenant_id", tenant_id)
            
            if not source or not name:
                continue
            
            # CRITICAL: Use new format tenant::source::name
            qid = f"{chunk_tenant}::{source}::{name}"
            
            # Add node with all metadata
            self.add_node(qid, **metadata)
        
        logger.info(f"Graph updated: {len(self._graph)} nodes")
    
    def get_related(
        self,
        qid: str,
        depth: int = 2,
        max_results: int = 10
    ) -> List[str]:
        """
        Get related QIDs via BFS traversal.
        
        Args:
            qid: Starting qualified ID
            depth: Maximum BFS depth
            max_results: Maximum number of related QIDs to return
        
        Returns:
            List of related QIDs (excluding the starting QID)
        """
        if qid not in self._graph:
            logger.debug(f"QID not in graph: {qid}")
            return []
        
        # BFS traversal
        visited: Set[str] = {qid}
        queue = deque([(qid, 0)])  # (qid, current_depth)
        related = []
        
        while queue and len(related) < max_results:
            current_qid, current_depth = queue.popleft()
            
            # Stop if we've reached max depth
            if current_depth >= depth:
                continue
            
            # Get neighbors
            neighbors = self._graph.get(current_qid, set())
            
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    related.append(neighbor)
                    queue.append((neighbor, current_depth + 1))
                    
                    if len(related) >= max_results:
                        break
        
        logger.debug(f"Found {len(related)} related QIDs for {qid} (depth={depth})")
        return related[:max_results]
    
    def get_metadata(self, qid: str) -> Optional[Dict]:
        """Get metadata for a QID."""
        return self._metadata.get(qid)
    
    def size(self) -> int:
        """Get number of nodes in graph."""
        return len(self._graph)
    
    def to_dict(self) -> Dict:
        """
        Serialize graph to dictionary for caching.
        Format:
        {
            "nodes": [{"id": qid, **metadata}],
            "links": [{"source": s, "target": t, "relation": r}]
        }
        """
        nodes = []
        for qid, meta in self._metadata.items():
            nodes.append({"id": qid, **meta})
            
        links = []
        for source, targets in self._graph.items():
            for target in targets:
                # Relation usually implied by metadata, but we can default
                links.append({"source": source, "target": target, "relation": "related"})
                
        return {"nodes": nodes, "links": links}

    @classmethod
    def from_dict(cls, data: Dict) -> "CodeGraph":
        """Reconstruct graph from dictionary."""
        graph = cls()
        
        # Restore nodes
        for node in data.get("nodes", []):
            qid = node.pop("id")
            graph.add_node(qid, **node)
            
        # Restore explicit edges (if any additional not covered by metadata)
        for link in data.get("links", []):
            graph.add_edge(link["source"], link["target"], link.get("relation", "related"))
            
        return graph

    def resolve_cross_file_edges(self) -> int:
        """
        Rewire intra-file call edges that point to dangling (non-existent) nodes
        to the real cross-file definition.

        When add_node resolves a call target it always assumes the callee lives in
        the same source file: ``tenant::caller_file::callee_name``.  If the callee
        is actually imported from another file that QID has no metadata entry — it
        is "dangling".  This method detects those dangling targets and, when exactly
        one real node with the same entity name exists elsewhere, rewires all
        incoming edges to the real node.

        Resolution rules:
        - 0 real candidates  → leave as-is (entity not indexed; will silently miss at retrieval)
        - 1 real candidate   → rewire (unambiguous cross-file reference)
        - >1 real candidates → skip   (ambiguous name; safer to do nothing)

        Should be called once after all chunks have been loaded via
        ``add_chunks_batch`` and before the graph is serialised to Redis.

        Returns:
            Number of individual edges that were rewired.
        """
        real_qids: Set[str] = set(self._metadata.keys())

        dangling_qids: Set[str] = {
            qid for qid in self._graph if qid not in real_qids
        }

        if not dangling_qids:
            logger.debug("resolve_cross_file_edges: no dangling nodes found")
            return 0

        # entity_name → list of real QIDs that carry that name
        entity_to_real: Dict[str, List[str]] = defaultdict(list)
        for qid in real_qids:
            parts = qid.split("::")
            if len(parts) >= 3:
                entity_to_real[parts[-1]].append(qid)

        rewired = 0
        for dangling_qid in dangling_qids:
            parts = dangling_qid.split("::")
            if len(parts) < 3:
                continue

            entity_name = parts[-1]
            dangling_file = parts[1]

            # Candidates must be in a *different* file than the dangling QID
            candidates = [
                qid for qid in entity_to_real.get(entity_name, [])
                if qid.split("::")[1] != dangling_file
            ]

            if len(candidates) != 1:
                logger.debug(
                    f"[CROSS_FILE] '{dangling_qid}': {len(candidates)} candidate(s) — skipping"
                )
                continue

            real_qid = candidates[0]
            logger.info(f"[CROSS_FILE] Rewiring '{dangling_qid}' → '{real_qid}'")

            for source_qid in list(self._graph.keys()):
                if dangling_qid in self._graph[source_qid]:
                    self._graph[source_qid].discard(dangling_qid)
                    self._graph[source_qid].add(real_qid)
                    rewired += 1

            # Remove the now-orphaned dangling entry
            del self._graph[dangling_qid]

        logger.info(
            f"[CROSS_FILE] resolve_cross_file_edges: {rewired} edge(s) rewired "
            f"from {len(dangling_qids)} dangling node(s)"
        )
        return rewired

    def clear(self) -> None:
        """Clear the entire graph."""
        self._graph.clear()
        self._metadata.clear()
        logger.debug("Graph cleared")


def parse_qualified_id(qid: str) -> tuple[str, str, str]:
    """
    Parse a tenant-scoped qualified ID into tenant, file, and entity.
    
    Args:
        qid: Qualified ID (tenant::file::entity or file::entity)
    
    Returns:
        Tuple of (tenant_id, file_path, entity_name)
    
    Raises:
        ValueError: If QID format is invalid
    """
    if "::" not in qid:
        raise ValueError(f"Invalid QID format (missing ::): {qid}")
    
    if qid.count("::") < 2:
        # Legacy format: "file::entity" — treat as default tenant
        parts = qid.split("::", 1)
        return "default", parts[0], parts[1]
    
    # New format: "tenant::file::entity"
    tenant_part, rest = qid.split("::", 1)
    file_path, entity_name = rest.rsplit("::", 1)
    return tenant_part, file_path, entity_name


TENANT_SEPARATOR = "::"

def build_qualified_id(tenant_id: str, file_path: str, entity_name: str) -> str:
    """
    Build a tenant-scoped qualified ID from tenant, file, and entity.
    
    Args:
        tenant_id: Tenant context for data isolation
        file_path: Source file path
        entity_name: Entity name (function, class, etc.)
    
    Returns:
        Qualified ID (tenant::file::entity)
    """
    return f"{tenant_id}{TENANT_SEPARATOR}{file_path}::{entity_name}"
