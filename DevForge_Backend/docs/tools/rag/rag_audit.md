 RAG Orchestration Audit: Production-Grade Analysis

📊 Your Current Pipeline
Query Input
    ↓
1. Intent Classification
    ↓
2. Semantic Cache Check
    ↓
3. Query Expansion
    ↓
4. Exact Cache Check
    ↓
5. Multi-Query Retrieval (if expanded)
    ↓
6. Hybrid Search (BM25 + Vector)
    ↓
7. Graph Context Expansion
    ↓
8. Reranking (CrossEncoder)
    ↓
9. Score Boosting (code-aware)
    ↓
10. Result Formatting
This is ambitious. Let's audit each stage.

🚨 Flaw 1: Intent Classifier Upstream of Everything
What's happening:
python# Step 1 gates EVERYTHING
intent = await self._intent_classifier.classify(query)

# Then semantic cache uses intent
cached = await self._semantic_cache.get(query, intent)

# Then expansion uses intent
expanded = await self._query_expander.expand(query, intent)
```

### **The Flaw:**
```
If intent classification is wrong:
├─ Wrong cache bucket → Cache miss (always)
├─ Wrong expansion strategy → Bad queries
├─ Wrong retrieval path → Bad results
└─ LLM gets irrelevant context

One wrong classification = entire pipeline corrupted
```

### **Production Reality:**
```
Intent classifiers fail on:
- Ambiguous queries ("explain this")
- Multi-intent ("summarize auth.py and create a github issue")
- Domain-specific jargon
- Short queries (<5 words)

Failure rate: ~15-25% in production
Fix: Intent as Hint, Not Gate
python# ❌ CURRENT: Intent gates everything
intent = await classify(query)
cache_result = await cache.get(query, intent)  # Intent is key

# ✅ CORRECT: Intent enriches, doesn't gate
intent = await classify(query)  # Can be "general" if uncertain

# Cache key = query ONLY (intent is metadata)
cache_result = await cache.get(query)

# Intent used as soft signal
retrieval_config = {
    "top_k": 10 if intent == "complex" else 5,
    "use_hybrid": intent in ["code", "technical"],
    "expand": intent not in ["simple", "factual"]
}

🚨 Flaw 2: Two Cache Layers Conflicting
What's happening:
python# Cache Layer 1: Semantic Cache (embedding similarity)
cached = await self._semantic_cache.get(query, intent)
if cached: return cached

# Cache Layer 2: Exact Match Cache (hash)
cache_key = cache_key_from_query(query, top_k)
cached = await self._query_cache.get(cache_key)
if cached: return cached
```

### **The Flaw:**
```
Two caches = two sources of truth

Problems:
1. Cache invalidation doubles in complexity
   - File deleted → must invalidate BOTH caches
   - Currently: Only one might be invalidated

2. Semantic cache uses intent as dimension
   - Same query, different intent = cache miss
   - "summarize auth.py" (code intent) ≠ 
     "summarize auth.py" (general intent)
   - Effectively broken cache

3. Order matters but is fragile
   - Semantic hit → return (skip exact)
   - Exact hit → return (skip semantic)
   - Miss → run full pipeline
   - What if semantic returns stale results?
Fix: Single Cache Layer
python# ✅ PRODUCTION PATTERN
class UnifiedCache:
    """Single cache, multiple lookup strategies"""
    
    async def get(self, query: str, top_k: int) -> Optional[dict]:
        # Strategy 1: Exact match (fastest)
        exact_key = self._hash(query, top_k)
        result = await self.redis.get(exact_key)
        if result:
            return json.loads(result)
        
        # Strategy 2: Semantic similarity (approximate)
        query_vec = await self.embed(query)
        similar = await self._find_similar_cached(query_vec, threshold=0.95)
        if similar:
            return similar
        
        return None
    
    async def invalidate_for_file(self, filename: str):
        """Single invalidation point"""
        # Delete all cache entries containing this file's chunks
        await self._delete_by_source(filename)

🚨 Flaw 3: Query Expansion Creates Noise
What's happening:
python# Expand 1 query into N queries
expanded_queries = await self._query_expander.expand(query, intent)
# e.g., ["auth.py", "authentication logic", "user login", "JWT validation"]

# Retrieve for EACH expanded query
for q in expanded_queries:
    results = await vector_search(q, top_k=initial_top_k)
    all_results.extend(results)

# Fuse results
final = reciprocal_rank_fusion(all_results)
```

### **The Flaw:**
```
Problem 1: Expansion hallucination
Query: "how does auth work?"
Expanded: ["OAuth implementation", "JWT tokens", "session management", 
           "database authentication", "bcrypt hashing"]

If your codebase uses simple API keys:
→ All expanded queries miss
→ Original query would have hit
→ RRF fusion dilutes correct results

Problem 2: top_k multiplication
initial_top_k = 30 (VECTOR_SEARCH_CANDIDATES)
expanded_queries = 4

Total retrieved: 120 chunks
After dedup: ~60 unique chunks
Reranker processes: 60 chunks → Very slow

