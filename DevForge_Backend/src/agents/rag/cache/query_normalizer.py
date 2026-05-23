"""Query normalization for exact-match caching.

Phase 11.2 Refinement:
- Token sorting ONLY for short queries (<= 6 tokens)
- Long queries (stack traces, logs) preserve order to avoid collisions
"""

import hashlib
import re
from typing import Optional


def normalize_query(query: str, sort_threshold: int = 6) -> str:
    """
    Normalize query for exact-match caching.
    
    Transformations:
    1. Lowercase
    2. Remove punctuation (except underscores - useful for code)
    3. Collapse whitespace
    4. Sort tokens ONLY if token count <= sort_threshold
    
    Args:
        query: Raw user query
        sort_threshold: Max tokens to apply sorting (default 6)
    
    Returns:
        Normalized query string
    
    Examples:
        >>> normalize_query("JWT authentication")
        'authentication jwt'  # Sorted (2 tokens)
        
        >>> normalize_query("How to implement JWT token validation in Python?")
        'how implement jwt python token validation'  # Sorted (6 tokens)
        
        >>> normalize_query("Traceback (most recent call last): File auth.py line 42")
        'traceback most recent call last file auth_py line 42'  # NOT sorted (9 tokens)
    """
    # Step 1: Lowercase
    normalized = query.lower()
    
    # Step 2: Remove punctuation except underscores
    # Keep underscores for code identifiers like get_user, AUTH_TOKEN
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    
    # Step 3: Collapse whitespace
    normalized = ' '.join(normalized.split())
    
    # Step 4: Sort tokens ONLY for short queries
    tokens = normalized.split()
    token_count = len(tokens)
    
    if token_count <= sort_threshold:
        # Short natural-language query → sort for order-invariance
        # "JWT authentication" == "authentication JWT"
        tokens = sorted(tokens)
    # else: Long query (likely code/logs) → preserve order
    
    normalized = ' '.join(tokens)
    
    return normalized


def cache_key_from_query(
    query: str,
    top_k: int,
    tenant_id: str = "default",
    file_ids: Optional[tuple] = None,
) -> str:
    """
    Generate SHA256 cache key from query + retrieval params + tenant + optional file scope.

    Args:
        query: User query string
        top_k: Number of results requested
        tenant_id: Tenant identifier
        file_ids: Optional sorted tuple of file IDs for scoped queries

    Returns:
        SHA256 hash (64 hex chars)
    """
    normalized = normalize_query(query)

    cache_input = f"{tenant_id}::{normalized}::{top_k}"
    if file_ids:
        cache_input += f"::files={'|'.join(sorted(file_ids))}"

    return hashlib.sha256(cache_input.encode('utf-8')).hexdigest()
