# Code Graph Endpoint — Design Spec

**Date:** 2026-05-24  
**Branch:** `rag_resolve`  
**Status:** Approved — ready for implementation  

---

## Problem

The in-memory code dependency graph (`CodeGraph`) built during RAG ingestion is only
used internally for context expansion. There is no way for:

- The **chat-UI LLM agent** to query entity relationships (e.g. "what calls CacheStore?")
- A **developer** to visualise the dependency graph of their uploaded code

This spec defines two new GET endpoints that expose the graph safely and efficiently.

---

## Consumers

| Consumer | Endpoint | Use |
|---|---|---|
| Graph renderer (dashboard / chat-UI) | `GET /api/v1/rag/graph` | Full node+link dump for D3/Cytoscape |
| LLM agent tool (`get_code_graph_related`) | `GET /api/v1/rag/graph/related` | BFS query per entity |

---

## Endpoints

### 1. `GET /api/v1/rag/graph`

Full slim graph dump for visualisation.

**Auth:** `Authorization: Bearer <tenant_jwt>` (existing `JWTAuthMiddleware`)

**Query params:** none

**Response — `CodeGraphResponse`:**

```json
{
  "node_count": 42,
  "link_count": 67,
  "nodes": [
    {
      "id": "6989d05d::/.../cache.ts::CacheStore",
      "name": "CacheStore",
      "chunk_type": "class",
      "source_file": "cache.ts",
      "language": "typescript"
    }
  ],
  "links": [
    {
      "source": "6989d05d::/.../user-repository.ts::UserRepository",
      "target": "6989d05d::/.../cache.ts::CacheStore",
      "relation": "calls"
    }
  ]
}
```

- `source_file` is the filename only — the full server path (`/app/data/uploads/...`) is
  never returned, only the last path segment.
- Full QIDs are kept in `id`, `source`, `target` so the renderer can wire edges and the
  client can pass them back to the `/related` endpoint.
- Empty graph (no files ingested) returns `node_count: 0, nodes: [], links: []` — not 404.

---

### 2. `GET /api/v1/rag/graph/related`

BFS entity query for the LLM tool.

**Auth:** `Authorization: Bearer <tenant_jwt>`

**Query params:**

| Param | Type | Default | Constraint | Description |
|---|---|---|---|---|
| `entity` | string | required | — | Entity name (`CacheStore`) or full QID |
| `depth` | int | `2` | 1–3 | BFS depth |
| `max` | int | `10` | 1–20 | Max results |
| `include_snippets` | bool | `false` | — | Attach 200-char content snippet to each result |

**Response — `GraphRelatedResponse`:**

```json
{
  "entity": "CacheStore",
  "anchor": {
    "id": "tenant::/.../cache.ts::CacheStore",
    "name": "CacheStore",
    "chunk_type": "class",
    "source_file": "cache.ts"
  },
  "related": [
    {
      "id": "tenant::/.../user-repository.ts::UserRepository",
      "name": "UserRepository",
      "chunk_type": "class",
      "source_file": "user-repository.ts",
      "snippet": "export class UserRepository { private cache: CacheStore..."
    }
  ],
  "related_count": 1,
  "ambiguous": false,
  "all_anchors": []
}
```

**Entity resolution rules:**

- `entity` contains `::` → treat as full QID, look up directly in `graph._graph`
- `entity` is a plain name → scan `graph._metadata` for `qid.split("::")[-1] == entity`
  - 0 matches → `anchor: null`, `related: []`, HTTP 200 (not 404)
  - 1 match → normal response
  - N>1 matches → use first match, set `ambiguous: true`, populate `all_anchors` with
    all N matches so the caller can re-query with a full QID

**Snippet behaviour:** when `include_snippets=true`, one `get_chunk_by_qualified_id`
pgvector call is made per related entity (max 20). If a lookup fails, `snippet` is `null`
for that entity; the rest of the response is unaffected.

---

## Data Flow

```
JWT → tenant_id
  └─ get_rag_agent(tenant_id)          # reuses TTL-cached agent (1hr)
       └─ agent._code_graph is None?
            yes → await agent.init_graph()
                    Redis hit  → ~5ms
                    Cold build → ~2-5s (pgvector metadata scan)
            no  → use existing graph
       └─ graph.to_dict()              # in-memory, no DB
            or
            graph.get_related(...)     # in-memory BFS
            + optional vector_store.get_chunk_by_qualified_id() per snippet
```

---

## Schema Changes

**File:** `src/api/schemas/rag.py` — add six new Pydantic models:

```python
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
    anchor: Optional[GraphAnchor]
    related: List[RelatedEntity]
    related_count: int
    ambiguous: bool = False
    all_anchors: List[GraphAnchor] = []
```

