"""Validation tests for Phase 10.1 async RAG API endpoints."""

import json


def test_imports():
    """Test 1: Verify all imports work."""
    print("Test 1: Verifying imports...")
    
    try:
        from src.api.rag_models import IngestAsyncRequest, IngestAsyncResponse, TaskStatusResponse
        from src.api.routers import ingest_documents_async, get_task_status
        from src.workers.tasks.rag_tasks import async_ingest_documents
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_request_model():
    """Test 2: Verify IngestAsyncRequest validation."""
    print("\nTest 2: Validating request model...")
    
    from src.api.rag_models import IngestAsyncRequest
    
    # Valid request
    try:
        req = IngestAsyncRequest(
            file_paths=["test.py", "test2.py"],
            collection_name="test_collection",
            embed_model="nomic-embed-text"
        )
        assert len(req.file_paths) == 2
        assert req.collection_name == "test_collection"
        print("✅ Valid request model")
    except Exception as e:
        print(f"❌ Request model failed: {e}")
        return False
    
    # Invalid request (empty file_paths)
    try:
        req = IngestAsyncRequest(file_paths=[])
        print("❌ Should have failed with empty file_paths")
        return False
    except Exception:
        print("✅ Correctly rejected empty file_paths")
    
    return True


def test_response_model():
    """Test 3: Verify response models."""
    print("\nTest 3: Validating response models...")
    
    from src.api.rag_models import IngestAsyncResponse, TaskStatusResponse
    
    try:
        # IngestAsyncResponse
        resp = IngestAsyncResponse(
            task_id="test-123",
            status="queued",
            collection="test_collection",
            total_files=5
        )
        assert resp.task_id == "test-123"
        print("✅ IngestAsyncResponse valid")
        
        # TaskStatusResponse
        status = TaskStatusResponse(
            task_id="test-123",
            status="SUCCESS",
            result={"chunks_created": 100}
        )
        assert status.status == "SUCCESS"
        print("✅ TaskStatusResponse valid")
        
        return True
    except Exception as e:
        print(f"❌ Response model failed: {e}")
        return False


def test_architecture_compliance():
    """Test 4: Verify no forbidden patterns exist."""
    print("\nTest 4: Checking architecture compliance...")
    
    import inspect
    from src.api import routers
    
    # Check: No /rag/graph/context endpoint
    router_source = inspect.getsource(routers)
    if "/rag/graph/context" in router_source:
        print("❌ FORBIDDEN: /rag/graph/context endpoint found!")
        return False
    print("✅ No forbidden /rag/graph/context endpoint")
    
    # Check: Endpoints delegate to Celery tasks
    if "async_ingest_documents.delay" not in router_source:
        print("❌ Endpoint doesn't delegate to Celery task")
        return False
    print("✅ Endpoints delegate to Celery tasks")
    
    # Check: Uses RAGAgent (via task)
    from src.workers.tasks import rag_tasks
    task_source = inspect.getsource(rag_tasks)
    if "from src.agents.rag.agent import RAGAgent" not in task_source:
        print("❌ Task doesn't import RAGAgent")
        return False
    print("✅ Task imports RAGAgent")
    
    return True


def run_all_tests():
    """Run all validation tests."""
    print("=" * 60)
    print("Day 2 API Endpoints - Validation Tests")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_request_model,
        test_response_model,
        test_architecture_compliance,
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
        print("\n❌ Some tests FAILED")
        return 1


if __name__ == "__main__":
    exit(run_all_tests())
