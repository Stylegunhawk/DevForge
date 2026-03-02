"""Tests for risk management and enforcement."""

import pytest
from src.core.risk import RiskLevel, OperationRiskRegistry, RiskGate, RiskViolation


class TestOperationRiskRegistry:
    """Test the operation risk registry."""
    
    def test_get_risk_level_known_operations(self):
        """Test getting risk levels for known operations."""
        assert OperationRiskRegistry.get_risk_level("list_repos") == RiskLevel.LOW
        assert OperationRiskRegistry.get_risk_level("create_issue") == RiskLevel.MEDIUM
        assert OperationRiskRegistry.get_risk_level("create_repo") == RiskLevel.HIGH
        assert OperationRiskRegistry.get_risk_level("delete_repo") == RiskLevel.CRITICAL
    
    def test_get_risk_level_unknown_operation(self):
        """Test getting risk level for unknown operation raises error."""
        with pytest.raises(ValueError, match="Unknown operation: unknown_op"):
            OperationRiskRegistry.get_risk_level("unknown_op")
    
    def test_list_operations_by_risk_level(self):
        """Test listing operations by risk level."""
        low_ops = OperationRiskRegistry.list_operations(RiskLevel.LOW)
        assert "list_repos" in low_ops
        assert "generate_changelog" in low_ops
        assert "create_repo" not in low_ops
        
        high_ops = OperationRiskRegistry.list_operations(RiskLevel.HIGH)
        assert "create_repo" in high_ops
        assert "delete_branch" in high_ops
        assert "list_repos" not in high_ops
        
        critical_ops = OperationRiskRegistry.list_operations(RiskLevel.CRITICAL)
        assert "delete_repo" in critical_ops
        assert "force_push" in critical_ops
        assert "create_repo" not in critical_ops


