"""Tests for cheatsheet context parser"""

import pytest
from src.agents.cheatsheet.context_parser import parse_code_context
from tests.fixtures.code_samples import (
    SAMPLE_SIMPLE,
    SAMPLE_MULTI_BLOCK,
    SAMPLE_EMPTY,
    SAMPLE_NO_SEPARATOR
)


def test_empty_context():
    """Test parsing empty context"""
    result = parse_code_context("")
    assert result['blocks'] == []
    assert result['total_lines'] == 0
    assert result['has_multiple_blocks'] == False


def test_single_block():
    """Test parsing single block without separator"""
    result = parse_code_context(SAMPLE_NO_SEPARATOR)
    assert len(result['blocks']) == 1
    assert result['blocks'][0] == "print('hello')"
    assert result['has_multiple_blocks'] == False


def test_multi_block():
    """Test parsing multi-block context"""
    result = parse_code_context(SAMPLE_MULTI_BLOCK)
    assert len(result['blocks']) == 2
    assert 'fibonacci' in result['blocks'][0]
    assert 'DataProcessor' in result['blocks'][1]
    assert result['has_multiple_blocks'] == True


def test_removes_language_prefix():
    """Test that language prefix is removed"""
    code = "// python\ndef test():\n    pass"
    result = parse_code_context(code)
    assert not result['blocks'][0].startswith('//')
    assert result['blocks'][0].startswith('def test')


def test_total_lines_count():
    """Test that total lines are counted correctly"""
    result = parse_code_context(SAMPLE_SIMPLE)
    # "def add(a, b):\n    return a + b" = 2 lines
    assert result['total_lines'] == 2
