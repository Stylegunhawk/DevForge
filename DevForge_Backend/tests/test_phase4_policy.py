# tests/test_phase4_policy.py
"""
Phase 4 — Policy Gate Tests.

Verifies PolicyGate.check() blocks operations based on:
1. GITOPS_PROTECTED_MODE env var
2. GITOPS_ENV production/staging/development rules
"""

import pytest
import os
from unittest.mock import patch
from src.core.policy import PolicyGate, PolicyViolation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def env_patch(env: str = "development", protected: str = "false"):
    """Patch env vars for a single test."""
    return patch.dict(os.environ, {"GITOPS_ENV": env, "GITOPS_PROTECTED_MODE": protected})


def is_blocked(operation: str, parameters: dict = None, context: dict = None,
               env: str = "development", protected: str = "false") -> bool:
    with env_patch(env, protected):
        return PolicyGate.check(operation, parameters or {}, context or {}) is not None


def violation(operation: str, parameters: dict = None, context: dict = None,
              env: str = "development", protected: str = "false") -> PolicyViolation:
    with env_patch(env, protected):
        return PolicyGate.check(operation, parameters or {}, context or {})


# ---------------------------------------------------------------------------
# Rule 1: Protected Mode
# ---------------------------------------------------------------------------

class TestProtectedMode:
    """GITOPS_PROTECTED_MODE=true blocks HIGH and CRITICAL."""

    def test_low_ops_pass_in_protected_mode(self):
        assert not is_blocked("list_repos", protected="true")
        assert not is_blocked("browse_files", protected="true")
        assert not is_blocked("list_branches", protected="true")

    def test_medium_ops_pass_in_protected_mode(self):
        assert not is_blocked("create_issue", protected="true")
        assert not is_blocked("commit_file", protected="true")
        assert not is_blocked("create_branch", protected="true")

    def test_high_ops_blocked_in_protected_mode(self):
        v = violation("create_repo", protected="true")
        assert v is not None
        assert v.policy == "protected_mode"
        assert v.status == "policy_blocked"
        assert "create_repo" in v.message

    def test_critical_ops_blocked_in_protected_mode(self):
        v = violation("delete_repo", protected="true")
        assert v is not None
        assert v.policy == "protected_mode"

    def test_scaffold_repo_blocked_in_protected_mode(self):
        assert is_blocked("scaffold_repo", protected="true")

    def test_delete_branch_blocked_in_protected_mode(self):
        assert is_blocked("delete_branch", protected="true")


# ---------------------------------------------------------------------------
# Rule 2: Production Environment
# ---------------------------------------------------------------------------

class TestProductionEnv:
    """GITOPS_ENV=production applies strict hard blocks."""

    def test_delete_repo_always_blocked_in_production(self):
        v = violation("delete_repo", env="production")
        assert v is not None
        assert v.policy == "env_restriction"
        assert v.status == "policy_blocked"

    def test_force_push_always_blocked_in_production(self):
        assert is_blocked("force_push", env="production")

    def test_delete_branch_main_blocked_in_production(self):
        v = violation("delete_branch", parameters={"branch_name": "main"}, env="production")
        assert v is not None
        assert v.policy == "env_restriction"

    def test_delete_branch_master_blocked_in_production(self):
        assert is_blocked("delete_branch", parameters={"branch_name": "master"}, env="production")

    def test_delete_branch_feature_allowed_in_production(self):
        """Non-protected branches can be deleted in production (risk gate still applies)."""
        assert not is_blocked("delete_branch", parameters={"branch_name": "feature/x"}, env="production")

    def test_create_repo_allowed_in_production(self):
        """create_repo is not in production blocklist (risk gate handles it)."""
        assert not is_blocked("create_repo", env="production")

    def test_list_repos_allowed_in_production(self):
        assert not is_blocked("list_repos", env="production")

    def test_policy_violation_to_dict(self):
        v = violation("delete_repo", env="production")
        d = v.to_dict()
        assert d["status"] == "policy_blocked"
        assert d["policy"] == "env_restriction"
        assert d["operation"] == "delete_repo"
        assert "message" in d


# ---------------------------------------------------------------------------
# Rule 3: Staging Environment
# ---------------------------------------------------------------------------

class TestStagingEnv:
    """GITOPS_ENV=staging blocks delete_repo; force_push needs confirmed."""

    def test_delete_repo_blocked_in_staging(self):
        v = violation("delete_repo", env="staging")
        assert v is not None
        assert v.policy == "env_restriction"

    def test_force_push_blocked_in_staging_without_confirmed(self):
        v = violation("force_push", env="staging")
        assert v is not None
        assert v.policy == "env_restriction"

    def test_force_push_allowed_in_staging_with_confirmed(self):
        assert not is_blocked("force_push", context={"confirmed": True}, env="staging")

    def test_force_push_allowed_in_staging_with_risk_confirmed(self):
        assert not is_blocked("force_push", context={"risk_confirmed": True}, env="staging")

    def test_delete_branch_allowed_in_staging(self):
        """Staging doesn't hard-block delete_branch (risk gate handles it)."""
        assert not is_blocked("delete_branch", parameters={"branch_name": "main"}, env="staging")

    def test_create_repo_allowed_in_staging(self):
        assert not is_blocked("create_repo", env="staging")


# ---------------------------------------------------------------------------
# Rule 4: Development — always allow
# ---------------------------------------------------------------------------

class TestDevelopmentEnv:
    """GITOPS_ENV=development (default) allows everything through the policy gate."""

    @pytest.mark.parametrize("operation", [
        "delete_repo", "force_push", "delete_branch", "create_repo",
        "merge_pr", "list_repos", "commit_file",
    ])
    def test_all_ops_pass_in_development(self, operation):
        assert not is_blocked(operation, env="development")

    def test_default_env_is_development(self):
        """When GITOPS_ENV is not set, default is development — everything passes."""
        env_copy = os.environ.copy()
        env_copy.pop("GITOPS_ENV", None)
        env_copy.pop("GITOPS_PROTECTED_MODE", None)
        with patch.dict(os.environ, env_copy, clear=True):
            assert PolicyGate.check("delete_repo") is None


# ---------------------------------------------------------------------------
# get_policy_summary
# ---------------------------------------------------------------------------

class TestPolicySummary:
    def test_summary_contains_expected_keys(self):
        with env_patch("production", "false"):
            summary = PolicyGate.get_policy_summary()
        assert summary["env"] == "production"
        assert summary["protected_mode"] is False
        assert "delete_repo" in summary["production_blocked"]
        assert "main" in summary["protected_branches"]
