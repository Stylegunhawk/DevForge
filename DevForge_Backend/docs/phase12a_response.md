### Test 1: Intent Classification - Code Search
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{"name": "retrieve_docs", "arguments": {"query": "find implementation of QueryExpander class", "top_k": 5}}'
```
{
    "success": true,
    "data": {
        "response": "I don't have enough information to answer that.",
        "documents": [
            {
                "id": "",
                "content": "Parameters\n\n| Parameter | Type | Required | Default | Description |\n|-----------|------|----------|---------|-------------|\n| `query` | string | ✅ Yes | - | Search query for semantic retrieval |\n| `file_paths` | array[string] | No | `[]` | Documents to ingest before searching |\n| `top_k` | integer | No | `5` | Number of results to return (1-50) |\n| `embed_model` | string | No | `\"nomic-embed-text\"` | Embedding model to use |\n| `include_context` | boolean | No | `false` | Enable graph-based context expansion |\n\n### New in Phase 10.1\n\n**`include_context`** - Enable code graph expansion:\n- Finds related functions via calls/imports\n- BFS traversal (default depth: 2)\n- Returns extended context with related code\n\n**Example:**\n```json\n{\n  \"query\": \"authentication logic\",\n  \"include_context\": true,\n  \"top_k\": 3\n}\n```\n\n---\n",
                "metadata": {
                    "name": "retrieve_docs_chunk_3",
                    "chunk_type": "documentation",
                    "source": "docs\\tools\\retrieve_docs.md",
                    "tool": "retrieve_docs"
                },
                "score": 0.0032
            },
            {
                "id": "",
                "content": "Parameters\n\n| Parameter | Type | Required | Default | Description |\n|-----------|------|----------|---------|-------------|\n| `query` | string | ✅ Yes | - | User query for relevance scoring |\n| `documents` | array[string] | ✅ Yes | - | List of documents to rerank |\n| `top_k` | integer | No | `5` | Number of top results to return |\n\n---\n",
                "metadata": {
                    "name": "rerank_docs_chunk_3",
                    "source": "docs\\tools\\rerank_docs.md",
                    "chunk_type": "documentation",
                    "tool": "rerank_docs"
                },
                "score": 0.0032
            },
            {
                "id": "",
                "content": "Best Practices\n\n1. **Set Appropriate Top-K**\n   - Use 2x initial retrieval for reranking pool\n   - Return top-k after reranking\n\n2. **Document Quality**\n   - Clean, well-formatted documents\n   - Remove boilerplate/noise\n   - Keep documents focused\n\n3. **Query Optimization**\n   - Clear, specific queries\n   - Use technical terms when applicable\n   - Consider using `refine_prompt` first\n\n4. **Performance**\n   - Batch small datasets\n   - Cache frequent queries\n   - Monitor reranking time\n\n---\n",
                "metadata": {
                    "chunk_type": "documentation",
                    "tool": "rerank_docs",
                    "source": "docs\\tools\\rerank_docs.md",
                    "name": "rerank_docs_chunk_16"
                },
                "score": 0.0029
            },
            {
                "id": "",
                "content": "Features\n\n- ✅ Cross-Encoder based reranking\n- ✅ Standalone or RAG-integrated usage\n- ✅ Configurable top-k results\n- ✅ Fast inference (< 200ms)\n- ✅ Automatic integration with `retrieve_docs`\n- ✅ CPU-optimized model\n\n---\n",
                "metadata": {
                    "name": "rerank_docs_chunk_2",
                    "tool": "rerank_docs",
                    "chunk_type": "documentation",
                    "source": "docs\\tools\\rerank_docs.md"
                },
                "score": 0.003
            },
            {
                "id": "",
                "content": "Validation & Robustness\n\nThe tool has been rigorously verified against complex production scenarios.\n\n### \"All-In-One\" Stress Test\nThe following complex prompt verifies multi-entity logic, regex patterns, context classification, and new semantic types in a single request:\n\n```bash\ncurl -X POST \"http://localhost:8001/api/gateway\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\n    \"name\": \"generate_data\",\n    \"arguments\": {\n      \"rows\": 20,\n      \"format\": \"json\",\n      \"prompt\": \"Generate a digital library and HR system. Entities: \\n1. employees (employee_id pattern: \\\"^EMP-[0-9]{5}$\\\", name, title, email, job_title, ip_v6, mac_address)\\n2. books (isbn pattern: \\\"^978-[0-9]{10}$\\\", title, author, genre enum:[\\\"Fiction\\\",\\\"Non-Fiction\\\",\\\"Sci-Fi\\\"])\\n3. libraries (name, city, street_address, zip_code)\\n4. checkouts (id, employee_id FK, book_id FK, library_id FK, status enum:[\\\"active\\\",\\\"returned\\\",\\\"overdue\\\"], checkout_date). \\nEnsure employees have unique IPs and checkouts link correctly.\",\n      \"realism_level\": \"high\",\n      \"enable_semantic_generation\": true\n    }\n  }'\n```\n\n**Verified Capabilities:**\n- ✅ **Context Refinement:** Distinguishes `book.title` (Product Name) from `employee.title` (Job Title).\n- ✅ **Lexical Expansion:** Generates valid `ip_v6`, `mac_address`, `zip_code`, `street_address`.\n- ✅ **Pattern Constraints:** Enforces `^EMP-[0-9]{5}$` and `^978-[0-9]{10}$` (ISBN) using `rstr`.\n- ✅ **Enum Constraints:** Respects status enums (`active`, `returned`, `overdue`).\n- ✅ **Multi-Entity:** correctly links `checkouts` to `employees`, `books`, and `libraries`.\n\n### Known Limitations\n- **Enum Extraction from Prompt:** While the tool supports enums defined in the schema, the LLM Schema Designer may occasionally miss specific enum values provided in a complex natural language prompt (e.g., specific book genres might default to a generic list).\n- **Complex FK Patterns:** Foreign keys are guaranteed to link to existing rows, but if the parent ID uses a comp",
                "metadata": {
                    "source": "docs\\tools\\generate_data.md",
                    "chunk_type": "documentation",
                    "name": "generate_data_chunk_9",
                    "tool": "generate_data"
                },
                "score": 0.003
            }
        ],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}

