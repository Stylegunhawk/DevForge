# tests/test_rag_graph_expansion.py
from src.storage.base_store import ChunkResult


def test_chunk_result_has_expanded_from():
    chunk = ChunkResult(id="abc", content="def foo(): pass", metadata={})
    assert hasattr(chunk, "expanded_from")
    assert chunk.expanded_from is None


def test_chunk_result_expanded_from_set():
    chunk = ChunkResult(
        id="abc",
        content="def foo(): pass",
        metadata={},
        expanded_from="tenant1::auth.py::validate_token"
    )
    assert chunk.expanded_from == "tenant1::auth.py::validate_token"
