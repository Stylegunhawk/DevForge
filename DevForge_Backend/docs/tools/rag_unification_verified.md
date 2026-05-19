# RAG Unification Verification Report

**Version:** 3
**Last Updated:** 2026-05-19
**Branch:** rag_resolve

Conclusion: The RAG pipelines are fully unified.

## PART 1 — RAG Entry Points

| Type | Endpoint / Function | Router File | Handler Function |
|------|---------------------|-------------|------------------|
| Ingestion | `POST /api/v1/rag/file/upload` | `src/api/routers/rag.py` | `upload_files` |
| Retrieval | `POST /api/v1/rag/chunk/semanticSearchForChat` | `src/api/routers/rag.py` | `semantic_search_for_chat` |
| Retrieval (Legacy) | `rag_agent_invoke` (Supervisor) | `src/agents/rag/agent.py` | `rag_agent_invoke` |

## PART 2 — Ingestion Convergence Proof

- Entry: `upload_files` (`src/api/routers/rag.py`) triggers `async_ingest_documents.delay(...)`.
- Task: `async_ingest_documents` (`src/workers/rag_tasks.py`) calls `agent.ingest_document(...)`.
- Agent: `RAGAgent.ingest_document` (`src/agents/rag/agent.py`) explicitly imports and calls `src.tools.rag.tools.ingest_documents`.
- Tool: `ingest_documents` (`src/tools/rag/tools.py`) performs file reading, chunking (`chunk_document`), and vector upsert.
- Result: Unified. All paths execute `src.tools.rag.tools.ingest_documents`.

## PART 3 — Chunking Authority Verification

- Authority: `src/tools/rag/tools.py` function `chunk_document`.
- Logic:
  - Imports `CodeChunker` and `TextChunker` from `src.agents.rag.chunking`.
  - Handles fallback logic for code vs. text.
- Verification: No other files instantiate `CodeChunker` or `TextChunker` for the purpose of ingestion.
- Result: Single Authority.

## PART 4 — Retrieval Convergence Proof

- Endpoint: `semantic_search_for_chat` (`src/api/routers/rag.py`) calls `RAGAgent.retrieve_with_reranking`.
- Legacy: `retrieve_node` (`src/agents/rag/agent.py`), called by `rag_agent_invoke`, calls `RAGAgent.retrieve_with_reranking`.
- Kernel: `RAGAgent.retrieve_with_reranking` (`src/agents/rag/agent.py`) handles intent, caching, expansion, and calls `RAGAgent._vector_search`.
- Vector: `RAGAgent._vector_search` (`src/agents/rag/agent.py`) calls `self.vector_store.search(...)` directly — i.e. the `BaseVectorStore` abstraction in `src/storage/base_store.py`.
- Note: `src.tools.rag.tools.retrieve_docs` is a thin shim that delegates *back* to `RAGAgent.retrieve_with_reranking`; the dependency runs from `tools.retrieve_docs` → `RAGAgent`, not the other way around. `_vector_search` does **not** call `tools.retrieve_docs`.
- Result: Unified. Both paths converge on `RAGAgent.retrieve_with_reranking`, which then reaches the vector store via the `BaseVectorStore` abstraction.

## PART 5 — Shadow Logic Detection

- Audit: Searched `src/` for `CodeChunker`, `TextChunker`, `RecursiveCharacterTextSplitter`.
- Findings:
  - `src/tools/rag/tools.py`: legitimate usage.
  - `src/agents/rag/chunking/`: class definitions.
  - `src/agents/rag/agent.py`: No direct instantiation of chunkers; delegates to tools.
  - No shadow logic found in routers or tasks.
- Final Statement: The RAG pipelines are fully unified. The legacy Supervisor path and the Lobe Chat endpoints execute identical logic for file processing, chunking, and retrieval.

## PART 6 — Post-AST-Fix Runtime Observations

The observations below come from a single curl-driven session after the AST chunking fix and are not static verifications. They are recorded for context only.

### 1. Ingestion & AST

From logs and status endpoints:

- AST chunking produced 15 chunks.
- Explicit log line: `AST chunking successful: 15 chunks (imports: 8, entities: 7)`.
- No fallback to text chunking occurred for the final run.
- Graph invalidation fired correctly.

This indicates the tree-sitter API usage and normalization fix are behaving as expected, and `CodeChunker` is the authoritative chunker on this run.

### 2. AST sanity query

Query: "Explain the ChangelogGenerator class".

Response:

- Returned the entire `ChangelogGenerator` class.
- Included constructor and main `generate()` flow.
- Clean, contiguous code.
- No mid-line slicing.
- No text-chunk noise.

### 3. Dependency query

Query: "How does changelog generation fetch commits from GitHub?"

Result:

- `_fetch_commits()` returned first.
- `ChangelogGenerator.generate()` also present.
- Imports and docstrings also surfaced.

`_fetch_commits` would not rank highly on vector similarity alone for that query, so its presence indicates the graph-expansion path is active: anchor found (`generate`), dependency traversed, candidate injected before reranking, reranker allowed it through.

### 4. Workflow query

Query: "Walk through the full flow of changelog generation step by step".

