"""Unit tests for RedisSessionStore using fakeredis."""
import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from src.storage.redis_session_store import RedisSessionStore


@pytest_asyncio.fixture
async def fake_redis():
    fake = FakeRedis(decode_responses=True)
    yield fake
    await fake.aclose()


@pytest_asyncio.fixture
async def session_store(fake_redis):
    yield RedisSessionStore(client=fake_redis, ttl_seconds=1800)


@pytest.mark.asyncio
async def test_get_or_create_returns_same_session_on_repeated_calls(session_store):
    s1 = await session_store.get_or_create(
        session_id="sess_abc", tenant_id="tenant-a",
        initial={"kind": "disambiguation", "candidates": ["a", "b"]},
    )
    s2 = await session_store.get_or_create(
        session_id="sess_abc", tenant_id="tenant-a",
        initial={"kind": "should-not-overwrite"},  # ignored because session exists
    )
    assert s1["kind"] == "disambiguation"
    assert s2["kind"] == "disambiguation"
    assert s2["candidates"] == ["a", "b"]


@pytest.mark.asyncio
async def test_update_patches_without_replace(session_store):
    await session_store.get_or_create(
        "sess_p", "tenant-a", initial={"kind": "disambiguation", "step": 1},
    )
    await session_store.update("sess_p", "tenant-a", {"step": 2})
    got = await session_store.get("sess_p", "tenant-a")
    assert got["kind"] == "disambiguation"  # preserved
    assert got["step"] == 2                 # patched


@pytest.mark.asyncio
async def test_sliding_ttl_resets_on_touch(session_store, fake_redis):
    await session_store.get_or_create("sess_t", "tenant-a", initial={"x": 1})
    # Shrink TTL to simulate aging
    await fake_redis.expire("gitops:session:tenant-a:sess_t", 60)
    await session_store.touch("sess_t", "tenant-a")
    ttl = await fake_redis.ttl("gitops:session:tenant-a:sess_t")
    assert 1800 - 5 <= ttl <= 1800


@pytest.mark.asyncio
async def test_cross_tenant_isolation(session_store):
    await session_store.get_or_create("sess_x", "tenant-a", initial={"x": 1})
    got = await session_store.get("sess_x", "tenant-b")
    assert got is None


@pytest.mark.asyncio
async def test_delete_then_get_returns_none_replay_protection(session_store):
    await session_store.get_or_create("sess_d", "tenant-a", initial={"x": 1})
    await session_store.delete("sess_d", "tenant-a")
    got = await session_store.get("sess_d", "tenant-a")
    assert got is None
