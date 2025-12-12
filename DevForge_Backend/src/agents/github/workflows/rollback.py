"""Rollback feasibility matrix for workflow operations.

Defines rollback actions, prechecks, and compensating actions for each operation type.
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import time

logger = logging.getLogger(__name__)


class RollbackFeasibility(Enum):
    """Rollback feasibility levels"""
    IMMEDIATE = "immediate"  # Can be rolled back immediately
    COMPENSATING = "compensating"  # Requires compensating action
    MANUAL = "manual"  # Requires manual intervention
    IMPOSSIBLE = "impossible"  # Cannot be rolled back


@dataclass
class RollbackAction:
    """Rollback action definition"""
    feasibility: RollbackFeasibility
    action: Optional[str]  # Function name to call for rollback
    time_bounds: Optional[int] = None  # Seconds before rollback becomes impossible
    requires_admin: bool = False
    prechecks: List[str] = None  # Prechecks that must pass
    compensating_action: Optional[str] = None  # Alternative if direct rollback fails
    
    def __post_init__(self):
        if self.prechecks is None:
            self.prechecks = []


class RollbackMatrix:
    """Rollback feasibility matrix for GitHub operations"""
    
    # Define rollback actions for each operation type
    MATRIX = {
        "create_branch": RollbackAction(
            feasibility=RollbackFeasibility.IMMEDIATE,
            action="delete_branch",
            prechecks=["branch_not_protected", "no_open_prs"]
        ),
        
        "commit": RollbackAction(
            feasibility=RollbackFeasibility.IMMEDIATE,
            action="revert_commit",
            prechecks=["branch_not_protected", "commit_not_merged"]
        ),
        
        "push": RollbackAction(
            feasibility=RollbackFeasibility.IMMEDIATE,
            action="force_push_reset",
            prechecks=["branch_not_protected", "no_open_prs"],
            time_bounds=300  # 5 minutes before too risky
        ),
        
        "create_pull_request": RollbackAction(
            feasibility=RollbackFeasibility.IMMEDIATE,
            action="close_pr",
            prechecks=["pr_not_merged"]
        ),
        
        "merge_pr": RollbackAction(
            feasibility=RollbackFeasibility.COMPENSATING,
            action=None,  # Cannot undo merge
            compensating_action="create_revert_pr",
            prechecks=["target_branch_not_protected"]
        ),
        
        "delete_branch": RollbackAction(
            feasibility=RollbackFeasibility.IMMEDIATE,
            action="restore_from_reflog",
            time_bounds=48 * 3600,  # 48 hours reflog window
            prechecks=["within_reflog_window"]
        ),
        
        "close_issue": RollbackAction(
            feasibility=RollbackFeasibility.IMMEDIATE,
            action="reopen_issue"
        ),
        
        "delete_repository": RollbackAction(
            feasibility=RollbackFeasibility.IMPOSSIBLE,
            action=None,
            requires_admin=True
        ),
        
        "force_push": RollbackAction(
            feasibility=RollbackFeasibility.MANUAL,
            action=None,
            compensating_action="notify_team_and_restore_backup",
            requires_admin=True
        )
    }
    
    @classmethod
    def get_rollback_action(cls, operation: str) -> Optional[RollbackAction]:
        """Get rollback action for operation
        
        Args:
            operation: Operation name
            
        Returns:
            RollbackAction if defined, None otherwise
        """
        return cls.MATRIX.get(operation)
    
    @classmethod
    def can_rollback(
        cls,
        operation: str,
        context: Dict[str, Any]
    ) -> bool:
        """Check if operation can be rolled back
        
        Args:
            operation: Operation name
            context: Operation context
            
        Returns:
            True if rollback is possible
        """
        action = cls.get_rollback_action(operation)
        
        if not action:
            return False
        
        if action.feasibility == RollbackFeasibility.IMPOSSIBLE:
            return False
        
        # Check time bounds
        if action.time_bounds and "executed_at" in context:
            elapsed = time.time() - context["executed_at"]
            if elapsed > action.time_bounds:
                logger.warning(
                    f"Rollback time window expired for {operation}: "
                    f"{elapsed}s > {action.time_bounds}s"
                )
                return False
        
        # Check prechecks
        for precheck in action.prechecks:
            if not cls._run_precheck(precheck, context):
                logger.warning(f"Precheck failed for {operation}: {precheck}")
                return False
        
        return action.feasibility in [
            RollbackFeasibility.IMMEDIATE,
            RollbackFeasibility.COMPENSATING
        ]
    
    @classmethod
    def _run_precheck(cls, precheck: str, context: Dict[str, Any]) -> bool:
        """Run precheck validation
        
        Args:
            precheck: Precheck name
            context: Operation context
            
        Returns:
            True if precheck passes
        """
        # Implementation would check actual GitHub state
        # For now, return True (will be implemented in Week 3)
        
        checks = {
            "branch_not_protected": lambda ctx: not ctx.get("branch_protected", False),
            "no_open_prs": lambda ctx: ctx.get("open_pr_count", 0) == 0,
            "commit_not_merged": lambda ctx: not ctx.get("commit_merged", False),
            "pr_not_merged": lambda ctx: not ctx.get("pr_merged", False),
            "target_branch_not_protected": lambda ctx: not ctx.get("target_protected", False),
            "within_reflog_window": lambda ctx: True  # Always true for now
        }
        
        check_fn = checks.get(precheck)
        if check_fn:
            return check_fn(context)
        
        # Unknown precheck - assume passes
        return True
    
    @classmethod
    def get_compensating_action(
        cls,
        operation: str
    ) -> Optional[str]:
        """Get compensating action for operation
        
        Args:
            operation: Operation name
            
        Returns:
            Compensating action name if available
        """
        action = cls.get_rollback_action(operation)
        if action:
            return action.compensating_action
        return None


# Quick PR workflow rollback matrix
QUICK_PR_ROLLBACK_MATRIX = {
    "step1_create_branch": {
        "rollback": "delete_branch",
        "compensating": None,
        "feasibility": "immediate"
    },
    "step2_commit": {
        "rollback": "delete_commit_and_branch",
        "compensating": None,
        "feasibility": "immediate"
    },
    "step3_push": {
        "rollback": "delete_branch",
        "compensating": None,
        "feasibility": "immediate"
    },
    "step4_create_pr": {
        "rollback": "close_pr_and_delete_branch",
        "compensating": None,
        "feasibility": "immediate"
    },
    "step5_merge_pr": {
        "rollback": None,
        "compensating": "create_revert_pr",
        "feasibility": "compensating"
    }
}
