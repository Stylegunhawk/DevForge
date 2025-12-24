"""End-to-end tests for LLM enrichment integration."""
import pytest
from unittest.mock import patch, Mock
import os

from src.agents.cheatsheet.agent import CheatsheetAgent
from src.agents.cheatsheet.config import config

# Fixtures to reset config
@pytest.fixture
def enable_enrichment():
    original = config.ENABLED
    config.ENABLED = True
    # Patch env to allow Enricher to initialize
    with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
        yield
    config.ENABLED = original

@pytest.fixture
def agent():
    return CheatsheetAgent()

def test_langchain_gets_enrichment(enable_enrichment, agent):
    """LangChain code should trigger enrichment and be in output."""
    
    # Mock Anthropic Response
    mock_response = Mock()
    mock_response.content = [Mock(text="### Debugging Tip\n- Use tracing")]
    mock_response.usage = Mock(output_tokens=30)
    
    with patch('src.agents.cheatsheet.section_enricher.Anthropic') as mock_anthropic:
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client
        
        result = agent.generate({
            'code_context': 'from langchain.graphs import StateGraph\ngraph = StateGraph()',
            'skill_level': 'intermediate',
            'conversation_history': 'Show me the latest LangGraph patterns',
            'language': 'python'
        })
    
    # Validation
    assert result['success'] is True
    data = result['data']
    
    # Check Enrichment Metadata
    assert data['enrichment']['enabled'] is True
    assert 'langchain' in data['enrichment']['target_libraries'] or 'langgraph' in data['enrichment']['target_libraries']
    assert len(data['enrichment']['enriched_sections']) > 0
    assert data['method'] == 'enriched'
    
    # Check Markdown Content
    assert '### Debugging Tip' in result['markdown']
    assert 'LangChain' in result['markdown'] or 'LangGraph' in result['markdown']

def test_pandas_uses_templates_only(enable_enrichment, agent):
    """Pandas should NOT trigger enrichment (fully templated) unless explicitly requested."""
    
    result = agent.generate({
        'code_context': 'import pandas as pd\ndf = pd.read_csv("data.csv")',
        'skill_level': 'intermediate',
        'language': 'python'
    })
    
    assert result['success'] is True
    data = result['data']
    
    assert data['enrichment']['enabled'] is False
    assert data['method'] == 'template'
    
    # Should maintain sub-second performance (mocking time not strictly needed here if logic holds)
    assert 'Pandas DataFrames' in result['markdown']

def test_enrichment_failure_graceful_degradation(enable_enrichment, agent):
    """If LLM API fails, should return base templates without crashing."""
    
    with patch('src.agents.cheatsheet.section_enricher.Anthropic', side_effect=Exception("Connection Error")):
        result = agent.generate({
            'code_context': 'from langchain import StateGraph',
            'skill_level': 'intermediate',
            'conversation_history': 'latest syntax',
            'language': 'python'
        })
    
    # Should still succeed
    assert result['success'] is True
    # If enrichment setup failed completely, enabled might be False
    # OR if it failed per-section, enabled was True but enriched_sections is empty.
    
    # In our implementation: `should_enrich` returns True, but loop handles exceptions.
    # So `enabled` will be True, but `enriched_sections` might be empty.
    
    data = result['data']
    # Check that we still got markdown
    assert 'markdown' in result
    assert len(result['markdown']) > 0

def test_feature_flag_disables_enrichment(agent):
    """If flag is OFF, should never enrich."""
    config.ENABLED = False
    
    result = agent.generate({
        'code_context': 'from langchain import StateGraph',
        'conversation_history': 'latest please',
        'language': 'python'
    })
    
    assert result['data']['enrichment']['enabled'] is False
    assert result['data']['enrichment']['reason'] == 'feature_disabled'
