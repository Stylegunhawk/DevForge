# RAG Comprehensive Validation Tests

Complete curl command suite for validating the RAG pipeline with docs/tools documentation.

---

## Setup

```bash
# 1. Start Ollama
ollama serve

# 2. Start Server
cd DevForge_Backend
.\venv\Scripts\activate
uvicorn src.main:app --reload --port 8000

# 3. Ingest Tools Documentation
python scripts/ingest_tools_docs.py
```

---

## Section 1: Basic Retrieval Tests

### 1.1 Simple Query
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "What is retrieve_docs?",
      "top_k": 3
    }
  }'
```

### 1.2 Code Search Query
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "find implementation of generate_data tool",
      "top_k": 5
    }
  }'
```

### 1.3 Debug Query
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "why does rerank_docs fail with empty list",
      "top_k": 3
    }
  }'
```

### 1.4 Explain Query
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "explain how semantic search works in RAG",
      "top_k": 5
    }
  }'
```

---

## Section 2: Tool-Specific Queries

### 2.1 Generate Data Tool
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "How to use generate_data tool to create JSON with 100 rows?",
      "top_k": 5
    }
  }'
```

### 2.2 GitHub Operations
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "How to create a GitHub issue using github_operation tool?",
      "top_k": 5
    }
  }'
```

### 2.3 Cheatsheet Generation
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "What languages does generate_cheatsheet support?",
      "top_k": 3
    }
  }'
```

### 2.4 Prompt Refinement
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "How to use refine_prompt tool for image generation prompts?",
      "top_k": 5
    }
  }'
```

### 2.5 Document Reranking
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "What model does rerank_docs use for cross-encoder?",
      "top_k": 3
    }
  }'
```

---

## Section 3: Complex Multi-Concept Queries

### 3.1 Cross-Tool Comparison
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "Compare retrieve_docs and rerank_docs - when to use each?",
      "top_k": 7
    }
  }'
```

### 3.2 Integration Query
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "How does the MCP gateway route requests to different tools?",
      "top_k": 5
    }
  }'
```

### 3.3 Error Handling Query
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "What errors can occur when using RAG tools and how to handle them?",
      "top_k": 5
    }
  }'
```

### 3.4 Configuration Query
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "What environment variables or settings are needed for the tools?",
      "top_k": 5
    }
  }'
```

---

## Section 4: Analytics & Monitoring

### 4.1 Check Intent Distribution
```bash
curl http://localhost:8000/api/rag/analytics/intent-distribution
```

### 4.2 Check Expansion Quality
```bash
curl http://localhost:8000/api/rag/analytics/expansion-quality
```

### 4.3 Check Cache Stats
```bash
curl http://localhost:8000/api/rag/analytics/cache-by-intent
```

### 4.4 Check Fallback Usage
```bash
curl http://localhost:8000/api/rag/analytics/fallback-usage
```

### 4.5 Check System Metrics
```bash
curl http://localhost:8000/api/rag/metrics
```

### 4.6 Health Check
```bash
curl http://localhost:8000/api/rag/health
```

---

## Section 4A: Phase 12A Query Intelligence Tests

### 4A.1 Intent Classification - Code Search
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "find the implementation of QueryExpander class",
      "top_k": 5
    }
  }'
```
**Expected Intent:** `code_search`

### 4A.2 Intent Classification - Explain
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "explain how semantic caching works in Phase 12A",
      "top_k": 5
    }
  }'
```
**Expected Intent:** `explain`

### 4A.3 Intent Classification - Debug
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "why does rerank_docs fail with empty documents list",
      "top_k": 3
    }
  }'
```
**Expected Intent:** `debug`

### 4A.4 Query Expansion Test
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "RAG configuration settings",
      "top_k": 5
    }
  }'
```
**Expected:** Server logs show `[PHASE 12A] Query expanded: 2-3 queries`

### 4A.5 Semantic Cache Test (First Call)
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "What is the default embedding model for RAG?",
      "top_k": 3
    }
  }'
```
**Expected:** Server logs show `[PHASE 12A] Semantic cache miss`

### 4A.6 Semantic Cache Test (Second Call - Similar Query)
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "What embedding model does RAG use by default?",
      "top_k": 3
    }
  }'
```
**Expected:** Server logs show `[PHASE 12A] ✅ SEMANTIC CACHE HIT`

### 4A.7 Multi-Query Fusion Test
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "How does hybrid search combine BM25 and vector results?",
      "top_k": 7
    }
  }'
```
**Expected:** Server logs show `[PHASE 12A] Fused N result sets → M docs`

### 4A.8 Complete Phase 12A Pipeline
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "Compare ChromaDB and Qdrant vector stores for RAG",
      "top_k": 5
    }
  }'
