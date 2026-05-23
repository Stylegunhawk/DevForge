# RAG Debugging Guide

**Branch:** `rag_resolve`  
**Last Updated:** 2026-05-23  
**Purpose:** Operational reference for debugging the RAG pipeline — JWT tokens, Docker commands, Redis inspection, pgvector queries, and common fixes.

---

## Quick Health Check

```bash
# 1. API health
curl -s http://localhost:8001/health | python3 -m json.tool

# 2. Docker service status
docker compose --profile rag ps

# 3. Redis connectivity
docker exec devforge-redis redis-cli ping   # → PONG

# 4. Postgres connectivity
docker exec devforge-postgres pg_isready -U devforge
```

---

## JWT Tokens (30-day, pre-minted)

**JWT_SECRET:** `C6P5W7gPZbjwCEH0nQ9KlqUPrAKH7C8FcuM3SsMokj0=`  
**Algorithm:** HS256 | **Claim:** `tenant_id`

### demonslayer52866@gmail.com
```
tenant_id: 6989d05d6aef175968c3cae5
collection: user_6989d05d6aef175968c3cae5
```
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI2OTg5ZDA1ZDZhZWYxNzU5NjhjM2NhZTUiLCJleHAiOjE3ODIxNDk5NTUsImlhdCI6MTc3OTU1Nzk1NSwib3JpZ2luYWxfaXNzdWVkX2F0IjoxNzc5NTU3OTU1LjM0OTM5NX0.0DQgT5yYy7glpfvk1PtG2qkOwuESdiM_9bTEua9x7sY
```

### 47d131bc tenant
```
tenant_id: 47d131bc-9490-4cae-8634-0c7a436b8c1f
collection: user_47d131bc-9490-4cae-8634-0c7a436b8c1f
```
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI0N2QxMzFiYy05NDkwLTRjYWUtODYzNC0wYzdhNDM2YjhjMWYiLCJleHAiOjE3ODIxNDk5NTUsImlhdCI6MTc3OTU1Nzk1NSwib3JpZ2luYWxfaXNzdWVkX2F0IjoxNzc5NTU3OTU1LjM0OTM5NX0.YwH2X2e2vZcvRkaUcXPRSGnnZ-IjvtWHUeEzkV7FjGw
```

### Mint a new JWT (any tenant_id)
```bash
cd DevForge_Backend && source venv/bin/activate
python3 -c "
import jwt
from datetime import datetime, timedelta, timezone
secret = 'C6P5W7gPZbjwCEH0nQ9KlqUPrAKH7C8FcuM3SsMokj0='
now = datetime.now(timezone.utc)
print(jwt.encode({'tenant_id': 'PASTE_TENANT_ID', 'exp': now + timedelta(days=30), 'iat': now, 'original_issued_at': now.timestamp()}, secret, algorithm='HS256'))
"
```

---

## Core curl Test Commands

Set `JWT` once, then run any test below:

```bash
JWT="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI2OTg5ZDA1ZDZhZWYxNzU5NjhjM2NhZTUiLCJleHAiOjE3ODIxNDk5NTUsImlhdCI6MTc3OTU1Nzk1NSwib3JpZ2luYWxfaXNzdWVkX2F0IjoxNzc5NTU3OTU1LjM0OTM5NX0.0DQgT5yYy7glpfvk1PtG2qkOwuESdiM_9bTEua9x7sY"
```

### List files for tenant
```bash
curl -s http://localhost:8001/api/v1/rag/files \
  -H "Authorization: Bearer $JWT" | python3 -m json.tool
```

### Semantic search (no filter)
```bash
curl -s -X POST http://localhost:8001/api/v1/rag/chunk/semanticSearchForChat \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"userQuery":"YOUR QUERY","messageId":"dbg-001","top_k":5}' \
  | python3 -c "
import sys,json; d=json.load(sys.stdin); chunks=d.get('chunks',[])
print(f'chunks={len(chunks)}, expansion_count={d.get(\"expansion_count\")}')
for c in chunks: print(f'  [{\"GRAPH\" if c.get(\"is_graph_expansion\") else \"VEC \"}] {c[\"filename\"]} score={c[\"similarity\"]:.3f}')
"
```

