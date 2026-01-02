"""Feature flags for GitOps v0.8 functionality.

Allows gradual rollout and A/B testing of new features.
"""

import os
from typing import Optional
from enum import Enum


class Feature(Enum):
    """Available feature flags"""
    
    # Intelligence features
    FUZZY_SEARCH = "fuzzy_search"
    COMMIT_GENERATION = "commit_generation"
    LOG_PARSING = "log_parsing"
    PR_INTELLIGENCE = "pr_intelligence"
    
    # Workflow features
    WORKFLOWS = "workflows"
    ASYNC_JOBS = "async_jobs"
    ROLLBACK = "rollback"
    
    # Safety features
    CONFIDENCE_GATING = "confidence_gating"
    DRY_RUN_ENFORCEMENT = "dry_run_enforcement"
    
    # Performance features
    LLM_CACHING = "llm_caching"
    PARALLEL_EXECUTION = "parallel_execution"


class FeatureFlags:
    """Feature flag manager with environment variable overrides"""
    
    # Default feature states
    DEFAULTS = {
        Feature.FUZZY_SEARCH: True,
        Feature.COMMIT_GENERATION: True,
        Feature.LOG_PARSING: True,
        Feature.PR_INTELLIGENCE: True,
        Feature.WORKFLOWS: True,
        Feature.ASYNC_JOBS: True,
        Feature.ROLLBACK: True,
        Feature.CONFIDENCE_GATING: True,
        Feature.DRY_RUN_ENFORCEMENT: True,
        Feature.LLM_CACHING: True,
        Feature.PARALLEL_EXECUTION: True,
    }
    
    @classmethod
    def is_enabled(cls, feature: Feature) -> bool:
        """Check if feature is enabled
        
        Args:
            feature: Feature to check
            
        Returns:
            True if enabled, False otherwise
        """
        # Check environment variable override
        env_key = f"GITOPS_FEATURE_{feature.value.upper()}"
        env_value = os.getenv(env_key)
        
        if env_value is not None:
            return env_value.lower() in ("true", "1", "yes", "on")
        
        # Fall back to default
        return cls.DEFAULTS.get(feature, False)
    
    @classmethod
    def enable(cls, feature: Feature):
        """Enable a feature at runtime (for testing)"""
        cls.DEFAULTS[feature] = True
    
    @classmethod
    def disable(cls, feature: Feature):
        """Disable a feature at runtime (for testing)"""
        cls.DEFAULTS[feature] = False
    
    @classmethod
    def get_enabled_features(cls) -> list[str]:
        """Get list of enabled features"""
        return [
            feature.value
            for feature in Feature
            if cls.is_enabled(feature)
        ]


def require_feature(feature: Feature):
    """Decorator to require feature flag
    
    Usage:
        @require_feature(Feature.FUZZY_SEARCH)
        async def fuzzy_search_repos(...):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            if not FeatureFlags.is_enabled(feature):
                raise FeatureDisabledError(
                    f"Feature '{feature.value}' is disabled"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class FeatureDisabledError(Exception):
    """Raised when attempting to use a disabled feature"""
    pass
