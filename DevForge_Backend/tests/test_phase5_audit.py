# tests/test_phase5_audit.py
"""
Phase 5 — Audit Escalation Tests.

Verifies EscalationLogger:
- Records CRITICAL attempts (blocked and executed)
- Records blocked HIGH attempts
- Never logs raw tokens
- Sanitizes parameters correctly
- Includes all required fields in every record
"""

import pytest
import hashlib
from src.core.audit import (
    EscalationLogger,
    _sanitize_params,
    get_escalation_logger,
)


# ---------------------------------------------------------------------------
# _sanitize_params
# ---------------------------------------------------------------------------

class TestSanitizeParams:
    def test_removes_token_keys(self):
        params = {"repo_name": "owner/repo", "github_token": "ghp_secret123"}
        result = _sanitize_params(params)
        assert result["repo_name"] == "owner/repo"
        assert result["github_token"] == "[REDACTED]"

    def test_removes_password_keys(self):
        result = _sanitize_params({"password": "hunter2", "name": "test"})
        assert result["password"] == "[REDACTED]"
        assert result["name"] == "test"

    def test_removes_key_containing_secret(self):
        result = _sanitize_params({"api_key": "sk-abc"})
        assert result["api_key"] == "[REDACTED]"

    def test_preserves_safe_params(self):
        params = {"repo_name": "owner/repo", "branch_name": "main", "confirmed": True}
        result = _sanitize_params(params)
        assert result == params

    def test_empty_params_returns_empty(self):
        assert _sanitize_params(None) == {}
        assert _sanitize_params({}) == {}


# ---------------------------------------------------------------------------
# EscalationLogger — record_critical
# ---------------------------------------------------------------------------

class TestRecordCritical:
    @pytest.fixture
    def logger(self):
        return EscalationLogger()

    def _token_hash(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def test_record_critical_blocked(self, logger):
        logger.record_critical(
            audit_id="audit_test_001",
            operation="delete_repo",
            parameters={"repo_name": "owner/my-repo"},
            outcome="blocked",
            token_hash=self._token_hash("ghp_test"),
            confirmed=False,
            reason="",
        )
        records = logger.get_records()
        assert len(records) == 1
        r = records[0]
        assert r["severity"] == "CRITICAL"
        assert r["operation"] == "delete_repo"
        assert r["outcome"] == "blocked"
        assert r["audit_id"] == "audit_test_001"
        assert r["confirmed"] is False
        assert r["policy_checked"] is True
        assert r["risk_level"] == "CRITICAL"
        assert "timestamp" in r

    def test_record_critical_executed(self, logger):
        logger.record_critical(
            audit_id="audit_test_002",
            operation="delete_repo",
            parameters={"repo_name": "owner/old-repo"},
            outcome="executed",
            token_hash="abc123hash",
            confirmed=True,
            reason="Repository archived",
        )
        r = logger.get_records()[0]
        assert r["outcome"] == "executed"
        assert r["confirmed"] is True
        assert r["reason"] == "Repository archived"

    def test_token_is_hash_not_raw(self, logger):
        """Raw token must NEVER appear in the record."""
        raw_token = "ghp_SuperSecretToken"
        expected_hash = self._token_hash(raw_token)
        logger.record_critical(
            audit_id="a",
            operation="delete_repo",
            token_hash=expected_hash,
        )
        r = logger.get_records()[0]
        assert r["token_hash"] == expected_hash
        # Ensure raw token string isn't anywhere in the record
        assert raw_token not in str(r)

    def test_sensitive_params_are_sanitized(self, logger):
        logger.record_critical(
            audit_id="b",
            operation="delete_repo",
            parameters={"repo_name": "owner/r", "github_token": "ghp_secret"},
        )
        r = logger.get_records()[0]
        assert r["parameters"]["github_token"] == "[REDACTED]"
        assert r["parameters"]["repo_name"] == "owner/r"

    def test_multiple_critical_records(self, logger):
        for i in range(3):
            logger.record_critical(audit_id=f"audit_{i}", operation="delete_repo")
        assert len(logger.get_records()) == 3

    def test_get_records_for_operation_filters_correctly(self, logger):
        logger.record_critical(audit_id="a1", operation="delete_repo")
        logger.record_critical(audit_id="a2", operation="force_push")
        delete_records = logger.get_records_for_operation("delete_repo")
        assert len(delete_records) == 1
        assert delete_records[0]["operation"] == "delete_repo"


# ---------------------------------------------------------------------------
# EscalationLogger — record_blocked_high
# ---------------------------------------------------------------------------

class TestRecordBlockedHigh:
    @pytest.fixture
    def logger(self):
        return EscalationLogger()

    def test_record_blocked_high_creates_record(self, logger):
        logger.record_blocked_high(
            audit_id="hi_001",
            operation="create_repo",
            parameters={"name": "new-repo"},
            token_hash="hash_abc",
            confirmed=False,
        )
        records = logger.get_records()
        assert len(records) == 1
        r = records[0]
        assert r["severity"] == "HIGH"
        assert r["risk_level"] == "HIGH"
        assert r["outcome"] == "blocked"
        assert r["operation"] == "create_repo"
        assert r["audit_id"] == "hi_001"
        assert r["policy_checked"] is True

    def test_high_record_does_not_have_reason_field_populated(self, logger):
        """record_blocked_high doesn't require reason — defaults to empty."""
        logger.record_blocked_high(audit_id="hi_002", operation="scaffold_repo")
        r = logger.get_records()[0]
        assert r["reason"] == ""

    def test_high_blocked_with_sensitive_params_sanitized(self, logger):
        logger.record_blocked_high(
            audit_id="hi_003",
            operation="create_repo",
            parameters={"name": "test", "api_key": "secret"},
        )
        r = logger.get_records()[0]
        assert r["parameters"]["api_key"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestEscalationLoggerSingleton:
    def test_get_escalation_logger_returns_same_instance(self):
        a = get_escalation_logger()
        b = get_escalation_logger()
        assert a is b

    def test_get_records_returns_copy(self):
        logger = EscalationLogger()
        logger.record_critical(audit_id="x", operation="delete_repo")
        records = logger.get_records()
        records.clear()  # modifying the copy
        assert len(logger.get_records()) == 1  # original unchanged