### Semantic search (scoped to specific file IDs)
```bash
curl -s -X POST http://localhost:8001/api/v1/rag/chunk/semanticSearchForChat \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{
    "userQuery":"YOUR QUERY",
    "messageId":"dbg-002",
    "top_k":5,
    "fileIds":["FILE_ID_1","FILE_ID_2"]
  }' | python3 -m json.tool
```

### Upload a file
```bash
curl -s -X POST http://localhost:8001/api/v1/rag/file/upload \
  -H "Authorization: Bearer $JWT" \
  -F "file=@/path/to/your/file.py" \
  -F "collection=default" | python3 -m json.tool
```

### Delete a file
```bash
curl -s -X DELETE http://localhost:8001/api/v1/rag/file/FILE_ID \
  -H "Authorization: Bearer $JWT" | python3 -m json.tool
```

---

## Redis Inspection & Fixes

```bash
# All RAG-related keys for a tenant
docker exec devforge-redis redis-cli KEYS "*6989d05d*"

# Check if a file's Redis metadata exists
docker exec devforge-redis redis-cli GET "file:FILE_ID"

# View graph cache key for a tenant
docker exec devforge-redis redis-cli GET "rag_graph:v2:user_TENANT_ID"

# Delete stale graph cache (forces rebuild on next query)
docker exec devforge-redis redis-cli DEL "rag_graph:v2:user_6989d05d6aef175968c3cae5"
docker exec devforge-redis redis-cli DEL "rag_graph:v2:user_47d131bc-9490-4cae-8634-0c7a436b8c1f"

# Flush ALL query semantic cache entries
docker exec devforge-redis redis-cli KEYS "query_cache:*" | xargs -r docker exec -i devforge-redis redis-cli DEL

# Rebuild BM25 index (clears stale in-memory index for one worker)
curl -s -X POST http://localhost:8001/api/rag/bm25/rebuild | python3 -m json.tool
```

---

## pgvector Inspection & Fixes

All commands run inside the postgres container (port not exposed to host).

```bash
# Total chunks and unique file_ids
docker exec devforge-postgres psql -U devforge -d devforge -c \
  "SELECT COUNT(*), COUNT(DISTINCT metadata->>'file_id') as files FROM rag_vectors;"

# Chunks per file_id for a specific tenant
docker exec devforge-postgres psql -U devforge -d devforge -c \
  "SELECT metadata->>'file_id', COUNT(*) FROM rag_vectors
   WHERE tenant_id = '6989d05d6aef175968c3cae5' GROUP BY 1 ORDER BY 2 DESC;"

# Find orphaned chunks (file_id in pgvector but not in Redis)
# Run inside the API container (has access to both services):
docker exec devforge-api python3 /tmp/find_orphans.py
# (script at DevForge_Backend/scripts/find_orphans.py — see below)

# Delete all chunks for a specific file_id
docker exec devforge-postgres psql -U devforge -d devforge -c \
  "DELETE FROM rag_vectors WHERE metadata->>'file_id' = 'FILE_ID';"

# Delete ALL chunks for a tenant
docker exec devforge-postgres psql -U devforge -d devforge -c \
  "DELETE FROM rag_vectors WHERE tenant_id = 'TENANT_ID';"
```

---

## Orphan Cleanup Script

Finds and purges all pgvector chunks with no corresponding Redis file metadata (across all tenants). Run inside the API container.

```python
# Save as: scripts/purge_orphans.py
# Run as:  docker cp scripts/purge_orphans.py devforge-api:/tmp/ && docker exec devforge-api python3 /tmp/purge_orphans.py
import asyncio, asyncpg
import redis.asyncio as aioredis

POSTGRES_URL = "postgresql://devforge:devforge123@postgres:5432/devforge"
REDIS_URL = "redis://redis:6379"

async def purge_orphans(dry_run=True):
    pg = await asyncpg.connect(POSTGRES_URL)
    r = aioredis.from_url(REDIS_URL, decode_responses=True)

    rows = await pg.fetch(
        "SELECT DISTINCT metadata->>'file_id' as fid, tenant_id FROM rag_vectors WHERE metadata->>'file_id' IS NOT NULL"
    )
    orphans = []
    for row in rows:
        if not await r.exists(f"file:{row['fid']}"):
            orphans.append(row['fid'])

    print(f"Orphans: {len(orphans)} file_ids")
    if not dry_run and orphans:
        result = await pg.execute(
            "DELETE FROM rag_vectors WHERE metadata->>'file_id' = ANY($1::text[])", orphans
        )
        print(f"Deleted: {result}")
    elif dry_run:
        for fid in orphans:
            print(f"  WOULD DELETE: {fid}")

    await pg.close(); await r.aclose()

asyncio.run(purge_orphans(dry_run=True))   # change to False to actually delete
```

