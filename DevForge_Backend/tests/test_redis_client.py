"""Unit tests for src/core/redis_client.py — factory + key helper + serde."""
import json
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_get_redis_client_raises_on_bogus_url(monkeypatch):
    """Fail-closed: bogus REDIS_URL must raise RuntimeError, not silent-fallback."""
    monkeypatch.setattr(
        "src.core.config.settings.REDIS_URL",
        "redis://nonexistent.invalid:6379/0",
    )
    import src.core.redis_client as rc
    rc._client = None  # reset singleton for this test
    with pytest.raises(RuntimeError, match="Redis required"):
        await rc.get_redis_client()


@pytest.mark.asyncio
async def test_get_redis_client_returns_singleton(monkeypatch):
    """Two calls return the same client instance (connection pool reuse)."""
    from fakeredis.aioredis import FakeRedis
    monkeypatch.setattr(
        "src.core.redis_client._build_client",
        lambda: FakeRedis(decode_responses=True),
    )
    import src.core.redis_client as rc
    rc._client = None
    c1 = await rc.get_redis_client()
    c2 = await rc.get_redis_client()
    assert c1 is c2


def test_tenant_key_composes_correctly(monkeypatch):
    """tenant_key(...) returns the exact gitops:{store}:{tenant}:{id} shape."""
    monkeypatch.setattr("src.core.config.settings.REDIS_GITOPS_KEY_PREFIX", "gitops")
    from src.core.redis_client import tenant_key
    assert tenant_key("audit", "tenant-a", "audit_xyz") == "gitops:audit:tenant-a:audit_xyz"
    assert tenant_key("job", "tenant-b", "job_123") == "gitops:job:tenant-b:job_123"
