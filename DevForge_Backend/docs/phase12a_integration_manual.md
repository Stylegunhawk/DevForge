# Phase 12A Integration Code for RAGAgent.retrieve_with_reranking()

## Insert this code at line 787 (after the debug log, before legacy cache check)

```python
# ========================================
# PHASE 12A: Query Intelligence Pipeline
# ========================================

# Step 1: Intent Classification
intent = "general"  # default
if self._intent_classifier and settings.ENABLE_INTENT_CLASSIFICATION:
    try:
        classification_result = await self._intent_classifier.classify(query)
        intent = classification_result.get("intent", "general")
        confidence = classification_result.get("confidence", 0.0)
        logger.info(f"[PHASE 12A] Intent: {intent} (confidence: {confidence:.2f})")
    except Exception as e:
        logger.warning(f"Intent classification failed: {e}, using default='general'")

# Step 2: Semantic Cache Check (intent-aware)
if use_cache and self._semantic_cache and settings.ENABLE_SEMANTIC_CACHE:
    try:
        cached_result = await self._semantic_cache.get(query, intent)
        if cached_result:
            logger.info(f"[PHASE 12A] ✅ SEMANTIC CACHE HIT (intent={intent})")
            return {
                **cached_result,
                "from_semantic_cache": True,
                "intent": intent,
                "cache_type": "semantic"
            }
        logger.debug(f"[PHASE 12A] Semantic cache miss (intent={intent})")
    except Exception as e:
        logger.warning(f"Semantic cache check failed: {e}")

# Step 3: Query Expansion (intent-aware)
expanded_queries = [query]  # default: just original query
if self._query_expander and settings.ENABLE_QUERY_EXPANSION:
    try:
        expansion_result = await self._query_expander.expand(query, intent)
        if expansion_result.get("success"):
            expanded_queries = expansion_result.get("expanded_queries", [query])
            logger.info(f"[PHASE 12A] Query expanded: {len(expanded_queries)} queries")
            for i, eq in enumerate(expanded_queries):
                logger.debug(f"  [{i}] {eq[:60]}...")
    except Exception as e:
        logger.warning(f"Query expansion failed: {e}, using original query only")

# Step 4:Multi-Query Retrieval + Fusion (for expanded queries)
if len(expanded_queries) > 1:
    # Retrieve for each expanded query
    from src.agents.rag.expansion import ResultFusion
    fusion = ResultFusion()
    
    all_results = []
    for eq in expanded_queries:
        eq_results = await self._vector_search(eq, top_k * 2)  # Get more for fusion
        all_results.append(eq_results)
    
    # Fuse results using RRF
    initial_results = fusion.fuse(all_results, top_k=initial_top_k)
    logger.info(f"[PHASE 12A] Fused {len(expanded_queries)} result sets → {len(initial_results)} docs")
else:
    # Single query - proceed with normal retrieval
    initial_results = None  # Will be retrieved in hybrid/vector section below

# ========================================
# End of Phase 12A Query Intelligence
# ========================================
```

## Changes Needed:

1. **Line 787**: Insert the above Phase 12A block
2. **Line 805-832**: Modify hybrid search logic to check if `initial_results is not None` first:

```python
# Phase 11.2 Day 3: Hybrid search (BM25 + Vector) or vector-only
if initial_results is None:  # <-- ADD THIS CHECK
    initial_top_k = settings.VECTOR_SEARCH_CANDIDATES if (use_reranking and settings.ENABLE_RERANKING) else top_k
    
    if use_hybrid and self._hybrid_retriever and settings.ENABLE_HYBRID_SEARCH:
        # ... existing hybrid search logic ...
    else:
        # Vector-only search
        initial_results = await self._vector_search(query, initial_top_k)
```

3. **Before returning final result**: Add semantic cache update:

```python
# Update semantic cache if enabled
if use_cache and self._semantic_cache and settings.ENABLE_SEMANTIC_CACHE:
    try:
        await self._semantic_cache.set(query, intent, result)
        logger.debug(f"[PHASE 12A] Cached result for intent={intent}")
    except Exception as e:
        logger.warning(f"Failed to cache result: {e}")

return result
```

## Manual Integration Steps:

1. Open `src/agents/rag/agent.py`
2. Go to line 787 (after the debug log)
3. Insert the Phase 12A pipeline code
4. Modify line 805 to add the `if initial_results is None:` check
5. Add semantic cache update before the final return statements (lines ~848, ~900)

This will activate Phase 12A query intelligence!
