"""Test Python intermediate and expert cheatsheets"""

import pytest
from src.agents.cheatsheet.agent import cheatsheet_agent


def test_python_intermediate_no_libraries():
    """Test Python intermediate without library detection"""
    result = cheatsheet_agent.generate({
        'language': 'python',
        'skill_level': 'intermediate'
    })
    
    assert result['success'] == True
    assert result['skill_level'] == 'intermediate'
    assert len(result['data']['sections']) > 0
    # Should have intermediate sections like data_structures, file_io, etc.
    section_titles = [s['title'] for s in result['data']['sections']]
    assert any('Data' in title or 'File' in title or 'Error' in title 
               for title in section_titles), "Should have intermediate content"


def test_python_expert_no_libraries():
    """Test Python expert without library detection"""
    result = cheatsheet_agent.generate({
        'language': 'python',
        'skill_level': 'expert'
    })
    
    assert result['success'] == True
    assert result['skill_level'] == 'expert'
    assert len(result['data']['sections']) > 0
    # Should have expert sections like decorators, generators, etc.
    section_titles = [s['title'] for s in result['data']['sections']]
    assert any('Decorator' in title or 'Generator' in title or 'Context' in title
               for title in section_titles), "Should have expert content"


def test_intermediate_with_medium_complexity():
    """Test that medium complexity code gets intermediate sections"""
    code = '''
import os
import json

def load_config(filename):
    with open(filename, 'r') as f:
        return json.load(f)

class ConfigManager:
    def __init__(self):
        self.config = {}
'''
    result = cheatsheet_agent.generate({
        'code_context': code,
        'skill_level': 'intermediate'
    })
    
    assert result['success'] == True
    assert result['data']['complexity_score'] >= 10
    assert len(result['data']['sections']) > 0


def test_expert_with_high_complexity():
    """Test that high complexity code gets expert sections"""
    code = '''
from functools import wraps
import asyncio

def timer(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        return result
    return wrapper

class AsyncIterator:
    async def __aiter__(self):
        for i in range(10):
            yield i
'''
    result = cheatsheet_agent.generate({
        'code_context': code,
        'skill_level': 'expert'
    })
    
    assert result['success'] == True
    assert result['data']['complexity_score'] >= 30
    assert len(result['data']['sections']) > 0
