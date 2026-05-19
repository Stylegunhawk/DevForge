# GET /api/v1/rag/file/{fileId}/chunks - Sequential Chunk Retrieval

## Overview

Retrieve all chunks for a specific file, ordered by their original index (`chunk_index`). This endpoint is optimized for "summarize this file" or sequential traversal use cases where vector similarity is not required.

## Endpoint

```
GET /api/v1/rag/file/{fileId}/chunks
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `fileId`  | string | ✅ Yes | - | The UUID of the file. |
| `limit`   | integer | No | `5` | Number of chunks to return. |
| `offset`  | integer | No | `0` | Skip first N chunks for pagination. |

## Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Bearer <tenant_jwt>` — validated by `JWTAuthMiddleware`; `tenant_id` claim extracted from the token. |

## Response

**Status:** `200 OK`  
**Schema:** `SemanticSearchResponse`

```json
{
  "chunks": [
    {
      "id": "chunk-uuid-1",
      "fileId": "file-uuid",
      "filename": "document.pdf",
      "fileUrl": "http://localhost:8001/static/...",
      "text": "Extracted text content from the first chunk...",
      "similarity": 1.0,
      "pageNumber": 1,
      "role": "supporting",
      "is_graph_expansion": false,
      "expanded_from": null
    }
  ],
  "queryId": null,
  "expansion_count": 0
}
```

> **Note on graph expansion fields:** Sequential chunk retrieval returns chunks in file order and does not run BFS graph expansion. `is_graph_expansion` will always be `false` and `expanded_from` will always be `null` on this endpoint. `expansion_count` will always be `0`. These fields exist in the response schema for consistency with `semanticSearchForChat`.
```

## Guarantees

- ✅ **Strict Ordering**: Chunks are guaranteed to be returned in the order they appear in the source file (`chunk_index`).
- ✅ **Tenant Isolation**: Only returns chunks from files belonging to the requesting tenant.
- ✅ **Pagination**: Full support for `limit` and `offset` for processing large files.
- ✅ **Enriched Metadata**: Includes `filename`, `fileUrl`, and `fileType` from the file store.

## Examples

```bash
# Get first 10 chunks of a file
curl "http://localhost:8001/api/v1/rag/file/uuid-123/chunks?limit=10" \
  -H "X-User-ID: my_tenant"

# Get next 10 chunks (offset)
curl "http://localhost:8001/api/v1/rag/file/uuid-123/chunks?limit=10&offset=10"
```

## Related Endpoints

- `GET /api/v1/rag/files` - List all files
- `POST /api/v1/rag/chunk/semanticSearchForChat` - Semantic search across files

---

**Version:** 1.1.0 (2026-05-19)

---

## Changelog

### 2026-05-19 — v1.1.0: Graph expansion fields in response schema

- Response schema now includes `is_graph_expansion: bool` and `expanded_from: Optional[str]` on each `ChatFileChunk`, and `expansion_count: int` on `SemanticSearchResponse`.
- These fields will always be `false`/`null`/`0` on this endpoint (sequential retrieval does not run BFS expansion), but are present for schema consistency with `semanticSearchForChat`.
