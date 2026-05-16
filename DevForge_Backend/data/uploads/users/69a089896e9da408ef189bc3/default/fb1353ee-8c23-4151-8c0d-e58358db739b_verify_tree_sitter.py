
import sys
import logging
from pathlib import Path

# Configure logging to stdout
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verification")

def check_dependencies():
    logger.info("Checking tree-sitter dependencies...")
    try:
        import tree_sitter
        logger.info(f"SUCCESS: tree-sitter found (version: {getattr(tree_sitter, '__version__', 'unknown')})")
    except ImportError:
        logger.error("FAILURE: tree-sitter NOT found")

    try:
        import tree_sitter_python
        logger.info("SUCCESS: tree-sitter-python found")
    except ImportError:
        logger.error("FAILURE: tree-sitter-python NOT found")

def check_code_chunker():
    logger.info("\nChecking CodeChunker behavior...")
    try:
        # Add src to path
        project_root = Path(__file__).parent
        sys.path.append(str(project_root))
        
        from src.agents.rag.chunking.code_chunker import CodeChunker
        from src.tools.rag.tools import chunk_document, getSupportExtensions
    except ImportError as e:
        logger.error(f"FAILURE: Could not import CodeChunker or related tools: {e}")
        # Try to import just CodeChunker
        try:
            from src.agents.rag.chunking.code_chunker import CodeChunker
            chunker = CodeChunker()
            logger.info("CodeChunker instantiated")
            
            # Test simple chunking
            code = "def foo():\n    pass\n\nprint('hello')"
            chunks = chunker.chunk(code, "test.py")
            logger.info(f"Chunk count for test.py: {len(chunks)}")
            for i, c in enumerate(chunks):
                logger.info(f"Chunk {i}: type={c['metadata']['chunk_type']}, name={c['metadata']['name']}")
                
        except Exception as inner_e:
             logger.error(f"Failed to instantiate/run CodeChunker: {inner_e}")
             
        return

if __name__ == "__main__":
    check_dependencies()
    check_code_chunker()