- Correct functions are present.
- However: repeated chunks, multiple copies of the same file, and formatting helpers diluting signal.

This is a ranking and grouping characteristic, not a correctness defect of the retrieval kernel.

### 5. Diagnosis

- Phase 1 observations met: ingestion produces correct chunk boundaries; dependency expansion fires.
- Phase 2 observations open: cross-file de-duplication, structural grouping, and narrative ordering for LLM consumption.

### 6. Forward-looking notes (not part of the verification)

- Deduplicate by qualified ID (source + name) as a post-rerank cleanup step rather than at retrieval time.
- Add `role` metadata to chunks (`entry`, `dependency`, `helper`, `formatting`) alongside the existing `is_graph_expansion` flag.
- For workflow questions, order context semantically: entry function, external calls, processing, output.

`ChangelogGenerator` and `_fetch_commits` referenced above are real symbols in `src/tools/changelog.py`.

## PART 7 — Graph Expansion Provenance Verification (v1.1.0)

**Date:** 2026-05-19 **Branch:** rag_resolve

### What was added

Three previously doc-only fields are now implemented end-to-end:

| Field | Location | Description |
|-------|----------|-------------|
| `ChunkResult.expanded_from` | `src/storage/base_store.py` | Anchor QID set on BFS-expanded chunk results |
| `ChatFileChunk.is_graph_expansion` | `src/api/schemas/rag.py` | Propagated to API response |
| `ChatFileChunk.expanded_from` | `src/api/schemas/rag.py` | Propagated to API response |
| `SemanticSearchResponse.expansion_count` | `src/api/schemas/rag.py` | Total expanded chunks in response |

### Implementation path verified

1. `_expand_with_graph_context()` (`agent.py`) — sets `"is_graph_expansion": True` and `"expanded_from": qid` on each BFS-expanded chunk dict
2. `retrieve_with_reranking()` (`agent.py`) — `ChunkResult(expanded_from=r.get("expanded_from"), ...)` conversion preserves the field
3. `semantic_search_for_chat()` (`routers/rag.py`) — extracts `is_graph = bool(doc.get("is_graph_expansion", False))` and `expanded_from = doc.get("expanded_from")`, passes both to `ChatFileChunk` constructor
4. Response builder computes `expansion_count = sum(1 for c in response_chunks if c.is_graph_expansion)`

### Test coverage

8 unit tests in `tests/test_rag_graph_expansion.py` (all passing 2026-05-19):
- `test_chunk_result_has_expanded_from`
- `test_chunk_result_expanded_from_set`
- `test_expand_with_graph_context_sets_expanded_from` (async, mocked CodeGraph + vector store)
- `test_chat_file_chunk_has_graph_fields`
- `test_chat_file_chunk_graph_fields_set`
- `test_semantic_search_response_has_expansion_count`
- `test_chat_file_chunk_serialization_includes_graph_fields`
- `test_semantic_search_response_expansion_count_counts_expanded`

### Live endpoint verification

Live curl test 2026-05-19 against running Docker stack confirmed:
- `is_graph_expansion: false`, `expanded_from: null` present on all chunks for a single-function Python file (expected — no cross-function call edges → BFS returns `[]`)
- `expansion_count: 0` returned correctly at response level
- Fields are present in response JSON for all chunks; no serialization errors

### Re-verify commands

```bash
# Confirm fields exist in models
grep -n "expanded_from\|is_graph_expansion\|expansion_count" \
  src/storage/base_store.py src/api/schemas/rag.py

# Confirm expander sets the field
grep -n "expanded_from" src/agents/rag/agent.py

# Confirm router wires it
grep -n "is_graph\|expanded_from\|expansion_count" src/api/routers/rag.py

# Run the graph expansion test suite
pytest tests/test_rag_graph_expansion.py -v
```

---

## How to re-verify

The checks below are the exact commands used to produce this report. Run them from the repo root.

```bash
# 1. Confirm chunker authority — should only show src/tools/rag/tools.py
#    and src/agents/rag/chunking/* (definitions).
grep -rn "CodeChunker\|TextChunker\|RecursiveCharacterTextSplitter" src/

# 2. Locate the verified symbols (line numbers will drift; symbols will not):
grep -n "def ingest_document\|def retrieve_with_reranking\|def _vector_search\|def retrieve_node\|def upload_files\|def semantic_search_for_chat" \
  src/agents/rag/agent.py src/api/routers/rag.py

# 3. Confirm tools.retrieve_docs is a shim that delegates back to the agent.
grep -n "def retrieve_docs\|get_rag_agent\|retrieve_with_reranking" src/tools/rag/tools.py

# 4. Confirm _vector_search calls the BaseVectorStore abstraction.
grep -n "self.vector_store.search" src/agents/rag/agent.py

# 5. Confirm the ingestion task chain.
grep -n "async_ingest_documents\|ingest_document" \
  src/api/routers/rag.py src/workers/rag_tasks.py src/agents/rag/agent.py

# 6. Run the RAG test suite.
pytest tests/test_rag.py -v

# 7. Run the graph expansion provenance test suite.
pytest tests/test_rag_graph_expansion.py -v
```
