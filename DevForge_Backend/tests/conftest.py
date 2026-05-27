"""Test infrastructure fixtures for the DevForge backend test suite.

Provides:
  - _bypass_api_key_middleware: autouse session fixture that patches
    api_key_store.validate_key so no Postgres connection is needed.
  - _bypass_rate_limiter: autouse session fixture that patches
    rate_limiter.check_limits so no Redis/Postgres connection is needed.
  - patch_github_operation: per-test fixture that yields a context manager
    for replacing SUPPORTED_TOOLS['github_operation'] directly.
"""

import pytest
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from src.main import app


# Session-scoped TestClient that properly triggers the FastAPI lifespan
# (including the FastMCP session manager). Used by test_github_integration.py.
# base_url uses localhost:80 so the Host header satisfies FastMCP's DNS-rebinding
# protection (allowed_hosts defaults to ["127.0.0.1:*", "localhost:*", "[::1]:*"]).
# The pattern "localhost:*" requires a port suffix, so "localhost:80" is needed;
# plain "localhost" without a port does NOT match the wildcard pattern.
@pytest.fixture(scope="session")
def started_client():
    with TestClient(
        app,
        base_url="http://localhost:8001",
        headers={"Accept": "application/json"},
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Internal helper — mirrors the shape APIKeyAuthMiddleware reads off metadata
# ---------------------------------------------------------------------------

class _FakeApiKeyMetadata:
    """Mimics the shape of APIKeyMetadata used by APIKeyAuthMiddleware.

    Mirrors every attribute the middleware reads at lines 50–82 of
    src/core/api_key_middleware.py:
      - expires_at           (checked first; None means never expires)
      - tenant_id
      - integration_name
      - tier
      - scopes
      - id                   (stored as request.state.api_key_id)
      - user_id
      - hourly_limit_override
      - monthly_limit_override
    """

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


_FAKE_METADATA = _FakeApiKeyMetadata(
    id="test-api-key-id",
    tier="enterprise",
    integration_name="pytest",
    tenant_id="test-tenant",
    user_id="test-user",
    scopes=["*"],
    expires_at=None,
    hourly_limit_override=None,
    monthly_limit_override=None,
)


# ---------------------------------------------------------------------------
# Fix 1: Bypass APIKeyAuthMiddleware for every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def _bypass_api_key_middleware():
    """Patch api_key_store.validate_key so every TestClient request passes auth.

    APIKeyAuthMiddleware imports api_key_store at module level:
        from src.storage.api_key_store import api_key_store   # line 14
    We patch it where it is USED (inside the middleware module) so the patch
    is effective regardless of import order.
    """
    with patch(
        "src.core.api_key_middleware.api_key_store.validate_key",
        new=AsyncMock(return_value=_FAKE_METADATA),
    ):
        yield


@pytest.fixture(autouse=True, scope="session")
def _bypass_rate_limiter():
    """Patch rate_limiter methods so no Redis/Postgres call is made.

    The MCP endpoint (routers/__init__.py) calls several rate_limiter methods
    when api_key_id is set (because _bypass_api_key_middleware sets it):
      - check_limits   (line ~1137): pre-check before executing tool
      - check_and_increment (line ~1244): post-execution increment
      - get_usage      (line ~1319): to build response headers
    All three talk to Redis/Postgres. We patch them all to return safe defaults.
    """
    fake_limit_info = {
        "hourly_used": 0,
        "hourly_limit": None,
        "monthly_used": 0,
        "monthly_limit": None,
        "hourly_reset_at": "2099-01-01T00:00:00",
        "monthly_reset_at": "2099-02-01T00:00:00",
    }
    with patch(
        "src.api.routers.rate_limiter.check_limits",
        new=AsyncMock(return_value=(True, fake_limit_info)),
    ), patch(
        "src.api.routers.rate_limiter.check_and_increment",
        new=AsyncMock(return_value={**fake_limit_info, "success": True}),
    ), patch(
        "src.api.routers.rate_limiter.get_usage",
        new=AsyncMock(return_value=fake_limit_info),
    ), patch(
        "src.api.mcp.dispatch.rate_limiter.check_limits",
        new=AsyncMock(return_value=(True, fake_limit_info)),
    ), patch(
        "src.api.mcp.dispatch.rate_limiter.check_and_increment",
        new=AsyncMock(return_value={**fake_limit_info, "success": True}),
    ), patch(
        "src.api.mcp.dispatch.rate_limiter.get_usage",
        new=AsyncMock(return_value=fake_limit_info),
    ):
        yield


# ---------------------------------------------------------------------------
# Fix 2: patch_github_operation — correct patch target for SUPPORTED_TOOLS
# ---------------------------------------------------------------------------

@pytest.fixture
def patch_github_operation():
    """Yield a context manager that replaces SUPPORTED_TOOLS['github_operation'].

    Patching the source module (src.agents.github.agent.github_agent_invoke)
    does NOT work because routers/__init__.py captures the reference at import
    time into SUPPORTED_TOOLS. We must patch the dict directly.

    Usage::

        async def test_x(patch_github_operation):
            mock = AsyncMock(return_value={"success": True, ...})
            with patch_github_operation(mock):
                response = client.post("/mcp/", json=...)
            mock.assert_called_once()
    """

    @contextmanager
    def _patch(replacement_callable):
        with patch.dict(
            "src.api.routers.SUPPORTED_TOOLS",
            {"github_operation": replacement_callable},
        ):
            yield replacement_callable

    return _patch