---

## Router Changes

**File:** `src/api/routers/rag.py` — two new handlers, no new file.

```python
@router.get("/graph", response_model=CodeGraphResponse,
            dependencies=[Depends(security_scheme)])
async def get_code_graph(request: Request): ...

@router.get("/graph/related", response_model=GraphRelatedResponse,
            dependencies=[Depends(security_scheme)])
async def get_graph_related(
    request: Request,
    entity: str = Query(...),
    depth: int = Query(2, ge=1, le=3),
    max: int = Query(10, ge=1, le=20),
    include_snippets: bool = Query(False),
): ...
```

---

## SvelteKit Proxy Routes (chat-UI)

Two new proxy routes following the existing JWT-injection pattern:

```
src/routes/api/v1/rag/graph/+server.ts
  GET → forward to GET http://backend/api/v1/rag/graph

src/routes/api/v1/rag/graph/related/+server.ts
  GET → forward to GET http://backend/api/v1/rag/graph/related
        (forward all query params: entity, depth, max, include_snippets)
```

---

## New LLM Tool

**File:** `src/lib/server/rag/ragTools.ts` — add `get_code_graph_related` tool definition.

**Advertised in:** `src/lib/server/textGeneration/mcp/runRagFlow.ts` alongside existing tools.

```typescript
{
  name: "get_code_graph_related",
  description:
    "Find code entities related to a given class or function via the dependency graph. " +
    "Use when you need to understand what a class depends on, what calls it, or what it imports. " +
    "Returns names and files of related entities. " +
    "Use include_snippets=true only when you need the actual code content of related entities.",
  parameters: {
    type: "object",
    properties: {
      entity: {
        type: "string",
        description: "Entity name (e.g. 'CacheStore') or full qualified ID (tenant::file::name)"
      },
      depth:           { type: "integer", default: 2, description: "BFS depth 1-3" },
      max:             { type: "integer", default: 10, description: "Max results 1-20" },
      include_snippets:{ type: "boolean", default: false }
    },
    required: ["entity"]
  }
}
```

---

## Error Handling

| Condition | Response |
|---|---|
| No files uploaded / graph empty | HTTP 200, `node_count: 0`, empty arrays |
| Entity not found | HTTP 200, `anchor: null`, `related: []` |
| Ambiguous entity name | HTTP 200, first match used, `ambiguous: true`, `all_anchors` populated |
| `init_graph()` DB failure | Graph defaults to empty; HTTP 200 with empty response |
| Invalid `depth` / `max` | HTTP 422 (FastAPI Pydantic validation) |
| Snippet lookup failure for one entity | `snippet: null` for that entity; rest unaffected |

No new 4xx codes. All edge cases return valid shaped responses so the LLM tool never
needs to handle error branches.

---

## Safety Constraints

| Concern | Mitigation |
|---|---|
| Server path leak | `source_file` = filename only; full path never in response |
| Expensive BFS | `depth` capped at 3, `max` capped at 20 via FastAPI validators |
| Cold graph latency | Only on first request per tenant per TTL window (1hr); subsequent calls use cached agent |
| Tenant cross-contamination | `get_rag_agent(tenant_id)` enforces per-tenant isolation — same as all RAG endpoints |
| `include_snippets` N+1 | At most 20 pgvector queries; acceptable at this scale |

---

## Tests

**File:** `tests/test_rag_graph_expansion.py` — 8 new test functions:

```
test_get_code_graph_empty_graph
test_get_code_graph_strips_full_path
test_get_graph_related_by_name
test_get_graph_related_by_full_qid
test_get_graph_related_entity_not_found
test_get_graph_related_ambiguous
test_get_graph_related_depth_cap
test_get_graph_related_with_snippets
```

---

## Files Changed

| File | Change |
|---|---|
| `src/api/schemas/rag.py` | Add 6 new Pydantic models |
| `src/api/routers/rag.py` | Add 2 GET handlers |
| `tests/test_rag_graph_expansion.py` | Add 8 tests |
| `src/routes/api/v1/rag/graph/+server.ts` | New proxy (chat-UI) |
| `src/routes/api/v1/rag/graph/related/+server.ts` | New proxy (chat-UI) |
| `src/lib/server/rag/ragTools.ts` | Add `get_code_graph_related` tool |
| `src/lib/server/textGeneration/mcp/runRagFlow.ts` | Advertise new tool |

---

## Out of Scope

- Pagination for the full graph dump (not needed at current scale)
- Write operations on the graph (adding/removing edges via API)
- WebSocket streaming of graph updates
- Per-edge metadata (relation type stored as string only)
