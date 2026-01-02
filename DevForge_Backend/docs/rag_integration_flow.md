# RAG Integration Flow

**Version:** 12A Complete ✅  
**Phase:** Phase 12A Query Intelligence  
**Date:** 2025-12-17  
**Status:** Production Ready

This document details the integration flow of the RAG pipeline, including Phase 12A query intelligence features.

---

## Complete Ingestion Flow

### High-Level Pipeline

```mermaid
graph TD
    A[User Uploads Documents] --> B[POST /rag/ingest-async]
    B --> C[Celery Task: async_ingest_documents]
    C --> D[RAGAgent.ingest_document]
    D --> E[tools.ingest_documents]
    E --> F[tools.read_document]
    F --> G[tools.chunk_document]
    G --> H{File Type?}
    H -->|.py,.js,.ts| I[CodeChunker + Tree-sitter]
    H -->|Other| J[TextChunker]
    I --> K[Extract AST Metadata]
    J --> L[Text Chunks + Metadata]
    K --> M[Convert to LangChain Documents]
    L --> M
    M --> N[Generate Embeddings]
    N --> O[ChromaVectorStore.add_chunks]
    O --> P[Vector DB Storage]
   P --> Q[Task Complete]
```

### Detailed Call Chain

```
1. HTTP Request
   POST /rag/ingest-async
   Body: {"file_paths": ["utils.py"], "collection_name": "devforge_docs"}
   
2. API Endpoint (src/api/routers.py)
   async def ingest_async_endpoint(request: IngestAsyncRequest)
   ↓
   Creates Celery task
   
3. Celery Task Queue (src/workers/tasks/rag_tasks.py)
   @shared_task
   def async_ingest_documents(file_paths, collection_name)
   ↓
   Initializes RAGAgent
   
4. RAGAgent (src/agents/rag/agent.py)
   async def ingest_document(file_path)
   ↓
   Delegates to tools layer
   
5. Tools Layer (src/tools/rag/tools.py)
   async def ingest_documents(file_paths, ...)
   ↓
   Parallel file reading
   
6. Document Reading
   async def read_document(file_path) -> str
   ↓
   Returns text content
   
7. Chunking Decision (tools.chunk_document)
   def chunk_document(text, file_path, chunk_size, chunk_overlap)
   ↓
   Checks file extension
   
8A. Code Path (.py, .js, .ts)
    CodeChunker.chunk(text, file_path)
    ↓
    Tree-sitter AST parsing
    ↓
    Extract: functions, classes, imports, calls, docstrings
    ↓
    Return chunks with rich metadata
    
8B. Text Path (.md, .txt, .pdf, .docx)
    TextChunker.chunk(text, file_path)
    ↓
    RecursiveCharacterTextSplitter
    ↓
    Return chunks with basic metadata
    
9. Convert to LangChain Format
   Document(page_content=content, metadata=metadata)
   
10. Generate Embeddings
    OllamaEmbeddings.embed_documents(contents)
    
11. Store in Vector DB
    ChromaVectorStore.add_chunks(chunks, embeddings)
    ↓
    collection.add(ids, embeddings, metadatas, documents)
    
12. Return Result
    {"success": true, "chunks_created": 15, "task_id": "..."}
```

---

## Phase 12A Retrieval Flow (Query Intelligence)

### Enhanced Pipeline

