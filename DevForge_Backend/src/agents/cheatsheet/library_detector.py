"""Detect libraries used in code"""

import re
from typing import List, Dict, Pattern


# Library signatures (expanded)
LIBRARY_SIGNATURES = {
    # Data Science
    'pandas': ['import pandas', 'pd.DataFrame', 'pd.read_csv', '.groupby(', '.merge(', 'pd.concat'],
    'numpy': ['import numpy', 'np.array', 'np.mean', 'np.random', 'np.sum'],
    'matplotlib': ['import matplotlib', 'plt.plot', 'plt.show', 'plt.figure'],
    'scikit-learn': ['from sklearn', 'fit(', 'predict(', 'train_test_split'],
    
    # Web Frameworks
    'fastapi': ['from fastapi', 'FastAPI(', '@app.get', '@app.post', 'Depends('],
    'flask': ['from flask', 'Flask(__name__)', '@app.route', 'render_template'],
    'django': ['from django', 'models.Model', 'views.View'],
    
    # Data Validation
    'pydantic': ['from pydantic', 'BaseModel', 'Field(', 'validator', '@field_validator'],
    
    # Async
    'asyncio': ['import asyncio', 'async def', 'await ', 'asyncio.gather', 'asyncio.create_task'],
    'aiohttp': ['import aiohttp', 'ClientSession', 'aiohttp.web'],
    
    # Database
    'sqlalchemy': ['from sqlalchemy', 'declarative_base', 'Column(', 'relationship(', 'Session'],
    
    # HTTP Clients
    'requests': ['import requests', 'requests.get', 'requests.post'],
    'httpx': ['import httpx', 'httpx.Client', 'httpx.AsyncClient'],
    
    # Testing
    'pytest': ['import pytest', '@pytest.fixture', '@pytest.mark'],
}


class LibraryDetector:
    """Optimized library detection with compiled regex"""
    
    def __init__(self):
        # Compile patterns once for performance
        self.patterns: Dict[str, Pattern] = {}
        for lib, signatures in LIBRARY_SIGNATURES.items():
            # Escape special regex chars and join with OR
            pattern = '|'.join(re.escape(sig) for sig in signatures)
            self.patterns[lib] = re.compile(pattern)
    
    def detect(self, code_blocks: List[str]) -> List[str]:
        """
        Detect libraries across all code blocks.
        
        Args:
            code_blocks: List of code strings to analyze
            
        Returns:
            Sorted list of library names
        """
        if not code_blocks:
            return []
        
        # Combine all blocks
        combined_code = '\n'.join(code_blocks)
        
        # Check each library
        detected = []
        for lib, pattern in self.patterns.items():
            if pattern.search(combined_code):
                detected.append(lib)
        
        return sorted(detected)  # Consistent ordering


# Singleton instance
_detector = LibraryDetector()


def detect_libraries(code_blocks: List[str]) -> List[str]:
    """Convenience function using singleton detector"""
    return _detector.detect(code_blocks)