Problem 3: Expansion LLM can contradict rewriter
+server.ts: Query rewriter runs on frontend
agent.py: Query expander runs on backend

Same query rewritten TWICE with different prompts
= Inconsistent retrieval signals
Fix: Conditional Expansion
python# ✅ CORRECT
async def retrieve(self, query: str, top_k: int):
    
    # Only expand if query is genuinely ambiguous
    should_expand = (
        len(query.split()) < 5 and      # Short = ambiguous
        not has_filename(query) and      # Specific = don't expand
        intent not in ["factual", "specific"]
    )
    
    if should_expand:
        expanded = await self._query_expander.expand(query)
        # Cap at 2 expansions max
        queries = [query] + expanded[:2]
        initial_top_k = top_k * 2  # Not 30
    else:
        queries = [query]
        initial_top_k = top_k
    
    # Retrieve
    results = await self._multi_query_retrieve(queries, initial_top_k)
    return results

🚨 Flaw 4: BM25 Index Built At Startup
What's happening:
python# On startup:
async def init_bm25(self):
    await self._bm25_index.build(
        self.vector_store,
        batch_size=settings.BM25_INDEX_BATCH_SIZE
    )
```

### **The Flaw:**
```
Problem 1: Stale index
User uploads file → Ingested to pgvector ✅
BM25 index → NOT updated (only rebuilt on restart)

Result: BM25 misses new documents
Hybrid search = 50% vector + 50% wrong BM25
= Worse than pure vector search

Problem 2: Startup latency
500 chunks × embed + BM25 build = 30-60 seconds
App unusable during startup

Problem 3: Memory pressure
BM25 index held in memory
500 chunks × avg 200 tokens = ~100MB RAM
No memory limit on containers
Fix: Incremental BM25 Updates
python# ✅ CORRECT
class BM25Index:
    async def add_documents(self, new_chunks: List[str]):
        """Incremental update - called after each ingestion"""
        self._corpus.extend(new_chunks)
        await self._rebuild()  # Fast: only new docs
    
    async def remove_documents(self, source: str):
        """Remove when file deleted"""
        self._corpus = [c for c in self._corpus 
                       if c.metadata["source"] != source]
        await self._rebuild()

# In ingestion pipeline:
async def ingest_document(self, ...):
    chunks = await chunk_document(file)
    await self.vector_store.add_chunks(chunks, embeddings)
    
    # Update BM25 immediately
    await self._bm25_index.add_documents(
        [c["content"] for c in chunks]
    )

🚨 Flaw 5: Reranking ALL 30 Candidates
What's happening:
pythonVECTOR_SEARCH_CANDIDATES = 30  # Retrieve 30

# Rerank all 30 with CrossEncoder
reranked = await self._reranker.rerank(query, initial_results[:30])
```

### **The Flaw:**
```
CrossEncoder reranking complexity:
- Must run query × each_chunk through neural network
- 30 candidates × ~200 tokens = 6000 token pairs
- Time: ~300-500ms on CPU (local setup)

But:
- Candidates 20-30 are almost always irrelevant
- Reranking junk doesn't improve quality
- Just wastes time

Production systems rerank top 10-15, not 30
Fix: Pre-filter Before Reranking
python# ✅ CORRECT
async def retrieve_with_reranking(self, query: str, top_k: int):
    
    # Retrieve more candidates
    candidates = await self._vector_search(
        query, 
        top_k=15,           # Not 30
        score_threshold=0.5  # Pre-filter low quality
    )
    
    # Only rerank if we have enough candidates
    if len(candidates) <= top_k:
        return candidates   # Skip reranking overhead
    
    # Rerank filtered set
    reranked = await self._reranker.rerank(query, candidates)
    
    # Return top_k
    return reranked[:top_k]

🚨 Flaw 6: Code Graph Not Invalidated on File Delete
What's happening:
python# File deleted:
await vector_store.delete_by_source(source, tenant_id)
# ↑ Removes vectors ✅

# But code graph:
# Graph still has references to deleted file
# graph.get_related(qid) returns dead references
```

### **The Flaw:**
```
Code graph stores relationships:
auth.py → imports → utils.py
auth.py → calls → database.py

When auth.py deleted:
- Vectors: Removed ✅
- BM25: Not updated ❌
- Code graph: Still has auth.py nodes ❌

Result:
1. Graph expansion returns dead chunk IDs
2. get_chunk_by_qualified_id() returns None
3. Silent failure (chunk just missing from results)
4. Or worse: KeyError crash
Fix: Coordinated Cleanup
python# ✅ CORRECT: Single deletion coordinator
async def delete_file(
    self, 
    source: str, 
    tenant_id: str,
    collection_name: str
):
    """Coordinated cleanup across all components"""
    
    results = await asyncio.gather(
        # 1. Delete vectors
        self.vector_store.delete_by_source(source, tenant_id),
        
        # 2. Update BM25
        self._bm25_index.remove_documents(source),
        
        # 3. Invalidate caches
        self._query_cache.invalidate_by_source(source),
        self._semantic_cache.invalidate_by_source(source),
        
        return_exceptions=True  # Don't fail if one component errors
    )
    
    # 4. Update code graph (after vector deletion)
    if self.code_graph:
        await self.code_graph.remove_file(source)
    
    logger.info(f"[RAG] Coordinated deletion: {source}, results: {results}")
    return results

