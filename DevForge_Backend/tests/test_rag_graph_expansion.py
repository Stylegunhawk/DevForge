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


import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_expand_with_graph_context_sets_expanded_from():
    """Verifies that graph-expanded chunks carry the anchor QID in expanded_from."""
    from src.agents.rag.agent import RAGAgent
    from src.agents.rag.graph.code_graph import CodeGraph

    # Build a minimal graph: authenticate calls validate_token
    graph = CodeGraph()
    tenant_id = "test_tenant"
    graph.add_node(
        f"{tenant_id}::auth.py::authenticate",
        calls=["validate_token"],
        source="auth.py",
        name="authenticate",
        tenant_id=tenant_id,
    )
    graph.add_node(
        f"{tenant_id}::auth.py::validate_token",
        calls=[],
        source="auth.py",
        name="validate_token",
        tenant_id=tenant_id,
    )

    related_chunk = MagicMock()
    related_chunk.id = "chunk-validate-token"
    related_chunk.content = "def validate_token(): pass"
    related_chunk.metadata = {
        "source": "auth.py",
        "name": "validate_token",
        "tenant_id": tenant_id,
    }

    mock_vector_store = AsyncMock()
    mock_vector_store.get_chunk_by_qualified_id = AsyncMock(return_value=related_chunk)

    agent = RAGAgent.__new__(RAGAgent)
    agent._code_graph = graph
    agent.vector_store = mock_vector_store
    agent.collection_name = f"user_{tenant_id}"
    agent.tenant_id = tenant_id

    anchors = [
        {"metadata": {"source": "auth.py", "name": "authenticate", "tenant_id": tenant_id}}
    ]

    results = await agent._expand_with_graph_context(anchors)

    assert len(results) == 1
    assert results[0]["expanded_from"] == f"{tenant_id}::auth.py::authenticate"
    assert results[0]["is_graph_expansion"] is True
    assert results[0]["id"] == "chunk-validate-token"
