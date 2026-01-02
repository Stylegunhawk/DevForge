"""Tests for GitHub rollback logic.

Verifies the RollbackMatrix correctly determines feasibility and actions based on context.
"""
import time
import pytest
from src.agents.github.workflows.rollback import RollbackMatrix, RollbackFeasibility

class TestRollbackMatrix:
    """Test RollbackMatrix logic"""

    def test_merge_pr_compensating_action(self):
        """Test that merged PRs require compensating action (revert PR)"""
        operation = "merge_pr"
        context = {
            "target_protected": False,
            "pr_merged": True
        }
        
        # Should be feasible via compensation
        assert RollbackMatrix.can_rollback(operation, context) is True
        
        action = RollbackMatrix.get_rollback_action(operation)
        assert action.feasibility == RollbackFeasibility.COMPENSATING
        assert action.compensating_action == "create_revert_pr"
        assert RollbackMatrix.get_compensating_action(operation) == "create_revert_pr"

    def test_protected_branch_blocks_rollback(self):
        """Test that protected target branch blocks rollback of merge"""
        operation = "merge_pr"
        context = {
            "target_protected": True,  # Protected branch
            "pr_merged": True
        }
        
        # Should NOT be feasible because precheck 'target_branch_not_protected' fails
        assert RollbackMatrix.can_rollback(operation, context) is False

    def test_delete_branch_reflog_window(self):
        """Test time bounds for delete_branch (reflog window)"""
        operation = "delete_branch"
        now = time.time()
        
        # Case 1: Within window (1 hour ago)
        context_fresh = {
            "executed_at": now - 3600
        }
        assert RollbackMatrix.can_rollback(operation, context_fresh) is True
        
        # Case 2: Outside window (49 hours ago, limit is 48h)
        context_stale = {
            "executed_at": now - (49 * 3600)
        }
        assert RollbackMatrix.can_rollback(operation, context_stale) is False

    def test_create_branch_immediate_rollback(self):
        """Test simple immediate rollback for create_branch"""
        operation = "create_branch"
        context = {
            "branch_protected": False,
            "no_open_prs": True,
            "open_pr_count": 0
        }
        
        assert RollbackMatrix.can_rollback(operation, context) is True
        action = RollbackMatrix.get_rollback_action(operation)
        assert action.feasibility == RollbackFeasibility.IMMEDIATE
        assert action.action == "delete_branch"

    def test_unknown_operation(self):
        """Test handling of unknown operations"""
        assert RollbackMatrix.can_rollback("unknown_op", {}) is False
        assert RollbackMatrix.get_rollback_action("unknown_op") is None

    def test_push_time_bounds(self):
        """Test strict time bounds for push rollback (5 mins)"""
        operation = "push"
        now = time.time()
        
        # 4 minutes ago - OK
        context_ok = {
            "executed_at": now - 240,
            "branch_protected": False,
            "open_pr_count": 0
        }
        assert RollbackMatrix.can_rollback(operation, context_ok) is True
        
        # 6 minutes ago - Too late
        context_late = {
            "executed_at": now - 360,
            "branch_protected": False,
            "open_pr_count": 0
        }
        assert RollbackMatrix.can_rollback(operation, context_late) is False
