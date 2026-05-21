from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_get_all_tiers_qualifies_updated_at_column():
    from src.storage.tier_config_store import TierConfigStore

    row = {
        "tier": "free",
        "hourly_limit": 50,
        "monthly_limit": 500,
        "cost_per_1k_tokens": 0.01,
        "max_expiry_days": 180,
        "is_active": True,
        "updated_at": datetime(2026, 5, 21, tzinfo=timezone.utc),
        "updated_by_email": "admin@example.com",
    }

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [row]

    class _Acquire:
        async def __aenter__(self_inner):
            return mock_conn

        async def __aexit__(self_inner, exc_type, exc, tb):
            return False

    class _Pool:
        def acquire(self_inner):
            return _Acquire()

    store = TierConfigStore()
    store._redis_initialized = True
    store.redis_client = None

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "src.storage.tier_config_store.PostgresPoolManager.get_pool",
            AsyncMock(return_value=_Pool()),
        )
        result = await store.get_all_tiers()

    query = mock_conn.fetch.await_args.args[0]
    assert "tc.updated_at" in query
    assert result["free"]["updated_at"] == "2026-05-21T00:00:00+00:00"
