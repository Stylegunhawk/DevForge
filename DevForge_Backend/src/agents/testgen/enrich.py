"""Optional RAG enrichment for generate_tests.

Pulls related dependency snippets from the tenant's indexed repo to improve
signature accuracy in generated tests. Strictly best-effort: any failure
(no indexed repo, RAG disabled, store error) degrades to an empty list and
never blocks the request. This only feeds the prompt — it does NOT relax the
import-symbol guard.
"""

from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)


async def fetch_repo_context(tenant_id: str, query: str, top_k: int = 4) -> List[str]:
    """Return up to `top_k` related code snippets, or [] on any failure."""
    if not tenant_id or tenant_id == "unknown":
        return []
    try:
        from src.agents.rag.agent import get_rag_agent
        from src.core.config import settings

        agent = get_rag_agent(tenant_id=tenant_id, collection_name=f"user_{tenant_id}")
        result = await agent.retrieve_with_reranking(
            query=query,
            top_k=top_k,
            use_reranking=True,
            use_cache=True,
            use_hybrid=False,
            score_threshold=getattr(settings, "RAG_SCORE_THRESHOLD", 0.0),
        )
        docs = result.get("documents", []) if isinstance(result, dict) else []
        snippets: List[str] = []
        for doc in docs:
            content = doc.get("content") if isinstance(doc, dict) else getattr(doc, "content", None)
            if content:
                snippets.append(content[:1200])
        return snippets
    except Exception as e:
        logger.info(f"fetch_repo_context skipped (no usable repo context): {e}")
        return []
