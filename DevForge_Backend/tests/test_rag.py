"""Unit and integration tests for RAG feature.

Tests cover:
- Embedding model factory (nomic-embed-text, bge-m3, invalid model)
- Vector store initialization (ChromaDB mock)
- Document reading (PDF, MD, TXT, DOCX, invalid paths, size limits)
- Document chunking (size, overlap, metadata)
- Document ingestion (single/multiple docs, errors, parallel processing)
- Document retrieval (top_k, score threshold, empty results)
- Response generation (mock LLM)
- RAG agent workflow (query-only, ingest+query, error handling)
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from langchain_core.documents import Document

from src.agents.rag.agent import RAGState, rag_agent_invoke
from src.tools.rag.tools import (
    chunk_document,
    generate_response,
    get_embedding_model,
    get_vector_store,
    ingest_documents,
    read_document,
    retrieve_docs,
)

# Mock embedding vectors (fixed for testing)
MOCK_EMBEDDING_DIM = 768
MOCK_EMBEDDING = [0.1] * MOCK_EMBEDDING_DIM


@pytest.fixture
def mock_ollama_embeddings():
    """Fixture for mock OllamaEmbeddings."""
    mock_embeddings = MagicMock()
    mock_embeddings.embed_documents = AsyncMock(return_value=[MOCK_EMBEDDING] * 5)
    mock_embeddings.embed_query = AsyncMock(return_value=MOCK_EMBEDDING)
    return mock_embeddings


@pytest.fixture
def mock_chroma_client():
    """Fixture for mock ChromaDB client."""
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.get_or_create_collection = MagicMock(return_value=mock_collection)
    return mock_client, mock_collection


@pytest.fixture
def mock_vector_store():
    """Fixture for mock vector store."""
    mock_store = MagicMock()
    mock_store.add_documents = MagicMock()
    mock_store.similarity_search_with_score = MagicMock(
        return_value=[
            (Document(page_content="Test content 1", metadata={"source": "test1.txt"}), 0.2),
            (Document(page_content="Test content 2", metadata={"source": "test2.txt"}), 0.3),
            (Document(page_content="Test content 3", metadata={"source": "test3.txt"}), 0.4),
        ]
    )
    return mock_store


@pytest.fixture
def mock_model_router():
    """Fixture for mock ModelRouter."""
    mock_router = MagicMock()
    mock_chat_model = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = "This is a test response based on the context."
    mock_chat_model.ainvoke = AsyncMock(return_value=mock_response)
    mock_router.get_chat_model = MagicMock(return_value=mock_chat_model)
    mock_router.select_model_by_task = MagicMock(return_value="gpt-oss:20b")
    return mock_router


@pytest.fixture
def temp_doc_files():
    """Fixture to create temporary document files for testing."""
    temp_dir = tempfile.mkdtemp()
    files = {}

    # Create a text file
    txt_file = Path(temp_dir) / "test.txt"
    txt_file.write_text("This is a test text file.\nIt has multiple lines.\nFor testing purposes.")
    files["txt"] = str(txt_file)

    # Create a markdown file
    md_file = Path(temp_dir) / "test.md"
    md_file.write_text("# Test Document\n\nThis is a **markdown** file for testing.")
    files["md"] = str(md_file)

    yield files

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


# ==================== Embedding Model Factory Tests ====================


class TestGetEmbeddingModel:
    """Tests for get_embedding_model function."""

    @patch("src.tools.rag.tools.OllamaEmbeddings")
    def test_get_embedding_model_nomic(self, mock_ollama_class, mock_ollama_embeddings):
        """Test embedding model initialization with nomic-embed-text."""
        mock_ollama_class.return_value = mock_ollama_embeddings

        result = get_embedding_model("nomic-embed-text")

        assert result == mock_ollama_embeddings
        mock_ollama_class.assert_called_once()

    @patch("src.tools.rag.tools.OllamaEmbeddings")
    def test_get_embedding_model_bge_m3(self, mock_ollama_class, mock_ollama_embeddings):
        """Test embedding model initialization with bge-m3."""
        mock_ollama_class.return_value = mock_ollama_embeddings

        result = get_embedding_model("bge-m3")

        assert result == mock_ollama_embeddings
        mock_ollama_class.assert_called_once()

    def test_get_embedding_model_invalid_empty(self):
        """Test embedding model with empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid model name"):
            get_embedding_model("")

    def test_get_embedding_model_invalid_none(self):
        """Test embedding model with None raises ValueError."""
        with pytest.raises(ValueError, match="Invalid model name"):
            get_embedding_model(None)


# ==================== Vector Store Factory Tests ====================


