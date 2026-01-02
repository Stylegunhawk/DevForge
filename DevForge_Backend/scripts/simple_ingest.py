"""
Simple Direct ChromaDB Ingestion Test
Uses SAME path as tools.py retrieval to ensure documents are found.

Usage:
    cd DevForge_Backend
    python scripts/simple_ingest.py
"""

import asyncio
import sys
sys.path.insert(0, ".")

async def main():
    print("=" * 50)
    print("Direct ChromaDB Ingestion Test (Fixed Path)")
    print("=" * 50)
    
    from langchain_core.documents import Document
    from langchain_chroma import Chroma
    from langchain_community.embeddings import OllamaEmbeddings
    from src.core.config import settings
    from pathlib import Path
    import chromadb
    
    print(f"Embedding model: {settings.RAG_EMBED_MODEL}")
    print(f"Ollama host: {settings.OLLAMA_HOST}")
    print(f"Collection: {settings.CHROMA_COLLECTION}")
    print(f"Persist dir: {settings.CHROMA_PERSIST_DIR}")
    print()
    
    # Create embeddings
    print("Initializing embeddings...")
    embeddings = OllamaEmbeddings(
        model=settings.RAG_EMBED_MODEL,
        base_url=settings.OLLAMA_HOST,
    )
    
    # MATCH THE EXACT SAME PATH AS tools.py
    persist_dir = Path(settings.CHROMA_PERSIST_DIR)
    persist_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Using persist directory: {persist_dir}")
    
    # Create Chroma client EXACTLY like tools.py
    chroma_client = chromadb.PersistentClient(path=str(persist_dir))
    
    vector_store = Chroma(
        client=chroma_client,
        collection_name=settings.CHROMA_COLLECTION,
        embedding_function=embeddings,
    )
    
    # Create simple test documents with ONLY scalar metadata
    test_docs = [
        Document(
            page_content="""
RAG_EMBED_MODEL is a configuration setting in DevForge Backend.
It specifies the embedding model used for semantic search.
Default value is 'nomic-embed-text'.
This model runs via Ollama for local embeddings.
            """.strip(),
            metadata={
                "source": "config.py",
                "chunk_type": "text",
                "name": "RAG_EMBED_MODEL_doc",
            }
        ),
        Document(
            page_content="""
The RAGAgent class is the main orchestrator for retrieval-augmented generation.
It handles document ingestion, semantic search, reranking, and response generation.
Located in src/agents/rag/agent.py.
            """.strip(),
            metadata={
                "source": "agent.py",
                "chunk_type": "text",
                "name": "RAGAgent_doc",
            }
        ),
        Document(
            page_content="""
DevForge Backend is an AI-powered developer productivity platform.
It provides tools for code generation, documentation, and RAG-based search.
Phase 12A adds intent classification, query expansion, and semantic caching.
            """.strip(),
            metadata={
                "source": "README.md",
                "chunk_type": "text",
                "name": "README_doc",
            }
        ),
    ]
    
    print(f"\nAdding {len(test_docs)} test documents...")
    
    try:
        # Add documents
        ids = vector_store.add_documents(test_docs)
        print(f"✅ Added {len(ids)} documents to ChromaDB!")
        print(f"Document IDs: {ids}")
        
        # Verify count
        collection = chroma_client.get_collection(settings.CHROMA_COLLECTION)
        count = collection.count()
        print(f"\n✅ Total documents in '{settings.CHROMA_COLLECTION}': {count}")
        
        print("\n" + "=" * 50)
        print("SUCCESS! Now test with curl:")
        print("=" * 50)
        print()
        print('curl -X POST http://localhost:8000/api/gateway \\')
        print('  -H "Content-Type: application/json" \\')
        print('  -d \'{"name": "retrieve_docs", "arguments": {"query": "What is RAG_EMBED_MODEL?", "top_k": 3}}\'')
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
