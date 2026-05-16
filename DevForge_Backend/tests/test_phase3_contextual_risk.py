# tests/test_phase3_contextual_risk.py
"""
Phase 3 — Contextual Risk Tests.

Verifies that RiskGate.check_contextual() elevates risk levels based on
the specific branch / base branch being operated on, producing the correct
block / pass behavior for each scenario.
"""

import pytest
from src.core.risk import RiskGate, RiskLevel, RiskViolation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def passes(operation: str, parameters: dict, context: dict = None) -> bool:
    """Return True if the contextual risk gate allows the operation."""
    return RiskGate.check_contextual(operation, parameters, context or {}) is None


def violation_level(operation: str, parameters: dict, context: dict = None) -> RiskLevel:
    """Return the effective risk level that caused the block, or None if passed."""
    result = RiskGate.check_contextual(operation, parameters, context or {})
    return result.risk_level if result else None


# ---------------------------------------------------------------------------
# merge_pr
# ---------------------------------------------------------------------------

class TestMergePr:
    """Context-aware risk for merge_pr based on base branch."""

    def test_merge_pr_into_main_is_blocked_as_high(self):
        """merge_pr into main → effective HIGH → needs confirmed."""
        result = RiskGate.check_contextual("merge_pr", {"base": "main"}, {})
        assert result is not None
        assert result.risk_level == RiskLevel.HIGH
        assert "confirmed=true" in result.missing_requirements

    def test_merge_pr_into_master_is_blocked_as_high(self):
        result = RiskGate.check_contextual("merge_pr", {"base": "master"}, {})
        assert result is not None
        assert result.risk_level == RiskLevel.HIGH

    def test_merge_pr_into_production_is_blocked_as_critical(self):
        """merge_pr into production → CRITICAL → needs confirmed + reason."""
        result = RiskGate.check_contextual("merge_pr", {"base": "production"}, {})
        assert result is not None
        assert result.risk_level == RiskLevel.CRITICAL
        assert "confirmed=true" in result.missing_requirements
        assert any("reason" in r for r in result.missing_requirements)

    def test_merge_pr_into_release_branch_is_blocked_as_critical(self):
        result = RiskGate.check_contextual("merge_pr", {"base": "release/2.0"}, {})
        assert result is not None
        assert result.risk_level == RiskLevel.CRITICAL

    def test_merge_pr_into_feature_branch_passes(self):
        """merge_pr into an ordinary feature branch → MEDIUM → passes."""
        assert passes("merge_pr", {"base": "feature/login"})

    def test_merge_pr_into_develop_passes(self):
        assert passes("merge_pr", {"base": "develop"})

    def test_merge_pr_into_main_with_confirmed_passes(self):
        """merge_pr into main with confirmed=True (HIGH) → should pass."""
        assert passes("merge_pr", {"base": "main"}, {"confirmed": True})

    def test_merge_pr_into_production_with_confirmed_and_reason_passes(self):
        assert passes(
            "merge_pr",
            {"base": "production"},
            {"confirmed": True, "reason": "Hotfix deployment"},
        )


# ---------------------------------------------------------------------------
# delete_branch
# ---------------------------------------------------------------------------

class TestDeleteBranch:
    """Context-aware risk for delete_branch based on branch name."""

    def test_delete_branch_main_blocked_as_critical(self):
        """Deleting 'main' → CRITICAL → needs confirmed + reason."""
        result = RiskGate.check_contextual("delete_branch", {"branch_name": "main"}, {})
        assert result is not None
        assert result.risk_level == RiskLevel.CRITICAL

    def test_delete_branch_master_blocked_as_critical(self):
        result = RiskGate.check_contextual("delete_branch", {"branch_name": "master"}, {})
        assert result is not None
        assert result.risk_level == RiskLevel.CRITICAL

    def test_delete_branch_production_blocked_as_critical(self):
        result = RiskGate.check_contextual("delete_branch", {"branch_name": "production"}, {})
        assert result is not None
        assert result.risk_level == RiskLevel.CRITICAL

    def test_delete_branch_release_blocked_as_high(self):
        """Deleting a release/* branch → HIGH → needs confirmed."""
        result = RiskGate.check_contextual("delete_branch", {"branch_name": "release/1.5"}, {})
        assert result is not None
        assert result.risk_level == RiskLevel.HIGH
        assert "confirmed=true" in result.missing_requirements

    def test_delete_branch_feature_blocked_as_high(self):
        """Deleting an ordinary branch → HIGH (static default) → needs confirmed."""
        result = RiskGate.check_contextual("delete_branch", {"branch_name": "feature/add-login"}, {})
        assert result is not None
        assert result.risk_level == RiskLevel.HIGH

    def test_delete_branch_feature_with_confirmed_passes(self):
        assert passes("delete_branch", {"branch_name": "feature/add-login"}, {"confirmed": True})

    def test_delete_branch_main_with_confirmed_still_blocked_without_reason(self):
        """CRITICAL ops need both confirmed AND reason."""
        result = RiskGate.check_contextual(
            "delete_branch", {"branch_name": "main"}, {"confirmed": True}
        )
        assert result is not None
        assert result.risk_level == RiskLevel.CRITICAL
        assert any("reason" in r for r in result.missing_requirements)

    def test_delete_branch_main_with_full_context_passes(self):
        assert passes(
            "delete_branch",
            {"branch_name": "main"},
            {"confirmed": True, "reason": "Repository archive"},
        )


# ---------------------------------------------------------------------------
# commit_file
# ---------------------------------------------------------------------------

class TestCommitFile:
    """Context-aware risk for commit_file based on target branch."""

    def test_commit_to_main_blocked_as_high(self):
        """Committing directly to main → HIGH → needs confirmed."""
        result = RiskGate.check_contextual("commit_file", {"branch": "main"}, {})
        assert result is not None
        assert result.risk_level == RiskLevel.HIGH
        assert "confirmed=true" in result.missing_requirements

    def test_commit_to_master_blocked_as_high(self):
        result = RiskGate.check_contextual("commit_file", {"branch": "master"}, {})
        assert result is not None
        assert result.risk_level == RiskLevel.HIGH

    def test_commit_to_production_blocked_as_high(self):
        result = RiskGate.check_contextual("commit_file", {"branch": "production"}, {})
        assert result is not None
        assert result.risk_level == RiskLevel.HIGH

    def test_commit_to_feature_branch_passes(self):
        """Committing to any other branch → MEDIUM → passes."""
        assert passes("commit_file", {"branch": "feature/new-landing"})

    def test_commit_to_main_with_confirmed_passes(self):
        assert passes("commit_file", {"branch": "main"}, {"confirmed": True})

    def test_commit_default_branch_no_branch_key_passes(self):
        """If branch key is absent, no contextual override → MEDIUM → passes."""
        assert passes("commit_file", {})


# ---------------------------------------------------------------------------
# Low-risk operations — always pass
# ---------------------------------------------------------------------------

class TestLowRiskOperations:
    """Sanity-check that read operations are never blocked by contextual rules."""

    @pytest.mark.parametrize("operation", [
        "list_repos", "browse_files", "read_file", "search_code",
        "generate_changelog", "analyze_ci_failure", "list_branches",
    ])
    def test_read_ops_always_pass(self, operation):
        assert passes(operation, {"repo_name": "owner/repo", "branch": "main"})
