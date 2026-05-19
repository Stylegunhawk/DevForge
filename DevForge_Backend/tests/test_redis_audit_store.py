"""Unit tests for RedisAuditStore + RedisEscalationStore using fakeredis."""
import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from src.storage.redis_audit_store import RedisAuditStore, RedisEscalationStore


@pytest_asyncio.fixture
async def fake_redis():
    """Per-test FakeRedis instance with decode_responses=True to match production."""
    fake = FakeRedis(decode_responses=True)
    yield fake
    await fake.aclose()


@pytest_asyncio.fixture
async def audit_store(fake_redis):
    yield RedisAuditStore(client=fake_redis, ttl_seconds=2592000)


@pytest_asyncio.fixture
async def escalation_store(fake_redis):
    yield RedisEscalationStore(client=fake_redis, ttl_seconds=7776000)


@pytest.mark.asyncio
async def test_save_and_get_roundtrip(audit_store):
    record = {
        "audit_id": "audit_test_1",
        "operation": "list_repos",
        "events": [{"event": "operation_start"}],
    }
    await audit_store.save("audit_test_1", "tenant-a", record)
    got = await audit_store.get("audit_test_1", "tenant-a")
    assert got is not None
    assert got["operation"] == "list_repos"
    assert got["events"][0]["event"] == "operation_start"


@pytest.mark.asyncio
async def test_cross_tenant_isolation_returns_none(audit_store):
    """Audit records keyed on tenant_id must not leak across tenants."""
    await audit_store.save("audit_test_1", "tenant-a", {"x": 1})
    got = await audit_store.get("audit_test_1", "tenant-b")
    assert got is None


@pytest.mark.asyncio
async def test_list_for_tenant_most_recent_first(audit_store):
    """LPUSH means the index returns records most-recent-first."""
    for i in range(3):
        await audit_store.save(f"audit_{i}", "tenant-a", {"i": i})
    listed = await audit_store.list_for_tenant("tenant-a", limit=10)
    assert [r["i"] for r in listed] == [2, 1, 0]


@pytest.mark.asyncio
async def test_list_trim_caps_at_5000(audit_store):
    """LTRIM keeps the index bounded at 5000 entries per tenant."""
    for i in range(5005):
        await audit_store.save(f"audit_{i}", "tenant-a", {"i": i})
    listed = await audit_store.list_for_tenant("tenant-a", limit=10000)
    assert len(listed) == 5000


@pytest.mark.asyncio
async def test_missing_tenant_id_raises(audit_store):
    with pytest.raises(ValueError, match="tenant_id is required"):
        await audit_store.save("audit_x", "", {"x": 1})


@pytest.mark.asyncio
async def test_save_ttl_is_30_days(audit_store, fake_redis):
    await audit_store.save("audit_x", "tenant-a", {"x": 1})
    ttl = await fake_redis.ttl("gitops:audit:tenant-a:audit_x")
    # 30 days = 2592000 seconds; allow 5s skew for test timing
    assert 2592000 - 5 <= ttl <= 2592000


@pytest.mark.asyncio
async def test_escalation_critical_record_persists(escalation_store):
    await escalation_store.record_critical(
        audit_id="audit_e1",
        tenant_id="tenant-a",
        operation="delete_repo",
        parameters={"repo_name": "owner/r"},
        outcome="executed",
        token_hash="abcd1234",
        confirmed=True,
        reason="cleanup",
    )
    records = await escalation_store.get_records_for_tenant("tenant-a", limit=10)
    assert len(records) == 1
    assert records[0]["operation"] == "delete_repo"
    assert records[0]["outcome"] == "executed"
    assert records[0]["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_escalation_ttl_is_90_days(escalation_store, fake_redis):
    await escalation_store.record_critical(
        audit_id="e1", tenant_id="t1", operation="x", outcome="blocked"
    )
    ttl = await fake_redis.ttl("gitops:escalation:t1:e1")
    assert 7776000 - 5 <= ttl <= 7776000
