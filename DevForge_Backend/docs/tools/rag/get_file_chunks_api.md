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
| `X-User-ID` | No | Tenant identifier. Defaults to `"default"`. |

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
      "fileUrl": "http://localhost:8000/static/...",
      "text": "Extracted text content from the first chunk...",
      "similarity": 1.0,
      "pageNumber": 1,
      "role": "supporting"
    }
  ],
  "queryId": null
}
```

## Guarantees

- ✅ **Strict Ordering**: Chunks are guaranteed to be returned in the order they appear in the source file (`chunk_index`).
- ✅ **Tenant Isolation**: Only returns chunks from files belonging to the requesting tenant.
- ✅ **Pagination**: Full support for `limit` and `offset` for processing large files.
- ✅ **Enriched Metadata**: Includes `filename`, `fileUrl`, and `fileType` from the file store.

## Examples

```bash
# Get first 10 chunks of a file
curl "http://localhost:8000/api/v1/rag/file/uuid-123/chunks?limit=10" \
  -H "X-User-ID: my_tenant"

# Get next 10 chunks (offset)
curl "http://localhost:8000/api/v1/rag/file/uuid-123/chunks?limit=10&offset=10"
```

## Related Endpoints

- `GET /api/v1/rag/files` - List all files
- `POST /api/v1/rag/chunk/semanticSearchForChat` - Semantic search across files

---

**Version:** 15.3 (2026-02-26)
