1.  Simple Query
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "What is retrieve_docs?",
      "top_k": 3
    }
}'
{
    "success": true,
    "data": {
        "response": "`retrieve_docs` is a **RAG (Retrieval‑Augmented Generation) document‑retrieval tool** that performs semantic search over a variety of file types. It supports code‑aware chunking, dependency‑graph expansion, and test‑source linking, and can ingest files asynchronously via Celery. The tool is production‑ready (v10.1, Phase 10.1) and offers features such as cross‑encoder reranking, configurable top‑k results, fast inference (< 200 ms), and optional graph‑based context expansion for code files 【1†L1-L5】【2†L1-L4】.",
        "documents": [
            {
                "id": "",
                "content": "Overview\n\nThe `retrieve_docs` tool provides semantic document search with **code-aware chunking**, **dependency graph expansion**, and **test-source linking**. Phase 10.1 enhancements include:\n- 🆕 Async ingestion via Celery task queue\n- 🆕 Tree-sitter AST parsing for code files (Python, JS, TS)\n- 🆕 Code dependency graph with BFS traversal\n- 🆕 Graph-based context expansion\n- ✅ Multi-format support (PDF, MD, TXT, DOCX, PY, JS, TS)\n- ✅ Dual vector store (ChromaDB local + Qdrant cloud)\n\n---\n",
                "metadata": {
                    "name": "retrieve_docs_chunk_1",
                    "chunk_type": "documentation",
                    "source": "docs\\tools\\retrieve_docs.md",
                    "tool": "retrieve_docs"
                },
                "score": 0.0034
            },
            {
                "id": "",
                "content": "# retrieve_docs - RAG Document Retrieval Tool\n\n**Tool Name:** `retrieve_docs`  \n**Version:** 10.1 (Phase 10.1)  \n**Status:** ✅ Production Ready  \n**Last Updated:** December 14, 2025\n\n---\n",
                "metadata": {
                    "chunk_type": "documentation",
                    "name": "retrieve_docs_chunk_0",
                    "tool": "retrieve_docs",
                    "source": "docs\\tools\\retrieve_docs.md"
                },
                "score": 0.0034
            },
            {
                "id": "",
                "content": "Features\n\n- ✅ Cross-Encoder based reranking\n- ✅ Standalone or RAG-integrated usage\n- ✅ Configurable top-k results\n- ✅ Fast inference (< 200ms)\n- ✅ Automatic integration with `retrieve_docs`\n- ✅ CPU-optimized model\n\n---\n",
                "metadata": {
                    "source": "docs\\tools\\rerank_docs.md",
                    "tool": "rerank_docs",
                    "name": "rerank_docs_chunk_2",
                    "chunk_type": "documentation"
                },
                "score": 0.0028
            },
            {
                "id": "",
                "content": "Parameters\n\n| Parameter | Type | Required | Default | Description |\n|-----------|------|----------|---------|-------------|\n| `query` | string | ✅ Yes | - | Search query for semantic retrieval |\n| `file_paths` | array[string] | No | `[]` | Documents to ingest before searching |\n| `top_k` | integer | No | `5` | Number of results to return (1-50) |\n| `embed_model` | string | No | `\"nomic-embed-text\"` | Embedding model to use |\n| `include_context` | boolean | No | `false` | Enable graph-based context expansion |\n\n### New in Phase 10.1\n\n**`include_context`** - Enable code graph expansion:\n- Finds related functions via calls/imports\n- BFS traversal (default depth: 2)\n- Returns extended context with related code\n\n**Example:**\n```json\n{\n  \"query\": \"authentication logic\",\n  \"include_context\": true,\n  \"top_k\": 3\n}\n```\n\n---\n",
                "metadata": {
                    "tool": "retrieve_docs",
                    "chunk_type": "documentation",
                    "name": "retrieve_docs_chunk_3",
                    "source": "docs\\tools\\retrieve_docs.md"
                },
                "score": 0.003
            },
            {
                "id": "",
                "content": "Parameters\n\n| Parameter | Type | Required | Default | Description |\n|-----------|------|----------|---------|-------------|\n| `query` | string | ✅ Yes | - | User query for relevance scoring |\n| `documents` | array[string] | ✅ Yes | - | List of documents to rerank |\n| `top_k` | integer | No | `5` | Number of top results to return |\n\n---\n",
                "metadata": {
                    "chunk_type": "documentation",
                    "name": "rerank_docs_chunk_3",
                    "tool": "rerank_docs",
                    "source": "docs\\tools\\rerank_docs.md"
                },
                "score": 0.0031
            }
        ],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}

2. Debug query
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "why does rerank_docs fail with empty list",
      "top_k": 3
    }
  }'
{
    "success": true,
    "data": {
        "response": "I don't have enough information to answer that.",
        "documents": [
            {
                "id": "",
                "content": "Overview\n\nThe `rerank_docs` tool improves search result quality by re-scoring retrieved documents using a Cross-Encoder model. It's designed to work standalone or integrated with the RAG pipeline to provide more relevant results based on semantic similarity.\n\n---\n",
                "metadata": {
                    "name": "rerank_docs_chunk_1",
                    "source": "docs\\tools\\rerank_docs.md",
                    "tool": "rerank_docs",
                    "chunk_type": "documentation"
                },
                "score": 0.0033
            },
            {
                "id": "",
                "content": "How It Works\n\n### Traditional Retrieval (Without Reranking)\n\n```\nQuery → Vector Search → Results\nQuality: ~75% relevance\n```\n\n### With Reranking\n\n```\nQuery → Vector Search → Initial Results → Rerank → Final Results\nQuality: ~85-90% relevance\n```\n\n### Reranking Process\n\n1. **Initial Retrieval:** Get top documents from vector store\n2. **Cross-Encoder Scoring:** Re-score each document against query\n3. **Re-Sorting:** Sort by new relevance scores\n4. **Top-K Selection:** Return most relevant documents\n\n---\n",
                "metadata": {
                    "tool": "rerank_docs",
                    "source": "docs\\tools\\rerank_docs.md",
                    "chunk_type": "documentation",
                    "name": "rerank_docs_chunk_4"
                },
                "score": 0.0033
            },
            {
                "id": "",
                "content": "Parameters\n\n| Parameter | Type | Required | Default | Description |\n|-----------|------|----------|---------|-------------|\n| `query` | string | ✅ Yes | - | User query for relevance scoring |\n| `documents` | array[string] | ✅ Yes | - | List of documents to rerank |\n| `top_k` | integer | No | `5` | Number of top results to return |\n\n---\n",
                "metadata": {
                    "tool": "rerank_docs",
                    "source": "docs\\tools\\rerank_docs.md",
                    "chunk_type": "documentation",
                    "name": "rerank_docs_chunk_3"
                },
                "score": 0.0035
            },
            {
                "id": "",
                "content": "# rerank_docs - Document Reranking Tool\n\n**Tool Name:** `rerank_docs`  \n**Version:** 0.7.0  \n**Phase:** 4 (Reranking)  \n**Status:** ✅ Production Ready\n\n---\n",
                "metadata": {
                    "name": "rerank_docs_chunk_0",
                    "tool": "rerank_docs",
                    "source": "docs\\tools\\rerank_docs.md",
                    "chunk_type": "documentation"
                },
                "score": 0.0037
            },
            {
                "id": "",
                "content": "Troubleshooting\n\n**Issue:** Slow reranking  \n**Solution:** Reduce document count or top_k\n\n**Issue:** Model loading errors  \n**Solution:** Check sentence-transformers installation\n\n**Issue:** Poor reranking quality  \n**Solution:** Ensure documents are relevant to domain\n\n---\n",
                "metadata": {
                    "tool": "rerank_docs",
                    "name": "rerank_docs_chunk_18",
                    "source": "docs\\tools\\rerank_docs.md",
                    "chunk_type": "documentation"
                },
                "score": 0.0035
            }
        ],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}

3.  Explain query
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "explain how semantic search works in RAG",
      "top_k": 5
    }
}'
{
    "success": true,
    "data": {
        "response": "Semantic search in the RAG system works by converting the query and documents into dense vector embeddings and then performing a similarity lookup in a vector store.\n\n1. **Embedding the query** – The query is encoded with the model defined by `RAG_EMBED_MODEL` (default **`nomic-embed-text`**, run locally via Ollama) 【2】.  \n2. **Vector lookup** – The vector store is searched with the query embedding to retrieve a pool of candidate documents (often more than the final `top_k` is needed) 【1】.  \n3. **Optional reranking** – If a cross‑encoder reranker is available, the retrieved candidates are rescored with a Cross‑Encoder (e.g., `ms‑marco‑MiniLM‑L‑6‑v2`) and the top `k` results are returned 【1】【4】.  \n\nThus, semantic search first uses the embedding model to find nearest‑neighbor vectors, then (optionally) refines the ranking with a reranker before delivering the final results.",
        "documents": [
            {
                "id": "",
                "content": "Integration with RAG\n\nThe reranker is automatically integrated into the RAG pipeline:\n\n```python\n# RAG workflow (simplified)\nasync def rag_retrieve(query, top_k=5):\n    # 1. Vector search (get more than needed)\n    initial_docs = vector_store.search(query, top_k=top_k * 2)\n    \n    # 2. Rerank (if reranker available)\n    if reranker_available:\n        reranked_docs = reranker.rerank(query, initial_docs, top_k=top_k)\n        return reranked_docs\n    \n    # 3. Return initial results\n    return initial_docs[:top_k]\n```\n\n---\n",
                "metadata": {
                    "name": "rerank_docs_chunk_11",
                    "tool": "rerank_docs",
                    "chunk_type": "documentation",
                    "source": "docs\\tools\\rerank_docs.md"
                },
                "score": 0.0045
            },
            {
                "id": "",
                "content": "RAG_EMBED_MODEL is a configuration setting in DevForge Backend.\nIt specifies the embedding model used for semantic search.\nDefault value is 'nomic-embed-text'.\nThis model runs via Ollama for local embeddings.",
                "metadata": {
                    "source": "config.py",
                    "chunk_type": "text",
                    "name": "RAG_EMBED_MODEL_doc"
                },
                "score": 0.0035
            },
            {
                "id": "",
                "content": "Overview\n\nThe `rerank_docs` tool improves search result quality by re-scoring retrieved documents using a Cross-Encoder model. It's designed to work standalone or integrated with the RAG pipeline to provide more relevant results based on semantic similarity.\n\n---\n",
                "metadata": {
                    "chunk_type": "documentation",
                    "name": "rerank_docs_chunk_1",
                    "source": "docs\\tools\\rerank_docs.md",
                    "tool": "rerank_docs"
                },
                "score": 0.0034
            },
            {
                "id": "",
                "content": "\n### 3. RAG (Retrieval-Augmented Generation)\n\n**Phase 11.2 Complete - Production Ready** ✅\n\n**Advanced Retrieval:**\n- 🔍 **Hybrid Search** - BM25 keyword + Vector semantic with RRF fusion (+8-12% accuracy)\n- 🚀 **Query Cache** - Exact-match caching (10-50ms vs 250ms, Redis + LRU fallback)\n- 🎯 **Cross-Encoder Reranking** - Two-stage retrieval (ms-marco-MiniLM-L-6-v2)\n- ⚡ **Code-Aware Boosting** - Prioritize functions, classes over text\n- 📊 **Observability** - /rag/metrics and /rag/health endpoints",
                "metadata": {
                    "imports": "",
                    "calls": "",
                    "end_line": 199,
                    "language": "markdown",
                    "name": "chunk_10",
                    "source": "README.md",
                    "chunk_type": "text",
                    "start_line": 189,
                    "docstring": ""
                },
                "score": 0.0038
            },
            {
                "id": "",
                "content": "The RAGAgent class is the main orchestrator for retrieval-augmented generation.\nIt handles document ingestion, semantic search, reranking, and response generation.\nLocated in src/agents/rag/agent.py.",
                "metadata": {
                    "source": "agent.py",
                    "chunk_type": "text",
                    "name": "RAGAgent_doc"
                },
                "score": 0.0036
            }
        ],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}

4. Tool Based query
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "What model does rerank_docs use for cross-encoder?",
      "top_k": 3
    }
}'
{
    "success": true,
    "data": {
        "response": "The **rerank_docs** tool uses the cross‑encoder model  \n\n**`cross-encoder/ms-marco-MiniLM-L-6-v2`**  \n\nas specified in the configuration settings (see the `RERANK_MODEL` entry)【4†L1-L4】.",
        "documents": [
            {
                "id": "",
                "content": "Overview\n\nThe `rerank_docs` tool improves search result quality by re-scoring retrieved documents using a Cross-Encoder model. It's designed to work standalone or integrated with the RAG pipeline to provide more relevant results based on semantic similarity.\n\n---\n",
                "metadata": {
                    "source": "docs\\tools\\rerank_docs.md",
                    "tool": "rerank_docs",
                    "chunk_type": "documentation",
                    "name": "rerank_docs_chunk_1"
                },
                "score": 0.0039
            },
            {
                "id": "",
                "content": "Implementation Details\n\n### Technology Stack\n- **sentence-transformers** 3.3.1 - Cross-encoder framework\n- **transformers** - Hugging Face library\n- **PyTorch** - Deep learning backend\n\n### Code Location\n- Agent: `src/agents/reranker.py`\n- Tests: `tests/test_reranker.py`\n\n### Architecture\n\n```python\nclass Reranker:\n    def __init__(self, model_name):\n        self.model = CrossEncoder(model_name)\n    \n    def rerank(self, query, documents, top_k):\n        # Create query-document pairs\n        pairs = [[query, doc] for doc in documents]\n        \n        # Score pairs\n        scores = self.model.predict(pairs)\n        \n        # Sort by score\n        ranked = sorted(zip(documents, scores), \n                       key=lambda x: x[1], \n                       reverse=True)\n        \n        # Return top-k\n        return ranked[:top_k]\n```\n\n---\n",
                "metadata": {
                    "source": "docs\\tools\\rerank_docs.md",
                    "tool": "rerank_docs",
                    "name": "rerank_docs_chunk_13",
                    "chunk_type": "documentation"
                },
                "score": 0.0037
            },
            {
                "id": "",
                "content": "Features\n\n- ✅ Cross-Encoder based reranking\n- ✅ Standalone or RAG-integrated usage\n- ✅ Configurable top-k results\n- ✅ Fast inference (< 200ms)\n- ✅ Automatic integration with `retrieve_docs`\n- ✅ CPU-optimized model\n\n---\n",
                "metadata": {
                    "tool": "rerank_docs",
                    "name": "rerank_docs_chunk_2",
                    "chunk_type": "documentation",
                    "source": "docs\\tools\\rerank_docs.md"
                },
                "score": 0.0044
            },
            {
                "id": "",
                "content": "Configuration\n\n### Model Settings\n\n```python\n# Model\nRERANK_MODEL = \"cross-encoder/ms-marco-MiniLM-L-6-v2\"\n\n# Performance\nRERANK_BATCH_SIZE = 32  # Documents per batch\nRERANK_MAX_LENGTH = 512  # Max token length\n\n# Thresholds\nRERANK_MIN_SCORE = 0.0  # Minimum score to include\n```\n\n---\n",
                "metadata": {
                    "chunk_type": "documentation",
                    "source": "docs\\tools\\rerank_docs.md",
                    "tool": "rerank_docs",
                    "name": "rerank_docs_chunk_10"
                },
                "score": 0.0038
            },
            {
                "id": "",
                "content": "Available Tools\n\n### 1. generate_data - Mock Data Generation\n**File:** [`generate_data.md`](./generate_data.md)  \n**Phase:** 1 (Foundation)  \n**Status:** ✅ Production Ready\n\n**Description:** Generate realistic mock CSV/JSON data using Faker and Pandas\n\n**Key Features:**\n- Multiple format support (CSV, JSON)\n- Custom field selection\n- 1-10,000 row generation\n- Fast execution (< 1s for small datasets)\n\n**Common Use Cases:**\n- API testing\n- Database seeding\n- UI prototyping\n- Performance testing\n\n---\n\n### 2. retrieve_docs - RAG Document Retrieval\n**File:** [`retrieve_docs.md`](./retrieve_docs.md)  \n**Phase:** 3.1 (RAG Agent)  \n**Status:** ✅ Production Ready\n\n**Description:** Semantic document search using RAG with ChromaDB or Qdrant\n\n**Key Features:**\n- Multi-format support (PDF, MD, TXT, DOCX)\n- Dual vector store (ChromaDB local + Qdrant cloud)\n- Automatic reranking\n- Configurable top-k results\n\n**Common Use Cases:**\n- Codebase documentation search\n- API reference lookup\n- Architecture documentation\n- Troubleshooting guides\n\n---\n\n### 3. github_operation - GitHub Automation\n**File:** [`github_operation.md`](./github_operation.md)  \n**Phase:** 3.3 (GitHub Operations)  \n**Status:** ✅ Production Ready\n\n**Description:** Automate GitHub operations using natural language commands\n\n**Key Features:**\n- Natural language query parsing\n- Repository management\n- Issue creation\n- File commits\n- Pull request automation\n\n**Common Use Cases:**\n- Automated issue creation\n- Repository listing\n- Quick commits\n- PR workflow automation\n\n---\n\n### 4. rerank_docs - Document Reranking\n**File:** [`rerank_docs.md`](./rerank_docs.md)  \n**Phase:** 4 (Reranking)  \n**Status:** ✅ Production Ready\n\n**Description:** Improve search quality using Cross-Encoder reranking\n\n**Key Features:**\n- Cross-Encoder based scoring\n- Standalone or RAG-integrated\n- 10-20% relevance improvement\n- Fast inference (< 200ms)\n\n**Common Use Cases:**\n- Search result refinement\n- Question answering\n- Code snippet selection\n- Do",
                "metadata": {
                    "name": "README_chunk_3",
                    "chunk_type": "documentation",
                    "source": "docs\\tools\\README.md",
                    "tool": "README"
                },
                "score": 0.0045
            }
        ],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}

5. Complex Multi-Concept Queries
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "What environment variables or settings are needed for the tools?",
      "top_k": 5
    }
  }'
{
    "success": true,
    "data": {
        "response": "The tools require the following environment variables and configuration settings:\n\n**Required environment variables**\n- `GITHUB_TOKEN` – a personal access token for GitHub access.【3†L1-L5】\n\n**Optional environment variables**\n- `GITHUB_USERNAME` – the GitHub username to use (if needed).【3†L7-L9】\n\n**Feature‑toggle variables** (enable or disable specific intelligence features):\n- `GITOPS_ENABLE_FUZZY_SEARCH`\n- `GITOPS_ENABLE_COMMIT_GEN`\n- `GITOPS_ENABLE_LOG_PARSING`\n- `GITOPS_ENABLE_CONFIDENCE_GATING`【3†L12-L15】\n\n**Threshold settings** (used by the enabled features):\n- `GITOPS_FUZZY_THRESHOLD` (default 0.85)\n- `GITOPS_COMMIT_CONFIDENCE_THRESHOLD` (default 0.90)【3†L17-L20】\n\n**Performance‑related settings**:\n- `GITOPS_REPO_CACHE_TTL` (default 3600 seconds)\n- `GITOPS_SESSION_TTL` (default 1800 seconds)【3†L22-L25】\n\nThese variables and settings must be defined in the execution environment for the tools to operate correctly.",
        "documents": [
            {
                "id": "",
                "content": "Parameters\n\n| Parameter | Type | Required | Default | Description |\n|-----------|------|----------|---------|-------------|\n| `query` | string | ✅ Yes | - | Search query for semantic retrieval |\n| `file_paths` | array[string] | No | `[]` | Documents to ingest before searching |\n| `top_k` | integer | No | `5` | Number of results to return (1-50) |\n| `embed_model` | string | No | `\"nomic-embed-text\"` | Embedding model to use |\n| `include_context` | boolean | No | `false` | Enable graph-based context expansion |\n\n### New in Phase 10.1\n\n**`include_context`** - Enable code graph expansion:\n- Finds related functions via calls/imports\n- BFS traversal (default depth: 2)\n- Returns extended context with related code\n\n**Example:**\n```json\n{\n  \"query\": \"authentication logic\",\n  \"include_context\": true,\n  \"top_k\": 3\n}\n```\n\n---\n",
                "metadata": {
                    "name": "retrieve_docs_chunk_3",
                    "source": "docs\\tools\\retrieve_docs.md",
                    "tool": "retrieve_docs",
                    "chunk_type": "documentation"
                },
                "score": 0.0033
            },
            {
                "id": "",
                "content": "Parameters\n\n| Parameter | Type | Required | Default | Description |\n|-----------|------|----------|---------|-------------|\n| `query` | string | ✅ Yes | - | User query for relevance scoring |\n| `documents` | array[string] | ✅ Yes | - | List of documents to rerank |\n| `top_k` | integer | No | `5` | Number of top results to return |\n\n---\n",
                "metadata": {
                    "tool": "rerank_docs",
                    "name": "rerank_docs_chunk_3",
                    "chunk_type": "documentation",
                    "source": "docs\\tools\\rerank_docs.md"
                },
                "score": 0.0032
            },
            {
                "id": "",
                "content": "Configuration\n\n### Required Environment Variables\n\n```bash\n# Required\nGITHUB_TOKEN=ghp_your_token_here\n\n# Optional\nGITHUB_USERNAME=your_username\n```\n\n### Feature Toggles\n\n```bash\n# Intelligence Features\nGITOPS_ENABLE_FUZZY_SEARCH=true\nGITOPS_ENABLE_COMMIT_GEN=true\nGITOPS_ENABLE_LOG_PARSING=true\nGITOPS_ENABLE_CONFIDENCE_GATING=true\n\n# Thresholds\nGITOPS_FUZZY_THRESHOLD=0.85\nGITOPS_COMMIT_CONFIDENCE_THRESHOLD=0.90\n\n# Performance\nGITOPS_REPO_CACHE_TTL=3600    # 1 hour\nGITOPS_SESSION_TTL=1800       # 30 minutes\n```\n\n---\n",
                "metadata": {
                    "chunk_type": "documentation",
                    "source": "docs\\tools\\github_operation.md",
                    "tool": "github_operation",
                    "name": "github_operation_chunk_6"
                },
                "score": 0.0031
            },
            {
                "id": "",
                "content": "   Should return valid JSON with `tools` array.\n\n3. **Add Plugin in Lobe Chat**\n   - Open Lobe Chat in browser\n   - Go to Settings → Plugin Store\n   - Click \"Add Custom Plugin\"\n   - Enter URL: `http://localhost:8000/api/manifests/devforge.json`\n   - Save\n\n4. **Enable Plugin in Assistant**\n   - Create or edit an assistant\n   - Enable the \"devforge\" plugin\n   - Save assistant settings\n\n5. **Test Tool Execution**\n   - Start a chat with the assistant",
                "metadata": {
                    "chunk_type": "text",
                    "name": "chunk_29",
                    "imports": "",
                    "source": "README.md",
                    "end_line": 427,
                    "calls": "",
                    "start_line": 412,
                    "language": "markdown",
                    "docstring": ""
                },
                "score": 0.0032
            },
            {
                "id": "",
                "content": "Configuration\n\n### Model Settings\n\n```python\n# Model\nRERANK_MODEL = \"cross-encoder/ms-marco-MiniLM-L-6-v2\"\n\n# Performance\nRERANK_BATCH_SIZE = 32  # Documents per batch\nRERANK_MAX_LENGTH = 512  # Max token length\n\n# Thresholds\nRERANK_MIN_SCORE = 0.0  # Minimum score to include\n```\n\n---\n",
                "metadata": {
                    "tool": "rerank_docs",
                    "chunk_type": "documentation",
                    "source": "docs\\tools\\rerank_docs.md",
                    "name": "rerank_docs_chunk_10"
                },
                "score": 0.003
            }
        ],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}


Analytics & Monitoring

1. Check Intent Distribution
curl http://localhost:8000/api/rag/analytics/intent-distribution
{
    "enabled": true,
    "intent_distribution": {},
    "method_breakdown": {},
    "total_classifications": 0
}

2. Check Expansion Quality
curl http://localhost:8000/api/rag/analytics/expansion-quality
{
    "enabled": false,
    "message": "Query expansion not initialized"
}

3. Check Cache Stats
curl http://localhost:8000/api/rag/analytics/cache-by-intent
{
    "enabled": false,
    "message": "Semantic cache not initialized"
}

4. Check Fallback Usage
curl http://localhost:8000/api/rag/analytics/fallback-usage
{
    "enabled": true,
    "total": 0,
    "method_breakdown": {},
    "intent_distribution": {},
    "recommendation": "No classifications yet"
}

5. Check System Metrics
curl http://localhost:8000/api/rag/metrics
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

6. Health Check
curl http://localhost:8000/api/rag/health
{
    "status": "healthy",
    "version": "11.2.0",
    "components": {
        "vector_store": "ok",
        "reranker": "not_loaded",
        "bm25_index": "not_ready"
    }
}