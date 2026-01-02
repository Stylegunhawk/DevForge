# RAG Golden Path Test Suite (Verified)

> **Tested**: 2025-12-16 | **Status**: ✅ Working  
> **Environment**: Windows, Ollama Cloud Models, No Redis/Docker

---

## Prerequisites

```bash
# Start Ollama
ollama serve

# Start Server (in DevForge_Backend)
.\venv\Scripts\activate
uvicorn src.main:app --reload --port 8000
```

---

## 1. Health Check

**GET** `http://localhost:8000/api/rag/health`

```json
// Expected Response
{
    "status": "healthy",
    "version": "11.2.0",
    "components": {
        "vector_store": "ok",
        "reranker": "not_loaded",
        "bm25_index": "not_ready"
    }
}
```

---

## 2. Basic Retrieval (✅ Verified Working)

**POST** `http://localhost:8000/api/gateway`

```json
{
    "name": "retrieve_docs",
    "arguments": {
        "query": "What is RAG_EMBED_MODEL?",
        "top_k": 3
    }
}
```

**Expected Response:**
```json
{
    "success": true,
    "data": {
        "response": "RAG_EMBED_MODEL is a configuration setting...",
        "documents": [
            {
                "content": "RAG_EMBED_MODEL is a configuration setting...",
                "score": 0.0042
            }
        ],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}
```

---

## 3. Intent Tests

### 3.1 Code Search Intent
```json
{
    "name": "retrieve_docs",
    "arguments": {
        "query": "find the RAGAgent class implementation",
        "top_k": 3
    }
}
```

### 3.2 Explain Intent
```json
{
    "name": "retrieve_docs",
    "arguments": {
        "query": "explain how reranking works",
        "top_k": 3
    }
}
```

### 3.3 Debug Intent
```json
{
    "name": "retrieve_docs",
    "arguments": {
        "query": "why does authentication fail with 401",
        "top_k": 3
    }
}
```

---

## 4. Analytics Endpoints (GET)

| Endpoint | URL |
|----------|-----|
| Intent Distribution | `GET /api/rag/analytics/intent-distribution` |
| Expansion Quality | `GET /api/rag/analytics/expansion-quality` |
| Cache by Intent | `GET /api/rag/analytics/cache-by-intent` |
| Fallback Usage | `GET /api/rag/analytics/fallback-usage` |
| Metrics | `GET /api/rag/metrics` |

---

## 5. Cache & Index Management (POST)

### Clear Cache
```
POST /api/rag/cache/clear
```
```json
{
    "status": "cleared",
    "message": "Query cache cleared successfully"
}
```

### Rebuild BM25 Index
```
POST /api/rag/bm25/rebuild
```
```json
{
    "status": "rebuilt",
    "message": "BM25 index rebuilt successfully"
}
```

---

## 6. List Available Tools

**POST** `http://localhost:8000/api/gateway`

```json
{
    "name": "invalid_tool",
    "arguments": {}
}
```

**Response shows available tools:**
```
['generate_data', 'retrieve_docs', 'github_operation', 'rerank_docs', 
 'refine_prompt', 'generate_cheatsheet', 'generate_changelog', 
 'analyze_ci_failure', 'scaffold_repository']
```

---

## 7. Pass/Fail Checklist

| # | Test | Expected | Status |
|---|------|----------|--------|
| 1 | Server starts | No errors | ✅ |
| 2 | Health check | 200 OK | ✅ |
| 3 | Swagger UI | Loads at /docs | ✅ |
| 4 | retrieve_docs | Returns documents | ✅ |
| 5 | LLM Response | Generates answer | ✅ |
| 6 | Analytics endpoints | Return JSON | ✅ |
| 7 | Cache clear | Status cleared | ✅ |
| 8 | BM25 rebuild | Status rebuilt | ✅ |

---

## Known Issues & Solutions

### Memory Error (8GB required)
**Error:** `model requires more system memory (8.0 GiB)`  
**Solution:** Use cloud models in config.py:
```python
DEFAULT_MODEL: str = "gpt-oss:20b-cloud"
RAG_LOCAL_MODEL: str = "gpt-oss:20b-cloud"
```

### Reranker Type Error
**Error:** `text input must be of type str`  
**Solution:** Fixed in `src/agents/reranker.py` - ensures string conversion

### Empty Documents
**Error:** `"documents": []`  
**Solution:** Run ingestion script first: `python scripts/simple_ingest.py`

---

**Last Updated**: 2025-12-16