### Test 2: Intent Classification - Explain
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{"name": "retrieve_docs", "arguments": {"query": "explain how semantic caching works in RAG", "top_k": 5}}'
```
{
    "success": true,
    "data": {
        "response": "I don't have enough information to answer that.",
        "documents": [
            {
                "id": "",
                "content": "Integration with RAG\n\nThe reranker is automatically integrated into the RAG pipeline:\n\n```python\n# RAG workflow (simplified)\nasync def rag_retrieve(query, top_k=5):\n    # 1. Vector search (get more than needed)\n    initial_docs = vector_store.search(query, top_k=top_k * 2)\n    \n    # 2. Rerank (if reranker available)\n    if reranker_available:\n        reranked_docs = reranker.rerank(query, initial_docs, top_k=top_k)\n        return reranked_docs\n    \n    # 3. Return initial results\n    return initial_docs[:top_k]\n```\n\n---\n",
                "metadata": {
                    "chunk_type": "documentation",
                    "source": "docs\\tools\\rerank_docs.md",
                    "tool": "rerank_docs",
                    "name": "rerank_docs_chunk_11"
                },
                "score": 0.0041
            },
            {
                "id": "",
                "content": "\n### 3. RAG (Retrieval-Augmented Generation)\n\n**Phase 11.2 Complete - Production Ready** ✅\n\n**Advanced Retrieval:**\n- 🔍 **Hybrid Search** - BM25 keyword + Vector semantic with RRF fusion (+8-12% accuracy)\n- 🚀 **Query Cache** - Exact-match caching (10-50ms vs 250ms, Redis + LRU fallback)\n- 🎯 **Cross-Encoder Reranking** - Two-stage retrieval (ms-marco-MiniLM-L-6-v2)\n- ⚡ **Code-Aware Boosting** - Prioritize functions, classes over text\n- 📊 **Observability** - /rag/metrics and /rag/health endpoints",
                "metadata": {
                    "start_line": 189,
                    "source": "README.md",
                    "calls": "",
                    "imports": "",
                    "chunk_type": "text",
                    "name": "chunk_10",
                    "language": "markdown",
                    "end_line": 199,
                    "docstring": ""
                },
                "score": 0.0036
            },
            {
                "id": "",
                "content": "RAG_EMBED_MODEL is a configuration setting in DevForge Backend.\nIt specifies the embedding model used for semantic search.\nDefault value is 'nomic-embed-text'.\nThis model runs via Ollama for local embeddings.",
                "metadata": {
                    "source": "config.py",
                    "name": "RAG_EMBED_MODEL_doc",
                    "chunk_type": "text"
                },
                "score": 0.0036
            },
            {
                "id": "",
                "content": "Configuration (Updated)\n\n### RAG Settings\n\n```python\n# Chunking\nRAG_CHUNK_SIZE = 500  # Characters per chunk (text files)\nRAG_CHUNK_OVERLAP = 50  # Overlap between chunks\n\n# Retrieval\nRAG_TOP_K = 5  # Default results\nRAG_SCORE_THRESHOLD = 0.5  # Minimum similarity score\n\n# Embedding\nRAG_EMBED_MODEL = \"nomic-embed-text\"\n\n# [NEW] Code Graph\nENABLE_CODE_GRAPH = True  # Enable graph expansion\nGRAPH_CONTEXT_DEPTH = 2   # BFS depth limit\nGRAPH_MAX_CONTEXT_CHUNKS = 3  # Max related chunks\n\n# [NEW] Async Processing\nCELERY_BROKER_URL = \"redis://localhost:6379/0\"\nCELERY_RESULT_BACKEND = \"redis://localhost:6379/0\"\nCELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes\n```\n\n---\n",
                "metadata": {
                    "tool": "retrieve_docs",
                    "name": "retrieve_docs_chunk_8",
                    "chunk_type": "documentation",
                    "source": "docs\\tools\\retrieve_docs.md"
                },
                "score": 0.0035
            },
            {
                "id": "",
                "content": "The RAGAgent class is the main orchestrator for retrieval-augmented generation.\nIt handles document ingestion, semantic search, reranking, and response generation.\nLocated in src/agents/rag/agent.py.",
                "metadata": {
                    "chunk_type": "text",
                    "name": "RAGAgent_doc",
                    "source": "agent.py"
                },
                "score": 0.0036
            }
        ],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}




