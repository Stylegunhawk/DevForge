
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.storage.pgvector_store import PgVectorStore
from src.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_pgvector():
    print("🐘 Verifying PgVector Implementation...")
    
    # Force postgres backend just in case
    settings.VECTOR_BACKEND = "postgres"
    
    store = PgVectorStore(table_name="test_vectors")
    
    # 1. Health Check
    if not await store.health_check():
        print("❌ Health check failed! Is Postgres running?")
        return
    print("✅ Health check passed")

    # 2. Add Chunk
    chunks = [{"content": "This is a test chunk related to apples.", "metadata": {"source": "test_file.txt", "name": "chunk1"}}]
    # Fake embedding (random float list of correct dimension)
    import random
    dim = settings.PG_VECTOR_DIMENSION
    embeddings = [[random.random() for _ in range(dim)]]
    
    await store.add_chunks(chunks, embeddings)
    print("✅ Added test chunk")

    # 3. Search
    results = await store.search(query_embedding=embeddings[0], top_k=1)
    if results and results[0].content == chunks[0]["content"]:
        print(f"✅ Search successful: Found '{results[0].content}' (score={results[0].score:.4f})")
    else:
        print("❌ Search failed!")

    # 4. Count
    count = await store.count()
    print(f"✅ Count: {count}")

    # 5. Delete by Source
    deleted = await store.delete_by_source("test_file.txt")
    print(f"✅ Deleted {deleted} chunks by source")

    # 6. Verify Deletion
    count_after = await store.count()
    if count_after == 0:
        print("✅ Deletion verified (Count is 0)")
    else:
        print(f"❌ Deletion failed! Count is {count_after}")

    # Cleanup table
    await store.clear()
    print("✅ Cleanup complete")

if __name__ == "__main__":
    asyncio.run(verify_pgvector())
