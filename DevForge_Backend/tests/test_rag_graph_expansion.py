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


def test_chat_file_chunk_has_graph_fields():
    from src.api.schemas.rag import ChatFileChunk
    chunk = ChatFileChunk(
        id="c1",
        fileId="f1",
        filename="auth.py",
        fileType="text/plain",
        fileUrl="http://example.com/auth.py",
        text="def authenticate(): pass",
        similarity=0.65,
    )
    assert hasattr(chunk, "is_graph_expansion")
    assert hasattr(chunk, "expanded_from")
    assert chunk.is_graph_expansion is False
    assert chunk.expanded_from is None


def test_chat_file_chunk_graph_fields_set():
    from src.api.schemas.rag import ChatFileChunk
    chunk = ChatFileChunk(
        id="c1",
        fileId="f1",
        filename="auth.py",
        fileType="text/plain",
        fileUrl="http://example.com/auth.py",
        text="def validate_token(): pass",
        similarity=0.0,
        is_graph_expansion=True,
        expanded_from="tenant1::auth.py::authenticate"
    )
    assert chunk.is_graph_expansion is True
    assert chunk.expanded_from == "tenant1::auth.py::authenticate"


def test_semantic_search_response_has_expansion_count():
    from src.api.schemas.rag import SemanticSearchResponse
    resp = SemanticSearchResponse(chunks=[], queryId="q1")
    assert hasattr(resp, "expansion_count")
    assert resp.expansion_count == 0


def test_chat_file_chunk_serialization_includes_graph_fields():
    """Verify ChatFileChunk JSON output includes the graph fields."""
    from src.api.schemas.rag import ChatFileChunk
    chunk = ChatFileChunk(
        id="c1",
        fileId="f1",
        filename="auth.py",
        fileType="text/plain",
        fileUrl="http://example.com/auth.py",
        text="def validate_token(): pass",
        similarity=0.0,
        is_graph_expansion=True,
        expanded_from="tenant1::auth.py::authenticate"
    )
    data = chunk.model_dump()
    assert data["is_graph_expansion"] is True
    assert data["expanded_from"] == "tenant1::auth.py::authenticate"


def test_semantic_search_response_expansion_count_counts_expanded():
    """Verify the expansion_count computation matches is_graph_expansion flags."""
    from src.api.schemas.rag import ChatFileChunk, SemanticSearchResponse

    def make_chunk(is_graph: bool) -> ChatFileChunk:
        return ChatFileChunk(
            id="c1", fileId="f1", filename="f.py", fileType="text/plain",
            fileUrl="http://x.com/f.py", text="x", similarity=0.5,
            is_graph_expansion=is_graph
        )

    chunks = [make_chunk(False), make_chunk(True), make_chunk(True)]
    # Simulate the router's computation
    computed_count = sum(1 for c in chunks if c.is_graph_expansion)

    resp = SemanticSearchResponse(
        chunks=chunks,
        queryId="q1",
        expansion_count=computed_count,
    )
    assert resp.expansion_count == 2
    assert computed_count == 2