class TestGetVectorStore:
    """Tests for get_vector_store function."""

    @patch("src.tools.rag.tools.chromadb.PersistentClient")
    @patch("src.tools.rag.tools.Chroma")
    def test_get_vector_store_chroma(self, mock_chroma_class, mock_client_class, mock_ollama_embeddings):
        """Test ChromaDB vector store initialization."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_store = MagicMock()
        mock_chroma_class.return_value = mock_store

        result = get_vector_store("chroma", mock_ollama_embeddings, "test_collection")

        assert result == mock_store
        mock_client_class.assert_called_once()
        mock_chroma_class.assert_called_once()

    def test_get_vector_store_invalid_backend(self, mock_ollama_embeddings):
        """Test invalid backend raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported vector backend"):
            get_vector_store("invalid_backend", mock_ollama_embeddings, "test_collection")

    @patch("src.tools.rag.tools.settings")
    @patch("src.tools.rag.tools.QdrantClient")
    @patch("src.tools.rag.tools.QdrantVectorStore")
    def test_get_vector_store_qdrant(self, mock_qdrant_store_class, mock_qdrant_client_class, mock_settings, mock_ollama_embeddings):
        """Test Qdrant Cloud vector store initialization."""
        mock_settings.QDRANT_URL = "https://test.qdrant.io"
        mock_settings.QDRANT_API_KEY = "test-api-key"
        mock_settings.QDRANT_COLLECTION = "test_collection"
        
        mock_client = MagicMock()
        mock_qdrant_client_class.return_value = mock_client
        mock_store = MagicMock()
        mock_qdrant_store_class.return_value = mock_store
        
        result = get_vector_store("qdrant", mock_ollama_embeddings, "test_collection")
        
        assert result == mock_store
        mock_qdrant_client_class.assert_called_once_with(
            url="https://test.qdrant.io",
            api_key="test-api-key",
            timeout=30
        )
        mock_qdrant_store_class.assert_called_once()

    @patch("src.tools.rag.tools.settings")
    def test_get_vector_store_qdrant_missing_url(self, mock_settings, mock_ollama_embeddings):
        """Test Qdrant backend raises ValueError when URL is missing."""
        mock_settings.QDRANT_URL = None
        mock_settings.QDRANT_API_KEY = "test-key"
        
        with pytest.raises(ValueError, match="QDRANT_URL is required"):
            get_vector_store("qdrant", mock_ollama_embeddings, "test_collection")

    @patch("src.tools.rag.tools.settings")
    def test_get_vector_store_qdrant_missing_api_key(self, mock_settings, mock_ollama_embeddings):
        """Test Qdrant backend raises ValueError when API key is missing."""
        mock_settings.QDRANT_URL = "https://test.qdrant.io"
        mock_settings.QDRANT_API_KEY = None
        
        with pytest.raises(ValueError, match="QDRANT_API_KEY is required"):
            get_vector_store("qdrant", mock_ollama_embeddings, "test_collection")


# ==================== Document Reading Tests ====================


