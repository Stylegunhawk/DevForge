# retrieve_docs - RAG Document Retrieval Tool

**Tool Name:** `retrieve_docs`  
**Version:** 0.7.0  
**Phase:** 3.1 (RAG Agent)  
**Status:** ✅ Production Ready

---

## Overview

The `retrieve_docs` tool provides semantic document search and retrieval using RAG (Retrieval-Augmented Generation). It supports ingesting documents in multiple formats and querying them using vector similarity search with ChromaDB (local) or Qdrant (cloud).

---

## Features

- ✅ Semantic search with vector embeddings
- ✅ Multi-format support (PDF, MD, TXT, DOCX)
- ✅ Dual vector store (ChromaDB local + Qdrant cloud)
- ✅ Document ingestion and chunking
- ✅ Automatic reranking with Cross-Encoder
- ✅ Configurable top-k results
- ✅ Async I/O for fast processing

---

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | ✅ Yes | - | Search query for semantic retrieval |
| `file_paths` | array[string] | No | `[]` | Documents to ingest before searching |
| `top_k` | integer | No | `5` | Number of results to return (1-50) |
| `embed_model` | string | No | `"nomic-embed-text"` | Embedding model to use |

### Embedding Models

- `nomic-embed-text` - **Default**, optimized for semantic search
- `bge-m3` - Fallback model, multi-lingual support

---

## API Usage

### Basic Search

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "explain authentication in Express.js"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "content": "Express.js authentication typically uses middleware...",
        "score": 0.89,
        "metadata": {"source": "express-auth.md"}
      }
    ],
    "query": "explain authentication in Express.js",
    "top_k": 5
  }
}
```

### Ingest and Search

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "How to implement JWT tokens?",
      "file_paths": ["/path/to/auth-guide.pdf", "/path/to/security.md"],
      "top_k": 3
    }
  }'
```

### Custom Embedding Model

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "database connection pooling",
      "embed_model": "bge-m3",
      "top_k": 10
    }
  }'
```

---

## Lobe Chat Usage

### Simple Search
```
"Search my documentation for error handling best practices"
```

### Ingest and Query
```
"Read the README.md file and tell me how to set up the project"
```

### Multi-Document Search
```
"Search across all markdown files for authentication examples"
```

---

## Document Processing Pipeline

```
Documents (PDF/MD/TXT/DOCX)
    ↓
Read Content (async I/O)
    ↓
Chunk Text (500 chars, 50 overlap)
    ↓
Generate Embeddings (nomic-embed-text)
    ↓
Store in Vector DB (ChromaDB/Qdrant)
    ↓
Semantic Search Query
    ↓
Retrieve Top-K Documents
    ↓
Rerank (Cross-Encoder)
    ↓
Return Results
```

---

## Vector Store Options

### ChromaDB (Local) - Default

**Advantages:**
- Fast local storage
- No API keys required
- Persistent collections
- Ideal for development

**Configuration:**
```python
VECTOR_BACKEND="chroma"
CHROMA_PERSIST_DIR="./data/chromadb"
```

### Qdrant (Cloud) - Fallback

**Advantages:**
- Cloud-hosted scalability
- Production-ready
- Multi-region support
- Automatic backups

**Configuration:**
```python
VECTOR_BACKEND="qdrant"
QDRANT_URL="https://your-cluster.qdrant.io"
QDRANT_API_KEY="your-api-key"
```

---

## Use Cases

### 1. Codebase Documentation Search

```json
{
  "query": "How to handle database migrations?",
  "file_paths": ["docs/database.md", "docs/setup.md"],
  "top_k": 5
}
```

### 2. API Reference Lookup

```json
{
  "query": "authentication endpoint parameters",
  "file_paths": ["api-reference.pdf"],
  "top_k": 3
}
```

### 3. Architecture Documentation

```json
{
  "query": "microservices communication patterns",
  "file_paths": ["architecture/overview.md", "architecture/services.md"],
  "top_k": 10
}
```

### 4. Troubleshooting Guides

```json
{
  "query": "connection timeout error solutions",
  "file_paths": ["troubleshooting.md"],
  "top_k": 5
}
```

---

## Configuration

### RAG Settings

```python
# Chunking
RAG_CHUNK_SIZE = 500  # Characters per chunk
RAG_CHUNK_OVERLAP = 50  # Overlap between chunks

