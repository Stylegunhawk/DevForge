**RAG SYSTEM**

**SECURITY & ARCHITECTURE AUDIT REPORT**

**CONFIDENTIAL — FOR INTERNAL ENGINEERING USE ONLY**

| System | DevForge RAG Backend |
| --- | --- |
| Version | Phase 15 (Multi-Tenant) |
| Audit Date | February 2026 |
| Status | ⚠️ CRITICAL ISSUES FOUND |
| Risk Level | 🔴 HIGH — Cross-Tenant Data Leak Risk |
| Bugs Found | 5 Critical | 3 High | 6 Medium |

# 1\. Executive Summary

| ⚠️ CRITICAL FINDINGThe RAG Code Graph component was implemented in Phase 12A but was NOT updated during Phase 15 multi-tenant migration. All graph operations execute without tenant isolation, creating a high-severity cross-tenant data leakage vulnerability. Users can access code dependencies from other users through graph expansion. |
| --- |

A comprehensive audit of the DevForge RAG system graph component and its integration with the multi-tenant Phase 15 architecture revealed significant security and data integrity issues. This report documents all findings with file-level evidence and provides structured remediation guidance.

## 1.1 Severity Overview

| Severity | Description |
| --- | --- |
| 🔴 CRITICAL | 5 bugs — Cross-tenant data leak via graph, QID collision, missing SQL tenant filter |
| 🟠 HIGH | 3 bugs — Broken deletion lifecycle, BM25 shared state, semantic cache shared across tenants |
| 🟡 MEDIUM | 6 issues — Silent failures swallowing errors, Redis cache stale data, CodeChunker None crash risk |

## 1.2 Phase Connectivity Status

The Phase 12A Code Graph was isolated from the Phase 15 multi-tenant migration. While tenant isolation was correctly applied to the agent factory, retrieval pipeline, and vector store operations, the graph subsystem was left untouched, creating a systemic gap.

| Subsystem | Phase 15 Applied? | Risk |
| --- | --- | --- |
| RAGAgent Factory (get_rag_agent) | YES ✅ | None |
| Vector Store Search SQL | YES ✅ | None |
| Celery Ingestion Pipeline | YES ✅ | None |
| Code Graph (CodeGraph class) | NO ❌ | 🔴 CRITICAL |
| iter_chunk_metadata SQL | NO ❌ | 🔴 CRITICAL |
| QID Format | NO ❌ | 🔴 CRITICAL |
| BM25 Index | NO ❌ | 🟠 HIGH |
| Semantic Cache | PARTIAL ⚠️ | 🟠 HIGH |
| Deletion Lifecycle | NO ❌ | 🟠 HIGH |

# 2\. Tenant Isolation Audit

Every RAG component was traced for tenant\_id propagation from API entry point through to storage. The following table summarizes findings:

| Component | Tenant-Safe? | Evidence (File:Line) |
| --- | --- | --- |
| Graph initialization | ❌ NO | agent.py:450 — CodeGraph() called with no tenant_id |
| iter_chunk_metadata SQL (PgVector) | ❌ NO | pgvector_store.py:248 — SELECT metadata FROM table ORDER BY created_at (no WHERE clause) |
| iter_chunk_metadata (ChromaDB) | ❌ NO | chroma_store.py:202 — No tenant/collection filter applied |
| QID Format | ❌ NO | code_graph.py:85 — qid = f"{source}::{name}" — no tenant prefix |
| get_related() | ❌ NO | code_graph.py:102 — Signature has no tenant_id parameter |
| get_chunk_by_qualified_id (PgVector) | ❌ NO | pgvector_store.py:223 — WHERE source=$1 AND name=$2, no tenant filter |
| get_chunk_by_qualified_id (Chroma) | ❌ NO | chroma_store.py:168 — where={source, name} only, no tenant filter |
| RAGAgent Factory | ✅ YES | agent.py:227 — get_rag_agent(tenant_id, collection_name) creates per-tenant instances |
| BM25 Index | ❌ NO | bm25_index.py:53 — build() reads ALL metadata without tenant filter |
| Semantic Cache | ✅ YES | semantic_cache.py:80 — Per-intent isolation via max_size_per_intent |

# 3\. Critical Bugs (Runtime Failures)

The following bugs will cause runtime failures or security violations in production. All have been verified with exact file and line number evidence.