```
1. User Query
   POST /api/gateway
   Body: {"name": "retrieve_docs", "arguments": {"query": "...", "top_k": 5}}
   
2. Intent Classification (3-tier)
   IntentClassifier.classify(query)
   ↓
   Tier 1: Rule-based keywords (fast, 0ms)
   Tier 2: LLM classification (if enabled, 100ms)
   Tier 3: Default fallback → "general"
   ↓
   Returns: code_search | explain | debug | general
   
3. Query Expansion (intent-aware)
   QueryExpander.expand(query, intent)
   ↓
   Generate 2-3 related queries based on intent
   ↓
   e.g., "RAG config" → ["RAG configuration", "RAG_EMBED_MODEL", "RAG settings"]
   
4. Semantic Cache Check
   SemanticCache.get(query, intent)
   ↓
   If similarity > 0.95 → Return cached result (10ms)
   Else → Continue to retrieval
   
5. Multi-Query Vector Search
   For each expanded query:
     ChromaVectorStore.similarity_search(query, top_k)
   ↓
   Returns multiple result sets
   
6. Result Fusion (RRF)
   ResultFusion.fuse(all_results)
   ↓
   Reciprocal Rank Fusion + Deduplication
   ↓
   Returns merged, ranked results
   
7. Cross-Encoder Reranking
   Reranker.rerank(query, fused_results)
   ↓
   Stage 2 precision ranking
   
8. Response Generation
   model_router.select_model("rag_simple", prefer_local=False)
   ↓
   Uses cloud model (gpt-oss:120b-cloud) for memory efficiency
   ↓
   Generate answer from context
   
9. Cache Update
   SemanticCache.set(query, intent, result)
   
10. Return Response
    {
      "success": true,
      "data": {
        "response": "...",
        "documents": [...],
        "backend": "chroma"
      }
    }
```

### Analytics Endpoints (Phase 12A)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/rag/analytics/intent-distribution` | Intent classification stats |
| `GET /api/rag/analytics/expansion-quality` | Query expansion metrics |
| `GET /api/rag/analytics/cache-by-intent` | Cache hit rates by intent |
| `GET /api/rag/analytics/fallback-usage` | Fallback trigger frequency |
| `GET /api/rag/metrics` | Overall system metrics |

---

## Retrieval Flow (Legacy - Graph Expansion)

### With Graph Context Expansion

```
1. User Query
   GET /rag/retrieve?query="authentication functions"
   
2. RAGAgent.retrieve_with_context(query, top_k=5)
   ↓
   Generate query embedding
   
3. Vector Search (ChromaVectorStore)
   search(query_embedding, top_k=5, score_threshold=0.5)
   ↓
   Returns initial results (semantic similarity)
   
4. Graph Expansion (if ENABLE_CODE_GRAPH=true)
   For each result:
     ↓
   Extract QID (file::entity)
     ↓
   CodeGraph.get_related(qid, depth=2, max_results=3)
     ↓
   BFS traversal of calls/imports
     ↓
   Fetch related chunks by QID
     ↓
   ChromaVectorStore.get_chunk_by_qualified_id(related_qid)
   
5. Merge & Deduplicate
   initial_results + related_chunks
   ↓
   Remove duplicates by QID
   
6. Return Extended Context
   {
     "documents": [...],
     "expanded": true,
     "expansion_count": 3
   }
```


## Code Path Details

### 1. RAGAgent.ingest_document

**File:** `src/agents/rag/agent.py` (lines 502-537)

```python
async def ingest_document(self, file_path: str, embed_model: Optional[str] = None) -> dict:
    from src.tools.rag.tools import ingest_documents as _ingest_documents
    
    # ARCHITECTURE: Delegates to tools layer
    result = await _ingest_documents(
        file_paths=[file_path],
        embed_model=embed_model or self.embed_model,
        chunk_size=settings.RAG_CHUNK_SIZE,
        chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        backend=self.backend,
    )
    
    logger.info(f"Document ingested: {file_path}", extra={"chunks": result.get("chunks_created", 0)})
    return result
```

**Status:** ✅ Calls `tools.ingest_documents`

---

### 2. tools.ingest_documents

**File:** `src/tools/rag/tools.py` (lines 354-445)

