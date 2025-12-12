"""Tests for confidence policy enforcement.

Tests confidence thresholds, branching behavior, and response formatting.
"""

import pytest
from src.core.confidence import (
    ConfidencePolicy,
    ConfidenceAction,
    check_confidence
)


class TestConfidencePolicy:
    """Test confidence policy enforcement"""
    
    def test_high_confidence_proceeds(self):
        """Test high confidence allows automatic execution"""
        decision = ConfidencePolicy.enforce(
            operation="commit_message",
            confidence=0.95,
            context={}
        )
        
        assert decision.action == ConfidenceAction.PROCEED
        assert decision.confidence == 0.95
        assert decision.threshold == 0.90
    
    def test_low_confidence_requires_confirmation(self):
        """Test low confidence requires user confirmation"""
        decision = ConfidencePolicy.enforce(
            operation="repo_discovery",
            confidence=0.78,
            context={"repo_name": "backend"}
        )
        
        assert decision.action == ConfidenceAction.REQUIRE_CONFIRMATION
        assert decision.confidence == 0.78
        assert decision.threshold == 0.85
        assert decision.preview is not None
    
    def test_very_low_confidence_rejected(self):
        """Test very low confidence is rejected"""
        decision = ConfidencePolicy.enforce(
            operation="commit_message",
            confidence=0.65,
            context={}
        )
        
        assert decision.action == ConfidenceAction.REJECT
        assert decision.confidence == 0.65
    
    def test_medium_confidence_creates_draft_pr(self):
        """Test medium confidence for commits creates draft PR"""
        decision = ConfidencePolicy.enforce(
            operation="commit_message",
            confidence=0.87,  # Between 0.85 and 0.90
            context={"message": "feat: test"}
        )
        
        assert decision.action == ConfidenceAction.CREATE_DRAFT
        assert decision.preview is not None
        assert "draft PR instead of direct commit" in decision.reason
    
    def test_destructive_op_high_threshold(self):
        """Test destructive operations have higher threshold"""
        # 0.90 should fail for destructive_op (needs 0.95)
        decision = ConfidencePolicy.enforce(
            operation="destructive_op",
            confidence=0.90,
            context={}
        )
        
        assert decision.action == ConfidenceAction.REQUIRE_CONFIRMATION
        
        # 0.95 should succeed
        decision = ConfidencePolicy.enforce(
            operation="destructive_op",
            confidence=0.95,
            context={}
        )
        
        assert decision.action == ConfidenceAction.PROCEED
    
    def test_auto_fix_requires_very_high_confidence(self):
        """Test auto-fix requires 0.95+ confidence"""
        decision = ConfidencePolicy.enforce(
            operation="auto_fix",
            confidence=0.93,
            context={}
        )
        
        assert decision.action == ConfidenceAction.REQUIRE_CONFIRMATION
        
        decision = ConfidencePolicy.enforce(
            operation="auto_fix",
            confidence=0.96,
            context={}
        )
        
        assert decision.action == ConfidenceAction.PROCEED
    
    def test_preview_generation(self):
        """Test preview object generation"""
        decision = ConfidencePolicy.enforce(
            operation="commit_message",
            confidence=0.78,
            context={
                "intent": {"operation": "commit"},
                "message": "Update files",
                "files": ["app.py", "test.py"]
            }
        )
        
        assert decision.preview is not None
        assert decision.preview["operation"] == "commit_message"
        assert decision.preview["commit_message"] == "Update files"
        assert decision.preview["files_affected"] == ["app.py", "test.py"]
        assert decision.preview["risk_level"] in ["low", "medium", "high"]
    
    def test_risk_assessment(self):
        """Test risk level assessment"""
        # High risk
        assert ConfidencePolicy._assess_risk("destructive_op", {}) == "high"
        assert ConfidencePolicy._assess_risk("bulk_operation", {}) == "high"
        
        # Medium risk
        assert ConfidencePolicy._assess_risk("commit_message", {}) == "medium"
        assert ConfidencePolicy._assess_risk("create_pr", {}) == "medium"
        
        # Low risk
        assert ConfidencePolicy._assess_risk("repo_discovery", {}) == "low"
    
    def test_format_confirmation_request(self):
        """Test confirmation request formatting"""
        decision = ConfidencePolicy.enforce(
            operation="commit_message",
            confidence=0.78,
            context={"message": "Update"}
        )
        
        response = ConfidencePolicy.format_confirmation_request(decision)
        
        assert response["success"] is False
        assert response["status"] == "needs_confirmation"
        assert response["confidence"] == 0.78
        assert "preview" in response
        assert "instruction" in response
    
    def test_format_rejection(self):
        """Test rejection response formatting"""
        decision = ConfidencePolicy.enforce(
            operation="commit_message",
            confidence=0.65,
            context={}
        )
        
        response = ConfidencePolicy.format_rejection(decision)
        
        assert response["success"] is False
        assert response["status"] == "rejected"
        assert response["confidence"] == 0.65
        assert "Cannot proceed safely" in response["message"]
    
    def test_check_confidence_helper_proceed(self):
        """Test check_confidence helper for proceed case"""
        result = check_confidence(
            operation="commit_message",
            confidence=0.95,
            context={}
        )
        
        # Should return None for proceed
        assert result is None
    
    def test_check_confidence_helper_draft_pr(self):
        """Test check_confidence helper for draft PR case"""
        result = check_confidence(
            operation="commit_message",
            confidence=0.87,
            context={"message": "test"}
        )
        
        assert result is not None
        assert result["_action"] == "create_draft_pr"
        assert "_confidence" in result
    
    def test_check_confidence_helper_confirmation(self):
        """Test check_confidence helper for confirmation case"""
        result = check_confidence(
            operation="repo_discovery",
            confidence=0.78,
            context={"repo_name": "test"}
        )
        
        assert result is not None
        assert result["status"] == "needs_confirmation"
        assert result["preview"] is not None
    
    def test_check_confidence_helper_rejection(self):
        """Test check_confidence helper for rejection case"""
        result = check_confidence(
            operation="commit_message",
            confidence=0.60,
            context={}
        )
        
        assert result is not None
        assert result["status"] == "rejected"
    
    def test_threshold_override(self):
        """Test threshold override for unknown operations"""
        from src.core.config import settings
        
        # Unknown operation should use default threshold
        decision = ConfidencePolicy.enforce(
            operation="unknown_op",
            confidence=0.90,
            context={}
        )
        
        # Should use GITOPS_FUZZY_THRESHOLD (0.85) as fallback
        assert decision.threshold == settings.GITOPS_FUZZY_THRESHOLD
    
    def test_confidence_at_exact_threshold(self):
        """Test confidence exactly at threshold"""
        # Exactly at threshold should proceed
        decision = ConfidencePolicy.enforce(
            operation="commit_message",
            confidence=0.90,
            context={}
        )
        
        assert decision.action == ConfidenceAction.PROCEED
    
    def test_confidence_just_below_threshold(self):
        """Test confidence just below threshold"""
        decision = ConfidencePolicy.enforce(
            operation="commit_message",
            confidence=0.89,
            context={}
        )
        
        # 0.89 is in draft PR range (0.85-0.90)
        assert decision.action == ConfidenceAction.CREATE_DRAFT
    
    def test_bulk_operation_threshold(self):
        """Test bulk operation confidence threshold"""
        decision = ConfidencePolicy.enforce(
            operation="bulk_operation",
            confidence=0.88,
            context={}
        )
        
        # Should require confirmation (threshold is 0.90)
        assert decision.action == ConfidenceAction.REQUIRE_CONFIRMATION
        
        decision = ConfidencePolicy.enforce(
            operation="bulk_operation",
            confidence=0.92,
            context={}
        )
        
        assert decision.action == ConfidenceAction.PROCEED


def test_confidence_decision_dataclass():
    """Test ConfidenceDecision dataclass"""
    from src.core.confidence import ConfidenceDecision
    
    decision = ConfidenceDecision(
        action=ConfidenceAction.PROCEED,
        confidence=0.95,
        threshold=0.90,
        reason="High confidence",
        preview={"test": "data"}
    )
    
    assert decision.action == ConfidenceAction.PROCEED
    assert decision.confidence == 0.95
    assert decision.threshold == 0.90
    assert decision.reason == "High confidence"
    assert decision.preview == {"test": "data"}