```
**Expected Logs:**
- `[PHASE 12A] Intent: explain (confidence: X.XX)`
- `[PHASE 12A] Semantic cache miss`
- `[PHASE 12A] Query expanded: 3-4 queries`
- `[PHASE 12A] Fused X result sets → Y docs`
- `[PHASE 12A] Cached result for intent=explain`

### 4A.9 Check Phase 12A Analytics
```bash
# Run after executing 4A.1-4A.8
curl http://localhost:8000/api/rag/analytics/intent-distribution
```
**Expected:**
```json
{
  "enabled": true,
  "total_classifications": 8,
  "intent_distribution": {
    "code_search": 1,
    "explain": 3,
    "debug": 1,
    "general": 3
  }
}
```

```bash
curl http://localhost:8000/api/rag/analytics/expansion-quality
```
**Expected:**
```json
{
  "enabled": true,
  "total": 8,
  "llm_success_rate": 1.0,
  "avg_expansions_per_query": 2.5
}
```

```bash
curl http://localhost:8000/api/rag/analytics/cache-by-intent
```
**Expected:**
```json
{
  "enabled": true,
  "hits": 1,
  "misses": 7,
  "hit_rate": 0.125,
  "cache_sizes": {
    "explain": 3,
    "code_search": 1,
    "debug": 1
  }
}
```

---

## Section 5: Cache & Index Operations

### 5.1 Clear Query Cache
```bash
curl -X POST http://localhost:8000/api/rag/cache/clear
```

### 5.2 Rebuild BM25 Index
```bash
curl -X POST http://localhost:8000/api/rag/bm25/rebuild
```

---

## Section 6: Edge Cases & Stress Tests

### 6.1 Very Long Query
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "I need to understand the complete workflow of how a user query goes through the RAG pipeline including intent classification, query expansion, vector search, BM25 keyword search, result fusion, cross-encoder reranking, and finally response generation with the LLM. Please explain each step in detail with code references.",
      "top_k": 10
    }
  }'
```

### 6.2 Short Query
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "RAG",
      "top_k": 3
    }
  }'
```

### 6.3 Code-Specific Query
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "async def retrieve_docs function signature and parameters",
      "top_k": 5
    }
  }'
```

### 6.4 Negative Query (Should Handle Gracefully)
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "How to make coffee with DevForge?",
      "top_k": 3
    }
  }'
```

### 6.5 High top_k Value
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "List all available tools and their purposes",
      "top_k": 20
    }
  }'
```

---

## Section 7: Repeated Query Cache Test

Run the same query twice to test cache hit:

### First Call (Cache Miss)
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "What is the default embedding model?",
      "top_k": 3
    }
  }'
```

### Second Call (Should Be Cache Hit)
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "What is the default embedding model?",
      "top_k": 3
    }
  }'
```

### Verify Cache in Server Logs
Look for: `[RAG-DEBUG] ✅ EXACT CACHE HIT`

---

## Section 8: Quick Test Script (PowerShell)

```powershell
# Save as test_rag.ps1

Write-Host "=== RAG Comprehensive Test ===" -ForegroundColor Cyan

# Test 1: Health
Write-Host "`n[1] Health Check" -ForegroundColor Yellow
curl http://localhost:8000/api/rag/health

# Test 2: Simple Query
Write-Host "`n[2] Simple Query" -ForegroundColor Yellow
$body = '{"name": "retrieve_docs", "arguments": {"query": "What is retrieve_docs?", "top_k": 3}}'
Invoke-WebRequest -Uri "http://localhost:8000/api/gateway" -Method POST -ContentType "application/json" -Body $body | Select-Object -ExpandProperty Content

# Test 3: Analytics
Write-Host "`n[3] Intent Distribution" -ForegroundColor Yellow
curl http://localhost:8000/api/rag/analytics/intent-distribution

# Test 4: Metrics
Write-Host "`n[4] System Metrics" -ForegroundColor Yellow
curl http://localhost:8000/api/rag/metrics

Write-Host "`n=== Tests Complete ===" -ForegroundColor Green
```

---

## Expected Success Criteria

| Test | Expected Result |
|------|-----------------|
| All retrieval queries | `"success": true` with documents |
| Analytics endpoints | Return valid JSON with `"enabled": true` |
| Cache tests | Second call faster (check logs) |
| Edge cases | Handle gracefully, no 500 errors |
| Metrics | Show correct component status |

---

**Document Version**: 1.0  
**Last Updated**: 2025-12-16  
**Tools Covered**: retrieve_docs, generate_data, github_operation, generate_cheatsheet, refine_prompt, rerank_docs