### Test 3: Semantic Cache Test (1st Call)
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{"name": "retrieve_docs", "arguments": {"query": "What is the default embedding model for RAG?", "top_k": 3}}'
```
{
    "success": true,
    "data": {
        "response": "The default embedding model for RAG is **`nomic-embed-text`**【1†L1-L3】【2†L9-L11】",
        "documents": [
            {
                "id": "",
                "content": "RAG_EMBED_MODEL is a configuration setting in DevForge Backend.\nIt specifies the embedding model used for semantic search.\nDefault value is 'nomic-embed-text'.\nThis model runs via Ollama for local embeddings.",
                "metadata": {
                    "chunk_type": "text",
                    "name": "RAG_EMBED_MODEL_doc",
                    "source": "config.py"
                },
                "score": 0.0044
            },
            {
                "id": "",
                "content": "Configuration (Updated)\n\n### RAG Settings\n\n```python\n# Chunking\nRAG_CHUNK_SIZE = 500  # Characters per chunk (text files)\nRAG_CHUNK_OVERLAP = 50  # Overlap between chunks\n\n# Retrieval\nRAG_TOP_K = 5  # Default results\nRAG_SCORE_THRESHOLD = 0.5  # Minimum similarity score\n\n# Embedding\nRAG_EMBED_MODEL = \"nomic-embed-text\"\n\n# [NEW] Code Graph\nENABLE_CODE_GRAPH = True  # Enable graph expansion\nGRAPH_CONTEXT_DEPTH = 2   # BFS depth limit\nGRAPH_MAX_CONTEXT_CHUNKS = 3  # Max related chunks\n\n# [NEW] Async Processing\nCELERY_BROKER_URL = \"redis://localhost:6379/0\"\nCELERY_RESULT_BACKEND = \"redis://localhost:6379/0\"\nCELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes\n```\n\n---\n",
                "metadata": {
                    "chunk_type": "documentation",
                    "tool": "retrieve_docs",
                    "source": "docs\\tools\\retrieve_docs.md",
                    "name": "retrieve_docs_chunk_8"
                },
                "score": 0.0036
            },
            {
                "id": "",
                "content": "Integration with RAG\n\nThe reranker is automatically integrated into the RAG pipeline:\n\n```python\n# RAG workflow (simplified)\nasync def rag_retrieve(query, top_k=5):\n    # 1. Vector search (get more than needed)\n    initial_docs = vector_store.search(query, top_k=top_k * 2)\n    \n    # 2. Rerank (if reranker available)\n    if reranker_available:\n        reranked_docs = reranker.rerank(query, initial_docs, top_k=top_k)\n        return reranked_docs\n    \n    # 3. Return initial results\n    return initial_docs[:top_k]\n```\n\n---\n",
                "metadata": {
                    "source": "docs\\tools\\rerank_docs.md",
                    "tool": "rerank_docs",
                    "chunk_type": "documentation",
                    "name": "rerank_docs_chunk_11"
                },
                "score": 0.0039
            },
            {
                "id": "",
                "content": "\n### 3. RAG (Retrieval-Augmented Generation)\n\n**Phase 11.2 Complete - Production Ready** ✅\n\n**Advanced Retrieval:**\n- 🔍 **Hybrid Search** - BM25 keyword + Vector semantic with RRF fusion (+8-12% accuracy)\n- 🚀 **Query Cache** - Exact-match caching (10-50ms vs 250ms, Redis + LRU fallback)\n- 🎯 **Cross-Encoder Reranking** - Two-stage retrieval (ms-marco-MiniLM-L-6-v2)\n- ⚡ **Code-Aware Boosting** - Prioritize functions, classes over text\n- 📊 **Observability** - /rag/metrics and /rag/health endpoints",
                "metadata": {
                    "source": "README.md",
                    "language": "markdown",
                    "end_line": 199,
                    "imports": "",
                    "start_line": 189,
                    "name": "chunk_10",
                    "docstring": "",
                    "chunk_type": "text",
                    "calls": ""
                },
                "score": 0.0032
            },
            {
                "id": "",
                "content": "The RAGAgent class is the main orchestrator for retrieval-augmented generation.\nIt handles document ingestion, semantic search, reranking, and response generation.\nLocated in src/agents/rag/agent.py.",
                "metadata": {
                    "chunk_type": "text",
                    "source": "agent.py",
                    "name": "RAGAgent_doc"
                },
                "score": 0.0031
            }
        ],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}

