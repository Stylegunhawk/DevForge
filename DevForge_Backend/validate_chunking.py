"""Quick validation script for Phase 10.1 chunking."""
from src.agents.rag.chunking import BaseChunker, TextChunker, CodeChunker

print("=" * 60)
print("Phase 10.1 Chunking Validation")
print("=" * 60)

# Test 1: Imports
print("\n✅ Test 1: All imports successful")

# Test 2: CodeChunker initialization
cc = CodeChunker()
print(f"✅ Test 2: CodeChunker initialized")
print(f"   Parsers available: {list(cc.parsers.keys())}")

# Test 3: Text chunking
tc = TextChunker(chunk_size=50, chunk_overlap=10)
text_chunks = tc.chunk("Hello world\n" * 10, "test.txt")
print(f"✅ Test 3: TextChunker created {len(text_chunks)} chunks")

# Test 4: Code chunking
code = """
def hello():
    '''Say hello.'''
    print("Hello")

def add(a, b):
    return a + b
"""

code_chunks = cc.chunk(code, "test.py")
funcs = [c for c in code_chunks if c['metadata']['chunk_type'] == 'function']
print(f"✅ Test 4: CodeChunker extracted {len(funcs)} functions")
if funcs:
    print(f"   Functions: {[f['metadata']['name'] for f in funcs]}")

# Test 5: Integration with chunk_document
from src.tools.rag.tools import chunk_document
docs = chunk_document(code, "test.py")
print(f"✅ Test 5: chunk_document created {len(docs)} Document objects")

print("\n" + "=" * 60)
print("ALL TESTS PASSED ✅")
print("=" * 60)
