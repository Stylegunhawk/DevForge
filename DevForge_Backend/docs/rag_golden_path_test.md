# RAG Golden Path Test Suite (Phase 10.1 → 11 → 12A)

> **Purpose**: Official test suite validating the complete RAG pipeline  
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
- ✅ Feature flags enabled by default

### Verify Server Health
```bash
curl http://localhost:8000/api/rag/health
```
**Expected**: `200 OK` with health status

### Verify Swagger UI
Open http://localhost:8000/docs — should load without errors

---

## 1. Basic Retrieval Test (Gateway)

### Purpose
Verify `retrieve_docs` tool is registered and responds.

### Command
```bash
curl -X POST http://localhost:8000/api/gateway ^
  -H "Content-Type: application/json" ^
  -d "{\"name\": \"retrieve_docs\", \"arguments\": {\"query\": \"How does authentication work?\", \"top_k\": 3}}"
```

**PowerShell version:**
```powershell
$body = @{
    name = "retrieve_docs"
    arguments = @{
        query = "How does authentication work?"
        top_k = 3
    }
} | ConvertTo-Json -Depth 3

Invoke-WebRequest -Uri "http://localhost:8000/api/gateway" -Method POST -ContentType "application/json" -Body $body
```

### Success Criteria
- Response contains `"success": true`
- Response contains `"data"` with results or empty array
- No 500 errors

### Expected [RAG-DEBUG] Logs
```
[RAG-DEBUG] Pipeline START: query='How does authentication...'
[RAG-DEBUG] flags(SEMANTIC=True, EXACT=True, EXPAND=True, HYBRID=True, RERANK=True)
```

---

## 2. Cold Retrieval Test (Full Pipeline)

### Purpose
Verify complete pipeline execution on first query (all caches empty).

### Command
```bash
curl -X POST http://localhost:8000/api/gateway ^
  -H "Content-Type: application/json" ^
  -d "{\"name\": \"retrieve_docs\", \"arguments\": {\"query\": \"explain how the configuration system loads settings\", \"top_k\": 5}}"
```

### Expected Execution Order (Phase 12A)
1. Intent classification (rule-based) → `explain`
2. Semantic cache check → **MISS**
3. Exact cache check → **MISS**
4. Query expansion (2-4 variations)
5. Hybrid search (BM25 + vector) **[Phase 11.2]**
6. RRF fusion
7. Reranking **[Phase 11]**
8. Cache set (semantic + exact)

### Expected [RAG-DEBUG] Logs
```
[RAG-DEBUG] ❌ SEMANTIC CACHE MISS
[RAG-DEBUG] ❌ EXACT CACHE MISS (memory)
```

### Success Criteria
- Response contains `"documents"` array
- `"reranked": true` if ENABLE_RERANKING=True

---

## 3. Warm Retrieval Test (Cache Hit)

### Purpose
Verify cache returns results on repeated query.

### Command (same as above)
```bash
curl -X POST http://localhost:8000/api/gateway ^
  -H "Content-Type: application/json" ^
  -d "{\"name\": \"retrieve_docs\", \"arguments\": {\"query\": \"explain how the configuration system loads settings\", \"top_k\": 5}}"
```

### Expected [RAG-DEBUG] Logs (one of)
```
[RAG-DEBUG] ✅ SEMANTIC CACHE HIT: similarity=0.xxx
```
**OR**
```
[RAG-DEBUG] ✅ EXACT CACHE HIT (memory)
```

### Success Criteria
- **Exact cache HIT** is guaranteed on identical queries
- **Semantic cache HIT** is probabilistic (depends on similarity threshold 0.92)
- Response returns faster than cold query

---

## 4. Intent Variation Test

### Purpose
Verify intent classification works for different query types.