### Test 4: Semantic Cache Test (2nd Call - Similar Query)
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{"name": "retrieve_docs", "arguments": {"query": "What embedding model does RAG use by default?", "top_k": 3}}'
```
{
    "success": true,
    "data": {
        "response": "The default embedding model used by the RAG pipeline is **`nomic-embed-text`**【1†L1-L3】【2†L9-L11】.",
        "documents": [
            {
                "id": "",
                "content": "RAG_EMBED_MODEL is a configuration setting in DevForge Backend.\nIt specifies the embedding model used for semantic search.\nDefault value is 'nomic-embed-text'.\nThis model runs via Ollama for local embeddings.",
                "metadata": {
                    "source": "config.py",
                    "chunk_type": "text",
                    "name": "RAG_EMBED_MODEL_doc"
                },
                "score": 0.0044
            },
            {
                "id": "",
                "content": "Configuration (Updated)\n\n### RAG Settings\n\n```python\n# Chunking\nRAG_CHUNK_SIZE = 500  # Characters per chunk (text files)\nRAG_CHUNK_OVERLAP = 50  # Overlap between chunks\n\n# Retrieval\nRAG_TOP_K = 5  # Default results\nRAG_SCORE_THRESHOLD = 0.5  # Minimum similarity score\n\n# Embedding\nRAG_EMBED_MODEL = \"nomic-embed-text\"\n\n# [NEW] Code Graph\nENABLE_CODE_GRAPH = True  # Enable graph expansion\nGRAPH_CONTEXT_DEPTH = 2   # BFS depth limit\nGRAPH_MAX_CONTEXT_CHUNKS = 3  # Max related chunks\n\n# [NEW] Async Processing\nCELERY_BROKER_URL = \"redis://localhost:6379/0\"\nCELERY_RESULT_BACKEND = \"redis://localhost:6379/0\"\nCELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes\n```\n\n---\n",
                "metadata": {
                    "chunk_type": "documentation",
                    "source": "docs\\tools\\retrieve_docs.md",
                    "tool": "retrieve_docs",
                    "name": "retrieve_docs_chunk_8"
                },
                "score": 0.0034
            },
            {
                "id": "",
                "content": "Parameters\n\n| Parameter | Type | Required | Default | Description |\n|-----------|------|----------|---------|-------------|\n| `query` | string | ✅ Yes | - | Search query for semantic retrieval |\n| `file_paths` | array[string] | No | `[]` | Documents to ingest before searching |\n| `top_k` | integer | No | `5` | Number of results to return (1-50) |\n| `embed_model` | string | No | `\"nomic-embed-text\"` | Embedding model to use |\n| `include_context` | boolean | No | `false` | Enable graph-based context expansion |\n\n### New in Phase 10.1\n\n**`include_context`** - Enable code graph expansion:\n- Finds related functions via calls/imports\n- BFS traversal (default depth: 2)\n- Returns extended context with related code\n\n**Example:**\n```json\n{\n  \"query\": \"authentication logic\",\n  \"include_context\": true,\n  \"top_k\": 3\n}\n```\n\n---\n",
                "metadata": {
                    "source": "docs\\tools\\retrieve_docs.md",
                    "name": "retrieve_docs_chunk_3",
                    "chunk_type": "documentation",
                    "tool": "retrieve_docs"
                },
                "score": 0.0031
            },
            {
                "id": "",
                "content": "Integration with RAG\n\nThe reranker is automatically integrated into the RAG pipeline:\n\n```python\n# RAG workflow (simplified)\nasync def rag_retrieve(query, top_k=5):\n    # 1. Vector search (get more than needed)\n    initial_docs = vector_store.search(query, top_k=top_k * 2)\n    \n    # 2. Rerank (if reranker available)\n    if reranker_available:\n        reranked_docs = reranker.rerank(query, initial_docs, top_k=top_k)\n        return reranked_docs\n    \n    # 3. Return initial results\n    return initial_docs[:top_k]\n```\n\n---\n",
                "metadata": {
                    "chunk_type": "documentation",
                    "tool": "rerank_docs",
                    "name": "rerank_docs_chunk_11",
                    "source": "docs\\tools\\rerank_docs.md"
                },
                "score": 0.0038
            },
            {
                "id": "",
                "content": "\n### 3. RAG (Retrieval-Augmented Generation)\n\n**Phase 11.2 Complete - Production Ready** ✅\n\n**Advanced Retrieval:**\n- 🔍 **Hybrid Search** - BM25 keyword + Vector semantic with RRF fusion (+8-12% accuracy)\n- 🚀 **Query Cache** - Exact-match caching (10-50ms vs 250ms, Redis + LRU fallback)\n- 🎯 **Cross-Encoder Reranking** - Two-stage retrieval (ms-marco-MiniLM-L-6-v2)\n- ⚡ **Code-Aware Boosting** - Prioritize functions, classes over text\n- 📊 **Observability** - /rag/metrics and /rag/health endpoints",
                "metadata": {
                    "language": "markdown",
                    "end_line": 199,
                    "chunk_type": "text",
                    "name": "chunk_10",
                    "imports": "",
                    "calls": "",
                    "docstring": "",
                    "start_line": 189,
                    "source": "README.md"
                },
                "score": 0.0031
            }
        ],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}