## 3.1. Graph Rebuilds From ALL Tenants Data

| Severity | 🔴 CRITICAL — Cross-Tenant Data Leakage |
| --- | --- |
| File | src/storage/pgvector_store.py:248 |
| Impact | Graph contains code from ALL tenants. Tenant A can see Tenant B's code dependencies, function calls, and file structure through graph expansion queries. |
| Trigger | Any graph rebuild — triggered on agent first access or Redis cache miss. |

### Vulnerable Code

| async with conn.transaction():cursor = await conn.cursor(f"SELECT metadata FROM {self.table_name} ORDER BY created_at") # ← NO WHERE tenant_id filter!# FIX REQUIRED:cursor = await conn.cursor(f"SELECT metadata FROM {self.table_name}WHERE tenant_id = $1 AND collection_name = $2ORDER BY created_at",tenant_id, collection_name) |
| --- |

### Remediation

Add tenant\_id and collection\_name parameters to iter\_chunk\_metadata() in BaseVectorStore, PgVectorStore, and ChromaVectorStore. Update the SQL WHERE clause and all call sites.

## 3.2. QID Format Excludes Tenant ID — Collision Risk

| Severity | 🔴 CRITICAL — Cross-Tenant Graph Node Collision |
| --- | --- |
| File | src/agents/rag/graph/code_graph.py:85 |
| Impact | Two tenants with identically named files produce identical QIDs. Graph edges created for Tenant A may resolve to Tenant B's code during graph expansion, causing incorrect and potentially sensitive results. |
| Trigger | Any graph node addition via add_chunks_batch() when multiple tenants have files with the same name. |

### Vulnerable Code

| # CURRENT (BROKEN):qid = f"{source}::{name}"# e.g., "auth.py::validate_user"# PROBLEM: Tenant A and Tenant B both have auth.py# Both produce QID: "auth.py::validate_user"# Graph edges span tenants incorrectly# FIX REQUIRED:qid = f"{tenant_id}::{source}::{name}"# e.g., "user_abc123::auth.py::validate_user" |
| --- |

### Remediation

Prefix QID with tenant\_id. Update QID format throughout: add\_chunks\_batch(), get\_related(), get\_chunk\_by\_qualified\_id(), and graph serialization/Redis cache. All existing cached graphs must be invalidated.

## 3.3. get\_chunk\_by\_qualified\_id Has No Tenant Filter

| Severity | 🔴 CRITICAL — Direct Cross-Tenant Data Access |
| --- | --- |
| File | src/storage/pgvector_store.py:223 |
| Impact | Graph expansion can return code chunks from ANY tenant when resolving a QID. Tenant A's graph traversal may fetch Tenant B's actual source code content and return it in the context sent to the LLM. |
| Trigger | Any retrieval with ENABLE_CODE_GRAPH=True where graph expansion finds a related QID and fetches its content. |

### Vulnerable Code

| # CURRENT (BROKEN):query = f"""SELECT chunk_id, content, metadataFROM {self.table_name}WHERE metadata->>'source' = $1AND metadata->>'name' = $2LIMIT 1;""" # ← Returns ANY tenant's chunk matching this QID!# FIX REQUIRED:WHERE metadata->>'source' = $1AND metadata->>'name' = $2AND tenant_id = $3AND collection_name = $4 |
| --- |

### Remediation

Add tenant\_id and collection\_name parameters to get\_chunk\_by\_qualified\_id() in both PgVectorStore and ChromaVectorStore. Update BaseVectorStore abstract method signature.

## 3.4. CodeGraph.add\_chunks\_batch() Ignores Tenant Metadata

| Severity | 🔴 CRITICAL — Tenant Context Ignored During Build |
| --- | --- |
| File | src/agents/rag/graph/code_graph.py:71-92 |
| Impact | Even though tenant_id is stored in chunk metadata (correctly set in Phase 15), it is completely ignored when building the graph. The graph has zero tenant context despite the data being available. |
| Trigger | Graph rebuild from vector store metadata — called during init_graph(). |

### Vulnerable Code

| def add_chunks_batch(self, chunks: List[Dict]) -> None:for chunk in chunks:metadata = chunk.get("metadata", {})source = metadata.get("source", "")name = metadata.get("name", "")# tenant_id IS in metadata but NEVER READtenant_id = metadata.get("tenant_id") # ← IGNOREDqid = f"{source}::{name}" # ← No tenant prefix# FIX REQUIRED:tenant_id = metadata.get("tenant_id", "default")qid = f"{tenant_id}::{source}::{name}" |
| --- |

