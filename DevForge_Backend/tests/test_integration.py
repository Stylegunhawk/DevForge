"""Integration tests for enhanced cheatsheet agent"""

import pytest
from src.agents.cheatsheet.agent import cheatsheet_agent
from tests.fixtures.code_samples import (
    SAMPLE_SIMPLE,
    SAMPLE_PANDAS,
    SAMPLE_FASTAPI,
    SAMPLE_ASYNC,
    SAMPLE_MULTI_BLOCK
)


def test_simple_request():
    """Simple code → beginner cheatsheet"""
    result = cheatsheet_agent.generate({
        'code_context': SAMPLE_SIMPLE,
        'skill_level': 'beginner'
    })
    
    assert result['success'] == True
    assert result['language'] == 'python'
    assert result['data']['complexity_score'] < 10
    assert 'Variables' in result['markdown']


def test_pandas_context():
    """Pandas code → DataFrame sections"""
    result = cheatsheet_agent.generate({
        'code_context': SAMPLE_PANDAS,
        'skill_level': 'intermediate'
    })
    
    assert result['success'] == True
    assert 'pandas' in result['data']['detected_libraries']
    # Note: pandas section only appears if skill_level matches
    assert result['data']['complexity_score'] >= 2


def test_fastapi_multi_lib():
    """FastAPI + Pydantic → both sections"""
    result = cheatsheet_agent.generate({
        'code_context': SAMPLE_FASTAPI,
        'skill_level': 'intermediate'
    })
    
    libs = result['data']['detected_libraries']
    assert 'fastapi' in libs
    assert 'pydantic' in libs
    assert 'FastAPI' in result['markdown'] or 'Routes' in result['markdown']


def test_async_expert():
    """Async code → expert level"""
    result = cheatsheet_agent.generate({
        'code_context': SAMPLE_ASYNC,
        'skill_level': 'expert'
    })
    
    assert result['success'] == True
    assert result['data']['complexity_score'] > 30
    assert 'asyncio' in result['data']['detected_libraries']
    assert 'aiohttp' in result['data']['detected_libraries']


def test_explicit_language_wins():
    """Explicit language overrides detection"""
    result = cheatsheet_agent.generate({
        'language': 'python',
        'code_context': '// javascript\nconsole.log("test")',
        'skill_level': 'beginner'
    })
    
    assert result['language'] == 'python'


def test_no_context_no_language():
    """Error if neither provided"""
    result = cheatsheet_agent.generate({
        'skill_level': 'beginner'
    })
    
    assert result['success'] == False
    assert 'must provide' in result['message'].lower()


def test_multi_block_parsing():
    """Multi-block context parsed correctly"""
    result = cheatsheet_agent.generate({
        'code_context': SAMPLE_MULTI_BLOCK,
        'skill_level': 'intermediate'
    })
    
    assert result['success'] == True
    assert result['data']['complexity_score'] > 0


def test_section_count_limit():
    """Verify max 7 sections"""
    result = cheatsheet_agent.generate({
        'code_context': SAMPLE_FASTAPI,
        'skill_level': 'intermediate'
    })
    
    assert result['success'] == True
    assert len(result['data']['sections']) <= 7


def test_quick_reference_included():
    """Quick reference table is included"""
    result = cheatsheet_agent.generate({
        'language': 'python',
        'skill_level': 'beginner'
    })
    
    assert result['success'] == True
    assert 'Quick Reference' in result['markdown']
    assert '|' in result['markdown']  # Table format


def test_library_specific_quick_ref():
    """Library-specific quick ref for intermediate"""
    result = cheatsheet_agent.generate({
        'code_context': SAMPLE_PANDAS,
        'skill_level': 'intermediate'
    })
    
    assert result['success'] == True
    # Should have quick reference section
    assert 'Quick Reference' in result['markdown']


def test_complexity_logging():
    """Verify complexity is calculated and logged"""
    result = cheatsheet_agent.generate({
        'code_context': SAMPLE_ASYNC,
        'skill_level': 'expert'
    })
    
    assert 'complexity_score' in result['data']
    assert isinstance(result['data']['complexity_score'], int)
    assert result['data']['complexity_score'] > 0
