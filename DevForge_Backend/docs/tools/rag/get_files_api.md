# GET /api/v1/rag/files - Batch File Retrieval

## Overview

Retrieve all file metadata for the current tenant in a single request.

## Endpoint

```
GET /api/v1/rag/files
```

## Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Bearer <tenant_jwt>` — validated by `JWTAuthMiddleware`; `tenant_id` claim extracted from the token. |

## Response

**Status:** `200 OK`  
**Schema:** `List[FileStatusResponse]`

```json
[
  {
    "id": "uuid-1",
    "name": "document.pdf",
    "size": 123456,
    "url": "http://localhost:8001/static/...",
    "fileType": "application/pdf",
    "chunkCount": 15,
    "chunkingStatus": "success",
    "embeddingStatus": "success",
    "finishEmbedding": true,
    "createdAt": "2026-02-11T10:00:00"
  }
]
```

Empty tenant returns `[]`.

## Examples

```bash
# Get all files for tenant
curl "http://localhost:8001/api/v1/rag/files" \
  -H "X-User-ID: my_tenant"

# Use default tenant
curl "http://localhost:8001/api/v1/rag/files"
```

## Guarantees

- ✅ Full tenant isolation via Redis SCAN
- ✅ Returns all files (pending + complete)
- ✅ Empty array if no files (NOT 404)
- ✅ Uses existing Redis cache (7-day TTL)

## Related Endpoints

- `POST /api/v1/rag/file/upload` - Upload files
- `GET /api/v1/rag/file/{fileId}` - Single file status
- `GET /api/v1/rag/file/{fileId}/chunks` - [Sequential chunk retrieval](get_file_chunks_api.md)
- `DELETE /api/v1/rag/file/{fileId}[?force=true]` - Delete file and chunks

---

**Version:** 0.8.0 (2026-05-08)
