1. http://localhost:8000/api/rag/health
{
    "status": "healthy",
    "version": "11.2.0",
    "components": {
        "vector_store": "ok",
        "reranker": "not_loaded",
        "bm25_index": "not_ready"
    }
}

2. curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "How does authentication work?",
      "top_k": 3
    }
  }'

{
    "success": true,
    "data": {
        "response": "I don't have enough information to answer that question. No relevant documents were found.",
        "documents": [],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}
server logs:  terminal logs:WARNING:src.agents.rag.agent:No documents retrieved (empty result or below threshold)
WARNING:src.agents.rag.agent:Empty context, generating fallback response
INFO:     127.0.0.1:58917 - "POST /api/gateway HTTP/1.1" 200 OK

3. curl http://localhost:8000/api/rag/analytics/intent-distribution

{
    "enabled": true,
    "intent_distribution": {},
    "method_breakdown": {},
    "total_classifications": 0
}

4. curl http://localhost:8000/api/rag/analytics/expansion-quality
{
    "enabled": false,
    "message": "Query expansion not initialized"
}

5.  curl http://localhost:8000/api/rag/analytics/cache-by-intent
{
    "enabled": false,
    "message": "Semantic cache not initialized"
}
6.  curl http://localhost:8000/api/rag/analytics/fallback-usage
{
    "enabled": true,
    "total": 0,
    "method_breakdown": {},
    "intent_distribution": {},
    "recommendation": "No classifications yet"
}

7. curl http://localhost:8000/api/rag/metrics

{
    "version": "11.2.0",
    "cache": {
        "enabled": true,
        "hit_rate": 0.0,
        "hits": 0,
        "misses": 0,
        "memory_size": 0,
        "backend": "memory_only"
    },
    "hybrid_search": {
        "enabled": true,
        "bm25_ready": false,
        "documents_indexed": 0
    },
    "reranking": {
        "enabled": true,
        "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "threshold": 0.3
    },
    "code_graph": {
        "enabled": false,
        "nodes": 0
    }
}

8. curl -X POST http://localhost:8000/api/rag/cache/clear

{
    "status": "cleared",
    "message": "Query cache cleared successfully",
    "stats": {
        "hits": 0,
        "misses": 0,
        "hit_rate": 0.0,
        "memory_size": 0,
        "backend": "memory_only"
    }
}

9. curl -X POST http://localhost:8000/api/rag/bm25/rebuild
{
    "status": "rebuilt",
    "message": "BM25 index rebuilt successfully",
    "stats": {
        "ready": false,
        "documents_indexed": 0,
        "index_type": "BM25Okapi"
    }
}

10. curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "invalid_tool",
    "arguments": {}
  }'
  {
    "success": false,
    "data": null,
    "message": "Tool 'invalid_tool' not found. Available tools: ['generate_data', 'retrieve_docs', 'github_operation', 'rerank_docs', 'refine_prompt', 'generate_cheatsheet', 'generate_changelog', 'analyze_ci_failure', 'scaffold_repository']"
}


