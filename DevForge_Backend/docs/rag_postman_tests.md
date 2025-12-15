# RAG Golden Path - Curl Commands (macOS/Linux)

Complete curl commands for testing the RAG pipeline through Phase 12A.

---

## Base URL
```
http://localhost:8000
```

---

## 1. Health Check
```bash
curl http://localhost:8000/api/rag/health
```

---

## 2. Basic Retrieval (retrieve_docs)
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "How does authentication work?",
      "top_k": 3
    }
  }'
```

---

## 3. Intent: Code Search
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "find the RAGAgent class implementation",
      "top_k": 3
    }
  }'
```

---

## 4. Intent: Explain  
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "explain how reranking works in detail",
      "top_k": 3
    }
  }'
```

---

## 5. Intent: Debug
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "why does authentication fail with 401 error",
      "top_k": 3
    }
  }'
```

---

## 6. With Graph Context (Phase 10.1)
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "JWT token validation",
      "include_context": true,
      "top_k": 5
    }
  }'
```

---

## 7. Analytics Endpoints (Phase 12A)

### Intent Distribution
```bash
curl http://localhost:8000/api/rag/analytics/intent-distribution
```

### Expansion Quality
```bash
curl http://localhost:8000/api/rag/analytics/expansion-quality
```

### Cache by Intent
```bash
curl http://localhost:8000/api/rag/analytics/cache-by-intent
```

### Fallback Usage
```bash
curl http://localhost:8000/api/rag/analytics/fallback-usage
```

---

## 8. Observability Endpoints (Phase 11.2)

### Metrics
```bash
curl http://localhost:8000/api/rag/metrics
```

### Clear Cache
```bash
curl -X POST http://localhost:8000/api/rag/cache/clear
```

### Rebuild BM25 Index
```bash
curl -X POST http://localhost:8000/api/rag/bm25/rebuild
```

---

## 9. List Available Tools
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "invalid_tool",
    "arguments": {}
  }'
```

---

## 10. Quick Test Script (bash)
```bash
#!/bin/bash
echo "=== RAG Golden Path Tests ==="

echo -e "\n[1] Health Check"
curl -s http://localhost:8000/api/rag/health | jq .

echo -e "\n[2] Basic Retrieval"
curl -s -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{"name": "retrieve_docs", "arguments": {"query": "test query", "top_k": 3}}' | jq .success

echo -e "\n[3] Intent Distribution"
curl -s http://localhost:8000/api/rag/analytics/intent-distribution | jq .

echo -e "\n[4] Expansion Quality"
curl -s http://localhost:8000/api/rag/analytics/expansion-quality | jq .

echo -e "\n[5] Cache by Intent"
curl -s http://localhost:8000/api/rag/analytics/cache-by-intent | jq .

echo -e "\n=== Tests Complete ==="
```

---

## Expected Success Response
```json
{
  "success": true,
  "data": {
    "documents": [...],
    "reranked": true
  }
}
```

---

## Postman Import

For Postman users, import these as requests:

| Method | Endpoint | Body |
|--------|----------|------|
| GET | `/api/rag/health` | - |
| POST | `/api/gateway` | `{"name": "retrieve_docs", "arguments": {"query": "...", "top_k": 3}}` |
| GET | `/api/rag/analytics/intent-distribution` | - |
| GET | `/api/rag/analytics/expansion-quality` | - |
| GET | `/api/rag/analytics/cache-by-intent` | - |
| GET | `/api/rag/analytics/fallback-usage` | - |

---

**Last Updated**: 2025-12-16