class TestReadDocument:
    """Tests for read_document function."""

    @pytest.mark.asyncio
    async def test_read_txt_file(self, temp_doc_files):
        """Test reading a TXT file."""
        content = await read_document(temp_doc_files["txt"])
        assert isinstance(content, str)
        assert "test text file" in content.lower()

    @pytest.mark.asyncio
    async def test_read_md_file(self, temp_doc_files):
        """Test reading a Markdown file."""
        content = await read_document(temp_doc_files["md"])
        assert isinstance(content, str)
        assert "markdown" in content.lower()

    @pytest.mark.asyncio
    async def test_read_invalid_path(self):
        """Test reading non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await read_document("/nonexistent/file.txt")

    @pytest.mark.asyncio
    async def test_read_unsupported_extension(self, temp_doc_files):
        """Test reading unsupported file type raises ValueError."""
        # Create a file with unsupported extension
        invalid_file = Path(temp_doc_files["txt"]).parent / "test.xyz"
        invalid_file.write_text("test")

        with pytest.raises(ValueError, match="Unsupported file type"):
            await read_document(str(invalid_file))

    @pytest.mark.asyncio
    async def test_read_directory_traversal_prevention(self):
        """Test directory traversal attack prevention."""
        with pytest.raises(ValueError, match="directory traversal"):
            await read_document("../../../etc/passwd")

    @pytest.mark.asyncio
    async def test_read_file_size_limit(self, temp_doc_files):
        """Test file size limit enforcement."""
        # Create a large file (over 10MB)
        large_file = Path(temp_doc_files["txt"]).parent / "large.txt"
        large_content = "x" * (11 * 1024 * 1024)  # 11MB
        large_file.write_text(large_content)

        with pytest.raises(ValueError, match="File too large"):
            await read_document(str(large_file))


# ==================== Document Chunking Tests ====================


class TestChunkDocument:
    """Tests for chunk_document function."""

    def test_chunk_document_basic(self):
        """Test basic document chunking."""
        text = "This is a test document. " * 100  # ~3000 chars
        chunks = chunk_document(text, "test.txt", chunk_size=500, chunk_overlap=50)

        assert isinstance(chunks, list)
        assert len(chunks) > 0
        assert all(isinstance(chunk, Document) for chunk in chunks)

    def test_chunk_document_metadata(self):
        """Test chunk metadata is set correctly."""
        text = "Test content. " * 50
        chunks = chunk_document(text, "source.md", chunk_size=200, chunk_overlap=20)

        assert len(chunks) > 0
        for i, chunk in enumerate(chunks):
            assert chunk.metadata["source"] == "source.md"
            assert chunk.metadata["chunk_index"] == i

    def test_chunk_document_overlap(self):
        """Test chunk overlap is applied."""
        text = "Word1 Word2 Word3 Word4 Word5 Word6 Word7 Word8 " * 20
        chunks = chunk_document(text, "test.txt", chunk_size=50, chunk_overlap=10)

        if len(chunks) > 1:
            # Check that chunks have overlap
            first_chunk_end = chunks[0].page_content[-20:]
            second_chunk_start = chunks[1].page_content[:20]
            # There should be some overlap in words
            assert any(word in second_chunk_start for word in first_chunk_end.split())


# ==================== Document Ingestion Tests ====================


class TestIngestDocuments:
    """Tests for ingest_documents function."""

    @pytest.mark.asyncio
    @patch("src.tools.rag.tools.get_vector_store")
    @patch("src.tools.rag.tools.get_embedding_model")
    async def test_ingest_single_document(
        self, mock_get_embeddings, mock_get_store, temp_doc_files, mock_vector_store
    ):
        """Test ingesting a single document."""
        mock_get_embeddings.return_value = MagicMock()
        mock_get_store.return_value = mock_vector_store

        result = await ingest_documents(
            file_paths=[temp_doc_files["txt"]], embed_model="nomic-embed-text", backend="chroma"
        )

        assert result["success"] is True
        assert result["documents_processed"] == 1
        assert result["chunks_created"] > 0
        assert result["backend"] == "chroma"
        mock_vector_store.add_documents.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.tools.rag.tools.get_vector_store")
    @patch("src.tools.rag.tools.get_embedding_model")
    async def test_ingest_multiple_documents(
        self, mock_get_embeddings, mock_get_store, temp_doc_files, mock_vector_store
    ):
        """Test ingesting multiple documents in parallel."""
        mock_get_embeddings.return_value = MagicMock()
        mock_get_store.return_value = mock_vector_store

        result = await ingest_documents(
            file_paths=[temp_doc_files["txt"], temp_doc_files["md"]],
            embed_model="nomic-embed-text",
            backend="chroma",
        )

        assert result["success"] is True
        assert result["documents_processed"] == 2
        assert result["chunks_created"] > 0

    @pytest.mark.asyncio
    @patch("src.tools.rag.tools.get_vector_store")
    @patch("src.tools.rag.tools.get_embedding_model")
    async def test_ingest_with_invalid_file(
        self, mock_get_embeddings, mock_get_store, temp_doc_files, mock_vector_store
    ):
        """Test ingestion handles invalid files gracefully."""
        mock_get_embeddings.return_value = MagicMock()
        mock_get_store.return_value = mock_vector_store

        result = await ingest_documents(
            file_paths=[temp_doc_files["txt"], "/nonexistent/file.txt"],
            embed_model="nomic-embed-text",
            backend="chroma",
        )

        # Should process valid file, skip invalid one
        assert result["success"] is True
        assert result["documents_processed"] == 1
        assert result["error"] is not None  # Error should be logged

    @pytest.mark.asyncio
    @patch("src.tools.rag.tools.get_vector_store")
    @patch("src.tools.rag.tools.get_embedding_model")
    async def test_ingest_handles_errors(
        self, mock_get_embeddings, mock_get_store, mock_vector_store
    ):
        """Test ingestion error handling."""
        mock_get_embeddings.return_value = MagicMock()
        mock_get_store.return_value = mock_vector_store
        mock_vector_store.add_documents.side_effect = Exception("Vector store error")

        result = await ingest_documents(
            file_paths=["/nonexistent/file.txt"], embed_model="nomic-embed-text", backend="chroma"
        )

        assert result["success"] is False
        assert "error" in result


# ==================== Document Retrieval Tests ====================


class TestRetrieveDocs:
    """Tests for retrieve_docs function."""

    @pytest.mark.asyncio
    @patch("src.tools.rag.tools.get_vector_store")
    @patch("src.tools.rag.tools.get_embedding_model")
    async def test_retrieve_docs_basic(
        self, mock_get_embeddings, mock_get_store, mock_vector_store
    ):
        """Test basic document retrieval."""
        mock_get_embeddings.return_value = MagicMock()
        mock_get_store.return_value = mock_vector_store

        results = await retrieve_docs("test query", top_k=3, embed_model="nomic-embed-text", backend="chroma")

        assert isinstance(results, list)
        assert len(results) > 0
        assert all("content" in doc and "score" in doc for doc in results)

    @pytest.mark.asyncio
    @patch("src.tools.rag.tools.get_vector_store")
    @patch("src.tools.rag.tools.get_embedding_model")
    async def test_retrieve_docs_top_k(self, mock_get_embeddings, mock_get_store, mock_vector_store):
        """Test top_k parameter enforcement."""
        mock_get_embeddings.return_value = MagicMock()
        mock_get_store.return_value = mock_vector_store

        results = await retrieve_docs("test query", top_k=2, embed_model="nomic-embed-text", backend="chroma")

        assert len(results) <= 2

    @pytest.mark.asyncio
    @patch("src.tools.rag.tools.get_vector_store")
    @patch("src.tools.rag.tools.get_embedding_model")
    async def test_retrieve_docs_score_threshold(
        self, mock_get_embeddings, mock_get_store, mock_vector_store
    ):
        """Test score threshold filtering."""
        mock_get_embeddings.return_value = MagicMock()
        mock_get_store.return_value = mock_vector_store
        # Mock scores that are below threshold (0.5)
        mock_vector_store.similarity_search_with_score.return_value = [
            (Document(page_content="content1", metadata={}), 0.6),  # similarity = 0.4 (below threshold)
            (Document(page_content="content2", metadata={}), 0.3),  # similarity = 0.7 (above threshold)
        ]

        results = await retrieve_docs(
            "test query", top_k=5, embed_model="nomic-embed-text", backend="chroma", score_threshold=0.5
        )

        # Only results with similarity >= 0.5 should be returned
        assert all(doc["score"] >= 0.5 for doc in results)

    @pytest.mark.asyncio
    @patch("src.tools.rag.tools.get_vector_store")
    @patch("src.tools.rag.tools.get_embedding_model")
    async def test_retrieve_docs_empty_results(
        self, mock_get_embeddings, mock_get_store, mock_vector_store
    ):
        """Test retrieval with empty results."""
        mock_get_embeddings.return_value = MagicMock()
        mock_get_store.return_value = mock_vector_store
        mock_vector_store.similarity_search_with_score.return_value = []

        results = await retrieve_docs("test query", top_k=5, embed_model="nomic-embed-text", backend="chroma")

        assert results == []


# ==================== Response Generation Tests ====================


class TestGenerateResponse:
    """Tests for generate_response function."""

    @pytest.mark.asyncio
    @patch("src.tools.rag.tools.model_router")
    async def test_generate_response_success(self, mock_router_module, mock_model_router):
        """Test successful response generation."""
        mock_router_module.select_model_by_task = MagicMock(return_value="gpt-oss:20b")
        mock_router_module.get_chat_model = mock_model_router.get_chat_model

        response = await generate_response(
            query="What is the main topic?", context="This document is about AI and machine learning."
        )

        assert isinstance(response, str)
        assert len(response) > 0
        mock_model_router.get_chat_model.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.tools.rag.tools.model_router")
    async def test_generate_response_with_model_hint(self, mock_router_module, mock_model_router):
        """Test response generation with model hint."""
        mock_router_module.get_chat_model = mock_model_router.get_chat_model

        response = await generate_response(
            query="Test query",
            context="Test context",
            model_hint="custom-model",
        )

        assert isinstance(response, str)
        # Should use custom model, not call select_model_by_task
        mock_model_router.get_chat_model.assert_called_with("custom-model")


# ==================== RAG Agent Workflow Tests ====================


class TestRAGAgentWorkflow:
    """Tests for RAG agent workflow."""

    @pytest.mark.asyncio
    @patch("src.agents.rag.agent.retrieve_docs")
    @patch("src.agents.rag.agent.generate_response")
    async def test_rag_agent_query_only(self, mock_generate, mock_retrieve):
        """Test RAG agent with query only (no ingestion)."""
        mock_retrieve.return_value = [
            {"content": "Test content", "metadata": {}, "score": 0.8, "id": "1"}
        ]
        mock_generate.return_value = "This is the answer."

        result = await rag_agent_invoke(query="Test question")

        assert result["success"] is True
        assert result["tool"] == "retrieve_docs"
        assert result["data"]["response"] == "This is the answer."
        assert len(result["data"]["documents"]) > 0
        assert "execution_time" in result

    @pytest.mark.asyncio
    @patch("src.agents.rag.agent.ingest_documents")
    @patch("src.agents.rag.agent.retrieve_docs")
    @patch("src.agents.rag.agent.generate_response")
    async def test_rag_agent_ingest_and_query(
        self, mock_generate, mock_retrieve, mock_ingest, temp_doc_files
    ):
        """Test RAG agent with document ingestion and query."""
        mock_ingest.return_value = {"success": True, "documents_processed": 1, "chunks_created": 5}
        mock_retrieve.return_value = [
            {"content": "Ingested content", "metadata": {}, "score": 0.9, "id": "1"}
        ]
        mock_generate.return_value = "Answer based on ingested docs."

        result = await rag_agent_invoke(
            query="Test question", file_paths=[temp_doc_files["txt"]]
        )

        assert result["success"] is True
        mock_ingest.assert_called_once()
        mock_retrieve.assert_called_once()
        mock_generate.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.agents.rag.agent.retrieve_docs")
    async def test_rag_agent_empty_retrieval(self, mock_retrieve):
        """Test RAG agent with empty retrieval results."""
        mock_retrieve.return_value = []

        result = await rag_agent_invoke(query="Test question")

        # Should still succeed but with empty context message
        assert result["success"] is True
        assert "don't have enough information" in result["data"]["response"].lower()

    @pytest.mark.asyncio
    @patch("src.agents.rag.agent.ingest_documents")
    async def test_rag_agent_ingestion_error(self, mock_ingest):
        """Test RAG agent error handling during ingestion."""
        mock_ingest.side_effect = Exception("Ingestion failed")

        result = await rag_agent_invoke(query="Test question", file_paths=["/invalid/path.txt"])

        assert result["success"] is False
        assert "error" in result
        assert "Ingestion failed" in result["error"]

    @pytest.mark.asyncio
    @patch("src.agents.rag.agent.retrieve_docs")
    async def test_rag_agent_retrieval_error(self, mock_retrieve):
        """Test RAG agent error handling during retrieval."""
        mock_retrieve.side_effect = Exception("Retrieval failed")

        result = await rag_agent_invoke(query="Test question")

        assert result["success"] is False
        assert "error" in result
        assert "Retrieval failed" in result["error"]

    @pytest.mark.asyncio
    @patch("src.agents.rag.agent.retrieve_docs")
    @patch("src.agents.rag.agent.generate_response")
    async def test_rag_agent_generation_error(self, mock_generate, mock_retrieve):
        """Test RAG agent error handling during response generation."""
        mock_retrieve.return_value = [{"content": "Test", "metadata": {}, "score": 0.8, "id": "1"}]
        mock_generate.side_effect = Exception("Generation failed")

        result = await rag_agent_invoke(query="Test question")

        assert result["success"] is False
        assert "error" in result
        assert "Generation failed" in result["error"]


# ==================== Integration Tests ====================


class TestRAGIntegration:
    """Integration tests for RAG workflow."""

    @pytest.mark.asyncio
    @patch("src.tools.rag.tools.get_vector_store")
    @patch("src.tools.rag.tools.get_embedding_model")
    @patch("src.tools.rag.tools.model_router")
    async def test_end_to_end_workflow(
        self,
        mock_router_module,
        mock_get_embeddings,
        mock_get_store,
        temp_doc_files,
        mock_vector_store,
        mock_model_router,
    ):
        """Test end-to-end RAG workflow."""
        mock_get_embeddings.return_value = MagicMock()
        mock_get_store.return_value = mock_vector_store
        mock_router_module.select_model_by_task = MagicMock(return_value="gpt-oss:20b")
        mock_router_module.get_chat_model = mock_model_router.get_chat_model

        # Ingest documents
        ingest_result = await ingest_documents(
            file_paths=[temp_doc_files["txt"]], embed_model="nomic-embed-text", backend="chroma"
        )
        assert ingest_result["success"] is True

        # Retrieve documents
        retrieve_result = await retrieve_docs(
            "test content", top_k=3, embed_model="nomic-embed-text", backend="chroma"
        )
        assert len(retrieve_result) > 0

        # Generate response
        context = "\n\n".join([doc["content"] for doc in retrieve_result])
        response = await generate_response("What is this about?", context)
        assert isinstance(response, str)
        assert len(response) > 0


# ==================== Supervisor RAG Integration Tests ====================


class TestSupervisorRAGRouting:
    """Tests for supervisor RAG routing integration."""

    @pytest.mark.asyncio
    @patch("src.agents.supervisor.rag_agent_invoke")
    async def test_supervisor_routes_rag_intent(self, mock_rag_agent):
        """Test supervisor routes 'rag' intent to RAG agent."""
        from src.agents.supervisor import supervisor

        # Mock RAG agent response
        mock_rag_agent.return_value = {
            "success": True,
            "tool": "retrieve_docs",
            "data": {
                "response": "Test response from RAG",
                "documents": [{"content": "doc1", "score": 0.8}],
                "backend": "chroma",
            },
            "execution_time": 1.5,
            "error": None,
        }

        # Mock intent classification to return "rag"
        with patch("src.agents.supervisor.model_router") as mock_router:
            mock_chat_model = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = "rag"
            mock_chat_model.ainvoke = AsyncMock(return_value=mock_response)
            mock_router.select_model_by_task = MagicMock(return_value="deepseek-r1:8b")
            mock_router.get_chat_model = MagicMock(return_value=mock_chat_model)

            result = await supervisor.ainvoke({"query": "What is in the documentation?"})

            assert result["intent"] == "rag"
            mock_rag_agent.assert_called_once()
            assert result["agent_result"]["success"] is True

    @pytest.mark.asyncio
    @patch("src.agents.supervisor.rag_agent_invoke")
    async def test_supervisor_handles_rag_errors(self, mock_rag_agent):
        """Test supervisor handles RAG agent errors gracefully."""
        from src.agents.supervisor import supervisor

        # Mock RAG agent to raise an error
        mock_rag_agent.side_effect = Exception("RAG agent failed")

        # Mock intent classification to return "rag"
        with patch("src.agents.supervisor.model_router") as mock_router:
            mock_chat_model = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = "rag"
            mock_chat_model.ainvoke = AsyncMock(return_value=mock_response)
            mock_router.select_model_by_task = MagicMock(return_value="deepseek-r1:8b")
            mock_router.get_chat_model = MagicMock(return_value=mock_chat_model)

            result = await supervisor.ainvoke({"query": "Search documents"})

            assert result["intent"] == "rag"
            assert result["error"] is not None
            assert "RAG execution failed" in result["error"]
            assert result["agent_result"]["success"] is False


# ── Task 1: cache_key_from_query with file_ids ──────────────────────────────

from src.agents.rag.cache.query_normalizer import cache_key_from_query
from src.agents.rag.cache.semantic_cache import SemanticCache

def test_cache_key_differs_with_different_file_ids():
    key_no_scope = cache_key_from_query("auth function", 5, tenant_id="t1")
    key_scoped   = cache_key_from_query("auth function", 5, tenant_id="t1", file_ids=("f_auth",))
    assert key_no_scope != key_scoped

def test_cache_key_order_independent_file_ids():
    key_a = cache_key_from_query("auth function", 5, tenant_id="t1", file_ids=("f_b", "f_a"))
    key_b = cache_key_from_query("auth function", 5, tenant_id="t1", file_ids=("f_a", "f_b"))
    assert key_a == key_b

def test_cache_key_none_file_ids_matches_no_arg():
    key_none = cache_key_from_query("auth function", 5, tenant_id="t1", file_ids=None)
    key_omit = cache_key_from_query("auth function", 5, tenant_id="t1")
    assert key_none == key_omit


# ── Task 2: SemanticCache scoped by file_ids ────────────────────────────────

@pytest.mark.asyncio
async def test_semantic_cache_scoped_miss_on_different_file_ids():
    """A cache entry stored without file_ids must not be returned for a scoped query."""
    cache = SemanticCache(similarity_threshold=0.92)

    fake_embedding = MagicMock()
    fake_embedding.similarity = MagicMock(return_value=0.99)  # would be a hit without scoping

    fake_result = {"documents": ["doc1"], "reranked": True}

    with patch.object(cache, '_embed_query', new=AsyncMock(return_value=fake_embedding)):
        # Store without file_ids
        await cache.set("auth function", "code_search", fake_result, tenant_id="t1")
        # Retrieve with file_ids — must be a MISS (different bucket)
        hit = await cache.get("auth function", "code_search", tenant_id="t1", file_ids=("f_auth",))
        assert hit is None


# ── Task 3: ChromaVectorStore file_ids filter ───────────────────────────────

from src.storage.chroma_store import ChromaVectorStore

@pytest.mark.asyncio
async def test_chroma_search_passes_where_filter_when_file_ids_set():
    """search() must pass where={"file_id": {"$in": [...]}} to collection.query when file_ids is set."""
    store = ChromaVectorStore.__new__(ChromaVectorStore)

    mock_collection = MagicMock()
    mock_collection.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    store._collection = mock_collection

    await store.search(
        query_embedding=[0.1, 0.2, 0.3],
        top_k=5,
        file_ids=["f_auth", "f_utils"],
    )

    call_kwargs = mock_collection.query.call_args.kwargs
    assert call_kwargs.get("where") == {"file_id": {"$in": ["f_auth", "f_utils"]}}

@pytest.mark.asyncio
async def test_chroma_search_no_where_filter_when_file_ids_none():
    """search() must NOT pass a where filter when file_ids is None."""
    store = ChromaVectorStore.__new__(ChromaVectorStore)

    mock_collection = MagicMock()
    mock_collection.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    store._collection = mock_collection

    await store.search(
        query_embedding=[0.1, 0.2, 0.3],
        top_k=5,
        file_ids=None,
    )

    call_kwargs = mock_collection.query.call_args.kwargs
    assert call_kwargs.get("where") is None


# ── Task 4: PgVectorStore file_ids filter ──────────────────────────────────

from unittest.mock import AsyncMock, MagicMock
from src.storage.pgvector_store import PgVectorStore

@pytest.mark.asyncio
async def test_pgvector_search_includes_file_id_any_clause_when_file_ids_set():
    """search() SQL must contain ANY($n) and bind file_ids when file_ids is provided."""
    store = PgVectorStore.__new__(PgVectorStore)
    store.table_name = "rag_chunks"
    store.collection_name = "user_t1"

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    store._get_conn = AsyncMock(return_value=mock_conn)

    await store.search(
        query_embedding=[0.1, 0.2],
        top_k=5,
        tenant_id="t1",
        collection_name="user_t1",
        file_ids=["f_auth"],
    )

    assert mock_conn.fetch.called
    sql_arg = mock_conn.fetch.call_args.args[0]
    assert "ANY(" in sql_arg
    # file_ids list should be among the bind params
    bind_params = mock_conn.fetch.call_args.args[1:]
    assert ["f_auth"] in bind_params


# ── Task 5: _vector_search passes file_ids to store ────────────────────────

from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.rag.agent import RAGAgent

@pytest.mark.asyncio
async def test_vector_search_passes_file_ids_to_chroma_store():
    """_vector_search(file_ids=...) must call vector_store.search with file_ids kwarg."""
    agent = RAGAgent.__new__(RAGAgent)
    agent.backend = "chroma"
    agent.collection_name = "user_t1"
    agent.tenant_id = "t1"

    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[])
    mock_store.embeddings = MagicMock()
    mock_store.embeddings.embed_query = MagicMock(return_value=[0.1, 0.2])
    agent.vector_store = mock_store

    with patch("asyncio.to_thread", new=AsyncMock(return_value=[0.1, 0.2])):
        await agent._vector_search("auth function", top_k=5, file_ids=["f_auth"])

    mock_store.search.assert_called_once()
    call_kwargs = mock_store.search.call_args.kwargs
    assert call_kwargs.get("file_ids") == ["f_auth"]


# ── Task 6: retrieve_with_reranking file_ids wiring ────────────────────────

@pytest.mark.asyncio
async def test_retrieve_with_reranking_skips_bm25_when_file_ids_set():
    """When file_ids is set, the hybrid retriever must NOT be called."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from src.agents.rag.agent import RAGAgent

    agent = RAGAgent.__new__(RAGAgent)
    agent.backend = "chroma"
    agent.collection_name = "user_t1"
    agent.tenant_id = "t1"
    agent._reranker = None
    agent._code_graph = None
    agent._intent_classifier = None
    agent._query_expander = None
    agent._query_cache = None
    agent._semantic_cache = None

    mock_context_shaper = MagicMock()
    mock_context_shaper.shape_context = MagicMock(side_effect=lambda x: x)
    agent._context_shaper = mock_context_shaper

    mock_hybrid = AsyncMock()
    agent._hybrid_retriever = mock_hybrid
    mock_bm25 = MagicMock()
    mock_bm25.is_ready = MagicMock(return_value=True)
    agent._bm25_index = mock_bm25

    agent._vector_search = AsyncMock(return_value=[])

    from src.core.config import settings
    with patch.object(settings, "ENABLE_HYBRID_SEARCH", True), \
         patch.object(settings, "ENABLE_RERANKING", False), \
         patch.object(settings, "ENABLE_CODE_GRAPH", False), \
         patch.object(settings, "ENABLE_INTENT_CLASSIFICATION", False), \
         patch.object(settings, "ENABLE_QUERY_EXPANSION", False), \
         patch.object(settings, "ENABLE_SEMANTIC_CACHE", False), \
         patch.object(settings, "ENABLE_QUERY_CACHE", False):
        await agent.retrieve_with_reranking(
            query="auth function",
            top_k=5,
            file_ids=["f_auth"],
        )

    mock_hybrid.search.assert_not_called()
    agent._vector_search.assert_called_once()
    call_kwargs = agent._vector_search.call_args.kwargs
    assert call_kwargs.get("file_ids") == ["f_auth"]


