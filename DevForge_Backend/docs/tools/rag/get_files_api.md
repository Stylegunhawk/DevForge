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
| `X-User-ID` | No | Tenant identifier. Defaults to `"default"`. |

## Response

**Status:** `200 OK`  
**Schema:** `List[FileStatusResponse]`

```json
[
  {
    "id": "uuid-1",
    "name": "document.pdf",
    "size": 123456,
    "url": "http://localhost:8000/static/...",
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
curl "http://localhost:8000/api/v1/rag/files" \
  -H "X-User-ID: my_tenant"

# Use default tenant
curl "http://localhost:8000/api/v1/rag/files"
```

## Guarantees

- ✅ Full tenant isolation via Redis SCAN
- ✅ Returns all files (pending + complete)
- ✅ Empty array if no files (NOT 404)
- ✅ Uses existing Redis cache (7-day TTL)

## Related Endpoints

- `POST /api/v1/rag/file/upload` - Upload files
- `GET /api/v1/rag/file/{fileId}` - Single file status
- `DELETE /api/v1/rag/file/{fileId}` - Delete file

---

**Version:** 15.2 (2026-02-11)
