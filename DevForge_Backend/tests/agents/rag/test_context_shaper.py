
import pytest
from src.agents.rag.context_shaper import ContextShaper

class MockChunk:
    def __init__(self, id, score, rerank_score=None, metadata=None):
        self.id = id
        self.score = score
        self.rerank_score = rerank_score
        self.metadata = metadata or {}

    def __repr__(self):
        return f"MockChunk(id={self.id}, score={self.score})"

def test_assign_roles_returns_sorted_list():
    """Regression test: _assign_roles must return the list sorted by score (descending)."""
    shaper = ContextShaper()
    
    # Create chunks with mixed scores
    chunk_low = MockChunk(id="low", score=0.1, rerank_score=0.1, metadata={"name": "low"})
    chunk_high = MockChunk(id="high", score=0.9, rerank_score=0.9, metadata={"name": "high"})
    chunk_mid = MockChunk(id="mid", score=0.5, rerank_score=0.5, metadata={"name": "mid"})
    
    chunks = [chunk_low, chunk_high, chunk_mid]
    
    # Call internal method (as verified in the user fix)
    assigned = shaper._assign_roles(chunks)
    
    # Verify order: High -> Mid -> Low
    assert assigned[0].id == "high"
    assert assigned[1].id == "mid"
    assert assigned[2].id == "low"
    
    # Verify Roles
    assert assigned[0].metadata["role"] == "entry"
    assert assigned[1].metadata["role"] == "supporting"
    assert assigned[2].metadata["role"] == "supporting"

def test_assign_roles_preserves_dependency():
    """Verify graph-expanded chunks become dependencies."""
    shaper = ContextShaper()
    
    chunk_entry = MockChunk(id="entry", score=0.9, rerank_score=0.9, metadata={"name": "main"})
    chunk_dep = MockChunk(id="dep", score=0.5, rerank_score=0.5, 
                         metadata={"name": "helper", "is_graph_expansion": True})
    chunk_supp = MockChunk(id="supp", score=0.4, rerank_score=0.4, metadata={"name": "other"})
    
    chunks = [chunk_supp, chunk_entry, chunk_dep]
    
    assigned = shaper._assign_roles(chunks)
    
    # Entry
    assert assigned[0].id == "entry"
    assert assigned[0].metadata["role"] == "entry"
    
    # Dependency
    assert assigned[1].id == "dep"
    assert assigned[1].metadata["role"] == "dependency"
    
    # Supporting
    assert assigned[2].id == "supp"
    assert assigned[2].metadata["role"] == "supporting"

def test_deduplicate_preserves_provenance():
    """Verify is_graph_expansion is preserved when merging duplicates."""
    shaper = ContextShaper()
    
    # Two chunks, same qualified ID
    # Chunk A: High score, regular vector match
    chunk_a = MockChunk(id="a", score=0.9, rerank_score=0.9, 
                       metadata={"qualified_id": "file::method", "is_graph_expansion": False})
    
    # Chunk B: Low score, but IS graph expansion
    chunk_b = MockChunk(id="b", score=0.5, rerank_score=0.5, 
                       metadata={"qualified_id": "file::method", "is_graph_expansion": True})
    
    chunks = [chunk_a, chunk_b]
    
    deduped = shaper._deduplicate(chunks)
    
    assert len(deduped) == 1
    survivor = deduped[0]
    
    # Should keep score from A
    assert survivor.score == 0.9 or survivor.rerank_score == 0.9
    
    # But inherit is_graph_expansion from B
    assert survivor.metadata["is_graph_expansion"] is True
