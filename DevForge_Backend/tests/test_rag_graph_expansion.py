# tests/test_rag_graph_expansion.py
from src.storage.base_store import ChunkResult
from src.agents.rag.graph.code_graph import CodeGraph


# ---------------------------------------------------------------------------
# Issue #6 — Cross-file edge resolution
# ---------------------------------------------------------------------------

def _make_graph_ab():
    """
    Minimal two-file graph:
      file_a.ts::UserRepository  calls  CacheStore  (imported from file_b.ts)
      file_b.ts::CacheStore      (real definition)
    """
    graph = CodeGraph()
    tenant = "t1"
    graph.add_node(
        f"{tenant}::file_b.ts::CacheStore",
        calls=[], imports=[], source="file_b.ts", name="CacheStore", tenant_id=tenant,
    )
    graph.add_node(
        f"{tenant}::file_a.ts::UserRepository",
        calls=["CacheStore"], imports=[], source="file_a.ts", name="UserRepository", tenant_id=tenant,
    )
    return graph, tenant


def test_cross_file_resolution_rewires_single_match():
    """After resolution, BFS from UserRepository reaches file_b.ts::CacheStore."""
    graph, tenant = _make_graph_ab()

    # Before: dangling edge to wrong file
    related_before = graph.get_related(f"{tenant}::file_a.ts::UserRepository")
    assert f"{tenant}::file_a.ts::CacheStore" in related_before
    assert f"{tenant}::file_b.ts::CacheStore" not in related_before

    rewired = graph.resolve_cross_file_edges()
    assert rewired == 1

    # After: edge points to real definition in file_b.ts
    related_after = graph.get_related(f"{tenant}::file_a.ts::UserRepository")
    assert f"{tenant}::file_b.ts::CacheStore" in related_after
    assert f"{tenant}::file_a.ts::CacheStore" not in related_after


def test_cross_file_resolution_skips_ambiguous_name():
    """When the same entity name exists in two files, no rewiring occurs."""
    graph = CodeGraph()
    tenant = "t1"

    # Two files both define "Helper"
    graph.add_node(
        f"{tenant}::utils_a.ts::Helper",
        calls=[], imports=[], source="utils_a.ts", name="Helper", tenant_id=tenant,
    )
    graph.add_node(
        f"{tenant}::utils_b.ts::Helper",
        calls=[], imports=[], source="utils_b.ts", name="Helper", tenant_id=tenant,
    )
    # file_c.ts calls Helper — ambiguous which file it comes from
    graph.add_node(
        f"{tenant}::file_c.ts::Service",
        calls=["Helper"], imports=[], source="file_c.ts", name="Service", tenant_id=tenant,
    )

    rewired = graph.resolve_cross_file_edges()
    assert rewired == 0  # skipped, not guessed

    # Dangling edge still exists (not removed on ambiguity)
    related = graph.get_related(f"{tenant}::file_c.ts::Service")
    assert f"{tenant}::file_c.ts::Helper" in related


def test_cross_file_resolution_no_dangling_nodes():
    """Returns 0 when all edges point to real nodes (nothing to do)."""
    graph = CodeGraph()
    tenant = "t1"
    graph.add_node(
        f"{tenant}::auth.py::authenticate",
        calls=["validate_token"], imports=[], source="auth.py",
        name="authenticate", tenant_id=tenant,
    )
    graph.add_node(
        f"{tenant}::auth.py::validate_token",
        calls=[], imports=[], source="auth.py",
        name="validate_token", tenant_id=tenant,
    )
    # Both nodes are in the same file, no dangling edge — intra-file works already
    assert graph.resolve_cross_file_edges() == 0


def test_cross_file_resolution_idempotent():
    """Calling resolve twice produces the same result as calling once."""
    graph, tenant = _make_graph_ab()
    first = graph.resolve_cross_file_edges()
    second = graph.resolve_cross_file_edges()
    assert first == 1
    assert second == 0  # nothing left to rewire on the second call


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
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


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


# ---------------------------------------------------------------------------
# Graph endpoint schemas
# ---------------------------------------------------------------------------

def test_graph_node_schema():
    from src.api.schemas.rag import GraphNode
    node = GraphNode(id="t1::auth.py::Foo", name="Foo", chunk_type="class", source_file="auth.py")
    assert node.id == "t1::auth.py::Foo"
    assert node.language is None