---

## Common Failure Patterns & Fixes

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| `chunks: []` on search | Redis file metadata missing (orphan filter) | Run `purge_orphans.py` then re-upload files |
| `expansion_count: 0` always | All related entities already returned by vector search (correct), OR graph cache stale | Delete `rag_graph:v2:*` keys, query once to rebuild; expansion only appears when vector search misses a related entity |
| Stale chunks after file delete | BM25 in-memory index not updated | Restart API container or call `/api/rag/bm25/rebuild` |
| New file not appearing in graph expansion | Celery cache key bug (Issue #1) | **Fixed 2026-05-23** — `rag_tasks.py` now uses `v2` key |
| `403 Forbidden` on file delete | File belongs to different tenant | Check `tenant_id` in JWT matches file owner |
| High latency (>500ms) | Cache miss + reranker overhead | Check `/api/rag/metrics` and semantic cache hit rate |
| `HTTPConnectionPool host.docker.internal` in tests | Ollama host unreachable from local | Run tests inside Docker or mock `OllamaEmbeddings` |

---

## Container Restart Checklist

When restarting the API container, the following in-memory state is **lost** and must be rebuilt:

| State | Where rebuilt | Triggered by |
|-------|--------------|-------------|
| Agent TTL cache (1hr) | `agent.py` `_agent_cache` | First request per tenant |
| BM25 index | `retrieval.py` `BM25Index` | `init_bm25()` on agent init |
| Code graph | `agent.py` `init_graph()` | First search request per tenant |

> After restart, the **first query per tenant** is slow (~2–5s) as the graph and BM25 rebuild from pgvector. Subsequent queries are fast.

```bash
# Restart API only (preserve Redis + Postgres state)
docker compose --profile rag restart api

# Hard restart full stack
docker compose --profile rag down && docker compose --profile rag up -d
```

---

## Key File Paths

| File | Purpose |
|------|---------|
| `src/api/routers/rag.py` | All RAG HTTP endpoints |
| `src/agents/rag/agent.py` | `RAGAgent`, `retrieve_with_reranking`, `init_graph` |
| `src/agents/rag/reranking/cross_encoder_reranker.py` | Cross-encoder, threshold, graph-extra logic |
| `src/storage/redis_file_store.py` | `get_file_metadata`, `get_file_metadata_by_path`, orphan filter source |
| `src/storage/pgvector_store.py` | `search`, `delete_by_file_id`, `delete_collection` |
| `src/workers/tasks/rag_tasks.py` | Celery async ingestion, graph cache invalidation (Issue #1 — fixed) |
| `src/api/schemas/rag.py` | `ChatFileChunk`, `SemanticSearchResponse`, `SemanticSearchRequest` |
| `docs/tools/rag/known_issues.md` | All open/resolved issues with fixes |

---

## Open Issues (as of 2026-05-24)

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | Celery graph cache uses old key | Medium | ✅ Fixed 2026-05-23 |
| 2 | Orphan filter: missing Redis = dropped chunk | High | ✅ Operational fix (code fix pending) |
| 3 | BM25 index stale after file deletion | Low | Open |
| 4 | `POST /api/rag/ingest-async` unauthenticated | High | ✅ Fixed (was stale docs) |
| 5 | TypeScript AST fallback for all exported classes | High | ✅ Fixed 2026-05-24 |
| 6 | Cross-file graph expansion returns 0 | Medium | ✅ Fixed 2026-05-24 |
| 7 | `chunkingStatus: "success"` masks ast_fallback | Low | Open |

See [`known_issues.md`](./known_issues.md) for full detail and fix recipes.
