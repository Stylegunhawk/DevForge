import asyncio
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Mock settings if needed (or rely on existing)
from src.tools.rag.tools import read_document, chunk_document, ingest_documents

async def main():
    # 1. Create a dummy .py file
    test_file = Path("test_ingest.py").resolve()
    with open(test_file, "w") as f:
        f.write("""
def hello_world():
    \"\"\"This is a test function.\"\"\"
    print("Hello, World!")

class TestClass:
    def method(self):
        pass
""")
    
    print(f"Created test file: {test_file}")
    
    try:
        # 2. Test read_document
        print("\n--- Testing read_document ---")
        content = await read_document(str(test_file))
        print(f"Read content length: {len(content)}")
        print(f"Content preview: {content[:50]}...")
        
        # 3. Test chunk_document
        print("\n--- Testing chunk_document ---")
        chunks = chunk_document(content, str(test_file))
        print(f"Generated {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            print(f"Chunk {i} type: {chunk.metadata.get('chunk_type', 'unknown')}")
            print(f"Chunk {i} source: {chunk.metadata.get('source')}")
            print(f"Chunk {i} content: {chunk.page_content[:30]}...")

        # 4. Test ingest_documents (mocking vector store or just running it)
        # We might not be able to fully run ingest if Chroma/Ollama not ready, but let's try
        print("\n--- Testing ingest_documents ---")
        # Just check if it runs without error (it might fail on Ollama if not running, but that's a different error)
        # We expect it to NOT fail with "Unsupported file type" or "0 chunks" (before embedding)
        
        # To avoid actual embedding call which might be slow or fail, we can rely on chunk_document result
        # But let's run it to see if it calls the right things
        # Note: This will try to contact Ollama and Chroma.
    
    except Exception as e:
        print(f"\n!!! ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()

if __name__ == "__main__":
    asyncio.run(main())