def test_graph_related_response_schema():
    from src.api.schemas.rag import GraphRelatedResponse, GraphAnchor
    anchor = GraphAnchor(id="t1::auth.py::Foo", name="Foo", chunk_type="class", source_file="auth.py")
    resp = GraphRelatedResponse(entity="Foo", anchor=anchor, related=[], related_count=0)
    assert resp.ambiguous is False
    assert resp.all_anchors == []


# ---------------------------------------------------------------------------
# GET /api/v1/rag/graph endpoint tests
# ---------------------------------------------------------------------------

def test_get_code_graph_empty_graph():
    """Empty graph → HTTP 200 with node_count=0 and empty arrays."""
    from src.main import app

    mock_agent = MagicMock()
    mock_agent.init_graph = AsyncMock()
    mock_agent._code_graph = CodeGraph()  # empty — no nodes

    with patch("src.api.routers.rag.get_rag_agent", return_value=mock_agent), \
         patch("src.core.middleware.verify_jwt", return_value={"tenant_id": "t_test"}):
        client = TestClient(app)
        response = client.get(
            "/api/v1/rag/graph",
            headers={"Authorization": "Bearer test_token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["node_count"] == 0
    assert data["link_count"] == 0
    assert data["nodes"] == []
    assert data["links"] == []


def test_get_code_graph_strips_full_path():
    """source_file in response must be the filename only, never the full server path."""
    from src.main import app

    graph = CodeGraph()
    graph.add_node(
        "t1::/app/data/uploads/users/t1/default/abc_cache.ts::CacheStore",
        calls=[], imports=[],
        source="/app/data/uploads/users/t1/default/abc_cache.ts",
        name="CacheStore",
        chunk_type="class",
        language="typescript",
        tenant_id="t1",
    )

    mock_agent = MagicMock()
    mock_agent.init_graph = AsyncMock()
    mock_agent._code_graph = graph

    with patch("src.api.routers.rag.get_rag_agent", return_value=mock_agent), \
         patch("src.core.middleware.verify_jwt", return_value={"tenant_id": "t1"}):
        client = TestClient(app)
        response = client.get(
            "/api/v1/rag/graph",
            headers={"Authorization": "Bearer test_token"},
        )

    assert response.status_code == 200
    nodes = response.json()["nodes"]
    assert len(nodes) == 1
    assert nodes[0]["source_file"] == "abc_cache.ts"
    assert "/app/" not in nodes[0]["source_file"]


# ---------------------------------------------------------------------------
# GET /api/v1/rag/graph/related endpoint tests
# ---------------------------------------------------------------------------

def _make_two_file_graph() -> CodeGraph:
    """
    Two-file graph:
      file_a.ts::UserRepository  calls  CacheStore (imported from file_b.ts)
      file_b.ts::CacheStore      (real definition)
    After resolve_cross_file_edges() the edge points to file_b.ts::CacheStore.
    """
    graph = CodeGraph()
    tenant = "t1"
    graph.add_node(
        f"{tenant}::file_b.ts::CacheStore",
        calls=[], imports=[], source="file_b.ts",
        name="CacheStore", chunk_type="class", language="typescript", tenant_id=tenant,
    )
    graph.add_node(
        f"{tenant}::file_a.ts::UserRepository",
        calls=["CacheStore"], imports=[], source="file_a.ts",
        name="UserRepository", chunk_type="class", language="typescript", tenant_id=tenant,
    )
    graph.resolve_cross_file_edges()
    return graph


def test_get_graph_related_by_name():
    """Plain entity name resolves to the correct anchor and returns related nodes."""
    from src.main import app

    mock_agent = MagicMock()
    mock_agent.init_graph = AsyncMock()
    mock_agent._code_graph = _make_two_file_graph()

    with patch("src.api.routers.rag.get_rag_agent", return_value=mock_agent), \
         patch("src.core.middleware.verify_jwt", return_value={"tenant_id": "t1"}):
        client = TestClient(app)
        response = client.get(
            "/api/v1/rag/graph/related?entity=UserRepository",
            headers={"Authorization": "Bearer test_token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["entity"] == "UserRepository"
    assert data["anchor"] is not None
    assert data["anchor"]["name"] == "UserRepository"
    assert data["related_count"] >= 1
    related_names = [r["name"] for r in data["related"]]
    assert "CacheStore" in related_names
    assert data["ambiguous"] is False


def test_get_graph_related_by_full_qid():
    """Full QID in entity param resolves directly without name scan."""
    from src.main import app

    mock_agent = MagicMock()
    mock_agent.init_graph = AsyncMock()
    mock_agent._code_graph = _make_two_file_graph()

    with patch("src.api.routers.rag.get_rag_agent", return_value=mock_agent), \
         patch("src.core.middleware.verify_jwt", return_value={"tenant_id": "t1"}):
        client = TestClient(app)
        response = client.get(
            "/api/v1/rag/graph/related?entity=t1::file_a.ts::UserRepository",
            headers={"Authorization": "Bearer test_token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["anchor"]["id"] == "t1::file_a.ts::UserRepository"
    assert data["ambiguous"] is False


def test_get_graph_related_entity_not_found():
    """Unknown entity → HTTP 200 with anchor=null and empty related list."""
    from src.main import app

    mock_agent = MagicMock()
    mock_agent.init_graph = AsyncMock()
    mock_agent._code_graph = _make_two_file_graph()

    with patch("src.api.routers.rag.get_rag_agent", return_value=mock_agent), \
         patch("src.core.middleware.verify_jwt", return_value={"tenant_id": "t1"}):
        client = TestClient(app)
        response = client.get(
            "/api/v1/rag/graph/related?entity=NonExistentClass",
            headers={"Authorization": "Bearer test_token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["anchor"] is None
    assert data["related"] == []
    assert data["related_count"] == 0


def test_get_graph_related_ambiguous():
    """Two files defining the same entity name → ambiguous=True, all_anchors populated."""
    from src.main import app

    graph = CodeGraph()
    tenant = "t1"
    graph.add_node(
        f"{tenant}::a.ts::Helper",
        calls=[], imports=[], source="a.ts",
        name="Helper", chunk_type="class", language="typescript", tenant_id=tenant,
    )
    graph.add_node(
        f"{tenant}::b.ts::Helper",
        calls=[], imports=[], source="b.ts",
        name="Helper", chunk_type="class", language="typescript", tenant_id=tenant,
    )

    mock_agent = MagicMock()
    mock_agent.init_graph = AsyncMock()
    mock_agent._code_graph = graph

    with patch("src.api.routers.rag.get_rag_agent", return_value=mock_agent), \
         patch("src.core.middleware.verify_jwt", return_value={"tenant_id": "t1"}):
        client = TestClient(app)
        response = client.get(
            "/api/v1/rag/graph/related?entity=Helper",
            headers={"Authorization": "Bearer test_token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["ambiguous"] is True
    assert data["anchor"] is not None          # first match used
    assert len(data["all_anchors"]) == 2


def test_get_graph_related_depth_cap():
    """depth param outside 1–3 → HTTP 422 validation error."""
    from src.main import app

    mock_agent = MagicMock()
    mock_agent.init_graph = AsyncMock()
    mock_agent._code_graph = CodeGraph()

    with patch("src.api.routers.rag.get_rag_agent", return_value=mock_agent), \
         patch("src.core.middleware.verify_jwt", return_value={"tenant_id": "t1"}):
        client = TestClient(app)
        response = client.get(
            "/api/v1/rag/graph/related?entity=Foo&depth=5",
            headers={"Authorization": "Bearer test_token"},
        )

    assert response.status_code == 422


def test_get_graph_related_with_snippets():
    """include_snippets=true attaches 200-char snippet; failure for one entity doesn't abort."""
    from src.main import app

    mock_agent = MagicMock()
    mock_agent.init_graph = AsyncMock()
    mock_agent._code_graph = _make_two_file_graph()

    fake_chunk = MagicMock()
    fake_chunk.content = "x" * 300  # longer than 200 — handler must truncate
    mock_agent.vector_store = MagicMock()
    mock_agent.vector_store.get_chunk_by_qualified_id = AsyncMock(return_value=fake_chunk)

    with patch("src.api.routers.rag.get_rag_agent", return_value=mock_agent), \
         patch("src.core.middleware.verify_jwt", return_value={"tenant_id": "t1"}):
        client = TestClient(app)
        response = client.get(
            "/api/v1/rag/graph/related?entity=UserRepository&include_snippets=true",
            headers={"Authorization": "Bearer test_token"},
        )

    assert response.status_code == 200
    data = response.json()
    for entity in data["related"]:
        if entity["snippet"] is not None:
            assert len(entity["snippet"]) <= 200
