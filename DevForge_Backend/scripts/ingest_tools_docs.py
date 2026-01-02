"""
Ingest ALL docs/tools/*.md files into ChromaDB for comprehensive RAG testing.

Usage:
    cd DevForge_Backend
    .\venv\Scripts\activate
    python scripts/ingest_tools_docs.py
"""

import asyncio
import sys
sys.path.insert(0, ".")

async def main():
    from langchain_core.documents import Document
    from langchain_chroma import Chroma
    from langchain_community.embeddings import OllamaEmbeddings
    from src.core.config import settings
    from pathlib import Path
    import chromadb
    
    print("=" * 60)
    print("DevForge RAG - Ingest Tools Documentation")
    print("=" * 60)
    
    # Find all .md files in docs/tools
    docs_tools_path = Path("docs/tools")
    md_files = list(docs_tools_path.glob("*.md"))
    
    print(f"\nFound {len(md_files)} .md files:")
    for f in md_files:
        print(f"  - {f}")
    
    # Initialize embeddings
    print("\nInitializing Ollama embeddings...")
    embeddings = OllamaEmbeddings(
        model=settings.RAG_EMBED_MODEL,
        base_url=settings.OLLAMA_HOST,
    )
    
    # Initialize ChromaDB (same path as server)
    persist_dir = Path(settings.CHROMA_PERSIST_DIR)
    persist_dir.mkdir(parents=True, exist_ok=True)
    
    chroma_client = chromadb.PersistentClient(path=str(persist_dir))
    
    vector_store = Chroma(
        client=chroma_client,
        collection_name=settings.CHROMA_COLLECTION,
        embedding_function=embeddings,
    )
    
    # Read and create documents
    documents = []
    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
            
            # Split into chunks (simple approach - by headers)
            chunks = content.split("\n## ")
            
            for i, chunk in enumerate(chunks):
                if len(chunk.strip()) > 50:  # Skip very short chunks
                    doc = Document(
                        page_content=chunk[:2000],  # Limit chunk size
                        metadata={
                            "source": str(md_file),
                            "chunk_type": "documentation",
                            "name": f"{md_file.stem}_chunk_{i}",
                            "tool": md_file.stem,
                        }
                    )
                    documents.append(doc)
                    
            print(f"  Processed: {md_file.name} ({len(chunks)} chunks)")
            
        except Exception as e:
            print(f"  Error reading {md_file}: {e}")
    
    print(f"\nTotal documents to ingest: {len(documents)}")
    
    # Add to ChromaDB
    print("Adding documents to ChromaDB...")
    try:
        ids = vector_store.add_documents(documents)
        print(f"✅ Successfully added {len(ids)} documents!")
        
        # Verify count
        collection = chroma_client.get_collection(settings.CHROMA_COLLECTION)
        total = collection.count()
        print(f"✅ Total documents in collection: {total}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 60)
    print("INGESTION COMPLETE! Ready for testing.")
    print("=" * 60)
    print("\nTest queries you can now ask:")
    print('  - "How does generate_data tool work?"')
    print('  - "Explain the rerank_docs parameters"')
    print('  - "What is the retrieve_docs tool used for?"')
    print('  - "How to use github_operation tool?"')
    print('  - "What are the cheatsheet generation options?"')


if __name__ == "__main__":
    asyncio.run(main())
