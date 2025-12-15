# RAG Golden Path Test Suite (Phase 12A)

> **Purpose**: Official test suite validating the complete RAG pipeline through Phase 12A  
> **Method**: curl-based manual tests (no pytest, no code execution)  
> **Environment**: Dev mode, no Redis, no Docker

---

## 0. Prerequisites

### Start the Server
```bash
cd DevForge_Backend
.\venv\Scripts\activate
uvicorn src.main:app --reload --port 8000
```

### Expected Startup Logs
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
WARNING:src.agents.rag.cache.query_cache:Redis not available, using in-memory LRU cache only
```

### Assumptions
- ✅ No Redis (in-memory LRU cache)
- ✅ No Docker (local dev)
- ✅ ChromaDB in default persist mode
- ✅ Ollama running locally (recommended, not required — pseudo-embedding fallback available)
- ✅ Feature flags enabled by default:
  - `ENABLE_INTENT_CLASSIFICATION=True`
  - `ENABLE_QUERY_EXPANSION=True`
  - `ENABLE_SEMANTIC_CACHE=True`
  - `ENABLE_HYBRID_SEARCH=True`
  - `ENABLE_RERANKING=True`

### Verify Server Health
```bash
curl http://localhost:8000/api/rag/health
```
**Expected**: `200 OK` with health status

---

## 1. Ingestion Test

### Purpose
Verify documents can be ingested into ChromaDB.

### Command
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rag_ingest",
    "arguments": {
      "file_paths": ["src/core/config.py"],
      "collection_name": "devforge_docs"
    }
  }'
```

> ⚠️ **Note**: This command assumes the `rag_ingest` tool is registered in the gateway router. If ingestion is exposed via a direct endpoint (e.g., `/api/rag/ingest`), use that instead. The goal is to ensure documents are chunked, embeddings are generated, and Chroma receives vectors.

### Success Criteria
- Response contains `"status": "success"` or `"chunks_created": N` where N > 0
- No errors in server logs

### Expected Logs
```
INFO: Ingesting 1 documents
INFO: Document ingested: src/core/config.py
```

---

## 2. Cold Retrieval Test (Full Pipeline)

### Purpose
Verify complete pipeline execution on first query (all caches empty).

### Command
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rag_retrieve",
    "arguments": {
      "query": "How does the configuration system work?",
      "top_k": 5
    }
  }'
```

### Expected Execution Order
1. Intent classification (rule-based)
2. Semantic cache check → **MISS**
3. Exact cache check → **MISS**
4. Query expansion (2-4 variations)
5. Hybrid search (BM25 + vector)
6. RRF fusion
7. Reranking
8. Cache set (semantic + exact)

### Expected [RAG-DEBUG] Logs
```
[RAG-DEBUG] Pipeline START: query='How does the configuration...'
[RAG-DEBUG] flags(SEMANTIC=True, EXACT=True, EXPAND=True, HYBRID=True, RERANK=True)
[RAG-DEBUG] SemanticCache.get() called: query='...', intent=explain
[RAG-DEBUG] ❌ SEMANTIC CACHE MISS: ...
[RAG-DEBUG] ❌ EXACT CACHE MISS: ...
[RAG-DEBUG] SemanticCache.set() called: query='...', intent=explain
```

### Success Criteria
- Response contains `"documents"` array with results
- `"reranked": true` in response
- All [RAG-DEBUG] logs show expected MISS → retrieval → SET flow

---

## 3. Warm Retrieval Test (Cache Hit)

### Purpose
Verify cache returns results on repeated query.

### Command (same as above)
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rag_retrieve",
    "arguments": {
      "query": "How does the configuration system work?",
      "top_k": 5
    }
  }'
```

### Expected [RAG-DEBUG] Logs
```
[RAG-DEBUG] Pipeline START: query='How does the configuration...'
[RAG-DEBUG] SemanticCache.get() called: query='...', intent=explain
[RAG-DEBUG] ✅ SEMANTIC CACHE HIT: similarity=0.xxx
```
**OR**
```
[RAG-DEBUG] ✅ EXACT CACHE HIT (memory): ...
```

### Success Criteria
- Response returns faster than cold query
- **Exact cache HIT** is guaranteed on identical queries
- **Semantic cache HIT** is probabilistic (depends on similarity threshold)
- No expansion/retrieval logs (short-circuited)

---

## 4. Intent Variation Test

### Purpose
Verify intent classification works for different query types.

### Test Cases

#### 4.1 Code Search Intent
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rag_retrieve",
    "arguments": {
      "query": "find implementation of RAGAgent class",
      "top_k": 3
    }
  }'
```
**Expected Intent**: `code_search`

#### 4.2 Explain Intent
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rag_retrieve",
    "arguments": {
      "query": "explain how reranking works in detail",
      "top_k": 3
    }
  }'
```
**Expected Intent**: `explain`

#### 4.3 Debug Intent
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rag_retrieve",
    "arguments": {
      "query": "why does authentication fail with 401 error",
      "top_k": 3
    }
  }'
