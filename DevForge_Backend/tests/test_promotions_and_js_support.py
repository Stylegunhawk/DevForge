"""Verification for Phase B (Promotion) and Phase C (JS Expansion)"""
import pytest
from unittest.mock import patch, Mock
import os

from src.agents.cheatsheet.agent import CheatsheetAgent
from src.agents.cheatsheet.config import config
from src.agents.cheatsheet.promotion_tracker import tracker

@pytest.fixture
def agent():
    return CheatsheetAgent()

@pytest.fixture
def enable_enrichment():
    original = config.ENABLED
    config.ENABLED = True
    # Patch Env
    with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
        yield
    config.ENABLED = original

# --- Phase C: JS/TS Support Tests ---

def test_generate_javascript_cheatsheet(agent):
    """Should detect JS and use JS templates"""
    result = agent.generate({
        'code_context': 'const x = 10; function add(a, b) { return a + b; }',
        'skill_level': 'beginner'
    })
    
    assert result['success'] is True
    assert result['language'] == 'javascript'
    assert 'Variables & Data Types' in result['markdown']
    assert 'Let vs Const' in result['markdown']

def test_generate_react_cheatsheet(agent):
    """Should detect React and include Hooks"""
    result = agent.generate({
        'code_context': 'import React, { useState } from "react";',
        'skill_level': 'beginner'
    })
    
    assert result['success'] is True
    assert 'react' in result['data']['detected_libraries']
    assert 'React Hooks' in result['markdown'] # From JS_LIBRARY_SECTIONS

# --- Phase B: Promotion & Telemetry Tests ---

def test_promotion_telemetry_fields(enable_enrichment, agent):
    """Response should include confidence and promotable bool"""
    
    # Mock efficient enrichment
    mock_resp = Mock()
    mock_resp.content = [Mock(text="### Tip\nPromote me")]
    mock_resp.usage = Mock(output_tokens=10)
    
    with patch('src.agents.cheatsheet.section_enricher.Anthropic') as mock_llm:
        mock_llm.return_value.messages.create.return_value = mock_resp
        
        result = agent.generate({
            'code_context': 'from langchain import StateGraph',
            'skill_level': 'intermediate',
            'conversation_history': 'latest',
            'language': 'python'
        })
        
    data = result['data']['enrichment']
    assert 'confidence' in data
    assert 'promotable' in data
    assert isinstance(data['promotable'], bool)

def test_promotion_tracker_logic():
    """Tracker should flag promotion after threshold"""
    # Reset
    tracker._counts.clear()
    tracker.PROMOTION_THRESHOLD = 2
    
    lib = 'test-lib'
    sec = 'Test Section'
    
    # 1st time
    tracker.record_enrichment(lib, sec)
    assert not tracker.should_promote(lib, sec)
    
    # 2nd time (Threshold reached)
    tracker.record_enrichment(lib, sec)
    assert tracker.should_promote(lib, sec)
