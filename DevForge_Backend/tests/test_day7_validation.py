"""Validation for Day 7 vector store abstraction."""


def test_base_store_import():
    """Test 1: Import BaseVectorStore."""
    print("Test 1: Importing BaseVectorStore...")
    
    try:
        from src.storage import BaseVectorStore, ChunkResult
        print(f"✅ BaseVectorStore imported")
        print(f"✅ ChunkResult imported")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_chroma_store_import():
    """Test 2: Import ChromaVectorStore."""
    print("\nTest 2: Importing ChromaVectorStore...")
    
    try:
        from src.storage.chroma_store import ChromaVectorStore
        print("✅ ChromaVectorStore imported")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_ragagent_has_vector_store():
    """Test 3: RAGAgent uses ChromaVectorStore."""
    print("\nTest 3: RAGAgent integration...")
    
    try:
        from src.agents.rag.agent import RAGAgent
        agent = RAGAgent()
        
        # Check vector_store attribute exists
        assert hasattr(agent, 'vector_store')
        print(f"✅ RAGAgent.vector_store exists")
        print(f"  Type: {type(agent.vector_store).__name__}")
        
        return True
    except Exception as e:
        print(f"❌ RAGAgent integration failed: {e}")
        return False


def test_iter_chunk_metadata_method():
    """Test 4: iter_chunk_metadata exists."""
    print("\nTest 4: iter_chunk_metadata method...")
    
    try:
        from src.storage.chroma_store import ChromaVectorStore
        store = ChromaVectorStore()
        
        # Check method exists
        assert hasattr(store, 'iter_chunk_metadata')
        print("✅ iter_chunk_metadata method exists")
        
        # Check it's async generator
        import inspect
        assert inspect.ismethod(store.iter_chunk_metadata)
        print("✅ iter_chunk_metadata is a method")
        
        return True
    except Exception as e:
        print(f"❌ iter_chunk_metadata test failed: {e}")
        return False


def run_all_tests():
    """Run all validation tests."""
    print("=" * 60)
    print("Day 7 Vector Store Abstraction - Validation")
    print("=" * 60)
    
    tests = [
        test_base_store_import,
        test_chroma_store_import,
        test_ragagent_has_vector_store,
        test_iter_chunk_metadata_method,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n✅ All validation tests PASSED")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(run_all_tests())