```
**Expected Intent**: `debug`

### Verification
Check server logs for:
```
[RAG-DEBUG] ... intent=code_search
[RAG-DEBUG] ... intent=explain
[RAG-DEBUG] ... intent=debug
```

---

## 5. Query Expansion Verification

### Purpose
Verify query expansion generates additional search variations.

### Command
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rag_retrieve",
    "arguments": {
      "query": "explain how the semantic caching mechanism works in detail",
      "top_k": 5
    }
  }'
```

### Expected Expansion Count by Intent
| Intent | Expected Expansions |
|--------|---------------------|
| debug | 2 |
| code_search | 3 |
| explain | 4 |

### Verification via Logs
Look for expansion-related logs showing:
- Original query
- Generated variations
- RRF fusion of results

### Note
If LLM is unavailable, keyword fallback is used (still valid expansion).

---

## 6. Analytics Verification

### Purpose
Verify analytics endpoints track pipeline metrics.

### 6.1 Intent Distribution
```bash
curl http://localhost:8000/api/rag/analytics/intent-distribution
```

**Example Response** (after multiple queries):
```json
{
  "enabled": true,
  "intent_distribution": {
    "debug": 1,
    "explain": 2,
    "code_search": 1
  },
  "method_breakdown": {
    "rule_based": 4,
    "default": 0
  },
  "total_classifications": 4
}
```

### 6.2 Expansion Quality
```bash
curl http://localhost:8000/api/rag/analytics/expansion-quality
```

**Example Response** (values depend on LLM availability):
```json
{
  "enabled": true,
  "llm_success_rate": 0.0,
  "keyword_fallback_rate": 1.0,
  "total_expansions": 4
}
```

### 6.3 Cache by Intent
```bash
curl http://localhost:8000/api/rag/analytics/cache-by-intent
```

**Example Response** (cache sizes depend on executed queries and intent distribution):
```json
{
  "enabled": true,
  "hits": 1,
  "misses": 3,
  "hit_rate": 0.25,
  "cache_sizes": {
    "explain": 2,
    "debug": 1,
    "code_search": 1
  }
}
```

### Why Values May Be Empty
- **First run**: No queries processed yet
- **Cache sizes = 0**: No successful retrievals cached
- **hit_rate = 0**: All queries are cold

### Non-Empty Indicates
- Pipeline is tracking metrics correctly
- Intent classification is working
- Cache is storing and retrieving

---

## 7. Failure-Safety Checks

### 7.1 Embeddings Unavailable
**Scenario**: Ollama not running

**Expected Behavior**:
- Semantic cache uses pseudo-embedding fallback
- Log shows: `[RAG-DEBUG] Using PSEUDO-EMBEDDING fallback`
- Query still returns results (degraded mode)

### 7.2 Semantic Cache Disabled
**Config**: `ENABLE_SEMANTIC_CACHE=False`

**Expected Behavior**:
- Falls back to exact cache only
- No semantic cache logs
- Pipeline completes normally

### 7.3 Expansion Disabled
**Config**: `ENABLE_QUERY_EXPANSION=False`

**Expected Behavior**:
- Original query only (no variations)
- No expansion logs
- Faster execution (single query)

### Graceful Degradation Principle
> All Phase 12A features are **additive**. Disabling any feature reduces capability but never breaks the pipeline.

---

## 8. Pass / Fail Criteria

### ✅ PASS Checklist

| # | Test | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Server starts | No errors, startup complete | ☐ |
| 2 | Swagger UI loads | http://localhost:8000/docs works | ☐ |
| 3 | Ingestion | Documents chunked and stored | ☐ |
| 4 | Cold retrieval | Full pipeline, cache MISS | ☐ |
| 5 | Warm retrieval | Cache HIT (semantic or exact) | ☐ |
| 6 | Intent: code_search | Classified correctly | ☐ |
| 7 | Intent: explain | Classified correctly | ☐ |
| 8 | Intent: debug | Classified correctly | ☐ |
| 9 | Analytics: intent-distribution | Returns valid JSON | ☐ |
| 10 | Analytics: expansion-quality | Returns valid JSON | ☐ |
| 11 | Analytics: cache-by-intent | Returns valid JSON | ☐ |

### ❌ FAIL Conditions
- Server fails to start
- Swagger returns 500 error
- Any curl command returns 5xx
- Cache never hits on repeated queries
- Analytics endpoints return `{"enabled": false}`

### Declaration

After completing all tests:

> **If all 11 checks pass**: RAG Pipeline VALID, Phase 12A COMPLETE ✅  
> **If any check fails**: Investigate logs, identify root cause, re-test

---

## Appendix: Quick Test Script (PowerShell)

```powershell
# Run all analytics checks
Write-Host "=== Intent Distribution ===" -ForegroundColor Cyan
curl http://localhost:8000/api/rag/analytics/intent-distribution

Write-Host "`n=== Expansion Quality ===" -ForegroundColor Cyan
curl http://localhost:8000/api/rag/analytics/expansion-quality

Write-Host "`n=== Cache by Intent ===" -ForegroundColor Cyan
curl http://localhost:8000/api/rag/analytics/cache-by-intent
```

---

**Document Version**: 1.0  
**Phase Coverage**: Up to Phase 12A  
**Last Updated**: 2025-12-16