@pytest.mark.asyncio
async def test_retrieve_with_reranking_empty_file_ids_uses_hybrid():
    """When file_ids=[], hybrid search must run normally (empty list = no scope)."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from src.agents.rag.agent import RAGAgent
    from src.core.config import settings

    agent = RAGAgent.__new__(RAGAgent)
    agent.backend = "chroma"
    agent.collection_name = "user_t1"
    agent.tenant_id = "t1"
    agent._reranker = None
    agent._code_graph = None
    agent._intent_classifier = None
    agent._query_expander = None
    agent._query_cache = None
    agent._semantic_cache = None

    mock_context_shaper = MagicMock()
    mock_context_shaper.shape_context = MagicMock(side_effect=lambda x: x)
    agent._context_shaper = mock_context_shaper

    mock_bm25 = MagicMock()
    mock_bm25.is_ready = MagicMock(return_value=True)
    agent._bm25_index = mock_bm25

    mock_hybrid = MagicMock()
    mock_hybrid.search = AsyncMock(return_value=[])
    agent._hybrid_retriever = mock_hybrid

    with patch.object(settings, "ENABLE_HYBRID_SEARCH", True), \
         patch.object(settings, "ENABLE_RERANKING", False), \
         patch.object(settings, "ENABLE_CODE_GRAPH", False), \
         patch.object(settings, "ENABLE_INTENT_CLASSIFICATION", False), \
         patch.object(settings, "ENABLE_QUERY_EXPANSION", False), \
         patch.object(settings, "ENABLE_SEMANTIC_CACHE", False), \
         patch.object(settings, "ENABLE_QUERY_CACHE", False):
        await agent.retrieve_with_reranking(
            query="auth function",
            top_k=5,
            file_ids=[],   # empty → treat as None → hybrid runs
        )

    mock_hybrid.search.assert_called_once()


# ── Task 7: Router integration ─────────────────────────────────────────────

from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_router_passes_fileids_to_agent():
    """POST semanticSearchForChat with fileIds must call retrieve_with_reranking(file_ids=[...])."""
    from src.main import app

    captured = {}

    async def mock_retrieve(**kwargs):
        captured.update(kwargs)
        return {"documents": []}

    mock_agent = MagicMock()
    mock_agent.retrieve_with_reranking = mock_retrieve

    fake_payload = {"tenant_id": "t_test"}

    with patch("src.api.routers.rag.get_rag_agent", return_value=mock_agent), \
         patch("src.core.middleware.verify_jwt", return_value=fake_payload), \
         patch("src.api.routers.rag.redis_store.save_query_metadata", new=AsyncMock()):
        client = TestClient(app)
        client.post(
            "/api/v1/rag/chunk/semanticSearchForChat",
            json={
                "messageId": "msg_test",
                "userQuery": "authenticate function",
                "fileIds": ["f_auth"],
            },
            headers={"Authorization": "Bearer test_token"},
        )

    assert captured.get("file_ids") == ["f_auth"]


@pytest.mark.asyncio
async def test_router_passes_none_when_fileids_empty():
    """POST semanticSearchForChat with fileIds=[] must call retrieve_with_reranking(file_ids=None)."""
    from src.main import app

    captured = {}

    async def mock_retrieve(**kwargs):
        captured.update(kwargs)
        return {"documents": []}

    mock_agent = MagicMock()
    mock_agent.retrieve_with_reranking = mock_retrieve

    fake_payload = {"tenant_id": "t_test"}

    with patch("src.api.routers.rag.get_rag_agent", return_value=mock_agent), \
         patch("src.core.middleware.verify_jwt", return_value=fake_payload), \
         patch("src.api.routers.rag.redis_store.save_query_metadata", new=AsyncMock()):
        client = TestClient(app)
        client.post(
            "/api/v1/rag/chunk/semanticSearchForChat",
            json={
                "messageId": "msg_test",
                "userQuery": "authenticate function",
                "fileIds": [],
            },
            headers={"Authorization": "Bearer test_token"},
        )

    assert captured.get("file_ids") is None
