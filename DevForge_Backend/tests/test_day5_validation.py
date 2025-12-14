"""Validation tests for Day 5 code graph."""


def test_imports():
    """Test 1: Verify code graph imports."""
    print("Test 1: Verifying code graph imports...")
    
    try:
        from src.agents.rag.graph import CodeGraph
        from src.agents.rag.graph.code_graph import parse_qualified_id, build_qualified_id
        print("✅ CodeGraph imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_qid_format():
    """Test 2: Test QID parsing and building."""
    print("\nTest 2: Testing QID format...")
    
    try:
        from src.agents.rag.graph.code_graph import parse_qualified_id, build_qualified_id
        
        # Test building
        qid = build_qualified_id("test.py", "add_function")
        assert qid == "test.py::add_function", f"Expected test.py::add_function, got {qid}"
        print(f"✅ Built QID: {qid}")
        
        # Test parsing
        file_path, entity = parse_qualified_id(qid)
        assert file_path == "test.py"
        assert entity == "add_function"
        print(f"✅ Parsed QID: file={file_path}, entity={entity}")
        
        # Test invalid QID
        try:
            parse_qualified_id("invalid:single:colon")
            print("❌ Should have failed on single colon")
            return False
        except ValueError:
            print("✅ Correctly rejected single-colon QID")
        
        return True
    except Exception as e:
        print(f"❌ QID test failed: {e}")
        return False


def test_graph_operations():
    """Test 3: Test graph node/edge operations."""
    print("\nTest 3: Testing graph operations...")
    
    try:
        from src.agents.rag.graph import CodeGraph
        
        graph = CodeGraph()
        
        # Add nodes
        graph.add_node("utils.py::helper", name="helper", chunk_type="function")
        graph.add_node("utils.py::process", name="process", chunk_type="function")
        
        # Add edge
        graph.add_edge("utils.py::process", "utils.py::helper", relation="calls")
        
        assert graph.size() == 2
        print(f"✅ Graph has {graph.size()} nodes")
        
        # Test metadata
        meta = graph.get_metadata("utils.py::helper")
        assert meta is not None
        assert meta["name"] == "helper"
        print(f"✅ Metadata retrieved: {meta['name']}")
        
        return True
    except Exception as e:
        print(f"❌ Graph operations failed: {e}")
        return False


def test_bfs_traversal():
    """Test 4: Test BFS traversal."""
    print("\nTest 4: Testing BFS traversal...")
    
    try:
        from src.agents.rag.graph import CodeGraph
        
        graph = CodeGraph()
        
        # Build a simple graph:
        # A → B → C
        # A → D
        graph.add_node("test.py::A", name="A")
        graph.add_node("test.py::B", name="B")
        graph.add_node("test.py::C", name="C")
        graph.add_node("test.py::D", name="D")
        
        graph.add_edge("test.py::A", "test.py::B")
        graph.add_edge("test.py::A", "test.py::D")
        graph.add_edge("test.py::B", "test.py::C")
        
        # Test BFS from A
        related = graph.get_related("test.py::A", depth=1, max_results=10)
        assert "test.py::B" in related
        assert "test.py::D" in related
        print(f"✅ BFS depth=1: {related}")
        
        # Test depth=2
        related2 = graph.get_related("test.py::A", depth=2, max_results=10)
        assert "test.py::C" in related2
        print(f"✅ BFS depth=2: {related2}")
        
        # Test max_results
        related_limited = graph.get_related("test.py::A", depth=2, max_results=2)
        assert len(related_limited) <= 2
        print(f"✅ Limited results: {related_limited}")
        
        return True
    except Exception as e:
        print(f"❌ BFS traversal failed: {e}")
        return False


def test_chunk_batch():
    """Test 5: Test adding chunks in batch."""
    print("\nTest 5: Testing chunk batch addition...")
    
    try:
        from src.agents.rag.graph import CodeGraph
        
        graph = CodeGraph()
        
        chunks = [
            {
                "content": "def hello(): pass",
                "metadata": {
                    "source": "test.py",
                    "name": "hello",
                    "chunk_type": "function",
                    "calls": ["print"],
                }
            },
            {
                "content": "def world(): pass",
                "metadata": {
                    "source": "test.py",
                    "name": "world",
                    "chunk_type": "function",
                    "calls": ["hello"],
                }
            }
        ]
        
        graph.add_chunks_batch(chunks)
        
        assert graph.size() == 2
        print(f"✅ Added batch: {graph.size()} nodes")
        
        # Verify QIDs were built correctly with ::
        meta = graph.get_metadata("test.py::hello")
        assert meta is not None
        print("✅ QID format correct (::)")
        
        return True
    except Exception as e:
        print(f"❌ Chunk batch test failed: {e}")
        return False


def test_ragagent_integration():
    """Test 6: Test RAGAgent code_graph property."""
    print("\nTest 6: Testing RAGAgent integration...")
    
    try:
        from src.agents.rag.agent import RAGAgent
        
        agent = RAGAgent()
        
        # Access code_graph property (should lazy-init)
        graph = agent.code_graph
        assert graph is not None
        print("✅ RAGAgent.code_graph lazy-initialized")
        
        # Verify it's the same instance
        graph2 = agent.code_graph
        assert graph is graph2
        print("✅ Same instance returned (cached)")
        
        return True
    except Exception as e:
        print(f"❌ RAGAgent integration failed: {e}")
        return False


def run_all_tests():
    """Run all validation tests."""
    print("=" * 60)
    print("Day 5 Code Graph - Validation Tests")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_qid_format,
        test_graph_operations,
        test_bfs_traversal,
        test_chunk_batch,
        test_ragagent_integration,
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