### Remediation

Extract tenant\_id from metadata in add\_chunks\_batch() and include it in QID construction. This is a prerequisite fix before Bug 3.2 can be fully resolved.

## 3.5. BM25 Index Shared Across All Tenants

| Severity | 🔴 CRITICAL — BM25 Hybrid Search Has No Tenant Isolation |
| --- | --- |
| File | src/agents/rag/retrieval/bm25_index.py:53 |
| Impact | BM25 hybrid search is contaminated with all tenants' document corpus. With HYBRID_ALPHA=0.5, 50% of retrieval results can include content from other tenants, bypassing vector store tenant isolation. |
| Trigger | Any retrieval with ENABLE_HYBRID_SEARCH=True — currently enabled by default. |

### Vulnerable Code

| # build() reads ALL metadata — no tenant filter:async def build(self, vector_store, batch_size=500):async for batch in vector_store.iter_chunk_metadata(batch_size=batch_size): # ← iter_chunk_metadata reads ALL tenantsself._add_batch(batch)# BM25 index then shared in hybrid retrieval:# HYBRID_ALPHA = 0.5 means 50% BM25 results# BM25 returns ALL tenant results, polluting hybrid search |
| --- |

### Remediation

Pass tenant\_id and collection\_name to BM25Index.build(). Implement per-tenant BM25 index storage, or build BM25 index from tenant-filtered iter\_chunk\_metadata() results.

# 4\. High Severity Issues

## 4.1 Broken Deletion Lifecycle

When a file is deleted, only the vector store rows are removed. The following components are NOT cleaned up:

| Component | Cleaned on Delete? | Impact |
| --- | --- | --- |
| Vector Store (PgVector/Chroma) | YES ✅ | Rows correctly removed |
| Code Graph Cache | PARTIAL ⚠️ | agent._code_graph = None invalidates; but Redis cache may still hold stale graph with deleted file |
| BM25 Index | NO ❌ | Deleted file's tokens remain in BM25 corpus forever until restart |
| Semantic Cache | NO ❌ | Cached results containing deleted file chunks continue to be returned |
| Exact Query Cache (Redis) | NO ❌ | Only TTL-based expiry. Stale results served until TTL expires (default: 3600s) |

## 4.2 Boost Applied After Reranking

**File:** src/agents/rag/agent.py:868-889

| # CURRENT (WRONG ORDER):reranked = await self.reranker.rerank(query, chunk_candidates, top_k=top_k*2)boosted = self.reranker.apply_code_boost(reranked) # ← Applied AFTER reranking# CrossEncoder produces calibrated scores. Multiplying by 1.2x after# reranking corrupts those scores and can surface less-relevant chunks.# FIX: Apply boost BEFORE rerankingpre_boosted = self._apply_initial_boost(candidates) # ← Before rerankerreranked = await self.reranker.rerank(query, pre_boosted, top_k=top_k*2) |
| --- |

## 4.3 retrieve\_with\_reranking Missing tenant\_id

**File:** src/api/routers/rag.py:119

| # CURRENT:result = await agent.retrieve_with_reranking(query=query,top_k=request.top_k,use_reranking=True# ← tenant_id NOT passed here)# Graph expansion therefore has no tenant context# when calling _expand_with_graph_context(anchors) |
| --- |

# 5\. Silent Failures & Medium Issues

| Location | Handler | Risk |
| --- | --- | --- |
| agent.py:431 | except Exception — Graph cache load | Falls back to rebuild silently; hides Redis errors |
| agent.py:469 | except Exception — Graph rebuild | Returns empty graph; user gets no RAG context with no error |
| code_graph.py:36 | logger.warning() — Invalid QID | Malformed nodes silently skipped; graph gaps undetected |
| query_cache.py:74 | except Exception — Redis get | Falls back to memory cache; hides Redis connectivity issues |
| semantic_cache.py:104 | except Exception — Embedding | Returns None; semantic cache disabled without notification |
| pgvector_store.py:236 | finally: conn.close() | Correct. Protects against connection leak. |

## 5.1 Redis Graph Cache Stale After Delete