### Test 5: Query Expansion
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{"name": "retrieve_docs", "arguments": {"query": "RAG configuration settings", "top_k": 5}}'
```
{
    "success": true,
    "data": {
        "response": "**RAG configuration settings (as defined in the provided context)**  \n\n| Category | Setting | Value / Description |\n|----------|----------|---------------------|\n| **Chunking** | `RAG_CHUNK_SIZE` | 500 characters per chunk (text files) |\n| | `RAG_CHUNK_OVERLAP` | 50 characters overlap between chunks |\n| **Retrieval** | `RAG_TOP_K` | 5 default results returned |\n| | `RAG_SCORE_THRESHOLD` | 0.5 minimum similarity score |\n| **Embedding** | `RAG_EMBED_MODEL` | `\"nomic-embed-text\"` – the default model used for semantic search (runs via Ollama) |\n| **Code Graph (optional)** | `ENABLE_CODE_GRAPH` | `True` – enables graph‑based expansion |\n| | `GRAPH_CONTEXT_DEPTH` | 2 (BFS depth limit) |\n| | `GRAPH_MAX_CONTEXT_CHUNKS` | 3 (max related chunks to pull) |\n| **Async Processing (Celery)** | `CELERY_BROKER_URL` | `\"redis://localhost:6379/0\"` |\n| | `CELERY_RESULT_BACKEND` | `\"redis://localhost:6379/0\"` |\n| | `CELERY_TASK_SOFT_TIME_LIMIT` | 300 seconds (5 min) |\n\nThese settings are defined in the **“Configuration (Updated)”** section of the context【1】. They control how documents are chunked, retrieved, embedded, optionally expanded via a code graph, and processed asynchronously.",
        "documents": [
            {
                "id": "",
                "content": "Configuration (Updated)\n\n### RAG Settings\n\n```python\n# Chunking\nRAG_CHUNK_SIZE = 500  # Characters per chunk (text files)\nRAG_CHUNK_OVERLAP = 50  # Overlap between chunks\n\n# Retrieval\nRAG_TOP_K = 5  # Default results\nRAG_SCORE_THRESHOLD = 0.5  # Minimum similarity score\n\n# Embedding\nRAG_EMBED_MODEL = \"nomic-embed-text\"\n\n# [NEW] Code Graph\nENABLE_CODE_GRAPH = True  # Enable graph expansion\nGRAPH_CONTEXT_DEPTH = 2   # BFS depth limit\nGRAPH_MAX_CONTEXT_CHUNKS = 3  # Max related chunks\n\n# [NEW] Async Processing\nCELERY_BROKER_URL = \"redis://localhost:6379/0\"\nCELERY_RESULT_BACKEND = \"redis://localhost:6379/0\"\nCELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes\n```\n\n---\n",
                "metadata": {
                    "tool": "retrieve_docs",
                    "source": "docs\\tools\\retrieve_docs.md",
                    "chunk_type": "documentation",
                    "name": "retrieve_docs_chunk_8"
                },
                "score": 0.0032
            },
            {
                "id": "",
                "content": "Integration with RAG\n\nThe reranker is automatically integrated into the RAG pipeline:\n\n```python\n# RAG workflow (simplified)\nasync def rag_retrieve(query, top_k=5):\n    # 1. Vector search (get more than needed)\n    initial_docs = vector_store.search(query, top_k=top_k * 2)\n    \n    # 2. Rerank (if reranker available)\n    if reranker_available:\n        reranked_docs = reranker.rerank(query, initial_docs, top_k=top_k)\n        return reranked_docs\n    \n    # 3. Return initial results\n    return initial_docs[:top_k]\n```\n\n---\n",
                "metadata": {
                    "chunk_type": "documentation",
                    "tool": "rerank_docs",
                    "name": "rerank_docs_chunk_11",
                    "source": "docs\\tools\\rerank_docs.md"
                },
                "score": 0.0032
            },
            {
                "id": "",
                "content": "RAG_EMBED_MODEL is a configuration setting in DevForge Backend.\nIt specifies the embedding model used for semantic search.\nDefault value is 'nomic-embed-text'.\nThis model runs via Ollama for local embeddings.",
                "metadata": {
                    "source": "config.py",
                    "name": "RAG_EMBED_MODEL_doc",
                    "chunk_type": "text"
                },
                "score": 0.0028
            },
            {
                "id": "",
                "content": "Features\n\n- ✅ Cross-Encoder based reranking\n- ✅ Standalone or RAG-integrated usage\n- ✅ Configurable top-k results\n- ✅ Fast inference (< 200ms)\n- ✅ Automatic integration with `retrieve_docs`\n- ✅ CPU-optimized model\n\n---\n",
                "metadata": {
                    "source": "docs\\tools\\rerank_docs.md",
                    "chunk_type": "documentation",
                    "name": "rerank_docs_chunk_2",
                    "tool": "rerank_docs"
                },
                "score": 0.0026
            },
            {
                "id": "",
                "content": "\n### 3. RAG (Retrieval-Augmented Generation)\n\n**Phase 11.2 Complete - Production Ready** ✅\n\n**Advanced Retrieval:**\n- 🔍 **Hybrid Search** - BM25 keyword + Vector semantic with RRF fusion (+8-12% accuracy)\n- 🚀 **Query Cache** - Exact-match caching (10-50ms vs 250ms, Redis + LRU fallback)\n- 🎯 **Cross-Encoder Reranking** - Two-stage retrieval (ms-marco-MiniLM-L-6-v2)\n- ⚡ **Code-Aware Boosting** - Prioritize functions, classes over text\n- 📊 **Observability** - /rag/metrics and /rag/health endpoints",
                "metadata": {
                    "chunk_type": "text",
                    "docstring": "",
                    "source": "README.md",
                    "calls": "",
                    "end_line": 199,
                    "start_line": 189,
                    "language": "markdown",
                    "imports": "",
                    "name": "chunk_10"
                },
                "score": 0.0026
            }
        ],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}

