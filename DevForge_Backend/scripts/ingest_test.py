"""
Simple RAG Ingestion Script - Run directly (no Celery/Redis required)

Usage:
    cd DevForge_Backend
    python scripts/ingest_test.py
"""

import asyncio
import sys
sys.path.insert(0, ".")

from src.tools.rag.tools import ingest_documents
from src.core.config import settings


async def main():
    # Files to ingest (use your actual project files)
    test_files = [
        "src/core/config.py",
        "src/agents/rag/agent.py",
        "README.md",
    ]
    
    print("=" * 50)
    print("RAG Ingestion Test Script")
    print("=" * 50)
    print(f"Embedding model: {settings.RAG_EMBED_MODEL}")
    print(f"Vector backend: {settings.VECTOR_BACKEND}")
    print(f"Files to ingest: {len(test_files)}")
    print()
    
    # Filter existing files
    from pathlib import Path
    existing_files = [f for f in test_files if Path(f).exists()]
    
    if not existing_files:
        print("ERROR: No files found to ingest!")
        print("Make sure you run this from the DevForge_Backend directory.")
        return
    
    print(f"Found {len(existing_files)} files:")
    for f in existing_files:
        print(f"  - {f}")
    print()
    
    print("Starting ingestion...")
    
    try:
        result = await ingest_documents(
            file_paths=existing_files,
            embed_model=settings.RAG_EMBED_MODEL,
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
            backend=settings.VECTOR_BACKEND,
        )
        
        print()
        print("=" * 50)
        print("INGESTION COMPLETE!")
        print("=" * 50)
        print(f"Result: {result}")
        
        if result.get("chunks_created", 0) > 0:
            print()
            print("✅ Documents ingested successfully!")
            print()
            print("Now test with curl:")
            print('curl -X POST http://localhost:8000/api/gateway \\')
            print('  -H "Content-Type: application/json" \\')
            print('  -d \'{"name": "retrieve_docs", "arguments": {"query": "What is RAG_EMBED_MODEL?", "top_k": 3}}\'')
        else:
            print("⚠️  No chunks created. Check file paths.")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
