"""Tests for library_detector"""

import pytest
from src.agents.cheatsheet.library_detector import detect_libraries
from tests.fixtures.code_samples import (
    SAMPLE_SIMPLE,
    SAMPLE_PANDAS,
    SAMPLE_FASTAPI,
    SAMPLE_ASYNC
)


def test_no_libraries():
    """Test code with no libraries"""
    result = detect_libraries(["def add(a, b):\n    return a + b"])
    assert result == []


def test_pandas_detection():
    """Test pandas library detection"""
    result = detect_libraries([SAMPLE_PANDAS])
    assert 'pandas' in result


def test_multi_library():
    """Test detection of multiple libraries"""
    code = """
import pandas as pd
from fastapi import FastAPI
import numpy as np
"""
    result = detect_libraries([code])
    assert 'pandas' in result
    assert 'fastapi' in result
    assert 'numpy' in result


def test_async_detection():
    """Test async library detection"""
    result = detect_libraries([SAMPLE_ASYNC])
    assert 'asyncio' in result
    assert 'aiohttp' in result


def test_empty_blocks():
    """Test handling empty code blocks"""
    result = detect_libraries([])
    assert result == []
    
    result = detect_libraries([''])
    assert result == []


def test_fastapi_pydantic():
    """Test FastAPI and Pydantic detection"""
    result = detect_libraries([SAMPLE_FASTAPI])
    assert 'fastapi' in result
    assert 'pydantic' in result


def test_sorted_output():
    """Test that output is sorted"""
    code = """
import pytest
import pandas as pd
from fastapi import FastAPI
"""
    result = detect_libraries([code])
    # Should be alphabetically sorted
    assert result == sorted(result)
