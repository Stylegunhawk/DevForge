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
  -H "Authorization: Bearer <tenant_jwt>"
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

**Version:** 1.3.0 (2026-05-24)

---

## Notes

**Issue #7 — ast_fallback not visible:** `chunkingStatus` in this response returns `"success"` even when all chunks were produced by the text fallback chunker (i.e., `ast_fallback=True` on every chunk). For TypeScript/JavaScript files, this occurred silently before the 2026-05-24 AST fix. A future improvement will expose `ast_fallback_count` in this response — see [known_issues.md](./known_issues.md#issue-7).

---

## Changelog

### 2026-05-24 — v1.3.0

- **Auth example corrected:** Example curl commands now use `Authorization: Bearer <tenant_jwt>` instead of the stale `X-User-ID` header. The endpoint has always required tenant JWT via `JWTAuthMiddleware`.
- **Issue #7 noted:** Added warning that `chunkingStatus: "success"` does not distinguish between AST chunks and text-fallback chunks.

### 2026-05-19 — v1.1.0: Version alignment

- No behavioral changes to this endpoint.
- Version bumped to align with RAG v1.1.0 rollout.