### 4.1 Code Search Intent
```bash
curl -X POST http://localhost:8000/api/gateway ^
  -H "Content-Type: application/json" ^
  -d "{\"name\": \"retrieve_docs\", \"arguments\": {\"query\": \"find the RAGAgent class implementation\", \"top_k\": 3}}"
```
**Expected Intent**: `code_search`  
**Keywords matched**: `find`, `implementation`, `class`

### 4.2 Explain Intent
```bash
curl -X POST http://localhost:8000/api/gateway ^
  -H "Content-Type: application/json" ^
  -d "{\"name\": \"retrieve_docs\", \"arguments\": {\"query\": \"explain how reranking works in detail\", \"top_k\": 3}}"
```
**Expected Intent**: `explain`  
**Keywords matched**: `explain`, `how`, `works`

### 4.3 Debug Intent
```bash
curl -X POST http://localhost:8000/api/gateway ^
  -H "Content-Type: application/json" ^
  -d "{\"name\": \"retrieve_docs\", \"arguments\": {\"query\": \"why does authentication fail with 401 error\", \"top_k\": 3}}"
```
**Expected Intent**: `debug`  
**Keywords matched**: `why`, `fail`, `error`

### Verification
Check server logs for intent classification:
```
[RAG-DEBUG] ... intent=code_search
[RAG-DEBUG] ... intent=explain
[RAG-DEBUG] ... intent=debug
```

---

## 5. Graph Context Expansion Test (Phase 10.1)

### Purpose
Verify code graph expansion retrieves related functions.

### Command
```bash
curl -X POST http://localhost:8000/api/gateway ^
  -H "Content-Type: application/json" ^
  -d "{\"name\": \"retrieve_docs\", \"arguments\": {\"query\": \"JWT token validation\", \"include_context\": true, \"top_k\": 5}}"
```

### Success Criteria
- Response may include `"expanded": true`
- Related functions (via calls/imports graph) included in results
- `expansion_count` > 0 indicates graph was used

---

## 6. Reranking Verification (Phase 11)

### Purpose
Verify two-stage retrieval (vector → cross-encoder reranking).

### Command
```bash
curl -X POST http://localhost:8000/api/gateway ^
  -H "Content-Type: application/json" ^
  -d "{\"name\": \"retrieve_docs\", \"arguments\": {\"query\": \"user authentication flow implementation\", \"top_k\": 5}}"
```

### Success Criteria
- Response contains `"reranked": true`
- Code chunks (functions, classes) may rank higher due to code-aware boosting

### Reranking Disabled Test
```bash
# Response should show "reranked": false
```

---

## 7. Analytics Verification (Phase 12A)

### Purpose
Verify analytics endpoints track pipeline metrics.

### 7.1 Intent Distribution
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

### 7.2 Expansion Quality
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

### 7.3 Cache by Intent
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

### 7.4 Fallback Usage (Intent Classification)
```bash
curl http://localhost:8000/api/rag/analytics/fallback-usage
```

### Why Values May Be Empty
- **First run**: No queries processed yet
- **Cache sizes = 0**: No successful retrievals cached
- **hit_rate = 0**: All queries are cold

---

## 8. Failure-Safety Checks

### 8.1 Embeddings Unavailable (Ollama offline)
**Expected Behavior**:
- Semantic cache uses pseudo-embedding fallback
- Log shows: `[RAG-DEBUG] Using PSEUDO-EMBEDDING fallback`
- Query still returns results (degraded mode)

### 8.2 Semantic Cache Disabled
**Config**: `ENABLE_SEMANTIC_CACHE=False`
**Expected**: Falls back to exact cache only, pipeline completes

### 8.3 Reranking Disabled
**Config**: `ENABLE_RERANKING=False`
**Expected**: Vector-only results, faster response

### 8.4 Query Expansion Disabled
**Config**: `ENABLE_QUERY_EXPANSION=False`
**Expected**: Original query only (no variations)

### Graceful Degradation Principle
> All Phase 12A features are **additive**. Disabling any feature reduces capability but never breaks the pipeline.

---

