# RAG Postman/Curl Tests (Verified)

All endpoints tested and verified working as of 2025-12-16.

---

## Base URL
```
http://localhost:8000
```

---

## 1. Health Check

**GET** `/api/rag/health`

---

## 2. Retrieve Documents (Main RAG Endpoint)

**POST** `/api/gateway`

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
    "name": "retrieve_docs",
    "arguments": {
        "query": "What is RAG_EMBED_MODEL?",
        "top_k": 3
    }
}
```

**Verified Response:**
```json
{
    "success": true,
    "data": {
        "response": "RAG_EMBED_MODEL is a configuration setting in the DevForge Backend that determines which embedding model is used for semantic search. Its default value is **`nomic-embed-text`**, and the model is executed locally via Ollama.",
        "documents": [
            {
                "id": "",
                "content": "RAG_EMBED_MODEL is a configuration setting in DevForge Backend...",
                "metadata": {
                    "source": "config.py",
                    "chunk_type": "text"
                },
                "score": 0.0042
            }
        ],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}
```

---

## 3. Analytics Endpoints (GET - No Body Required)

### Intent Distribution
**GET** `/api/rag/analytics/intent-distribution`

### Expansion Quality
**GET** `/api/rag/analytics/expansion-quality`

### Cache by Intent
**GET** `/api/rag/analytics/cache-by-intent`

### Fallback Usage
**GET** `/api/rag/analytics/fallback-usage`

### Metrics (Phase 11.2)
**GET** `/api/rag/metrics`

**Response:**
```json
{
    "version": "11.2.0",
    "cache": {
        "enabled": true,
        "hit_rate": 0.0,
        "backend": "memory_only"
    },
    "hybrid_search": {
        "enabled": true,
        "bm25_ready": false
    },
    "reranking": {
        "enabled": true,
        "model": "cross-encoder/ms-marco-MiniLM-L-6-v2"
    }
}
```

---

## 4. Cache Management (POST)

### Clear Cache
**POST** `/api/rag/cache/clear`

**Response:**
```json
{
    "status": "cleared",
    "message": "Query cache cleared successfully"
}
```

### Rebuild BM25 Index
**POST** `/api/rag/bm25/rebuild`

**Response:**
```json
{
    "status": "rebuilt",
    "message": "BM25 index rebuilt successfully"
}
```

---

## 5. Test Different Intents

### Code Search
```json
{
    "name": "retrieve_docs",
    "arguments": {
        "query": "find the RAGAgent class implementation",
        "top_k": 3
    }
}
```

### Explain
```json
{
    "name": "retrieve_docs",
    "arguments": {
        "query": "explain how the configuration system loads settings",
        "top_k": 5
    }
}
```

### Debug
```json
{
    "name": "retrieve_docs",
    "arguments": {
        "query": "why does authentication fail with 401 error",
        "top_k": 3
    }
}
```

---

## 6. List Available Tools

**POST** `/api/gateway`

```json
{
    "name": "invalid_tool",
    "arguments": {}
}
```

**Response (shows all tools):**
```json
{
    "success": false,
    "message": "Tool 'invalid_tool' not found. Available tools: ['generate_data', 'retrieve_docs', 'github_operation', 'rerank_docs', 'refine_prompt', 'generate_cheatsheet', 'generate_changelog', 'analyze_ci_failure', 'scaffold_repository']"
}
```

---

## Postman Collection Summary

| Method | Endpoint | Body Required |
|--------|----------|---------------|
| GET | `/api/rag/health` | No |
| POST | `/api/gateway` | Yes (retrieve_docs) |
| GET | `/api/rag/analytics/intent-distribution` | No |
| GET | `/api/rag/analytics/expansion-quality` | No |
| GET | `/api/rag/analytics/cache-by-intent` | No |
| GET | `/api/rag/analytics/fallback-usage` | No |
| GET | `/api/rag/metrics` | No |
| POST | `/api/rag/cache/clear` | No |
| POST | `/api/rag/bm25/rebuild` | No |

---

## Setup Before Testing

1. **Start Ollama:** `ollama serve`
2. **Start Server:** `uvicorn src.main:app --reload --port 8000`
3. **Ingest Documents:** `python scripts/simple_ingest.py`

---

**Verified**: 2025-12-16
