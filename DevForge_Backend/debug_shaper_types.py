
import sys
import os
# Ensure project root is in path
sys.path.append(os.getcwd())

try:
    from src.storage.base_store import ChunkResult
    from src.agents.rag.context_shaper import ContextShaper

    # Mock chunks
    c1 = ChunkResult(id="1", content="test", metadata={"role": "supporting", "score": 0.5})
    c2 = ChunkResult(id="2", content="test2", metadata={"role": "supporting", "score": 0.9})

    shaper = ContextShaper()
    result = shaper.shape_context([c1, c2])

    print(f"Result type: {type(result)}")
    if result:
        print(f"Item type: {type(result[0])}")
        print(f"First item: {result[0]}")
    else:
        print("Empty result")

except Exception as e:
    print(f"CRASH: {e}")