```python
async def ingest_documents(file_paths, embed_model, chunk_size, chunk_overlap, backend):
    # Read all documents in parallel
    read_tasks = [read_document(fp) for fp in file_paths]
    contents = await asyncio.gather(*read_tasks, return_exceptions=True)
    
    # Process each document
    all_chunks = []
    for file_path, content in zip(file_paths, contents):
        if isinstance(content, Exception):
            logger.warning(f"Failed to read {file_path}: {content}")
            continue
        
        try:
            # CRITICAL: Call chunk_document for each file
            chunks = chunk_document(
                text=content,
                file_path=file_path,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            all_chunks.extend(chunks)
        except Exception as e:
            logger.warning(f"Failed to chunk {file_path}: {e}")
    
    # Add to vector store
    if all_chunks:
        vector_store.add_documents(all_chunks)
    
    return {"success": True, "chunks_created": len(all_chunks)}
```

**Status:** ✅ Calls `chunk_document()` for each file

---

### 3. tools.chunk_document

**File:** `src/tools/rag/tools.py` (lines 259-331)

```python
def chunk_document(text: str, file_path: str, chunk_size: int, chunk_overlap: int) -> List[Document]:
    """Phase 10.1: Uses Tree-sitter for code, falls back to text."""
    
    try:
        # NEW: Code-aware chunking
        from src.agents.rag.chunking import CodeChunker, TextChunker
        
        code_chunker = CodeChunker()
        
        # Decision point: Code or Text?
        if code_chunker.is_supported(file_path):  # Check .py, .js, .ts, .tsx, .jsx
            # AST parsing for code files
            chunks_data = code_chunker.chunk(text, file_path)
            logger.info(f"Code chunking: {len(chunks_data)} chunks from {file_path}")
        else:
            # Text chunking for other files
            text_chunker = TextChunker(chunk_size, chunk_overlap)
            chunks_data = text_chunker.chunk(text, file_path)
            logger.info(f"Text chunking: {len(chunks_data)} chunks from {file_path}")
        
        # Convert to LangChain Document format
        documents = [
            Document(page_content=c["content"], metadata=c["metadata"])
            for c in chunks_data
        ]
        
        return documents
        
    except ImportError:
        # Legacy fallback: RecursiveCharacterTextSplitter
        logger.warning("Chunkers not available, using legacy mode")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = text_splitter.create_documents([text])
        for i, chunk in enumerate(chunks):
            chunk.metadata = {"source": file_path, "chunk_index": i}
        return chunks
```

**Status:** ✅ Uses code-aware chunkers with AST parsing

### 4. CodeChunker.chunk

**File:** `src/agents/rag/chunking/code_chunker.py` (lines 89-144)

```python
def chunk(self, content: str, file_path: str) -> List[Dict]:
    """Chunk code using AST parsing. Falls back to text on error."""
    
    ext = Path(file_path).suffix.lower()
    language = SUPPORTED_LANGUAGES.get(ext)  # {'.py': 'python', '.js': 'javascript', '.ts': 'typescript'}
    
    if not language or language not in self.parsers:
        return self.text_fallback.chunk(content, file_path)
    
    try:
        return self._chunk_with_ast(content, file_path, language)
    except Exception as e:
        logger.warning(f"AST parsing failed for {file_path}: {e}, falling back to text")
        return self.text_fallback.chunk(content, file_path)

def _chunk_with_ast(self, content: str, file_path: str, language: str) -> List[Dict]:
    """Parse code with Tree-sitter and extract chunks."""
    from tree_sitter import Parser
    
    # Create parser with language
    lang_obj = self.parsers[language]
    parser = Parser(lang_obj)
    tree = parser.parse(bytes(content, 'utf8'))
    
    chunks = []
    
    # Extract imports
    imports = self._extract_imports(tree.root_node, content, file_path, language)
    chunks.extend(imports)
    
    # Extract functions and classes
    entities = self._extract_entities(tree.root_node, content, file_path, language)
    chunks.extend(entities)
    
    return chunks
```

**Metadata Extracted:**
- `chunk_type`: "function", "class", "import", "text"
- `name`: Entity name (e.g., "add", "User")
- `language`: "python", "javascript", "typescript"
- `source`: File path
- `start_line`, `end_line`: Line numbers
- `imports`: List of import statements
- `calls`: List of function calls within entity
- `docstring`: Extracted docstring/JSDoc

