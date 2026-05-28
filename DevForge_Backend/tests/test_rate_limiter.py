"""Unit tests for src/core/rate_limiter.py.

Covers the atomic Lua acquire path, the release() refund path, and the
back-compat no-op behavior of check_and_increment.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.rate_limiter import RateLimiter


def _fake_redis_with_acquire_script(script_return):
    """Build a fake redis_client whose register_script returns an awaitable
    callable that resolves to ``script_return`` (the Lua script's return value).
    """
    fake_script = AsyncMock(return_value=script_return)
    fake_redis = MagicMock()
    fake_redis.register_script = MagicMock(return_value=fake_script)
    return fake_redis, fake_script


def _attach_redis(rl: RateLimiter, fake_redis) -> None:
    rl.redis_client = fake_redis
    rl._redis_initialized = True


@pytest.mark.asyncio
class TestCheckLimitsAtomicAcquire:
    async def test_allowed_returns_post_increment_counts(self):
        rl = RateLimiter()
        fake_redis, fake_script = _fake_redis_with_acquire_script([1, 7, 42])
        _attach_redis(rl, fake_redis)

        with patch.object(rl, "_get_limits", AsyncMock(return_value={"hourly": 2000, "monthly": None})), \
             patch.object(rl, "_persist_monthly_to_db", AsyncMock()):
            allowed, usage = await rl.check_limits(
                api_key_id="00000000-0000-0000-0000-000000000001",
                tier="enterprise",
            )

        assert allowed is True
        assert usage["hourly_used"] == 7
        assert usage["monthly_used"] == 42
        fake_script.assert_awaited_once()
        call_args = fake_script.await_args.kwargs["args"]
        assert call_args[0] == 2000  # hourly_limit
        assert call_args[1] == -1    # monthly unlimited encodes as -1
        assert call_args[2] == 3600  # hourly TTL

    async def test_blocked_returns_false_and_skips_db_persist(self):
        rl = RateLimiter()
        fake_redis, _ = _fake_redis_with_acquire_script([0, 50, 100])
        _attach_redis(rl, fake_redis)
        persist = AsyncMock()

        with patch.object(rl, "_get_limits", AsyncMock(return_value={"hourly": 50, "monthly": 500})), \
             patch.object(rl, "_persist_monthly_to_db", persist):
            allowed, usage = await rl.check_limits(
                api_key_id="00000000-0000-0000-0000-000000000001",
                tier="free",
            )

        assert allowed is False
        assert usage["hourly_used"] == 50
        assert usage["monthly_used"] == 100
        persist.assert_not_awaited()  # no DB bump when the slot is denied

    async def test_script_registered_once_across_calls(self):
        rl = RateLimiter()
        fake_redis, _ = _fake_redis_with_acquire_script([1, 1, 1])
        _attach_redis(rl, fake_redis)

        with patch.object(rl, "_get_limits", AsyncMock(return_value={"hourly": 2000, "monthly": None})), \
             patch.object(rl, "_persist_monthly_to_db", AsyncMock()):
            await rl.check_limits(api_key_id="k", tier="enterprise")
            await rl.check_limits(api_key_id="k", tier="enterprise")

        assert fake_redis.register_script.call_count == 1  # cached after first use

    async def test_fails_open_when_redis_unavailable(self):
        rl = RateLimiter()
        rl.redis_client = None
        rl._redis_initialized = True

        with patch.object(rl, "_get_limits", AsyncMock(return_value={"hourly": 50, "monthly": 500})):
            allowed, usage = await rl.check_limits(api_key_id="k", tier="free")

        assert allowed is True
        assert usage["hourly_used"] == 0


@pytest.mark.asyncio
class TestRelease:
    async def test_decrements_both_counters(self):
        rl = RateLimiter()
        fake_pipe = MagicMock()
        fake_pipe.decr = MagicMock()
        fake_pipe.execute = AsyncMock(return_value=[0, 0])
        fake_redis = MagicMock()
        fake_redis.pipeline = MagicMock(return_value=fake_pipe)
        _attach_redis(rl, fake_redis)

        await rl.release(api_key_id="00000000-0000-0000-0000-000000000001")

        assert fake_pipe.decr.call_count == 2
        fake_pipe.execute.assert_awaited_once()

    async def test_noop_without_redis(self):
        rl = RateLimiter()
        rl.redis_client = None
        rl._redis_initialized = True
        # Must not raise
        await rl.release(api_key_id="k")


@pytest.mark.asyncio
class TestCheckAndIncrementBackCompat:
    async def test_does_not_invoke_acquire_script(self):
        """check_and_increment is now a no-op for counters — slot is already
        reserved atomically inside check_limits. It must NOT call the Lua
        script (which would double-count) and must return current usage.
        """
        rl = RateLimiter()
        fake_redis, fake_script = _fake_redis_with_acquire_script([1, 999, 999])
        _attach_redis(rl, fake_redis)

        with patch.object(rl, "get_usage", AsyncMock(return_value={"hourly_used": 5})) as gu:
            result = await rl.check_and_increment(
                api_key_id="k", tier="enterprise", tokens_used=500,
            )

        fake_script.assert_not_awaited()
        gu.assert_awaited_once()
        assert result == {"hourly_used": 5}
