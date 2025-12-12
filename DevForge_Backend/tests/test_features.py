"""Tests for feature flags functionality.

Tests feature enablement, environment overrides, and decorators.
"""

import pytest
import os
from src.core.features import Feature, FeatureFlags, require_feature, FeatureDisabledError


class TestFeatureFlags:
    """Test FeatureFlags functionality"""
    
    def test_default_enabled_features(self):
        """Test that default features are enabled"""
        assert FeatureFlags.is_enabled(Feature.FUZZY_SEARCH)
        assert FeatureFlags.is_enabled(Feature.COMMIT_GENERATION)
        assert FeatureFlags.is_enabled(Feature.WORKFLOWS)
    
    def test_runtime_enable_disable(self):
        """Test runtime feature toggle"""
        # Disable feature
        FeatureFlags.disable(Feature.LOG_PARSING)
        assert not FeatureFlags.is_enabled(Feature.LOG_PARSING)
        
        # Re-enable feature
        FeatureFlags.enable(Feature.LOG_PARSING)
        assert FeatureFlags.is_enabled(Feature.LOG_PARSING)
    
    def test_environment_variable_override(self, monkeypatch):
        """Test environment variable override"""
        # Disable via environment
        monkeypatch.setenv("GITOPS_FEATURE_FUZZY_SEARCH", "false")
        
        # Should be disabled despite default
        assert not FeatureFlags.is_enabled(Feature.FUZZY_SEARCH)
        
        # Enable via environment
        monkeypatch.setenv("GITOPS_FEATURE_FUZZY_SEARCH", "true")
        assert FeatureFlags.is_enabled(Feature.FUZZY_SEARCH)
    
    def test_environment_variable_values(self, monkeypatch):
        """Test different environment variable values"""
        test_cases = [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("0", False),
            ("no", False),
            ("off", False),
        ]
        
        for value, expected in test_cases:
            monkeypatch.setenv("GITOPS_FEATURE_ASYNC_JOBS", value)
            assert FeatureFlags.is_enabled(Feature.ASYNC_JOBS) == expected
    
    def test_get_enabled_features(self):
        """Test getting list of enabled features"""
        enabled = FeatureFlags.get_enabled_features()
        
        assert isinstance(enabled, list)
        assert "fuzzy_search" in enabled
        assert "commit_generation" in enabled


class TestRequireFeatureDecorator:
    """Test require_feature decorator"""
    
    @pytest.mark.asyncio
    async def test_decorator_allows_enabled_feature(self):
        """Test decorator allows execution when feature enabled"""
        
        @require_feature(Feature.FUZZY_SEARCH)
        async def test_function():
            return "success"
        
        FeatureFlags.enable(Feature.FUZZY_SEARCH)
        result = await test_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_decorator_blocks_disabled_feature(self):
        """Test decorator blocks execution when feature disabled"""
        
        @require_feature(Feature.LOG_PARSING)
        async def test_function():
            return "should not execute"
        
        FeatureFlags.disable(Feature.LOG_PARSING)
        
        with pytest.raises(FeatureDisabledError) as exc_info:
            await test_function()
        
        assert "log_parsing" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_decorator_with_arguments(self):
        """Test decorator on function with arguments"""
        
        @require_feature(Feature.WORKFLOWS)
        async def create_workflow(name: str, steps: list):
            return {"name": name, "steps": steps}
        
        FeatureFlags.enable(Feature.WORKFLOWS)
        result = await create_workflow("test_workflow", ["step1", "step2"])
        
        assert result["name"] == "test_workflow"
        assert len(result["steps"]) == 2


def test_feature_enum_values():
    """Test Feature enum has expected values"""
    assert Feature.FUZZY_SEARCH.value == "fuzzy_search"
    assert Feature.COMMIT_GENERATION.value == "commit_generation"
    assert Feature.LOG_PARSING.value == "log_parsing"
    assert Feature.PR_INTELLIGENCE.value == "pr_intelligence"
    assert Feature.WORKFLOWS.value == "workflows"
    assert Feature.ASYNC_JOBS.value == "async_jobs"
    assert Feature.ROLLBACK.value == "rollback"