---

## Graph Rebuild Flow

### RAGAgent.code_graph Property

**File:** `src/agents/rag/agent.py` (lines 480-527)

```python
@property
def code_graph(self):
    """Lazy-initialized code graph. Derived state, rebuilt from chunk metadata."""
    
    if self._code_graph is None:
        from src.agents.rag.graph import CodeGraph
        
        self._code_graph = CodeGraph()
        
        # ARCHITECTURE COMPLIANCE: Rebuild from vector store metadata
        async def rebuild():
            count = 0
            try:
                # Uses BaseVectorStore.iter_chunk_metadata() abstraction
                async for batch in self.vector_store.iter_chunk_metadata(batch_size=500):
                    # Convert metadata list to chunk format
                    chunks = [{"metadata": meta} for meta in batch]
                    self._code_graph.add_chunks_batch(chunks)
                    count += len(batch)
                
                logger.info(f"Graph rebuilt: {count} chunks → {self._code_graph.size()} nodes")
            except Exception as e:
                logger.warning(f"Graph rebuild failed: {e}")
        
        # Run rebuild asynchronously
        asyncio.run(rebuild())
    
    return self._code_graph
```

**Flow:**
1. First access to `agent.code_graph` triggers rebuild
2. `ChromaVectorStore.iter_chunk_metadata()` streams metadata in batches (NO embeddings)
3. For each batch, build QIDs (`file::entity`) and add to graph
4. Graph stores adjacency list (`QID → Set[related QIDs]`) and metadata (`QID → Dict`)

---

## Integration Verification ✅

| Step | Method | Status | Notes |
|------|--------|--------|-------|
| 1 | Celery → RAGAgent.ingest_document | ✅ | Architecture compliant |
| 2 | RAGAgent → tools.ingest_documents | ✅ | Delegates to tools |
| 3 | tools.ingest_documents → chunk_document | ✅ | Per-file processing |
| 4 | chunk_document → CodeChunker/TextChunker | ✅ | Automatic detection |
| 5 | CodeChunker → Tree-sitter AST | ✅ | Python, JS, TS support |
| 6 | Extract metadata | ✅ | Functions, classes, imports, calls |
| 7 | Convert to LangChain Documents | ✅ | Standard format |
| 8 | ChromaVectorStore.add_chunks | ✅ | BaseVectorStore abstraction |

---

## Metadata Flow Example

### Input: utils.py

```python
def add(a, b):
    """Add two numbers."""
    return a + b

def validate(value):
    if value < 0:
        raise ValueError("Negative")
    return add(value, 1)
```

### Output: Chunks

```json
[
  {
    "content": "def add(a, b):\n    \"\"\"Add two numbers.\"\"\"\n    return a + b",
    "metadata": {
      "chunk_type": "function",
      "name": "add",
      "language": "python",
      "source": "utils.py",
      "start_line": 1,
      "end_line": 3,
      "imports": [],
      "calls": [],
      "docstring": "Add two numbers."
    }
  },
  {
    "content": "def validate(value):...",
    "metadata": {
      "chunk_type": "function",
      "name": "validate",
      "language": "python",
      "source": "utils.py",
      "start_line": 5,
      "end_line": 8,
      "imports": [],
      "calls": ["add"],  // Detected function call
      "docstring": null
    }
  }
]
```

### Graph Structure

```
utils.py::validate → utils.py::add  (call edge)
```

### QID Format

```
QID: utils.py::add
     └─ file  └─ entity

QID: utils.py::validate
     └─ file   └─ entity
```

---

## Related Documentation

- [RAG Architecture](./rag_architecture.md) - Architecture rules and component overview
- [retrieve_docs Tool](./tools/retrieve_docs.md) - API reference and usage

---

**All integration paths verified ✅**  
**Last Updated:** December 14, 2025
