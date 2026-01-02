"""
Test ChromaDB retrieval directly - bypass API to debug
"""

import asyncio
import sys
sys.path.insert(0, ".")

async def main():
    from src.tools.rag.tools import retrieve_docs
    from src.core.config import settings
    
    print("=" * 50)
    print("Direct Retrieval Test")
    print("=" * 50)
    print(f"Collection: {settings.CHROMA_COLLECTION}")
    print(f"Persist dir: {settings.CHROMA_PERSIST_DIR}")
    print()
    
    query = "RAG embed model"
    print(f"Query: {query}")
    print()
    
    try:
        results = await retrieve_docs(
            query=query,
            top_k=5,
            embed_model=settings.RAG_EMBED_MODEL,
            backend="chroma",
            score_threshold=0.0,  # Accept ALL results
        )
        
        print(f"Results count: {len(results)}")
        print()
        
        if results:
            for i, r in enumerate(results):
                print(f"[{i+1}] Score: {r.get('score')}")
                print(f"    Content: {r.get('content', '')[:100]}...")
                print()
        else:
            print("❌ No results returned!")
            print()
            print("Testing direct ChromaDB access...")
            
            # Direct ChromaDB test
            import chromadb
            from pathlib import Path
            
            persist_dir = Path(settings.CHROMA_PERSIST_DIR)
            client = chromadb.PersistentClient(path=str(persist_dir))
            
            print(f"Collections: {[c.name for c in client.list_collections()]}")
            
            try:
                collection = client.get_collection(settings.CHROMA_COLLECTION)
                count = collection.count()
                print(f"Collection '{settings.CHROMA_COLLECTION}' count: {count}")
                
                if count > 0:
                    peek = collection.peek(3)
                    print(f"Sample docs: {peek.get('documents', [])[:100]}")
            except Exception as e:
                print(f"Error accessing collection: {e}")
                
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