🚨 Flaw 7: Score Boosting After Reranking
What's happening:
python# AFTER CrossEncoder reranking:
boosted = apply_code_aware_boosting(reranked_chunks)

# Boost factors:
BOOST_FUNCTION = 1.2
BOOST_CLASS = 1.15
BOOST_TEXT = 0.95
```

### **The Flaw:**
```
CrossEncoder reranking is already semantic + code-aware
It reads the actual content to score relevance

Multiplying its output by arbitrary factors:
1. Breaks calibrated scores
2. Can surface less relevant chunks
3. Defeats purpose of expensive reranking

Example:
CrossEncoder score: function=0.7, class=0.8
After boost:        function=0.84, class=0.92

But class was already MORE relevant (0.8 > 0.7)
Boost just amplifies the difference arbitrarily
Fix: Boost BEFORE Reranking
python# ✅ CORRECT: Boost vector scores, then rerank
async def retrieve_with_reranking(self, query: str, top_k: int):
    
    # 1. Vector search
    candidates = await self._vector_search(query, top_k=15)
    
    # 2. Apply lightweight boost to initial scores
    #    (helps reranker see better candidates)
    boosted_candidates = self._apply_initial_boost(candidates)
    
    # 3. Reranker makes FINAL decision
    #    Don't touch scores after this
    reranked = await self._reranker.rerank(query, boosted_candidates)
    
    return reranked[:top_k]

📊 Orchestration Flaw Summary
FlawSeverityImpactFix ComplexityIntent gates pipeline🔴 CriticalWrong results 15-25%MediumDual cache conflict🔴 CriticalStale/missed resultsMediumQuery expansion noise🔴 HighDiluted resultsLowBM25 stale after upload🔴 HighHybrid search brokenMediumReranking 30 candidates🟡 MediumSlow + low ROILowGraph not invalidated🟡 MediumDead referencesMediumBoost after reranking🟡 MediumScore corruptionLow

✅ Production-Grade Orchestration
pythonasync def retrieve(self, query: str, top_k: int, tenant_id: str):
    
    # ============================================
    # STAGE 1: CACHE (Fast path)
    # ============================================
    cached = await self.cache.get(query, top_k)
    if cached:
        return cached

    # ============================================
    # STAGE 2: QUERY PREPARATION
    # ============================================
    # Intent as hint only (not gate)
    intent = await self._classify_intent(query)
    
    # Conditional expansion
    queries = [query]
    if self._should_expand(query, intent):
        expanded = await self._expand(query, intent)
        queries.extend(expanded[:2])  # Max 2 expansions

    # ============================================
    # STAGE 3: RETRIEVAL
    # ============================================
    # Pre-filter with threshold
    candidates = await self._retrieve_multi_query(
        queries, 
        top_k=15,
        score_threshold=0.5  # Filter noise early
    )

    # ============================================
    # STAGE 4: HYBRID FUSION (if BM25 ready)
    # ============================================
    if self._bm25_index.is_ready():
        bm25_results = await self._bm25_search(query)
        candidates = reciprocal_rank_fusion(
            [candidates, bm25_results]
        )[:15]  # Still cap at 15

    # ============================================
    # STAGE 5: RERANKING (Final authority)
    # ============================================
    if len(candidates) > top_k:
        # Boost BEFORE reranking
        candidates = self._apply_code_boost(candidates)
        reranked = await self._reranker.rerank(query, candidates)
        final = reranked[:top_k]
    else:
        final = candidates

    # ============================================
    # STAGE 6: GRAPH EXPANSION (Additive only)
    # ============================================
    if settings.ENABLE_CODE_GRAPH:
        related = await self._expand_graph(final)
        # Add related chunks WITHOUT displacing top results
        final = final + [r for r in related 
                        if r not in final][:2]

    # ============================================
    # STAGE 7: CACHE + RETURN
    # ============================================
    await self.cache.set(query, top_k, final)
    return final[:top_k]

🚦 Implementation Priority
Fix This Week:

✅ Single cache layer (unify dual cache)
✅ BM25 incremental updates (fix stale index)
✅ Coordinated file deletion (fix dead graph refs)
✅ Move boost before reranking (fix score corruption)

Fix Next Week:

Intent as hint not gate
Conditional expansion (not always)
Pre-filter candidates before reranking (top 15 not 30)

Validate:

After each fix, measure retrieval precision
Use a test set of known queries + expected files
Track: chunks_returned, relevant_chunks, precision@5


🎯 One-Line Summary Per Flaw

Intent classifier - Gates pipeline it shouldn't control
Dual cache - Two sources of truth = stale results
Query expansion - Expands always when it should expand sometimes
BM25 stale - Never updated after file upload
Rerank 30 - Expensive and low ROI past top 15
Graph invalidation - Dead references on file delete
Boost after rerank - Corrupts calibrated scores

Fix these 7 flaws = production-competitive RAG. 🚀
