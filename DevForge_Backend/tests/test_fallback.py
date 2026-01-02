"""Test fallback behavior for section selector"""

import pytest
from src.agents.cheatsheet.section_selector import select_sections


def test_fallback_for_missing_templates():
    """Test that selector never returns empty, even for unsupported language"""
    result = select_sections(
        language='javascript',  # No templates exist
        skill_level='intermediate',
        detected_libraries=[],
        complexity_score=15
    )
    
    # Should fallback to Python beginner
    assert len(result) > 0, "Selector must never return empty list"
    assert result[0]['title'] in ['Variables & Types', 'Control Flow', 'Functions']


def test_fallback_for_missing_skill_level():
    """Test fallback when Python intermediate templates don't exist"""
    result = select_sections(
        language='python',
        skill_level='intermediate',
        detected_libraries=[],
        complexity_score=15
    )
    
    # Should fallback to Python beginner since intermediate doesn't exist yet
    assert len(result) > 0, "Selector must never return empty list"


def test_supported_vs_detected_libraries():
    """Test that unsupported libraries don't break selector"""
    result = select_sections(
        language='python',
        skill_level='beginner',
        detected_libraries=['numpy', 'flask'],  # Detected but no templates
        complexity_score=5
    )
    
    # Should return Python beginner sections (no library sections available)
    assert len(result) > 0
    assert result[0]['title'] in ['Variables & Types', 'Control Flow', 'Functions']
