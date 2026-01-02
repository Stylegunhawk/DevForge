"""LLM confidence policy enforcement.

Enforces confidence thresholds for safety and requires user confirmation
when confidence is below acceptable levels.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from src.core.config import settings

logger = logging.getLogger(__name__)


class ConfidenceAction(Enum):
    """Actions based on confidence score"""
    PROCEED = "proceed"  # High confidence - execute automatically
    REQUIRE_CONFIRMATION = "require_confirmation"  # Low confidence - need user approval
    CREATE_DRAFT = "create_draft_pr"  # Medium confidence for commits - create draft PR
    REJECT = "reject"  # Too low - refuse to execute


@dataclass
class ConfidenceDecision:
    """Decision based on confidence score"""
    action: ConfidenceAction
    confidence: float
    threshold: float
    reason: str
    preview: Optional[Dict[str, Any]] = None


class ConfidencePolicy:
    """Enforce confidence thresholds at runtime"""
    
    # Default thresholds
    THRESHOLDS = {
        "intent_classification": 0.85,
        "commit_message": 0.90,
        "repo_discovery": 0.85,
        "auto_fix": 0.95,
        "destructive_op": 0.95,
        "bulk_operation": 0.90
    }
    
    @classmethod
    def enforce(
        cls,
        operation: str,
        confidence: float,
        context: Dict[str, Any]
    ) -> ConfidenceDecision:
        """Enforce confidence policy for operation
        
        Args:
            operation: Operation type
            confidence: Confidence score (0.0 to 1.0)
            context: Operation context for preview generation
            
        Returns:
            ConfidenceDecision with action to take
        """
        threshold = cls.THRESHOLDS.get(operation, settings.GITOPS_FUZZY_THRESHOLD)
        
        # High confidence - proceed
        if confidence >= threshold:
            return ConfidenceDecision(
                action=ConfidenceAction.PROCEED,
                confidence=confidence,
                threshold=threshold,
                reason=f"High confidence ({confidence:.2f} ≥ {threshold})"
            )
        
        # Special handling for commit operations (medium confidence)
        if operation == "commit_message" and 0.85 <= confidence < 0.90:
            return ConfidenceDecision(
                action=ConfidenceAction.CREATE_DRAFT,
                confidence=confidence,
                threshold=threshold,
                reason=f"Medium confidence ({confidence:.2f}) - will create draft PR instead of direct commit",
                preview=cls._generate_preview(operation, context)
            )
        
        # Low confidence - require confirmation
        if confidence >= 0.70:
            return ConfidenceDecision(
                action=ConfidenceAction.REQUIRE_CONFIRMATION,
                confidence=confidence,
                threshold=threshold,
                reason=f"Low confidence ({confidence:.2f} < {threshold}) - user confirmation required",
                preview=cls._generate_preview(operation, context)
            )
        
        # Very low confidence - reject
        return ConfidenceDecision(
            action=ConfidenceAction.REJECT,
            confidence=confidence,
            threshold=threshold,
            reason=f"Confidence too low ({confidence:.2f}) - cannot proceed safely"
        )
    
    @classmethod
    def _generate_preview(
        cls,
        operation: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate preview for user confirmation
        
        Args:
            operation: Operation type
            context: Operation context
            
        Returns:
            Preview dict
        """
        preview = {
            "operation": operation,
            "parsed_intent": context.get("intent", {}),
            "risk_level": cls._assess_risk(operation, context)
        }
        
        # Add operation-specific preview data
        if operation == "commit_message":
            preview["commit_message"] = context.get("message")
            preview["files_affected"] = context.get("files", [])
        
        elif operation == "repo_discovery":
            preview["matched_repo"] = context.get("repo_name")
            preview["alternatives"] = context.get("alternatives", [])
        
        elif operation == "destructive_op":
            preview["warning"] = "This operation cannot be easily reversed"
            preview["affected_resources"] = context.get("resources", [])
        
        return preview
    
    @classmethod
    def _assess_risk(
        cls,
        operation: str,
        context: Dict[str, Any]
    ) -> str:
        """Assess risk level of operation
        
        Args:
            operation: Operation type
            context: Operation context
            
        Returns:
            Risk level: "low" | "medium" | "high"
        """
        # Destructive operations are high risk
        if operation in ["destructive_op", "bulk_operation", "delete_repo"]:
            return "high"
        
        # Commits and PRs are medium risk
        if operation in ["commit_message", "create_pr", "merge_pr"]:
            return "medium"
        
        # Read operations are low risk
        return "low"
    
    @classmethod
    def format_confirmation_request(
        cls,
        decision: ConfidenceDecision
    ) -> Dict[str, Any]:
        """Format confirmation request for Lobe Chat
        
        Args:
            decision: ConfidenceDecision
            
        Returns:
            Response dict for confirmation
        """
        return {
            "success": False,
            "status": "needs_confirmation",
            "confidence": decision.confidence,
            "threshold": decision.threshold,
            "reason": decision.reason,
            "preview": decision.preview,
            "message": f"""⚠️ Confidence below threshold ({decision.confidence:.0%} < {decision.threshold:.0%})

Please review and confirm:
""",
            "instruction": "Respond with 'yes' to proceed or 'no' to cancel"
        }
    
    @classmethod
    def format_rejection(
        cls,
        decision: ConfidenceDecision
    ) -> Dict[str, Any]:
        """Format rejection response
        
        Args:
            decision: ConfidenceDecision
            
        Returns:
            Response dict for rejection
        """
        return {
            "success": False,
            "status": "rejected",
            "confidence": decision.confidence,
            "threshold": decision.threshold,
            "reason": decision.reason,
            "message": f"""❌ Cannot proceed safely

Confidence score ({decision.confidence:.0%}) is too low. Please:
1. Provide more specific information
2. Use exact repository/resource names
3. Add additional context
"""
        }


def check_confidence(operation: str, confidence: float, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Helper function to check confidence and return response if needed
    
    Args:
        operation: Operation type
        confidence: Confidence score
        context: Operation context
        
    Returns:
        Response dict if confirmation/rejection needed, None if can proceed
    """
    decision = ConfidencePolicy.enforce(operation, confidence, context)
    
    if decision.action == ConfidenceAction.PROCEED:
        return None
    
    elif decision.action == ConfidenceAction.CREATE_DRAFT:
        # Signal to create draft PR instead
        return {
            "_action": "create_draft_pr",
            "_reason": decision.reason,
            "_confidence": confidence
        }
    
    elif decision.action == ConfidenceAction.REQUIRE_CONFIRMATION:
        return ConfidencePolicy.format_confirmation_request(decision)
    
    else:  # REJECT
        return ConfidencePolicy.format_rejection(decision)
