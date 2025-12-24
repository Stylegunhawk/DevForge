"""Tests for section enricher."""
import pytest
from unittest.mock import Mock, patch
from src.agents.cheatsheet.section_enricher import SectionEnricher

@pytest.fixture
def enricher():
    # Patch env BEFORE init to ensure key is found
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
        return SectionEnricher()

@pytest.fixture
def base_section():
    return {
        'title': 'LangChain Graphs',
        'explanation': 'Build stateful agents',
        'examples': [{'title': 'Basic Graph', 'code': 'graph = StateGraph()'}]
    }

def test_enrichment_preserves_base_structure(enricher, base_section):
    """Enrichment must keep original section intact and add llm_enrichment."""
    
    mock_response = Mock()
    mock_response.content = [Mock(text="### Debugging Tip\n- Check state")]
    mock_response.usage = Mock(output_tokens=50)
    
    with patch.object(enricher.client.messages, 'create', return_value=mock_response):
        result = enricher.enrich_section(
            base_section=base_section,
            user_code='graph = StateGraph()',
            library='langchain'
        )
    
    # Original keys must exist
    assert result['title'] == base_section['title']
    assert result['explanation'] == base_section['explanation']
    assert result['examples'] == base_section['examples']
    
    # Enrichment added
    assert 'llm_enrichment' in result
    assert 'Debugging Tip' in result['llm_enrichment']
    assert result['enrichment_metadata']['tokens_used'] == 50

def test_enrichment_failure_returns_original(enricher, base_section):
    """If LLM fails, return base section unchanged."""
    
    with patch.object(enricher.client.messages, 'create', side_effect=Exception("API Error")):
        result = enricher.enrich_section(
            base_section=base_section,
            user_code='code',
            library='langchain'
        )
    
    # Should return original without enrichment
    assert result == base_section
    assert 'llm_enrichment' not in result

def test_init_without_key_warns_logs(base_section):
    """If no API key, init should succeed but enrich should be no-op."""
    with patch.dict('os.environ', {}, clear=True):
        enricher_no_key = SectionEnricher()
        assert enricher_no_key.client is None
        
        result = enricher_no_key.enrich_section(base_section, "code")
        assert result == base_section
        assert 'llm_enrichment' not in result
