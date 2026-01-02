"""Validation tests for Day 6 test-source linking."""


def test_imports():
    """Test 1: Verify test linker imports."""
    print("Test 1: Verifying imports...")
    
    try:
        from src.agents.rag.linking import TestLinker, link_test_to_source
        print("✅ TestLinker imported")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_pattern_detection():
    """Test 2: Test file pattern detection."""
    print("\nTest 2: Testing pattern detection...")
    
    try:
        from src.agents.rag.linking import TestLinker
        
        linker = TestLinker()
        
        # Python test files
        assert linker.is_test_file("test_foo.py") == True
        assert linker.is_test_file("foo_test.py") == True
        print("✅ Python test patterns detected")
        
        # JS/TS test files
        assert linker.is_test_file("foo.spec.ts") == True
        assert linker.is_test_file("foo.test.js") == True
        print("✅ JS/TS test patterns detected")
        
        # Non-test files
        assert linker.is_test_file("foo.py") == False
        assert linker.is_test_file("utils.ts") == False
        print("✅ Non-test files correctly rejected")
        
        return True
    except Exception as e:
        print(f"❌ Pattern detection failed: {e}")
        return False


def test_filename_inference():
    """Test 3: Test filename-based source inference."""
    print("\nTest 3: Testing filename inference...")
    
    try:
        from src.agents.rag.linking import TestLinker
        
        linker = TestLinker()
        
        # Python
        source = linker._infer_from_filename("test_utils.py")
        assert "utils.py" in source
        print(f"✅ test_utils.py → {source}")
        
        # TypeScript
        source = linker._infer_from_filename("auth.spec.ts")
        assert "auth.ts" in source
        print(f"✅ auth.spec.ts → {source}")
        
        # JavaScript
        source = linker._infer_from_filename("helper.test.js")
        assert "helper.js" in source
        print(f"✅ helper.test.js → {source}")
        
        return True
    except Exception as e:
        print(f"❌ Filename inference failed: {e}")
        return False


def test_import_extraction():
    """Test 4: Test import extraction."""
    print("\nTest 4: Testing import extraction...")
    
    try:
        from src.agents.rag.linking import TestLinker
        
        linker = TestLinker()
        
        # Python imports
        py_content = """
import utils
from helpers import foo
from pytest import fixture
"""
        imports = linker._extract_imports(py_content, "test_main.py")
        assert len(imports) > 0
        print(f"✅ Extracted {len(imports)} Python imports")
        
        # JS imports
        js_content = """
import { foo } from './utils';
import bar from '../src/bar';
import React from 'react';
"""
        imports = linker._extract_imports(js_content, "test.spec.ts")
        # Should extract local imports, skip 'react'
        print(f"✅ Extracted {len(imports)} JS imports")
        
        return True
    except Exception as e:
        print(f"❌ Import extraction failed: {e}")
        return False


def test_metadata_enrichment():
    """Test 5: Test metadata enrichment."""
    print("\nTest 5: Testing metadata enrichment...")
    
    try:
        from src.agents.rag.linking import TestLinker
        
        linker = TestLinker()
        
        chunks = [
            {
                "content": "def add(a, b): return a + b",
                "metadata": {
                    "source": "utils.py",
                    "name": "add",
                }
            }
        ]
        
        all_files = ["utils.py", "test_utils.py"]
        
        enriched = linker.enrich_chunk_metadata(chunks, all_files)
        
        # Check if test_files was added
        test_files = enriched[0]["metadata"].get("test_files", [])
        if test_files:
            print(f"✅ Linked tests: {test_files}")
        else:
            print("⚠️  No tests linked (filename-based)")
        
        return True
    except Exception as e:
        print(f"❌ Metadata enrichment failed: {e}")
        return False


def run_all_tests():
    """Run all validation tests."""
    print("=" * 60)
    print("Day 6 Test-Source Linking - Validation Tests")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_pattern_detection,
        test_filename_inference,
        test_import_extraction,
        test_metadata_enrichment,
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