class TestRiskGate:
    """Test the risk gate enforcement."""
    
    def test_low_medium_operations_pass_without_context(self):
        """Test LOW and MEDIUM operations pass without any context."""
        # LOW operations
        assert RiskGate.check("list_repos") is None
        assert RiskGate.check("browse_files") is None
        assert RiskGate.check("generate_changelog") is None
        
        # MEDIUM operations
        assert RiskGate.check("create_issue") is None
        assert RiskGate.check("commit_file") is None
        assert RiskGate.check("create_branch") is None
    
    def test_high_operations_blocked_without_confirmation(self):
        """Test HIGH operations blocked without confirmed=true."""
        violation = RiskGate.check("create_repo")
        assert violation is not None
        assert violation.operation == "create_repo"
        assert violation.risk_level == RiskLevel.HIGH
        assert "confirmed=true" in violation.missing_requirements
        
        violation = RiskGate.check("delete_branch")
        assert violation is not None
        assert violation.risk_level == RiskLevel.HIGH
        assert "confirmed=true" in violation.missing_requirements
    
    def test_high_operations_pass_with_confirmation(self):
        """Test HIGH operations pass with confirmed=true."""
        context = {"confirmed": True}
        assert RiskGate.check("create_repo", context) is None
        assert RiskGate.check("delete_branch", context) is None
        assert RiskGate.check("scaffold_repo", context) is None
    
    def test_critical_operations_blocked_without_requirements(self):
        """Test CRITICAL operations blocked without confirmed and reason."""
        # Missing both
        violation = RiskGate.check("delete_repo")
        assert violation is not None
        assert violation.risk_level == RiskLevel.CRITICAL
        assert "confirmed=true" in violation.missing_requirements
        assert "reason (non-empty string)" in violation.missing_requirements
        
        # Missing reason only
        context = {"confirmed": True}
        violation = RiskGate.check("delete_repo", context)
        assert violation is not None
        assert "reason (non-empty string)" in violation.missing_requirements
        assert "confirmed=true" not in violation.missing_requirements
        
        # Missing confirmation only
        context = {"reason": "Need to delete this repo"}
        violation = RiskGate.check("delete_repo", context)
        assert violation is not None
        assert "confirmed=true" in violation.missing_requirements
        assert "reason (non-empty string)" not in violation.missing_requirements
    
    def test_critical_operations_pass_with_requirements(self):
        """Test CRITICAL operations pass with confirmed=true and non-empty reason."""
        context = {"confirmed": True, "reason": "Repository is no longer needed"}
        assert RiskGate.check("delete_repo", context) is None
        assert RiskGate.check("force_push", context) is None
    
    def test_critical_operations_blocked_with_empty_reason(self):
        """Test CRITICAL operations blocked with empty reason."""
        context = {"confirmed": True, "reason": ""}
        violation = RiskGate.check("delete_repo", context)
        assert violation is not None
        assert "reason (non-empty string)" in violation.missing_requirements
        
        context = {"confirmed": True, "reason": "   "}
        violation = RiskGate.check("delete_repo", context)
        assert violation is not None
        assert "reason (non-empty string)" in violation.missing_requirements
    
    def test_validate_and_raise_passes(self):
        """Test validate_and_raise passes when requirements met."""
        # LOW/MEDIUM - no context needed
        RiskGate.validate_and_raise("list_repos")
        RiskGate.validate_and_raise("create_issue")
        
        # HIGH with confirmation
        RiskGate.validate_and_raise("create_repo", {"confirmed": True})
        
        # CRITICAL with confirmation and reason
        RiskGate.validate_and_raise("delete_repo", {
            "confirmed": True, 
            "reason": "Test deletion"
        })
    
    def test_validate_and_raise_raises(self):
        """Test validate_and_raise raises when requirements not met."""
        # HIGH without confirmation
        with pytest.raises(ValueError, match="Operation create_repo requires: confirmed=true"):
            RiskGate.validate_and_raise("create_repo")
        
        # CRITICAL without requirements
        with pytest.raises(ValueError, match="Operation delete_repo requires: confirmed=true, reason \\(non-empty string\\)"):
            RiskGate.validate_and_raise("delete_repo")
    
    def test_get_operation_summary(self):
        """Test getting operation summary."""
        summary = RiskGate.get_operation_summary()
        
        assert "list_repos" in summary
        assert summary["list_repos"]["risk_level"] == "low"
        assert summary["list_repos"]["requirements"] == ["none"]
        
        assert "create_repo" in summary
        assert summary["create_repo"]["risk_level"] == "high"
        assert summary["create_repo"]["requirements"] == ["confirmed=true"]
        
        assert "delete_repo" in summary
        assert summary["delete_repo"]["risk_level"] == "critical"
        assert "confirmed=true" in summary["delete_repo"]["requirements"]
        assert "reason (non-empty string)" in summary["delete_repo"]["requirements"]
    
    def test_unknown_operation_raises(self):
        """Test that unknown operations raise ValueError."""
        with pytest.raises(ValueError, match="Unknown operation: unknown_op"):
            RiskGate.check("unknown_op")
        
        with pytest.raises(ValueError, match="Risk validation failed: Unknown operation: unknown_op"):
            RiskGate.validate_and_raise("unknown_op")


class TestRiskGateContextExtraction:
    """Test risk gate context extraction from agent context."""
    
    def test_context_extraction_with_risk_fields(self):
        """Test extracting risk confirmation from agent context."""
        context = {
            "risk_confirmed": True,
            "risk_reason": "User confirmed operation",
            "other_field": "should be ignored"
        }
        
        # HIGH operation should pass with risk_confirmed
        assert RiskGate.check("create_repo", context) is None
        
        # CRITICAL operation should pass with both fields
        assert RiskGate.check("delete_repo", context) is None
    
    def test_context_extraction_without_risk_fields(self):
        """Test behavior when risk fields not in context."""
        context = {"other_field": "value"}
        
        # HIGH operation should fail
        violation = RiskGate.check("create_repo", context)
        assert violation is not None
        assert "confirmed=true" in violation.missing_requirements
        
        # CRITICAL operation should fail
        violation = RiskGate.check("delete_repo", context)
        assert violation is not None
        assert len(violation.missing_requirements) == 2


if __name__ == "__main__":
    pytest.main([__file__])
