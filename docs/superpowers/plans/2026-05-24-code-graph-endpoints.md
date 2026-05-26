# Code Graph Endpoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the in-memory `CodeGraph` via two GET endpoints — a full node+link dump for visualization (`GET /api/v1/rag/graph`) and a BFS entity query for the LLM agent tool (`GET /api/v1/rag/graph/related`).

**Architecture:** Both handlers call the existing `get_rag_agent(tenant_id, collection_name)` factory (TTL-cached per tenant, 1hr), call `init_graph()` lazily on first request, then query the in-memory `CodeGraph`. No new backend files — all Python changes go in the existing `schemas/rag.py` and `routers/rag.py`. The chat-UI (separate SvelteKit repo) gains two proxy routes and one new LLM tool definition.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest + unittest.mock; SvelteKit (+server.ts), TypeScript

---

## File Map

| File | Action | What changes |
|---|---|---|
| `DevForge_Backend/src/api/schemas/rag.py` | Modify | Add 6 new Pydantic models |
| `DevForge_Backend/src/api/routers/rag.py` | Modify | Add 2 GET handlers (section 6) |
| `DevForge_Backend/tests/test_rag_graph_expansion.py` | Modify | Add 8 endpoint tests |
| `chat-ui/src/routes/api/v1/rag/graph/+server.ts` | Create | Proxy GET → backend `/graph` |
| `chat-ui/src/routes/api/v1/rag/graph/related/+server.ts` | Create | Proxy GET → backend `/graph/related` |
| `chat-ui/src/lib/server/rag/ragTools.ts` | Modify | Add `get_code_graph_related` tool |
| `chat-ui/src/lib/server/textGeneration/mcp/runRagFlow.ts` | Modify | Advertise new tool |

> **Note:** Tasks 1–3 are in `DevForge_Backend/`. Tasks 4–7 are in the chat-UI SvelteKit repo (separate codebase — adjust paths to match your actual directory).

---

## Task 1: Pydantic Schemas

**Files:**
- Modify: `DevForge_Backend/src/api/schemas/rag.py`

The router does `from src.api.schemas.rag import *`, so all models added here are immediately available in the router.

- [ ] **Step 1: Write two failing schema tests**

Append to `DevForge_Backend/tests/test_rag_graph_expansion.py`:

```python
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
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd DevForge_Backend && source venv/bin/activate
pytest tests/test_rag_graph_expansion.py::test_graph_node_schema tests/test_rag_graph_expansion.py::test_graph_related_response_schema -v
```

Expected: `ImportError: cannot import name 'GraphNode'`

- [ ] **Step 3: Add 6 models to `src/api/schemas/rag.py`**

Append after the `FileUploadResponse` class (at the end of the file):

```python
# ============================================================================
# 7. CODE GRAPH RESPONSES
# ============================================================================

class GraphNode(BaseModel):
    id: str
    name: str
    chunk_type: str
    source_file: str
    language: Optional[str] = None


class GraphLink(BaseModel):
    source: str
    target: str
    relation: str


class CodeGraphResponse(BaseModel):
    node_count: int
    link_count: int
    nodes: List[GraphNode]
    links: List[GraphLink]


class GraphAnchor(BaseModel):
    id: str
    name: str
    chunk_type: str
    source_file: str


class RelatedEntity(BaseModel):
    id: str
    name: str
    chunk_type: str
    source_file: str
    snippet: Optional[str] = None


class GraphRelatedResponse(BaseModel):
    entity: str
    anchor: Optional[GraphAnchor] = None
    related: List[RelatedEntity] = []
    related_count: int
    ambiguous: bool = False
    all_anchors: List[GraphAnchor] = []
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_rag_graph_expansion.py::test_graph_node_schema tests/test_rag_graph_expansion.py::test_graph_related_response_schema -v
```

Expected: `2 passed`

- [ ] **Step 5: Stage the changes**

```bash
git add src/api/schemas/rag.py tests/test_rag_graph_expansion.py
```

---

## Task 2: `GET /api/v1/rag/graph` Endpoint

**Files:**
- Modify: `DevForge_Backend/src/api/routers/rag.py`
- Modify: `DevForge_Backend/tests/test_rag_graph_expansion.py`

- [ ] **Step 1: Write two failing endpoint tests**

Append to `DevForge_Backend/tests/test_rag_graph_expansion.py`:

```python
# ---------------------------------------------------------------------------
# GET /api/v1/rag/graph endpoint tests
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


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
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd DevForge_Backend && source venv/bin/activate
pytest tests/test_rag_graph_expansion.py::test_get_code_graph_empty_graph tests/test_rag_graph_expansion.py::test_get_code_graph_strips_full_path -v
```

Expected: `404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Add the handler to `src/api/routers/rag.py`**

Add a new section before the `# 5. QUERY DELETION` comment block (after the delete file handler, around line 426):

```python
# ============================================================================
# 6. CODE GRAPH ENDPOINTS
# ============================================================================

@router.get(
    "/graph",
    response_model=CodeGraphResponse,
    summary="Get full code dependency graph",
    description=(
        "Returns all nodes and edges in the tenant's code dependency graph. "
        "Returns node_count=0 and empty arrays when no files have been ingested (never 404). "
        "Requires JWT authentication."
    ),
    dependencies=[Depends(security_scheme)],
)
async def get_code_graph(request: Request) -> CodeGraphResponse:
    tenant_id = get_current_tenant_id(request)
    collection_name = f"user_{tenant_id}"

    agent = get_rag_agent(tenant_id=tenant_id, collection_name=collection_name)
    if agent._code_graph is None:
        await agent.init_graph()

    graph = agent._code_graph
    graph_dict = graph.to_dict()

    nodes = []
    for node in graph_dict["nodes"]:
        raw_source = node.get("source", "")
        nodes.append(GraphNode(
            id=node["id"],
            name=node.get("name", ""),
            chunk_type=node.get("chunk_type", "unknown"),
            source_file=Path(raw_source).name if raw_source else "",
            language=node.get("language"),
        ))

    links = []
    for link in graph_dict["links"]:
        links.append(GraphLink(
            source=link["source"],
            target=link["target"],
            relation=link.get("relation", "related"),
        ))

    return CodeGraphResponse(
        node_count=len(nodes),
        link_count=len(links),
        nodes=nodes,
        links=links,
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_rag_graph_expansion.py::test_get_code_graph_empty_graph tests/test_rag_graph_expansion.py::test_get_code_graph_strips_full_path -v
```

Expected: `2 passed`

- [ ] **Step 5: Stage the changes**

```bash
git add src/api/routers/rag.py tests/test_rag_graph_expansion.py
```

---

## Task 3: `GET /api/v1/rag/graph/related` Endpoint

**Files:**
- Modify: `DevForge_Backend/src/api/routers/rag.py`
- Modify: `DevForge_Backend/tests/test_rag_graph_expansion.py`

- [ ] **Step 1: Write six failing endpoint tests**

Append to `DevForge_Backend/tests/test_rag_graph_expansion.py`:

```python
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
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd DevForge_Backend && source venv/bin/activate
pytest tests/test_rag_graph_expansion.py::test_get_graph_related_by_name \
       tests/test_rag_graph_expansion.py::test_get_graph_related_by_full_qid \
       tests/test_rag_graph_expansion.py::test_get_graph_related_entity_not_found \
       tests/test_rag_graph_expansion.py::test_get_graph_related_ambiguous \
       tests/test_rag_graph_expansion.py::test_get_graph_related_depth_cap \
       tests/test_rag_graph_expansion.py::test_get_graph_related_with_snippets -v
```

