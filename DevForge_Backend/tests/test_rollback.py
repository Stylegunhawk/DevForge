"""Tests for rollback feasibility matrix.

Tests rollback actions, prechecks, time bounds, and compensating actions.
"""

import pytest
import time
from src.agents.github.workflows.rollback import (
    RollbackMatrix,
    RollbackFeasibility,
    QUICK_PR_ROLLBACK_MATRIX
)


class TestRollbackMatrix:
    """Test rollback matrix functionality"""
    
    def test_get_rollback_action(self):
        """Test retrieving rollback actions"""
        action = RollbackMatrix.get_rollback_action("create_branch")
        
        assert action is not None
        assert action.feasibility == RollbackFeasibility.IMMEDIATE
        assert action.action == "delete_branch"
    
    def test_immediate_rollback(self):
        """Test immediate rollback operations"""
        operations = ["create_branch", "commit", "create_pull_request", "close_issue"]
        
        for op in operations:
            action = RollbackMatrix.get_rollback_action(op)
            assert action.feasibility == RollbackFeasibility.IMMEDIATE
            assert action.action is not None
    
    def test_compensating_action(self):
        """Test compensating actions for irreversible ops"""
        action = RollbackMatrix.get_rollback_action("merge_pr")
        
        assert action.feasibility == RollbackFeasibility.COMPENSATING
        assert action.action is None  # Cannot undo merge
        assert action.compensating_action == "create_revert_pr"
    
    def test_impossible_rollback(self):
        """Test impossible rollback operations"""
        action = RollbackMatrix.get_rollback_action("delete_repository")
        
        assert action.feasibility == RollbackFeasibility.IMPOSSIBLE
        assert action.action is None
        assert action.requires_admin is True
    
    def test_time_bounds(self):
        """Test time-bound rollback checks"""
        # Delete branch has 48hr window
        action = RollbackMatrix.get_rollback_action("delete_branch")
        assert action.time_bounds == 48 * 3600
        
        # Within window
        context_recent = {"executed_at": time.time() - 3600}  # 1 hour ago
        assert RollbackMatrix.can_rollback("delete_branch", context_recent)
        
        # Outside window
        context_old = {"executed_at": time.time() - (49 * 3600)}  # 49 hours ago
        assert not RollbackMatrix.can_rollback("delete_branch", context_old)
    
    def test_prechecks(self):
        """Test precheck validation"""
        # Branch not protected precheck
        context_protected = {"branch_protected": True}
        context_unprotected = {"branch_protected": False}
        
        # Should fail with protected branch
        assert not RollbackMatrix.can_rollback("create_branch", context_protected)
        
        # Should pass with unprotected branch
        assert RollbackMatrix.can_rollback("create_branch", context_unprotected)
    
    def test_pr_not_merged_precheck(self):
        """Test PR not merged precheck"""
        context_merged = {"pr_merged": True}
        context_open = {"pr_merged": False}
        
        # Cannot rollback merged PR
        assert not RollbackMatrix.can_rollback("create_pull_request", context_merged)
        
        # Can rollback open PR
        assert RollbackMatrix.can_rollback("create_pull_request", context_open)
    
    def test_get_compensating_action(self):
        """Test getting compensating action"""
        comp_action = RollbackMatrix.get_compensating_action("merge_pr")
        assert comp_action == "create_revert_pr"
        
        # Operation with no compensating action
        comp_action = RollbackMatrix.get_compensating_action("create_branch")
        assert comp_action is None
    
    def test_unknown_operation(self):
        """Test handling unknown operations"""
        action = RollbackMatrix.get_rollback_action("unknown_op")
        assert action is None
        
        # Cannot rollback unknown operation
        assert not RollbackMatrix.can_rollback("unknown_op", {})
    
    def test_quick_pr_rollback_matrix(self):
        """Test Quick PR workflow rollback matrix"""
        # Verify all steps have rollback defined
        assert "step1_create_branch" in QUICK_PR_ROLLBACK_MATRIX
        assert "step2_commit" in QUICK_PR_ROLLBACK_MATRIX
        assert "step3_push" in QUICK_PR_ROLLBACK_MATRIX
        assert "step4_create_pr" in QUICK_PR_ROLLBACK_MATRIX
        assert "step5_merge_pr" in QUICK_PR_ROLLBACK_MATRIX
        
        # Step 1-4 should have immediate rollback
        for step in ["step1_create_branch", "step2_commit", "step3_push", "step4_create_pr"]:
            assert QUICK_PR_ROLLBACK_MATRIX[step]["feasibility"] == "immediate"
            assert QUICK_PR_ROLLBACK_MATRIX[step]["rollback"] is not None
        
        # Step 5 (merge) should have compensating action
        step5 = QUICK_PR_ROLLBACK_MATRIX["step5_merge_pr"]
        assert step5["feasibility"] == "compensating"
        assert step5["rollback"] is None
        assert step5["compensating"] == "create_revert_pr"
    
    def test_multiple_prechecks(self):
        """Test operation with multiple prechecks"""
        action = RollbackMatrix.get_rollback_action("create_branch")
        assert len(action.prechecks) == 2
        assert "branch_not_protected" in action.prechecks
        assert "no_open_prs" in action.prechecks
        
        # All prechecks must pass
        context_all_pass = {
            "branch_protected": False,
            "open_pr_count": 0
        }
        assert RollbackMatrix.can_rollback("create_branch", context_all_pass)
        
        # If any precheck fails, rollback should fail
        context_one_fail = {
            "branch_protected": False,
            "open_pr_count": 3  # Has open PRs
        }
        assert not RollbackMatrix.can_rollback("create_branch", context_one_fail)


def test_rollback_action_dataclass():
    """Test RollbackAction dataclass"""
    from src.agents.github.workflows.rollback import RollbackAction
    
    action = RollbackAction(
        feasibility=RollbackFeasibility.IMMEDIATE,
        action="test_action",
        time_bounds=3600,
        requires_admin=False,
        prechecks=["check1", "check2"]
    )
    
    assert action.feasibility == RollbackFeasibility.IMMEDIATE
    assert action.action == "test_action"
    assert action.time_bounds == 3600
    assert not action.requires_admin
    assert len(action.prechecks) == 2
