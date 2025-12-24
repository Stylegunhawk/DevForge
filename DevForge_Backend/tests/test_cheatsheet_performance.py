"""Performance benchmarks for cheatsheet agent"""

import time
import pytest
from src.agents.cheatsheet.agent import cheatsheet_agent
from tests.fixtures.code_samples import (
    SAMPLE_SIMPLE,
    SAMPLE_FASTAPI,
    SAMPLE_ASYNC
)


def test_response_time_simple():
    """Simple code should be < 300ms"""
    start = time.time()
    result = cheatsheet_agent.generate({
        'code_context': SAMPLE_SIMPLE,
        'skill_level': 'beginner'
    })
    elapsed = time.time() - start
    
    assert elapsed < 0.3  # 300ms
    assert result['success'] == True


def test_response_time_complex():
    """Complex code should be < 500ms"""
    start = time.time()
    result = cheatsheet_agent.generate({
        'code_context': SAMPLE_FASTAPI,
        'skill_level': 'intermediate'
    })
    elapsed = time.time() - start
    
    assert elapsed < 0.5  # 500ms
    assert result['success'] == True


def test_response_time_expert():
    """Expert level should be < 500ms"""
    start = time.time()
    result = cheatsheet_agent.generate({
        'code_context': SAMPLE_ASYNC,
        'skill_level': 'expert'
    })
    elapsed = time.time() - start
    
    assert elapsed < 0.5  # 500ms
    assert result['success'] == True


def test_response_time_no_context():
    """No context (explicit language) should be < 200ms"""
    start = time.time()
    result = cheatsheet_agent.generate({
        'language': 'python',
        'skill_level': 'beginner'
    })
    elapsed = time.time() - start
    
    assert elapsed < 0.2  # 200ms
    assert result['success'] == True


def test_average_response_time():
    """Average of 10 requests should be < 400ms"""
    times = []
    
    for _ in range(10):
        start = time.time()
        cheatsheet_agent.generate({
            'code_context': SAMPLE_FASTAPI,
            'skill_level': 'intermediate'
        })
        times.append(time.time() - start)
    
    avg_time = sum(times) / len(times)
    assert avg_time < 0.4  # 400ms average