Expected: `404 Not Found` (route doesn't exist yet); depth_cap test gets 404 not 422.

- [ ] **Step 3: Add the handler to `src/api/routers/rag.py`**

Add the `Query` import to the existing `fastapi` import line at the top of `src/api/routers/rag.py`:

```python
from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException, Request, Depends, security, Query
```

Then add the following handler inside the `# 6. CODE GRAPH ENDPOINTS` section, immediately after the `get_code_graph` handler:

```python
@router.get(
    "/graph/related",
    response_model=GraphRelatedResponse,
    summary="Get entities related to a code entity via BFS",
    description=(
        "BFS query on the code dependency graph. Accepts a plain entity name "
        "(e.g. 'CacheStore') or a full qualified ID (tenant::file::entity). "
        "Returns HTTP 200 with anchor=null when the entity is not found. "
        "Requires JWT authentication."
    ),
    dependencies=[Depends(security_scheme)],
)
async def get_graph_related(
    request: Request,
    entity: str = Query(..., description="Entity name or full QID"),
    depth: int = Query(2, ge=1, le=3, description="BFS depth (1–3)"),
    max: int = Query(10, ge=1, le=20, description="Max results (1–20)"),
    include_snippets: bool = Query(False, description="Attach 200-char code snippet to each result"),
) -> GraphRelatedResponse:
    tenant_id = get_current_tenant_id(request)
    collection_name = f"user_{tenant_id}"

    agent = get_rag_agent(tenant_id=tenant_id, collection_name=collection_name)
    if agent._code_graph is None:
        await agent.init_graph()

    graph = agent._code_graph

    # --- Entity resolution ---
    if "::" in entity:
        # Full QID: direct adjacency-list lookup
        anchor_qid: Optional[str] = entity if entity in graph._graph else None
        all_anchor_qids: list = [anchor_qid] if anchor_qid else []
        ambiguous = False
    else:
        # Plain name: scan metadata for matching last segment
        matching_qids = [
            qid for qid in graph._metadata
            if qid.split("::")[-1] == entity
        ]
        if not matching_qids:
            anchor_qid = None
            all_anchor_qids = []
            ambiguous = False
        elif len(matching_qids) == 1:
            anchor_qid = matching_qids[0]
            all_anchor_qids = [anchor_qid]
            ambiguous = False
        else:
            anchor_qid = matching_qids[0]
            all_anchor_qids = matching_qids
            ambiguous = True

    if anchor_qid is None:
        return GraphRelatedResponse(
            entity=entity,
            anchor=None,
            related=[],
            related_count=0,
            ambiguous=False,
            all_anchors=[],
        )

    def _to_anchor(qid: str) -> GraphAnchor:
        meta = graph._metadata.get(qid, {})
        return GraphAnchor(
            id=qid,
            name=meta.get("name", qid.split("::")[-1]),
            chunk_type=meta.get("chunk_type", "unknown"),
            source_file=Path(meta.get("source", "")).name,
        )

    anchor = _to_anchor(anchor_qid)
    all_anchors = [_to_anchor(q) for q in all_anchor_qids] if ambiguous else []

    # --- BFS ---
    related_qids = graph.get_related(anchor_qid, depth=depth, max_results=max)

    # --- Build related entities, optionally fetch snippets ---
    related: list = []
    for qid in related_qids:
        meta = graph._metadata.get(qid)
        if meta is None:
            continue  # skip dangling nodes that slipped through
        snippet: Optional[str] = None
        if include_snippets:
            try:
                chunk = await agent.vector_store.get_chunk_by_qualified_id(
                    qid, tenant_id=tenant_id, collection_name=collection_name
                )
                if chunk:
                    snippet = chunk.content[:200]
            except Exception:
                pass  # snippet remains None; rest of response is unaffected
        related.append(RelatedEntity(
            id=qid,
            name=meta.get("name", qid.split("::")[-1]),
            chunk_type=meta.get("chunk_type", "unknown"),
            source_file=Path(meta.get("source", "")).name,
            snippet=snippet,
        ))

    return GraphRelatedResponse(
        entity=entity,
        anchor=anchor,
        related=related,
        related_count=len(related),
        ambiguous=ambiguous,
        all_anchors=all_anchors,
    )
```

- [ ] **Step 4: Run all 8 new endpoint tests**

```bash
pytest tests/test_rag_graph_expansion.py::test_get_code_graph_empty_graph \
       tests/test_rag_graph_expansion.py::test_get_code_graph_strips_full_path \
       tests/test_rag_graph_expansion.py::test_get_graph_related_by_name \
       tests/test_rag_graph_expansion.py::test_get_graph_related_by_full_qid \
       tests/test_rag_graph_expansion.py::test_get_graph_related_entity_not_found \
       tests/test_rag_graph_expansion.py::test_get_graph_related_ambiguous \
       tests/test_rag_graph_expansion.py::test_get_graph_related_depth_cap \
       tests/test_rag_graph_expansion.py::test_get_graph_related_with_snippets -v
```

Expected: `8 passed`

- [ ] **Step 5: Run the full graph expansion test suite to confirm no regressions**

```bash
pytest tests/test_rag_graph_expansion.py -v
```

Expected: all tests pass (12 pre-existing + 8 new + 2 schema = 22 total)

- [ ] **Step 6: Stage the changes**

```bash
git add src/api/routers/rag.py tests/test_rag_graph_expansion.py
```

---

## Task 4: SvelteKit Proxy — `GET /api/v1/rag/graph`

> **Context:** This task is in the chat-UI SvelteKit repo, not `DevForge_Backend/`. Adjust the base path to match your actual project layout. The existing proxy routes under `src/routes/api/v1/rag/` follow this same pattern.

**Files:**
- Create: `src/routes/api/v1/rag/graph/+server.ts`

- [ ] **Step 1: Create the proxy file**

```typescript
// src/routes/api/v1/rag/graph/+server.ts
import type { RequestHandler } from "@sveltejs/kit";
import { BACKEND_URL } from "$env/static/private";

export const GET: RequestHandler = async ({ request, locals }) => {
  const token = locals.ragToken; // injected by hooks.server.ts from the user session

  const backendRes = await fetch(`${BACKEND_URL}/api/v1/rag/graph`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const body = await backendRes.text();
  return new Response(body, {
    status: backendRes.status,
    headers: { "Content-Type": "application/json" },
  });
};
```

> **Note:** Replace `locals.ragToken` with the actual field name your `hooks.server.ts` uses to expose the tenant JWT. Replace `BACKEND_URL` with the correct env var if your project uses a different name.

- [ ] **Step 2: Verify the route is reachable (manual curl through the SvelteKit dev server)**

```bash
# Start the dev server if not already running
npm run dev

# Test the proxy (replace SESSION_TOKEN with a valid session cookie value)
curl -s "http://localhost:5173/api/v1/rag/graph" \
  -H "Cookie: session=SESSION_TOKEN" | python3 -m json.tool
```

Expected: JSON with `node_count`, `nodes`, `links` fields.

- [ ] **Step 3: Stage the new file**

```bash
git add src/routes/api/v1/rag/graph/+server.ts
```

---

## Task 5: SvelteKit Proxy — `GET /api/v1/rag/graph/related`

**Files:**
- Create: `src/routes/api/v1/rag/graph/related/+server.ts`

- [ ] **Step 1: Create the proxy file**

```typescript
// src/routes/api/v1/rag/graph/related/+server.ts
import type { RequestHandler } from "@sveltejs/kit";
import { BACKEND_URL } from "$env/static/private";

export const GET: RequestHandler = async ({ request, locals, url }) => {
  const token = locals.ragToken;

  // Forward all query params: entity, depth, max, include_snippets
  const backendUrl = new URL(`${BACKEND_URL}/api/v1/rag/graph/related`);
  url.searchParams.forEach((value, key) => {
    backendUrl.searchParams.set(key, value);
  });

  const backendRes = await fetch(backendUrl.toString(), {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const body = await backendRes.text();
  return new Response(body, {
    status: backendRes.status,
    headers: { "Content-Type": "application/json" },
  });
};
```

- [ ] **Step 2: Verify the route is reachable**

```bash
curl -s "http://localhost:5173/api/v1/rag/graph/related?entity=CacheStore&depth=2&max=10" \
  -H "Cookie: session=SESSION_TOKEN" | python3 -m json.tool
```

Expected: JSON with `entity`, `anchor`, `related`, `related_count` fields.

- [ ] **Step 3: Stage the new file**

```bash
git add src/routes/api/v1/rag/graph/related/+server.ts
```

---

## Task 6: LLM Tool Definition — `ragTools.ts`

**Files:**
- Modify: `src/lib/server/rag/ragTools.ts`

- [ ] **Step 1: Add the `get_code_graph_related` tool definition**

In `ragTools.ts`, find where the existing tool definitions (e.g. `list_files`, `retrieve_docs`) are exported and add:

```typescript
export const getCodeGraphRelatedTool = {
  name: "get_code_graph_related",
  description:
    "Find code entities related to a given class or function via the dependency graph. " +
    "Use when you need to understand what a class depends on, what calls it, or what it imports. " +
    "Returns names and files of related entities. " +
    "Use include_snippets=true only when you need the actual code content of related entities.",
  parameters: {
    type: "object" as const,
    properties: {
      entity: {
        type: "string",
        description:
          "Entity name (e.g. 'CacheStore') or full qualified ID (tenant::file::name)",
      },
      depth: {
        type: "integer",
        default: 2,
        description: "BFS depth 1–3",
      },
      max: {
        type: "integer",
        default: 10,
        description: "Max results 1–20",
      },
      include_snippets: {
        type: "boolean",
        default: false,
        description: "Attach 200-char code snippet to each related entity",
      },
    },
    required: ["entity"],
  },
};

export async function runGetCodeGraphRelated(
  params: { entity: string; depth?: number; max?: number; include_snippets?: boolean },
  fetch: typeof globalThis.fetch,
  ragToken: string
): Promise<string> {
  const url = new URL("/api/v1/rag/graph/related", "http://localhost"); // base replaced by fetch
  url.searchParams.set("entity", params.entity);
  if (params.depth !== undefined) url.searchParams.set("depth", String(params.depth));
  if (params.max !== undefined) url.searchParams.set("max", String(params.max));
  if (params.include_snippets) url.searchParams.set("include_snippets", "true");

  const res = await fetch(`/api/v1/rag/graph/related?${url.searchParams.toString()}`, {
    headers: { Authorization: `Bearer ${ragToken}` },
  });

  if (!res.ok) return JSON.stringify({ error: `HTTP ${res.status}` });
  return res.text();
}
```

> **Note:** The exact export style (named exports vs default object, handler function vs inline) should match what the other tools in `ragTools.ts` use. Adapt accordingly.

- [ ] **Step 2: Stage the change**

```bash
git add src/lib/server/rag/ragTools.ts
```

---

## Task 7: Advertise the Tool in `runRagFlow.ts`

**Files:**
- Modify: `src/lib/server/textGeneration/mcp/runRagFlow.ts`

- [ ] **Step 1: Import and register the new tool**

In `runRagFlow.ts`, find where the existing tools are imported and the tools array is built. Add:

```typescript
import { getCodeGraphRelatedTool, runGetCodeGraphRelated } from "$lib/server/rag/ragTools";
```

In the tools array passed to the LLM (alongside `list_files`, `retrieve_docs`, etc.):

```typescript
getCodeGraphRelatedTool,
```

In the tool-call dispatch block (the `switch` or `if` chain that handles each tool name):

```typescript
case "get_code_graph_related": {
  const result = await runGetCodeGraphRelated(
    toolCall.input as { entity: string; depth?: number; max?: number; include_snippets?: boolean },
    fetch,
    ragToken
  );
  toolResults.push({ tool_use_id: toolCall.id, content: result });
  break;
}
```

> **Note:** The exact dispatch pattern depends on how `runRagFlow.ts` currently handles tool results. Match the structure of adjacent tool cases exactly.

- [ ] **Step 2: Stage the change**

```bash
git add src/lib/server/textGeneration/mcp/runRagFlow.ts
```

---

## Final Verification

- [ ] **Run the full backend test suite to confirm no regressions**

```bash
cd DevForge_Backend && source venv/bin/activate
pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all pre-existing tests continue to pass; new tests pass.

- [ ] **Live smoke test against the running Docker stack**

```bash
# Set JWT (from RAG_DEBUGGING.md)
JWT="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI2OTg5ZDA1ZDZhZWYxNzU5NjhjM2NhZTUiLCJleHAiOjE3ODIxNDk5NTUsImlhdCI6MTc3OTU1Nzk1NSwib3JpZ2luYWxfaXNzdWVkX2F0IjoxNzc5NTU3OTU1LjM0OTM5NX0.0DQgT5yYy7glpfvk1PtG2qkOwuESdiM_9bTEua9x7sY"

# Full graph dump
curl -s http://localhost:8001/api/v1/rag/graph \
  -H "Authorization: Bearer $JWT" | python3 -m json.tool

# Related query (plain name)
curl -s "http://localhost:8001/api/v1/rag/graph/related?entity=CacheStore&depth=2&max=10" \
  -H "Authorization: Bearer $JWT" | python3 -m json.tool

# Related query (entity not found — should return 200 with anchor=null)
curl -s "http://localhost:8001/api/v1/rag/graph/related?entity=DoesNotExist" \
  -H "Authorization: Bearer $JWT" | python3 -m json.tool

# Validation guard (depth=5 → should return 422)
curl -s "http://localhost:8001/api/v1/rag/graph/related?entity=CacheStore&depth=5" \
  -H "Authorization: Bearer $JWT" | python3 -m json.tool
```

- [ ] **Stage all remaining changes**

```bash
cd DevForge_Backend && git add src/api/schemas/rag.py src/api/routers/rag.py tests/test_rag_graph_expansion.py
```