# Retrieval
RAG_TOP_K = 5  # Default results
RAG_SCORE_THRESHOLD = 0.5  # Minimum similarity score

# Embedding
RAG_EMBED_MODEL = "nomic-embed-text"
RAG_EMBED_MODEL_FALLBACK = "bge-m3"
```

---

## Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Document ingestion (1 PDF) | 1-3s | Depends on size |
| Search query | < 500ms | With caching |
| Reranking | < 200ms | Cross-encoder |
| Embedding generation | < 100ms | Per document |

---

## Supported Document Formats

### PDF
- Text extraction with PyPDF
- Handles multi-page documents
- Preserves formatting

### Markdown (.md)
- Pure text extraction
- Preserves code blocks
- Fast processing

### Text (.txt)
- Direct text ingestion
- Fastest processing
- No formatting

### DOCX
- Word document support
- Text paragraph extraction
- Handles tables

---

## Reranking

The tool automatically applies Cross-Encoder reranking to improve result quality:

**Model:** `cross-encoder/ms-marco-MiniLM-L-6-v2`

**Process:**
1. Initial retrieval (top-k from vector store)
2. Re-score with Cross-Encoder
3. Re-sort by relevance score
4. Return top-k results

**Benefit:** 10-20% improvement in result quality

---

## Error Handling

### Document Not Found

```json
{
  "query": "test",
  "file_paths": ["/invalid/path.pdf"]
}
```

**Response:**
```json
{
  "success": false,
  "message": "File not found: /invalid/path.pdf"
}
```

### Invalid Format

```json
{
  "query": "test",
  "file_paths": ["file.xyz"]  // Unsupported format
}
```

**Response:**
```json
{
  "success": false,
  "message": "Unsupported file format: .xyz"
}
```

### Empty Query

```json
{
  "query": ""  // Error: query required
}
```

**Response:**
```json
{
  "success": false,
  "message": "query parameter is required"
}
```

---

## Implementation Details

### Technology Stack
- **ChromaDB** 1.3.2 - Local vector store
- **Qdrant Client** 1.7.0+ - Cloud vector store
- **LangChain** - Embeddings and chains
- **sentence-transformers** - Reranking
- **PyPDF** 3.17.0+ - PDF parsing
- **python-docx** 1.1.0 - DOCX parsing

### Code Location
- Agent: `src/agents/rag/agent.py`
- Tools: `src/tools/rag/tools.py`
- Tests: `tests/test_rag.py`

---

## Examples

### Search Existing Documentation

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "React hooks best practices",
      "top_k": 5
    }
  }'
```

### Ingest New Document

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "What are the main features?",
      "file_paths": ["/path/to/README.md"]
    }
  }'
```

### Multi-Document Search

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "retrieve_docs",
    "arguments": {
      "query": "deployment procedures",
      "file_paths": [
        "/docs/deployment.md",
        "/docs/infrastructure.pdf",
        "/docs/ci-cd.txt"
      ],
      "top_k": 10
    }
  }'
```

---

##Testing

### Run Tests
```bash
pytest tests/test_rag.py -v
```

### Test Coverage
- ✅ Document ingestion (33+ tests)
- ✅ Semantic search
- ✅ Vector store operations
- ✅ Reranking integration
- ✅ Error handling

---

## Best Practices

1. **Chunk Size** - 500 chars works well for most documents
2. **Top-K Selection** - Start with 5, increase if needed
3. **File Formats** - Prefer markdown for best results
4. **Vector Store** - Use ChromaDB for dev, Qdrant for prod
5. **Query Optimization** - Use `refine_prompt` tool for better queries

---

## Troubleshooting

**Issue:** Poor search results  
**Solution:** Increase top_k, try different embedding model, or refine query

**Issue:** Slow document ingestion  
**Solution:** Reduce chunk size or process documents async

**Issue:** Vector store errors  
**Solution:** Check Qdrant credentials or ChromaDB permissions

---

## Related Tools

- `rerank_docs` - Standalone document reranking
- `refine_prompt` - Optimize search queries (use `rag` domain)
- `generate_cheatsheet` - Generate documentation cheat sheets

---

**Last Updated:** December 2, 2025  
**Maintainer:** DevForge Team  
**Feedback:** Create an issue in the repository