The Redis cache key for the graph is f"rag\_graph:{self.collection\_name}" (agent.py:430). When a file is deleted, agent.\_code\_graph = None correctly clears the in-memory graph, but the Redis-serialized graph is NOT deleted. The next request loads the stale Redis graph, which still contains the deleted file's nodes and edges.

| # agent.py:430cache_key = f"rag_graph:{self.collection_name}"# Delete handler (rag.py:263):agent._code_graph = None # Clears memory only# Redis key "rag_graph:user_abc123" still has stale graph!# FIX: Also delete Redis key on file deletionawait redis_client.delete(f"rag_graph:{collection_name}") |
| --- |

# 6\. Remediation Plan

Fixes are ordered by severity and dependency. Bugs 6.1–6.3 must be fixed before 6.4–6.5 as they share dependent components.

| # | Fix | File | Est. Time | Dependency |
| --- | --- | --- | --- | --- |
| 1 | Add tenant filter to iter_chunk_metadata() SQL | pgvector_store.py:248 chroma_store.py:202 | 1 hr | None — fix first |
| 2 | Add tenant_id prefix to QID format | code_graph.py:85 | 2 hrs | Requires Fix 1 |
| 3 | Add tenant filter to get_chunk_by_qualified_id() | pgvector_store.py:223 chroma_store.py:168 | 1 hr | None |
| 4 | Read tenant_id in add_chunks_batch() | code_graph.py:71 | 30 min | Requires Fix 1 & 2 |
| 5 | Fix BM25 tenant isolation | bm25_index.py:53 | 2 hrs | Requires Fix 1 |
| 6 | Fix deletion lifecycle | rag.py delete endpoint | 2 hrs | Requires Fix 1 & 5 |
| 7 | Delete Redis graph key on file delete | rag.py:263 | 30 min | Requires Fix 6 |
| 8 | Move code boost before reranking | agent.py:868 | 30 min | None |
| 9 | Pass tenant_id to retrieve_with_reranking | rag.py:119 | 1 hr | None |
| 10 | Invalidate Redis graph cache on delete | rag.py delete endpoint | 30 min | Requires Fix 7 |

## 6.1 Recommended Fix Order

| Phase | Actions |
| --- | --- |
| Phase A (Security — Do First) | Fix iter_chunk_metadata SQL (Bug 3.1) Fix QID format with tenant prefix (Bug 3.2) Fix get_chunk_by_qualified_id tenant filter (Bug 3.3) Invalidate all existing Redis graph caches |
| Phase B (Data Integrity) | Fix add_chunks_batch tenant read (Bug 3.4) Fix BM25 tenant isolation (Bug 3.5) Implement coordinated deletion lifecycle (Issue 4.1) |
| Phase C (Quality) | Move boost before reranking (Issue 4.2) Pass tenant_id to retrieve_with_reranking (Issue 4.3) Add structured logging for silent failures (Section 5) |

## 6.2 Minimum Viable Fix (Emergency Patch)

If an emergency patch is needed immediately before full remediation, disable the code graph to eliminate the cross-tenant leak:

| # .env — Emergency patch to prevent data leakENABLE_CODE_GRAPH=FalseENABLE_HYBRID_SEARCH=False# This disables graph expansion and BM25 hybrid search.# RAG continues to function via pure vector search.# Zero cross-tenant risk until proper fixes are deployed. |
| --- |

# 7\. Appendix: File Reference

| File | Role in Audit |
| --- | --- |
| src/agents/rag/agent.py | RAGAgent — graph init, retrieval pipeline, Phase 12A + 15 |
| src/agents/rag/graph/code_graph.py | CodeGraph — QID construction, graph traversal |
| src/storage/pgvector_store.py | PgVectorStore — SQL queries, tenant filtering |
| src/storage/chroma_store.py | ChromaVectorStore — Chroma queries, tenant filtering |
| src/agents/rag/retrieval/bm25_index.py | BM25Index — Hybrid search, shared state |
| src/agents/rag/cache/semantic_cache.py | SemanticCache — Intent-keyed in-memory cache |
| src/agents/rag/cache/query_cache.py | QueryCache — Redis-backed exact match cache |
| src/api/routers/rag.py | RAG API — Upload, search, delete endpoints |
| src/workers/tasks/rag_tasks.py | Celery tasks — Async ingestion pipeline |
| src/agents/rag/chunking/code_chunker.py | CodeChunker — AST-based code chunking |