### Test 6: Multi-Query Fusion
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{"name": "retrieve_docs", "arguments": {"query": "Compare ChromaDB and Qdrant vector stores", "top_k": 7}}'
```
{
    "success": true,
    "data": {
        "response": "I don't have enough information to answer that.",
        "documents": [
            {
                "id": "",
                "content": "- ✅ **Dual Vector Store**: Seamless fallback between local ChromaDB and cloud Qdrant.\n- ✅ **Manifest Update**: Bumped to `v0.3.1` with new tools `retrieve_docs` and `github_operation`.\n\n**New Components:**\n- `src/agents/rag/` & `src/tools/rag/` - Document processing and retrieval.\n- `src/agents/github/` & `src/tools/github/` - GitHub API integration.\n- `src/core/model_router.py` - Updated with RAG and GitHub model profiles.\n\n## 🧠 Phase 4 Summary (v0.4.0)\n",
                "metadata": {
                    "name": "chunk_13",
                    "language": "markdown",
                    "docstring": "",
                    "end_line": 231,
                    "calls": "",
                    "source": "README.md",
                    "chunk_type": "text",
                    "imports": "",
                    "start_line": 222
                },
                "score": 0.0034
            },
            {
                "id": "",
                "content": "How It Works\n\n### Traditional Retrieval (Without Reranking)\n\n```\nQuery → Vector Search → Results\nQuality: ~75% relevance\n```\n\n### With Reranking\n\n```\nQuery → Vector Search → Initial Results → Rerank → Final Results\nQuality: ~85-90% relevance\n```\n\n### Reranking Process\n\n1. **Initial Retrieval:** Get top documents from vector store\n2. **Cross-Encoder Scoring:** Re-score each document against query\n3. **Re-Sorting:** Sort by new relevance scores\n4. **Top-K Selection:** Return most relevant documents\n\n---\n",
                "metadata": {
                    "chunk_type": "documentation",
                    "tool": "rerank_docs",
                    "source": "docs\\tools\\rerank_docs.md",
                    "name": "rerank_docs_chunk_4"
                },
                "score": 0.0029
            },
            {
                "id": "",
                "content": "\n**Core Features:**\n- 📝 **Code-Aware Chunking** - AST-based parsing (Tree-sitter) for Python, JS, TS\n- 🔗 **Dependency Graph** - BFS traversal with QID-based linking\n- 🧪 **Test-Source Linking** - Automatic test file association\n- ⚙️ **Async Processing** - Celery task queue for ingestion\n- 🔌 **Vector Store Abstraction** - ChromaDB + pgvector support\n\n**Performance:**\n- <50ms cached queries\n- <200ms reranking overhead (30 candidates)\n- <300MB memory footprint\n- 40-60% cache hit rate (production)\n",
                "metadata": {
                    "name": "chunk_11",
                    "docstring": "",
                    "end_line": 213,
                    "language": "markdown",
                    "chunk_type": "text",
                    "imports": "",
                    "calls": "",
                    "start_line": 200,
                    "source": "README.md"
                },
                "score": 0.0028
            },
            {
                "id": "",
                "content": "Features\n\n- ✅ Cross-Encoder based reranking\n- ✅ Standalone or RAG-integrated usage\n- ✅ Configurable top-k results\n- ✅ Fast inference (< 200ms)\n- ✅ Automatic integration with `retrieve_docs`\n- ✅ CPU-optimized model\n\n---\n",
                "metadata": {
                    "name": "rerank_docs_chunk_2",
                    "chunk_type": "documentation",
                    "tool": "rerank_docs",
                    "source": "docs\\tools\\rerank_docs.md"
                },
                "score": 0.0028
            },
            {
                "id": "",
                "content": "Validation & Robustness\n\nThe tool has been rigorously verified against complex production scenarios.\n\n### \"All-In-One\" Stress Test\nThe following complex prompt verifies multi-entity logic, regex patterns, context classification, and new semantic types in a single request:\n\n```bash\ncurl -X POST \"http://localhost:8001/api/gateway\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\n    \"name\": \"generate_data\",\n    \"arguments\": {\n      \"rows\": 20,\n      \"format\": \"json\",\n      \"prompt\": \"Generate a digital library and HR system. Entities: \\n1. employees (employee_id pattern: \\\"^EMP-[0-9]{5}$\\\", name, title, email, job_title, ip_v6, mac_address)\\n2. books (isbn pattern: \\\"^978-[0-9]{10}$\\\", title, author, genre enum:[\\\"Fiction\\\",\\\"Non-Fiction\\\",\\\"Sci-Fi\\\"])\\n3. libraries (name, city, street_address, zip_code)\\n4. checkouts (id, employee_id FK, book_id FK, library_id FK, status enum:[\\\"active\\\",\\\"returned\\\",\\\"overdue\\\"], checkout_date). \\nEnsure employees have unique IPs and checkouts link correctly.\",\n      \"realism_level\": \"high\",\n      \"enable_semantic_generation\": true\n    }\n  }'\n```\n\n**Verified Capabilities:**\n- ✅ **Context Refinement:** Distinguishes `book.title` (Product Name) from `employee.title` (Job Title).\n- ✅ **Lexical Expansion:** Generates valid `ip_v6`, `mac_address`, `zip_code`, `street_address`.\n- ✅ **Pattern Constraints:** Enforces `^EMP-[0-9]{5}$` and `^978-[0-9]{10}$` (ISBN) using `rstr`.\n- ✅ **Enum Constraints:** Respects status enums (`active`, `returned`, `overdue`).\n- ✅ **Multi-Entity:** correctly links `checkouts` to `employees`, `books`, and `libraries`.\n\n### Known Limitations\n- **Enum Extraction from Prompt:** While the tool supports enums defined in the schema, the LLM Schema Designer may occasionally miss specific enum values provided in a complex natural language prompt (e.g., specific book genres might default to a generic list).\n- **Complex FK Patterns:** Foreign keys are guaranteed to link to existing rows, but if the parent ID uses a comp",
                "metadata": {
                    "source": "docs\\tools\\generate_data.md",
                    "tool": "generate_data",
                    "name": "generate_data_chunk_9",
                    "chunk_type": "documentation"
                },
                "score": 0.0029
            }
        ],
        "backend": "chroma"
    },
    "message": "retrieve_docs executed successfully"
}

## Analytics Endpoints

### Check Intent Distribution
```bash
curl http://localhost:8000/api/rag/analytics/intent-distribution
```
{
    "enabled": true,
    "intent_distribution": {},
    "method_breakdown": {},
    "total_classifications": 0
}

### Check Expansion Quality
```bash
curl http://localhost:8000/api/rag/analytics/expansion-quality
```
{
    "enabled": true,
    "total": 0,
    "llm_success_rate": 0.0,
    "keyword_fallback_rate": 0.0,
    "recommendation": "No expansions yet"
}

### Check Semantic Cache Stats
```bash
curl http://localhost:8000/api/rag/analytics/cache-by-intent
```
{
    "enabled": true,
    "hits": 0,
    "misses": 0,
    "hit_rate": 0.0,
    "avg_similarity": 0.0,
    "threshold": 0.92,
    "cache_sizes": {},
    "total_cached": 0
}