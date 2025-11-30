"""Tests for Reranker agent."""

import pytest
from src.agents.reranker import Reranker


@pytest.mark.asyncio
async def test_reranker_empty_list():
    """Test reranker with empty document list."""
    reranker = Reranker()
    result = await reranker.rerank("query", [], top_k=5)
    assert result == []


@pytest.mark.asyncio
async def test_reranker_top_k():
    """Test that top_k is respected."""
    reranker = Reranker()
    documents = [f"Document {i}" for i in range(10)]
    reranked = await reranker.rerank("test", documents, top_k=3)
    assert len(reranked) == 3


@pytest.mark.asyncio
async def test_reranker_relevance():
    """Test that relevant documents are ranked higher."""
    reranker = Reranker()
    query = "python programming"
    documents = [
        "The weather is nice today.",
        "Python is a great programming language.",
        "I like to eat apples.",
    ]
    reranked = await reranker.rerank(query, documents, top_k=1)
    assert "Python" in reranked[0]


@pytest.mark.asyncio
async def test_reranker_with_objects():
    """Test reranking objects using a key function."""
    reranker = Reranker()
    query = "python"
    documents = [
        {"id": 1, "content": "The weather is nice."},
        {"id": 2, "content": "Python is great."},
        {"id": 3, "content": "I like apples."},
    ]
    
    reranked = await reranker.rerank(
        query, 
        documents, 
        top_k=1, 
        key=lambda x: x["content"]
    )
    
    assert len(reranked) == 1
    assert reranked[0]["id"] == 2
