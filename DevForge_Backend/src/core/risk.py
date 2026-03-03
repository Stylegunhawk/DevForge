"""Risk management and enforcement for GitOps operations.

Implements backend-only risk validation with no UI dependencies.
All destructive safeguards are enforced in the backend as required.
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for GitOps operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Severity ordering for RiskLevel — used by contextual risk escalation logic.
# Contextual rules can only ESCALATE risk, never downgrade it.
# max(static, contextual, key=_RISK_ORDER.get) always returns the higher level.
_RISK_ORDER: dict["RiskLevel", int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


@dataclass
class RiskViolation:
    """Risk violation details."""
    operation: str
    risk_level: RiskLevel
    missing_requirements: list[str]
    message: str


class OperationRiskRegistry:
    """Registry mapping operations to their risk levels."""
    
    # Final risk levels from Phase 0 analysis
    RISK_LEVELS = {
        # Read Operations - LOW
        "list_repos": RiskLevel.LOW,
        "browse_files": RiskLevel.LOW,
        "read_file": RiskLevel.LOW,
        "search_code": RiskLevel.LOW,
        "generate_changelog": RiskLevel.LOW,
        "analyze_ci_failure": RiskLevel.LOW,
        "list_branches": RiskLevel.LOW,
        
        # Write Operations - MEDIUM
        "create_issue": RiskLevel.MEDIUM,
        "commit_file": RiskLevel.MEDIUM,
        "create_pull_request": RiskLevel.MEDIUM,
        "create_branch": RiskLevel.MEDIUM,
        "merge_pr": RiskLevel.MEDIUM,  # Contextual rules escalate to HIGH/CRITICAL for protected branches
        
        # High Impact Operations - HIGH
        "create_repo": RiskLevel.HIGH,  # Production impact
        "scaffold_repo": RiskLevel.HIGH,  # Production impact
        "delete_branch": RiskLevel.HIGH,  # Conditional rollback
        "push": RiskLevel.HIGH,  # Time-bounded destructive
        
        # Rollback Matrix Operations
        "commit": RiskLevel.MEDIUM,
        "close_issue": RiskLevel.MEDIUM,
        
        # Critical Operations - CRITICAL
        "delete_repo": RiskLevel.CRITICAL,
        "force_push": RiskLevel.CRITICAL,  # Protected branch
    }
    
    @classmethod
    def get_risk_level(cls, operation: str) -> RiskLevel:
        """Get risk level for an operation.
        
        Args:
            operation: Operation name
            
        Returns:
            RiskLevel for the operation
            
        Raises:
            ValueError: If operation is not registered
        """
        if operation not in cls.RISK_LEVELS:
            raise ValueError(f"Unknown operation: {operation}")
        return cls.RISK_LEVELS[operation]
    
    @classmethod
    def list_operations(cls, risk_level: RiskLevel) -> list[str]:
        """List all operations with a given risk level.
        
        Args:
            risk_level: Risk level to filter by
            
        Returns:
            List of operation names with the specified risk level
        """
        return [op for op, level in cls.RISK_LEVELS.items() if level == risk_level]


class RiskGate:
    """Risk enforcement gate for GitOps operations."""
    
    @classmethod
    def check(cls, operation: str, context: Optional[Dict[str, Any]] = None) -> Optional[RiskViolation]:
        """Check if operation passes risk requirements.
        
        Args:
            operation: Operation name
            context: Operation context (may contain confirmation data)
            
        Returns:
            RiskViolation if requirements not met, None if passes
            
        Raises:
            ValueError: If operation is not registered
        """
        context = context or {}

        # Support both bare keys (confirmed/reason) and prefixed keys (risk_confirmed/risk_reason)
        # so test_risk.py and agent-side code can both pass context transparently.
        effective_context = {
            "confirmed": context.get("confirmed") or context.get("risk_confirmed"),
            "reason": context.get("reason") or context.get("risk_reason") or "",
        }

        try:
            risk_level = OperationRiskRegistry.get_risk_level(operation)
        except ValueError as e:
            raise ValueError(f"Risk validation failed: {e}")

        logger.debug(f"Checking risk for {operation}: {risk_level.value}")

        # LOW and MEDIUM operations pass without requirements
        if risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
            logger.debug(f"Operation {operation} passes (risk level: {risk_level.value})")
            return None

        missing_requirements = []

        # HIGH operations require explicit confirmation
        if risk_level == RiskLevel.HIGH:
            if not effective_context.get("confirmed"):
                missing_requirements.append("confirmed=true")

        # CRITICAL operations require confirmation AND reason
        elif risk_level == RiskLevel.CRITICAL:
            if not effective_context.get("confirmed"):
                missing_requirements.append("confirmed=true")

            reason = str(effective_context.get("reason", "")).strip()
            if not reason:
                missing_requirements.append("reason (non-empty string)")

        if missing_requirements:
            violation = RiskViolation(
                operation=operation,
                risk_level=risk_level,
                missing_requirements=missing_requirements,
                message=f"Operation {operation} requires: {', '.join(missing_requirements)}"
            )
            logger.warning(f"Risk gate blocked: {violation.message}")
            return violation
        
        logger.info(f"Operation {operation} passed risk gate (risk level: {risk_level.value})")
        return None

    @classmethod
    def _get_contextual_risk_level(
        cls, operation: str, parameters: Optional[Dict[str, Any]]
    ) -> Optional[RiskLevel]:
        """Return a context-aware override of the static risk level, or None to keep the default.

        Rules:
          merge_pr:
            base == "main" | "master"          → HIGH
            base == "production" | "release/*"  → CRITICAL
            any other branch                    → MEDIUM (keep default)

          delete_branch:
            branch == "main"|"master"|"production" → CRITICAL
            branch matches "release/*"               → HIGH
            any other branch                         → HIGH (keep default, still need confirmed)

          commit_file:
            branch == "main"|"master"|"production" → HIGH
            any other branch                        → MEDIUM (keep default)
        """
        if parameters is None:
            return None

        import fnmatch  # stdlib, safe to import here

        if operation == "merge_pr":
            base = parameters.get("base", "").lower()
            if base in ("main", "master"):
                return RiskLevel.HIGH
            if base == "production" or fnmatch.fnmatch(base, "release/*"):
                return RiskLevel.CRITICAL
            return None  # keep MEDIUM default

        if operation == "delete_branch":
            branch = parameters.get("branch_name", "").lower()
            if branch in ("main", "master", "production"):
                return RiskLevel.CRITICAL
            if fnmatch.fnmatch(branch, "release/*"):
                return RiskLevel.HIGH
            return None  # keep HIGH default

        if operation == "commit_file":
            branch = parameters.get("branch", "").lower()
            if branch in ("main", "master", "production"):
                return RiskLevel.HIGH
            return None  # keep MEDIUM default

        return None

    @classmethod
    def check_contextual(
        cls,
        operation: str,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional["RiskViolation"]:
        """Check risk requirements with context-aware risk level elevation.

        This is a drop-in replacement for check() that also considers the
        parameters (branch name, base branch, etc.) to escalate risk where needed.

        Args:
            operation: Operation name
            parameters: Validated operation parameters (used for branch/base checks)
            context: Operation context (may contain confirmation data)

        Returns:
            RiskViolation if requirements not met, None if passes

        Raises:
            ValueError: If operation is not registered
        """
        context = context or {}
        parameters = parameters or {}

        try:
            static_risk = OperationRiskRegistry.get_risk_level(operation)
        except ValueError as e:
            raise ValueError(f"Risk validation failed: {e}")

        # Compute effective risk: contextual can ONLY escalate, never downgrade.
        # Invariant: effective_risk >= static_risk always.
        # Example: static=MEDIUM, contextual=CRITICAL → effective=CRITICAL ✅
        #          static=HIGH,   contextual=MEDIUM   → effective=HIGH   ✅ (no downgrade)
        contextual_override = cls._get_contextual_risk_level(operation, parameters)
        if contextual_override is not None:
            risk_level = max(static_risk, contextual_override, key=lambda r: _RISK_ORDER[r])
        else:
            risk_level = static_risk

        logger.debug(
            f"Contextual risk for {operation}: static={static_risk.value} "
            f"override={contextual_override.value if contextual_override else 'none'} "
            f"effective={risk_level.value}"
        )

        # LOW / MEDIUM → passes without requirements
        if risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM):
            return None

        missing_requirements = []

        # Extract risk confirmation from context
        confirmed = context.get("confirmed") or context.get("risk_confirmed")
        reason = (context.get("reason") or context.get("risk_reason") or "").strip()

        if risk_level == RiskLevel.HIGH:
            if not confirmed:
                missing_requirements.append("confirmed=true")

        elif risk_level == RiskLevel.CRITICAL:
            if not confirmed:
                missing_requirements.append("confirmed=true")
            if not reason:
                missing_requirements.append("reason (non-empty string)")

        if missing_requirements:
            violation = RiskViolation(
                operation=operation,
                risk_level=risk_level,
                missing_requirements=missing_requirements,
                message=f"Operation {operation} requires: {', '.join(missing_requirements)}",
            )
            logger.warning(f"Contextual risk gate blocked: {violation.message}")
            return violation

        logger.info(
            f"Operation {operation} passed contextual risk gate (risk level: {risk_level.value})"
        )
        return None

    @classmethod
    def validate_and_raise(cls, operation: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Validate operation and raise exception if blocked.

        Args:
            operation: Operation name
            context: Operation context

        Raises:
            ValueError: If operation is blocked by risk gate
        """
        violation = cls.check(operation, context)
        if violation:
            raise ValueError(violation.message)

    @classmethod
    def get_operation_summary(cls) -> Dict[str, Dict[str, str]]:
        """Get summary of all operations and their risk levels.

        Returns:
            Dict mapping operation names to risk info
        """
        summary = {}
        for operation, risk_level in OperationRiskRegistry.RISK_LEVELS.items():
            summary[operation] = {
                "risk_level": risk_level.value,
                "requirements": cls._get_requirements_for_risk(risk_level)
            }
        return summary

    @classmethod
    def _get_requirements_for_risk(cls, risk_level: RiskLevel) -> list[str]:
        """Get requirements for a risk level.

        Args:
            risk_level: Risk level

        Returns:
            List of requirement descriptions
        """
        if risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
            return ["none"]
        elif risk_level == RiskLevel.HIGH:
            return ["confirmed=true"]
        elif risk_level == RiskLevel.CRITICAL:
            return ["confirmed=true", "reason (non-empty string)"]
        return []
