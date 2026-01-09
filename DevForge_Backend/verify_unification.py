
import sys
import os
import asyncio
import logging
import uuid
# Ensure project root is in path
sys.path.append(os.getcwd())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    try:
        from src.tools.rag.tools import ingest_documents
        from src.storage.chroma_store import ChromaVectorStore
        from src.agents.rag.agent import get_shared_rag_agent
        from src.core.config import settings

        # 1. Create dummy file
        test_file = "test_unification.txt"
        with open(test_file, "w") as f:
            f.write("This is a test document for pipeline unification.\nIt should be ingested with strict metadata.\nEnd of file.")
        
        file_path = str(os.path.abspath(test_file))
        file_id = f"test_{uuid.uuid4()}"
        
        logger.info(f"--- TEST 1: Ingestion via tools.py (Unified) ---")
        logger.info(f"File: {file_path}")
        logger.info(f"File ID: {file_id}")
        
        # Call tools.ingest_documents
        result = await ingest_documents(
            file_paths=[file_path],
            file_id=file_id,
        )
        logger.info(f"Ingestion Result: {result}")
        
        if not result["success"]:
            logger.error("Ingestion FAILED")
            return
            
        # 2. Verify Metadata in Chroma
        logger.info(f"--- TEST 2: Verify Metadata in ChromaVectorStore ---")
        store = ChromaVectorStore(collection_name=settings.CHROMA_COLLECTION)
        
        # Search by file_id? Chroma doesn't allow easy filtering by metadata in standard retrieval without 'where'
        # We can use _collection.get()
        chroma_res = await asyncio.to_thread(
            store._collection.get,
            where={"file_id": file_id}
        )
        
        ids = chroma_res.get("ids", [])
        metadatas = chroma_res.get("metadatas", [])
        
        logger.info(f"Found {len(ids)} chunks for file_id {file_id}")
        
        if not ids:
            logger.error("No chunks found in Chroma! Metadata loss?")
        else:
            first_meta = metadatas[0]
            logger.info(f"First Chunk Metadata: {first_meta}")
            if "chunk_id" in first_meta and "source" in first_meta:
                 logger.info("✅ SUCCESS: chunk_id and source present")
            else:
                 logger.error("❌ FAILURE: Missing standard metadata")

        # 3. Verify Retrieval via Agent
        logger.info(f"--- TEST 3: Retrieval via Agent (Unified) ---")
        agent = get_shared_rag_agent()
        query = "pipeline unification"
        
        # Force a fresh search (bypass cache if possible, or assume cache key is different)
        results = await agent.retrieve_with_reranking(query=query, top_k=3, use_cache=False)
        
        docs = results.get("documents", [])
        logger.info(f"Retrieved {len(docs)} documents")
        
        match_found = False
        for doc in docs:
            # Check if our test file is in results
            # doc is ChunkResult object
            meta = getattr(doc, 'metadata', {})
            logger.info(f"Retrieved Doc File ID: {meta.get('file_id')}")
            if meta.get("file_id") == file_id:
                match_found = True
                logger.info("✅ SUCCESS: Retrieved ingested document")
                break
        
        if not match_found:
            logger.warning("⚠️ Warning: Test document not retrieved (might be ranking issue or low score)")

    except Exception as e:
        logger.error(f"CRASH: {e}", exc_info=True)
    finally:
        # Cleanup
        if os.path.exists("test_unification.txt"):
            os.remove("test_unification.txt")

if __name__ == "__main__":
    asyncio.run(main())
