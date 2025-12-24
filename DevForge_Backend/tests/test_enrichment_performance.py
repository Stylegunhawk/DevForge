"""Performance tests for enrichment."""
import pytest
import time
from unittest.mock import patch, Mock
import os

from src.agents.cheatsheet.agent import CheatsheetAgent
from src.agents.cheatsheet.config import config

@pytest.fixture
def enable_enrichment():
    original = config.ENABLED
    config.ENABLED = True
    # Patch Environment for all tests using this fixture
    with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
        yield
    config.ENABLED = original

@pytest.fixture
def agent():
    return CheatsheetAgent()

def test_template_response_still_fast(enable_enrichment, agent):
    """Non-enriched requests must stay <500ms (SLO)."""
    
    start = time.time()
    result = agent.generate({
        'code_context': 'import pandas as pd',
        'skill_level': 'beginner',
        'language': 'python'
    })
    elapsed = time.time() - start
    
    # Assert correctness first
    assert result['success'] is True
    assert result['data']['method'] == 'template'
    
    # Assert performance 
    # Note: On CI/CD this might fluctuate, but locally should be very fast.
    # We use 0.5s as a hard limit for "fast path".
    assert elapsed < 0.5, f"Template generation took {elapsed:.4f}s (SLO: <0.5s)"

def test_enriched_response_under_threshold(enable_enrichment, agent):
    """Enriched requests should be acceptable (<5s)."""
    
    # Mock strict timing to simulate LLM delay
    mock_response = Mock()
    mock_response.content = [Mock(text="### Tip\nContent")]
    mock_response.usage = Mock(output_tokens=20)
    
    # We simulate a 2-second LLM call
    def delayed_response(*args, **kwargs):
        time.sleep(2.0) 
        return mock_response

    with patch('src.agents.cheatsheet.section_enricher.Anthropic') as mock_anthropic:
        mock_client = Mock()
        mock_client.messages.create.side_effect = delayed_response
        mock_anthropic.return_value = mock_client
        
        start = time.time()
        result = agent.generate({
            'code_context': 'from langchain import StateGraph',
            'conversation_history': 'latest syntax',
            'skill_level': 'intermediate',
            'language': 'python'
        })
        elapsed = time.time() - start
        
        # Verify enrichment happened
        assert result['data']['enrichment']['enabled'] is True
        
        # Verify total time is reasonable (overhead < ~100ms + LLM time)
        assert elapsed < 5.0, f"Enriched generation took {elapsed:.4f}s (SLO: <5.0s)"
        assert elapsed >= 2.0, "Mock delay didn't work"
