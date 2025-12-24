"""Tests for enrichment detection logic."""
import pytest
from unittest.mock import patch
from src.agents.cheatsheet.enrichment_detector import should_enrich_sections
from src.agents.cheatsheet.config import config

# Helper to force config enabled/disabled state
@pytest.fixture
def enable_enrichment():
    original = config.ENABLED
    config.ENABLED = True
    yield
    config.ENABLED = original

@pytest.fixture
def disable_enrichment():
    original = config.ENABLED
    config.ENABLED = False
    yield
    config.ENABLED = original

def test_feature_flag_disabled(disable_enrichment):
    """Enrichment blocked when flag is off."""
    result = should_enrich_sections(
        detected_libraries=['langchain'],
        code_context='from langchain import StateGraph',
        conversation_history='latest'
    )
    
    assert result['enrich'] is False
    assert result['reason'] == 'feature_disabled'

def test_stable_library_skipped(enable_enrichment):
    """Pandas should not trigger enrichment (it is fully templated)."""
    result = should_enrich_sections(
        detected_libraries=['pandas'],
        code_context='import pandas as pd',
        conversation_history='help me with dataframes'
    )
    
    assert result['enrich'] is False
    assert result['reason'] == 'stable_libraries'

def test_langchain_with_latest_request(enable_enrichment):
    """LangChain + 'latest' mention should trigger enrichment."""
    result = should_enrich_sections(
        detected_libraries=['langchain'],
        code_context='from langchain.graphs import StateGraph',
        conversation_history='Show me the latest LangGraph syntax'
    )
    
    assert result['enrich'] is True
    assert 'langchain' in result['target_libraries']
    assert result['reason'] == 'user_needs_latest'

def test_debugging_complex_code(enable_enrichment):
    """Errors + complex patterns should trigger enrichment."""
    result = should_enrich_sections(
        detected_libraries=['langgraph'],
        code_context='@agent.tool\nasync def process():\n    raise Exception("Failed")'
    )
    
    assert result['enrich'] is True
    assert result['reason'] == 'debugging_context'

def test_weak_signals_skipped(enable_enrichment):
    """Fast library but trivial code and no conversation -> skip to save tokens."""
    # Assuming "import langchain" is not complex enough (score < 2 indicators)
    result = should_enrich_sections(
        detected_libraries=['langchain'],
        code_context='import langchain',
        conversation_history=''
    )
    
    assert result['enrich'] is False
    assert result['reason'] == 'weak_signals'