## 9. Available Tools Check

### List all registered tools
```bash
curl -X POST http://localhost:8000/api/gateway ^
  -H "Content-Type: application/json" ^
  -d "{\"name\": \"invalid_tool\", \"arguments\": {}}"
```

**Expected Response** (shows available tools):
```json
{
  "success": false,
  "message": "Tool 'invalid_tool' not found. Available tools: ['generate_data', 'retrieve_docs', 'github_operation', 'rerank_docs', 'refine_prompt', 'generate_cheatsheet', 'generate_changelog', 'analyze_ci_failure', 'scaffold_repository']"
}
```

---

## 10. Pass / Fail Criteria

### ✅ PASS Checklist

| # | Test | Expected Result | Pass |
|---|------|-----------------|------|
| 1 | Server starts | No errors, startup complete | ☐ |
| 2 | Swagger UI loads | http://localhost:8000/docs works | ☐ |
| 3 | `retrieve_docs` responds | Gateway returns success | ☐ |
| 4 | Cold retrieval | Full pipeline, cache MISS logs | ☐ |
| 5 | Warm retrieval | Cache HIT (semantic or exact) | ☐ |
| 6 | Intent: code_search | Classified correctly in logs | ☐ |
| 7 | Intent: explain | Classified correctly in logs | ☐ |
| 8 | Intent: debug | Classified correctly in logs | ☐ |
| 9 | Reranking | `"reranked": true` in response | ☐ |
| 10 | Analytics: intent-distribution | Returns valid JSON | ☐ |
| 11 | Analytics: expansion-quality | Returns valid JSON | ☐ |
| 12 | Analytics: cache-by-intent | Returns valid JSON | ☐ |

### ❌ FAIL Conditions
- Server fails to start
- Swagger returns 500 error
- Any curl command returns 5xx
- Cache never hits on repeated queries
- Analytics endpoints return `{"enabled": false}`

---

## 11. Quick Test Script (PowerShell)

```powershell
Write-Host "=== RAG Golden Path Tests ===" -ForegroundColor Cyan

# Test 1: Gateway health
Write-Host "`n[1] Testing gateway..." -ForegroundColor Yellow
$body = '{"name": "retrieve_docs", "arguments": {"query": "test query", "top_k": 3}}'
Invoke-WebRequest -Uri "http://localhost:8000/api/gateway" -Method POST -ContentType "application/json" -Body $body

# Test 2: Analytics
Write-Host "`n[2] Analytics - Intent Distribution" -ForegroundColor Yellow
curl http://localhost:8000/api/rag/analytics/intent-distribution

Write-Host "`n[3] Analytics - Expansion Quality" -ForegroundColor Yellow
curl http://localhost:8000/api/rag/analytics/expansion-quality

Write-Host "`n[4] Analytics - Cache by Intent" -ForegroundColor Yellow
curl http://localhost:8000/api/rag/analytics/cache-by-intent

Write-Host "`n=== Tests Complete ===" -ForegroundColor Green
```

---

## Phase Coverage Summary

| Phase | Feature | Test Section |
|-------|---------|--------------|
| 10.1 | Code Chunking (AST) | N/A (ingestion) |
| 10.1 | Code Graph Expansion | §5 |
| 10.1 | QID Format (file::entity) | §5 |
| 11 | Cross-Encoder Reranking | §6 |
| 11 | Sigmoid Normalization | §6 |
| 11 | Code-Aware Boosting | §6 |
| 11.2 | Query Cache (exact) | §3 |
| 11.2 | Hybrid Search (BM25+Vector) | §2 |
| 12A | Intent Classification (3-tier) | §4 |
| 12A | Semantic Cache | §3 |
| 12A | Query Expansion | §2 |
| 12A | Analytics Endpoints | §7 |

---

**Document Version**: 2.0  
**Phase Coverage**: 10.1 → 11 → 11.2 → 12A  
**Last Updated**: 2025-12-16
