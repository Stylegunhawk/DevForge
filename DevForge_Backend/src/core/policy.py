# src/core/policy.py
"""Policy Gate for GitOps operations.

Runs BEFORE the risk gate in the StateGraph.
Answers: "Is this operation allowed at all?" based on environment
configuration and protection mode, independent of risk context.
"""

import fnmatch
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class PolicyViolation:
    """Represents a policy-level block. Returned when an op is disallowed entirely."""
    status: str                 # always "policy_blocked"
    policy: str                 # e.g. "protected_mode", "env_restriction"
    message: str                # user-friendly reason
    operation: str              # operation name that was blocked

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "policy": self.policy,
            "message": self.message,
            "operation": self.operation,
        }


# ---------------------------------------------------------------------------
# Environment-level operation blocklists
# ---------------------------------------------------------------------------

# Operations that are ALWAYS blocked in production
_PRODUCTION_BLOCKED_OPS: frozenset[str] = frozenset({
    "delete_repo",
    "force_push",
})

# Ops that are hard-blocked in staging
_STAGING_BLOCKED_OPS: frozenset[str] = frozenset({
    "delete_repo",
})

# In production, delete_branch of protected branches is blocked entirely
_PROTECTED_BRANCH_NAMES: frozenset[str] = frozenset({"main", "master"})


# ---------------------------------------------------------------------------
# PolicyGate
# ---------------------------------------------------------------------------

class PolicyGate:
    """
    Runs before the risk gate to enforce environment-level and protection-mode rules.

    Priority:
      1. GITOPS_PROTECTED_MODE=true  → block HIGH and CRITICAL entirely
      2. GITOPS_ENV=production        → env-specific hard blocks
      3. GITOPS_ENV=staging           → softer env blocks
      4. GITOPS_ENV=development       → permits everything (risk gate still runs)
    """

    # Import here to avoid circular import; risk.py has no dependency on policy.py
    @staticmethod
    def _get_env() -> str:
        """Read current environment. Defaults to 'development'."""
        return os.getenv("GITOPS_ENV", "development").lower().strip()

    @staticmethod
    def _is_protected_mode() -> bool:
        return os.getenv("GITOPS_PROTECTED_MODE", "false").lower() in ("true", "1", "yes")

    @classmethod
    def check(
        cls,
        operation: str,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[PolicyViolation]:
        """Check if operation is allowed under current policy.

        Args:
            operation: Operation name
            parameters: Validated operation parameters (used for branch checks)
            context: Full operation context (for staging force_push confirmation)

        Returns:
            PolicyViolation if blocked, None if allowed
        """
        parameters = parameters or {}
        context = context or {}
        env = cls._get_env()

        # ------------------------------------------------------------------ #
        # Rule 1: Protected mode — block HIGH and CRITICAL entirely
        # ------------------------------------------------------------------ #
        if cls._is_protected_mode():
            from src.core.risk import OperationRiskRegistry, RiskLevel
            try:
                risk_level = OperationRiskRegistry.get_risk_level(operation)
            except ValueError:
                # Unknown operations fall through; risk gate will catch them
                risk_level = None

            if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                logger.warning(
                    f"[POLICY] Protected mode blocked {operation} ({risk_level.value})"
                )
                return PolicyViolation(
                    status="policy_blocked",
                    policy="protected_mode",
                    message=(
                        f"Operation '{operation}' is not allowed in protected mode "
                        f"(risk level: {risk_level.value}). "
                        "Disable GITOPS_PROTECTED_MODE to perform this action."
                    ),
                    operation=operation,
                )

        # ------------------------------------------------------------------ #
        # Rule 2: Production environment restrictions
        # ------------------------------------------------------------------ #
        if env == "production":
            # Hard-blocked operations
            if operation in _PRODUCTION_BLOCKED_OPS:
                logger.warning(f"[POLICY] Production hard-blocked: {operation}")
                return PolicyViolation(
                    status="policy_blocked",
                    policy="env_restriction",
                    message=(
                        f"Operation '{operation}' is permanently blocked in the production environment."
                    ),
                    operation=operation,
                )

            # delete_branch of main/master blocked in production
            if operation == "delete_branch":
                branch = parameters.get("branch_name", "").lower()
                if branch in _PROTECTED_BRANCH_NAMES:
                    logger.warning(
                        f"[POLICY] Production blocked delete of protected branch: {branch}"
                    )
                    return PolicyViolation(
                        status="policy_blocked",
                        policy="env_restriction",
                        message=(
                            f"Deleting the '{branch}' branch is not allowed in the production environment."
                        ),
                        operation=operation,
                    )

        # ------------------------------------------------------------------ #
        # Rule 3: Staging environment restrictions
        # ------------------------------------------------------------------ #
        elif env == "staging":
            if operation in _STAGING_BLOCKED_OPS:
                logger.warning(f"[POLICY] Staging hard-blocked: {operation}")
                return PolicyViolation(
                    status="policy_blocked",
                    policy="env_restriction",
                    message=(
                        f"Operation '{operation}' is blocked in the staging environment."
                    ),
                    operation=operation,
                )

            # force_push in staging requires explicit confirmation
            if operation == "force_push":
                confirmed = context.get("confirmed") or context.get("risk_confirmed")
                if not confirmed:
                    logger.warning("[POLICY] Staging force_push requires confirmed=true")
                    return PolicyViolation(
                        status="policy_blocked",
                        policy="env_restriction",
                        message=(
                            "Force push in staging requires explicit confirmation. "
                            "Pass confirmed=true to proceed."
                        ),
                        operation=operation,
                    )

        # ------------------------------------------------------------------ #
        # Rule 4: Development — always allow (risk gate handles rest)
        # ------------------------------------------------------------------ #
        logger.debug(f"[POLICY] Operation {operation} allowed in env={env}")
        return None

    @classmethod
    def get_policy_summary(cls) -> Dict[str, Any]:
        """Return a summary of active policy config for diagnostics."""
        return {
            "env": cls._get_env(),
            "protected_mode": cls._is_protected_mode(),
            "production_blocked": sorted(_PRODUCTION_BLOCKED_OPS),
            "staging_blocked": sorted(_STAGING_BLOCKED_OPS),
            "protected_branches": sorted(_PROTECTED_BRANCH_NAMES),
        }
