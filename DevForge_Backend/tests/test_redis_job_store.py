"""Unit tests for RedisJobStore using fakeredis."""
import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from src.storage.redis_job_store import RedisJobStore


@pytest_asyncio.fixture
async def fake_redis():
    fake = FakeRedis(decode_responses=True)
    yield fake
    await fake.aclose()


@pytest_asyncio.fixture
async def job_store(fake_redis):
    yield RedisJobStore(client=fake_redis, ttl_seconds=86400)


@pytest.mark.asyncio
async def test_create_and_get_roundtrip(job_store):
    await job_store.create(
        job_id="job_1", tenant_id="tenant-a",
        payload={"operation": "scaffold_repo", "name": "demo"},
    )
    got = await job_store.get("job_1", "tenant-a")
    assert got is not None
    assert got["status"] == "pending"
    assert got["payload"] == '{"operation": "scaffold_repo", "name": "demo"}'


@pytest.mark.asyncio
async def test_update_partial_preserves_other_fields(job_store):
    await job_store.create(
        job_id="job_2", tenant_id="tenant-a",
        payload={"operation": "scaffold_repo"},
    )
    await job_store.update("job_2", "tenant-a", status="completed",
                           result={"repo_url": "https://github.com/owner/demo"})
    got = await job_store.get("job_2", "tenant-a")
    assert got["status"] == "completed"
    assert got["result"] == '{"repo_url": "https://github.com/owner/demo"}'
    # original payload still present
    assert got["payload"] == '{"operation": "scaffold_repo"}'


@pytest.mark.asyncio
async def test_update_refreshes_ttl_to_24h(job_store, fake_redis):
    await job_store.create("job_3", "tenant-a", payload={})
    # Manually shrink TTL to simulate an aged job
    await fake_redis.expire("gitops:job:tenant-a:job_3", 60)
    await job_store.update("job_3", "tenant-a", status="running")
    ttl = await fake_redis.ttl("gitops:job:tenant-a:job_3")
    assert 86400 - 5 <= ttl <= 86400


@pytest.mark.asyncio
async def test_cross_tenant_isolation(job_store):
    await job_store.create("job_x", "tenant-a", payload={"x": 1})
    got = await job_store.get("job_x", "tenant-b")
    assert got is None


@pytest.mark.asyncio
async def test_list_for_tenant_capped_at_1000(job_store):
    for i in range(1005):
        await job_store.create(f"job_{i}", "tenant-a", payload={"i": i})
    listed = await job_store.list_for_tenant("tenant-a", limit=10000)
    assert len(listed) == 1000


@pytest.mark.asyncio
async def test_missing_tenant_id_raises(job_store):
    with pytest.raises(ValueError, match="tenant_id is required"):
        await job_store.create("job_x", "", payload={})
