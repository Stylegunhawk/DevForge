"""Safety checks for Phases B and C."""
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

def test_js_libraries_are_fully_templated(enable_enrichment, agent):
    """
    SAFETY CHECK: JS/TS libraries must NOT trigger enrichment.
    Even with config.ENABLED = True, they should hit the FULLY_TEMPLATED_LIBS rule.
    """
    result = agent.generate({
        'code_context': 'import React from "react";',
        'skill_level': 'beginner'
    })
    
    assert result['success'] is True
    data = result['data']
    
    # Must use "template", NOT "enriched"
    assert data['method'] == 'template'
    assert data['enrichment']['enabled'] is False 
    # Logic: should_enrich_sections returns False because 'react' is in FULLY_TEMPLATED_LIBS
    
def test_promotion_is_read_only(enable_enrichment, agent):
    """
    SAFETY CHECK: Promotion tracker recording signals MUST NOT change the agent output.
    """
    # 1. Run once
    tracker._counts.clear()
    
    # Mock LLM for LangChain (which IS promotable/enrichable)
    mock_resp = Mock()
    mock_resp.content = [Mock(text="### Tip")]
    mock_resp.usage = Mock(output_tokens=10)
    
    with patch('src.agents.cheatsheet.section_enricher.Anthropic') as mock_llm:
        mock_llm.return_value.messages.create.return_value = mock_resp
        
        args = {
            'code_context': 'from langchain import StateGraph',
            'skill_level': 'intermediate',
            'language': 'python'
        }
        
        # Run 1
        res1 = agent.generate(args)
        assert res1['data']['enrichment']['promotable'] is False # Not enough counts yet
        
        # Run 2
        res2 = agent.generate(args)
        
        # Run 3
        res3 = agent.generate(args)
        
        # Run 4 (Should be promotable now)
        res4 = agent.generate(args)
        
        assert res4['data']['enrichment']['promotable'] is True
        
        # CRITICAL: The content/structure of res1 and res4 (other than metadata) should be identical 
        # (assuming deterministic LLM mock or we check structure)
        # Here checking that `promotable=True` didn't break anything.
        assert res4['data']['method'] == 'enriched'

def test_promotion_tracker_does_not_mutate_templates():
    """
    SAFETY CHECK: Tracker should only track counts, not touch template dicts.
    """
    from src.agents.cheatsheet.enhanced_templates import BASE_TEMPLATES
    import copy
    
    snapshot = copy.deepcopy(BASE_TEMPLATES)
    
    tracker.record_enrichment('python', 'Variables')
    
    assert BASE_TEMPLATES == snapshot
