"""Result fusion for multi-query expansion.

Combines results from multiple query variations using:
- Reciprocal Rank Fusion (RRF)
- Deduplication by qualified_id
- Diversity-aware ranking
"""

import logging
from typing import List, Dict
from collections import defaultdict

logger = logging.getLogger(__name__)


def fuse_results_rrf(
    results_per_query: List[List],
    k: int = 60,
    weights: List[float] = None
) -> List:
    """
    Fuse results from multiple queries using Reciprocal Rank Fusion.
    
    Algorithm:
        RRF_score(doc) = Σ weight_i * (1 / (k + rank_i))
    
    Args:
        results_per_query: List of result lists (one per query variation)
        k: RRF constant (default 60, from literature)
        weights: Optional weights per query (default: equal weights)
    
    Returns:
        Fused and deduplicated result list
    """
    if not results_per_query:
        return []
    
    # Default to equal weights
    if weights is None:
        weights = [1.0] * len(results_per_query)
    
    # Deduplication tracking
    doc_scores = defaultdict(float)
    doc_objects = {}  # Store first occurrence of each doc
    
    # Process each query's results
    for query_idx, results in enumerate(results_per_query):
        weight = weights[query_idx]
        
        for rank, doc in enumerate(results):
            # Get document ID (qualified_id or id)
            doc_id = getattr(doc, 'qualified_id', None) or getattr(doc, 'id', str(rank))
            
            # RRF score contribution
            rrf_score = weight * (1.0 / (k + rank))
            doc_scores[doc_id] += rrf_score
            
            # Store first occurrence
            if doc_id not in doc_objects:
                doc_objects[doc_id] = doc
    
    # Sort by fused score (descending)
    sorted_docs = sorted(
        doc_objects.items(),
        key=lambda x: doc_scores[x[0]],
        reverse=True
    )
    
    # Extract deduplicated documents
    fused = [doc for doc_id, doc in sorted_docs]
    
    logger.debug(
        f"RRF fusion: {sum(len(r) for r in results_per_query)} total → "
        f"{len(fused)} unique (k={k})"
    )
    
    return fused


def fuse_results_weighted(
    results_per_query: List[List],
    weights: List[float]
) -> List:
    """
    Weighted fusion (simpler than RRF).
    
    First query gets highest weight, subsequent queries contribute less.
    
    Args:
        results_per_query: List of result lists
        weights: Weight per query (e.g., [0.5, 0.2, 0.15, 0.15])
    
    Returns:
        Fused result list
    """
    return fuse_results_rrf(results_per_query, k=60, weights=weights)


def calculate_diversity(results: List, top_k: int = 10) -> float:
    """
    Calculate diversity score for result set.
    
    Measures how diverse the top-k results are (by content similarity).
    Higher score = more diverse results.
    
    Args:
        results: Result list
        top_k: Number of results to analyze
    
    Returns:
        Diversity score [0, 1]
    """
    if len(results) < 2:
        return 1.0  # Perfect diversity (no duplicates possible)
    
    # Simple diversity: unique qualified_ids / total
    top_results = results[:top_k]
    unique_ids = set()
    
    for doc in top_results:
        doc_id = getattr(doc, 'qualified_id', None) or getattr(doc, 'id', None)
        if doc_id:
            unique_ids.add(doc_id)
    
    diversity = len(unique_ids) / len(top_results) if top_results else 1.0
    
    return diversity


def measure_expansion_improvement(
    baseline_results: List,
    expanded_results: List,
    top_k: int = 10
) -> Dict:
    """
    Measure quality improvement from expansion.
    
    Metrics:
    - Recall improvement (new relevant docs found)
    - Diversity improvement
    - Overlap percentage
    
    Args:
        baseline_results: Results from original query only
        expanded_results: Results from expansion + fusion
        top_k: Number of results to compare
    
    Returns:
        Improvement metrics dict
    """
    baseline_top = baseline_results[:top_k]
    expanded_top = expanded_results[:top_k]
    
    # Extract IDs
    baseline_ids = set(
        getattr(doc, 'qualified_id', getattr(doc, 'id', str(i)))
        for i, doc in enumerate(baseline_top)
    )
    
    expanded_ids = set(
        getattr(doc, 'qualified_id', getattr(doc, 'id', str(i)))
        for i, doc in enumerate(expanded_top)
    )
    
    # Metrics
    overlap = len(baseline_ids & expanded_ids)
    new_docs = len(expanded_ids - baseline_ids)
    recall_improvement = new_docs / len(baseline_ids) if baseline_ids else 0.0
    
    diversity_baseline = calculate_diversity(baseline_results, top_k)
    diversity_expanded = calculate_diversity(expanded_results, top_k)
    diversity_improvement = diversity_expanded - diversity_baseline
    
    return {
        "overlap_count": overlap,
        "new_docs_count": new_docs,
        "recall_improvement": recall_improvement,
        "diversity_baseline": diversity_baseline,
        "diversity_expanded": diversity_expanded,
        "diversity_improvement": diversity_improvement,
        "improvement_percentage": recall_improvement * 100
    }
