# GitOps Slice 2 — Redis-Backed Persistence for Audit, Jobs, and Sessions

**Date:** 2026-05-16
**Status:** Draft — pending user review
**Scope:** Slice 2 of the "make gitops tool production-grade" initiative
**Resolves blockers:** #4 (per-worker audit/jobs state), #8 (disambiguation session storage)
**Depends on:** Slice 1 (already merged — #5 escalation wiring, #9 upgrade_url, #10 SSRF guard)
**Author:** generated via the `superpowers:brainstorming` skill

---

## Goal (one sentence)

Move the GitOps audit log, async job queue, and disambiguation session store out of per-worker in-memory Python dicts into Redis so all 6 Gunicorn workers share consistent state and `/jobs/{id}` lookups stop randomly 404-ing.

## Why now

1. **Production deploys use Gunicorn × 6 workers** (per `DevForge_Backend/CLAUDE.md`). Each worker has its own `AuditLogger._logs` dict, `JobQueue.jobs` dict, and `SessionManager.sessions` dict. A job created by worker 3 is invisible to worker 5 when the client polls `/jobs/{id}`.
2. **Worker restart vaporizes audit history.** Today, a Gunicorn worker restart loses every audit timeline the worker held. This is incompatible with the security/compliance use case.
3. **The disambiguation flow returns `needs_clarification` with no state persistence** — the next call has to restart from scratch (Blocker #8). Spec §3 also documents this gap.
4. **Redis is already a hard dependency** of this project (`src/core/rate_limiter.py` uses `redis.asyncio` for rate-limit counters). Adopting Redis for the GitOps stores adds zero new infra to the operational footprint.

## Non-goals

- No data migration. Existing per-worker in-memory audit records evaporate on deploy (they always have).
- No admin/export endpoints for audit history. The Redis schema supports it but the endpoint isn't built here.
- No Redis cluster sharding. Single-instance Redis only, matching `rate_limiter.py`.
- No rollback execution (Blocker #3). That's Slice 3 and depends on this slice's persistent audit_id lookup.
- No unification with the rate limiter's separate `_get_redis_client` factory. Two factories live side by side for now (low value, high blast radius to merge).
- No new metrics/dashboards. Existing observability tooling stays as is.

---

## §1 Architecture

Three Redis-backed adapter classes replace the per-worker in-memory dicts in `AuditLogger`, `JobQueue`, and `SessionManager`. All three share a single connection-pool factory.

```
src/core/redis_client.py            ── single factory, connection pool, health check
        │
        ├──> src/storage/redis_audit_store.py    ── RedisAuditStore + RedisEscalationStore
        ├──> src/storage/redis_job_store.py      ── RedisJobStore
        └──> src/storage/redis_session_store.py  ── RedisSessionStore
                            │
                            └──> swapped into singleton factories at bottom of:
                                  src/core/audit.py
                                  src/core/jobs.py
                                  src/core/session.py
```

**Why this shape:**
- Each store has one responsibility, one file. No cross-talk.
- The shared `get_redis_client()` factory does a fail-closed `PING` health check on first use — if Redis is unreachable and `REDIS_URL` is set, the singleton raises and the API health check fails. Matches the explicit fail-closed decision.
- The existing in-memory `AuditLogger`, `JobQueue`, `SessionManager` classes stay as pure-Python fallbacks for unit tests. The singleton factories at the bottom of each module check `settings.REDIS_URL` (when set, return Redis adapter; when None or in pytest, return in-memory).
- Redis keys are prefixed `gitops:{store_type}:{tenant_id}:{logical_id}` so listing per-tenant is `SCAN MATCH gitops:audit:{tenant_id}:*` — O(records) for that tenant only, zero cross-tenant leakage.
- Tiered TTLs are set per-key via `SET ... EX`: audit 30d, escalation 90d, jobs 24h (refreshed on update), sessions 30min (sliding).

**Backward compat at the contract level:**
- Tests continue to work using the in-memory fallback. No Redis required for unit tests.
- Production must set `REDIS_URL`. The existing `config.py:75` warning about localhost-Redis-in-production stays.
- `audit_id` format unchanged. Keys add a tenant prefix but the `audit_id` itself is opaque to callers.

---

## §2 Components

| File | LoC est | Responsibility |
|------|---------|----------------|
| `src/core/redis_client.py` (new) | ~80 | `get_redis_client()` singleton returning `redis.asyncio.Redis` with connection pool. Performs fail-closed `PING` at first call; raises `RuntimeError("Redis required for gitops stores")` if `REDIS_URL` is unset or unreachable. Reads `REDIS_URL`, optional `REDIS_GITOPS_DB` (default `0`), `REDIS_GITOPS_KEY_PREFIX` (default `"gitops"`). Exposes a `tenant_key(store_type, tenant_id, logical_id)` helper that returns `"{prefix}:{store_type}:{tenant_id}:{logical_id}"`. Shared `_dumps`/`_loads` JSON helpers. |
| `src/storage/redis_audit_store.py` (new) | ~140 | Two classes: `RedisAuditStore` + `RedisEscalationStore`. `RedisAuditStore` methods: `save(audit_id, tenant_id, record)`, `get(audit_id, tenant_id)`, `list_for_tenant(tenant_id, limit=50)`. JSON STRING values with 30d TTL. `RedisEscalationStore`: append-only — `record_critical(...)`, `record_blocked_high(...)`, `get_records_for_tenant(...)`. 90d TTL. Each tenant has a per-tenant `LIST` index plus per-record `STRING` so list-recent is fast and bounded via `LTRIM`. |
| `src/storage/redis_job_store.py` (new) | ~120 | `RedisJobStore` replacing `JobQueue.jobs`. Methods: `create(job_id, tenant_id, payload)`, `update(job_id, tenant_id, status, result=None)`, `get(job_id, tenant_id)`, `list_for_tenant(tenant_id)`. `HASH` per job (partial updates), per-tenant `LIST` index capped at 1000. 24h TTL refreshed on every update. |
| `src/storage/redis_session_store.py` (new) | ~110 | `RedisSessionStore` replacing `SessionManager.sessions`. Methods: `get_or_create(session_id, tenant_id, initial=None)`, `update(session_id, tenant_id, patch)`, `touch(session_id, tenant_id)`, `delete(session_id, tenant_id)`. Sliding TTL: every read/write resets to `settings.GITOPS_SESSION_TTL` (default 1800s). |
| `src/core/audit.py` (modify) | ~25 lines changed | At module bottom: `get_audit_logger()` and `get_escalation_logger()` factories return the Redis adapter when `settings.REDIS_URL` is set AND `PYTEST_CURRENT_TEST` is unset; otherwise return the existing in-memory singletons. `EscalationLogger` and any new public method become `async def` (Issue 1 of §7). |
| `src/core/jobs.py` (modify) | ~20 lines changed | Same factory swap pattern. `JobQueue` already mostly async. |
| `src/core/session.py` (modify) | ~20 lines changed | Same factory swap pattern. `SessionContext` and `SessionManager` methods become `async def`. |
| `src/agents/github/agent.py` (modify) | ~30 lines changed | (a) Add `await` to the two existing `escalation.record_*(...)` call sites at line 690 and line 1008. (b) Wire the disambiguation flow to **save** the disambiguation context into a session and return `session_id` in the response. (c) On the **next** call, if `context.session_id` is present, restore the disambiguation context and short-circuit fuzzy-search. This is the actual fix for Blocker #8. |
| `src/api/routers/__init__.py` (modify) | ~10 lines changed | Pass `tenant_id` (already on `request.state.tenant_id` from `APIKeyAuthMiddleware`) into `github_agent_invoke`. The agent forwards it to all three stores when constructing keys. |
| `src/core/config.py` (modify) | ~6 lines added | New optional settings: `REDIS_GITOPS_DB: int = 0`, `REDIS_GITOPS_KEY_PREFIX: str = "gitops"`, `GITOPS_AUDIT_TTL_SECONDS: int = 2592000`, `GITOPS_ESCALATION_TTL_SECONDS: int = 7776000`, `GITOPS_JOB_TTL_SECONDS: int = 86400`. `GITOPS_SESSION_TTL` already exists. |
| `tests/test_redis_audit_store.py` (new) | ~120 | 8 cases using `fakeredis.aioredis.FakeRedis`. |
| `tests/test_redis_job_store.py` (new) | ~110 | 6 cases. |
| `tests/test_redis_session_store.py` (new) | ~100 | 5 cases. |
| `tests/test_redis_client.py` (new) | ~80 | 3 cases (fail-closed health check, singleton identity, in-memory fallback). |
| `tests/test_github_integration.py` (modify) | ~250 added | New `TestSlice2Persistence` class — 10 cases run against the in-memory fallback. |
| `tests/test_phase5_audit.py`, `tests/test_session.py`, `tests/test_jobs.py` (modify) | ~12 LoC each | Add `@pytest.mark.asyncio` and `await` to call sites of methods that become async. |

**Total estimated diff:** ~750 LoC production (incl. 4 new files), ~440 LoC new tests, ~36 LoC of existing-test updates. 4 new files, 7 modified files. No production file grows by more than ~30 LoC.

---

## §3 Data flow & Redis key structure

### Key layout (tenant-scoped, never overlap)

```
gitops:audit:{tenant_id}:{audit_id}                 STRING (JSON)       TTL 30d
gitops:audit_index:{tenant_id}                      LIST<audit_id>      TTL refreshed on LPUSH; LTRIM to 5000
gitops:escalation:{tenant_id}:{audit_id}            STRING (JSON)       TTL 90d
gitops:escalation_index:{tenant_id}                 LIST<audit_id>      TTL 90d; LTRIM to 5000
gitops:job:{tenant_id}:{job_id}                     HASH                TTL 24h refreshed on update
gitops:job_index:{tenant_id}                        LIST<job_id>        TTL 24h; LTRIM to 1000
gitops:session:{tenant_id}:{session_id}             STRING (JSON)       sliding TTL 30min
```

- **Per-tenant `*_index` LIST:** `SCAN MATCH pattern:*` is O(records-across-all-tenants); `LRANGE` on a per-tenant index is O(returned). Fast tenant listing; bounded memory via `LTRIM`.
- **STRING+JSON for audit/sessions, HASH for jobs:** jobs get partial updates frequently (`HSET job:x status completed result <json>`); HASH avoids re-serializing the whole record. Audit and sessions are append-once or full-replace, so STRING is simpler.
- **LIST not SORTED SET for indexes:** insertion order is what we want (most-recent first). Sorted-set would require a timestamp score and adds complexity for no win.

### Write path — audit record (best-effort after operation success)

```
agent.py (any node emitting an audit event)
   └─ timeline.add_event(...)                       ── mutates in-memory Timeline
agent.py end of execute_github_operation
   └─ await get_audit_logger().save(audit_id, tenant_id, timeline.to_dict())
            │
            └─ RedisAuditStore.save:
                  pipeline:
                    SET    gitops:audit:{t}:{a} <json>  EX 2592000
                    LPUSH  gitops:audit_index:{t} {a}
                    LTRIM  gitops:audit_index:{t} 0 4999
                    EXPIRE gitops:audit_index:{t} 2592000
                  EXEC
```

Single pipelined round-trip per audit save. If `EXEC` fails (Redis down mid-call), the call raises `RedisError`; the outer try/except in `execute_github_operation` already catches and logs. The user's response still completes successfully — only the audit record is lost. We treat audit save as best-effort once the operation has executed (we can't rollback a real GitHub action because Redis went down between the API call and the audit save).

### Write path — escalation record

Same pipelined shape as audit but separate key prefix and 90d TTL. The escalation pipeline runs from `agent.py` risk-gate block and execute success paths (already wired in Slice 1) — the change is that `EscalationLogger.record_*()` now writes to Redis instead of `self._records`. All three current call sites in `agent.py` get an `await` prefix.

### Write path — job state

```
celery worker creates job:
   pipeline:
     HSET   gitops:job:{t}:{j} status=pending payload=<json> created_at=<ts>
     EXPIRE gitops:job:{t}:{j} 86400
     LPUSH  gitops:job_index:{t} {j}
     LTRIM  gitops:job_index:{t} 0 999
     EXPIRE gitops:job_index:{t} 86400
   EXEC

celery worker updates job:
   HSET   gitops:job:{t}:{j} status=completed result=<json> updated_at=<ts>
   EXPIRE gitops:job:{t}:{j} 86400         (TTL refresh on each update)
```

### Read path — `/jobs/{job_id}`

```
GET /api/jobs/{job_id}
   tenant_id = request.state.tenant_id
   ┌─ HGETALL gitops:job:{tenant_id}:{job_id}
   │     hit  → return job
   │     miss → ...
   └─ 404 (job belongs to a different tenant, or expired, or never existed)
```

This is the fix for Blocker #4: every worker queries the same Redis key, so `/jobs/{id}` works regardless of which worker handles the request.

### Write+read path — disambiguation session (fix for Blocker #8)

```
Call N (fuzzy match returns multiple repos):
   session_id = f"sess_{uuid.uuid4().hex[:16]}"
   await RedisSessionStore.get_or_create(session_id, tenant_id, initial={
      "kind": "disambiguation",
      "operation": "create_issue",
      "candidates": [{"repo": "owner/api-backend", "confidence": 0.85}, ...],
      "params_pending": {"title": "...", "body": "..."},
      "entry_method": state["entry_method"],
   })
   response: {success: false, status: "needs_clarification",
              session_id: "<session_id>", options: [...]}

Call N+1 (user picks option):
   arguments.context.session_id = "<session_id>"
   arguments.context.selected_repo = "owner/api-backend"
   agent flow:
      session = await RedisSessionStore.get(session_id, tenant_id)
      if session and session["kind"] == "disambiguation":
         # Skip fuzzy_search entirely. Use the candidate the user picked.
         state["parameters"] = {**session["params_pending"], "repo_name": selected_repo}
         state["entry_method"] = session.get("entry_method", "natural_language")
         await RedisSessionStore.delete(session_id, tenant_id)   # one-shot use
         # Continue into validate → policy → risk → execute as normal
```

The `session_id` is opaque to the caller — they echo it back. TTL slides on every access (sliding 30min). After successful resolution, the session is **deleted** in the same flow so the caller can't replay it.

### Serialization

- Stdlib `json.dumps(..., default=str)` so `datetime` and `Decimal` serialize without custom encoders.
- Single shared `_dumps`/`_loads` pair in `src/core/redis_client.py` — consistent formatting, single audit point for serialization bugs.

---

## §4 Error handling

| Failure mode | Behavior | User-visible response |
|--------------|----------|----------------------|
| **Redis unreachable at startup** | `get_redis_client()` does `PING` on first access. If it fails AND `REDIS_URL` is set, raise `RuntimeError("Redis required for gitops stores: <reason>")`. The `/health` endpoint reflects this. In-memory fallback is NOT used in production. | First request returns HTTP 503 `{"detail": "Storage backend unavailable"}`. Operators see the error in logs immediately. |
| **Redis unreachable mid-call (audit save)** | The agent's `execute_github_operation` already wraps audit writes in try/except. On `RedisError`, log `ERROR [audit_id] Redis write failed, audit record lost: <error>` and continue. The user-facing response still succeeds because the GitHub action already happened. | User sees normal success response. Operations team gets log alert. |
| **Redis unreachable mid-call (job create)** | The Celery task creation path fails the entire task — raise `RedisError`. Caller gets HTTP 500 with `{"success": false, "message": "Failed to create async job"}`. **Do NOT** silently fall back to in-memory because the next polling call won't find the job. | User sees a clean 500; can retry. No silent failure. |
| **Redis unreachable mid-call (session save)** | Session write failure on disambiguation path → log error, return the disambiguation response WITHOUT a `session_id`. Caller can still pick a repo manually but loses the session-restore optimization. | `response.session_id` absent. Caller can still proceed by sending a fresh disambiguation request with their resolved repo. |
| **Redis key collision** | Effectively impossible: keys are `gitops:{store_type}:{tenant_id}:{audit_id_or_uuid}` with UUID-suffixed tails. SET semantics are last-write-wins by design. | N/A |
| **Invalid `tenant_id` (None or empty)** | Reject at adapter boundary — `RedisAuditStore.save(...)` raises `ValueError("tenant_id is required for Redis-backed stores")`. The agent reads `tenant_id` from `request.state.tenant_id`, set by `APIKeyAuthMiddleware`. | HTTP 500 with a clear message — should never happen with a correctly-configured API key. |
| **Serialization failure** | If `_dumps(value)` raises, log `ERROR` with the audit_id and drop the entire record. Do NOT crash the user's call. `default=str` coerces most non-trivial types rather than raising. | User sees normal response. Audit record lost. |
| **TTL clock skew / sudden expiry** | Cannot happen — Redis enforces TTL server-side. We don't depend on client clocks. | N/A |
| **Session `session_id` from another tenant** | Key constructed from tenant + session_id; cross-tenant access returns `None`. Agent treats `None` as "no session, proceed with full disambiguation". | User sees fresh disambiguation rather than a leaked session — fail-safe by design. |
| **Session expired between disambiguation and resolution** | Same as cross-tenant: returns `None`, agent falls back to fresh disambiguation. | Second disambiguation rather than mysterious error. |
| **Replay attack on session_id** | After successful resolution, session is `DEL`'d. A replayed `session_id` returns `None`. Replay impossible. | N/A |
| **Fakeredis vs real Redis behavior divergence in tests** | Tests use `fakeredis.aioredis.FakeRedis`. Pinned to `fakeredis>=2.20` (tested `EX` on `SET` and `EXPIRE` on `LIST`). | N/A |

---

## §5 Backward compatibility — strict guarantees

1. **Existing in-memory tests run without Redis.** Factory at bottom of `audit.py`/`jobs.py`/`session.py` returns the in-memory singleton when `settings.REDIS_URL` is None OR `PYTEST_CURRENT_TEST` is set. The 33 existing structured-mode tests need zero changes.
2. **`audit_id` format unchanged** (`audit_YYYYMMDD_<12hex>` from `generate_audit_id()`). Keys gain a tenant prefix but the `audit_id` itself stays opaque to callers.
3. **`tenant_id` flows through without API contract change.** Already on `request.state.tenant_id` from middleware. Passed as a new optional kwarg into `github_agent_invoke(..., tenant_id=...)`. Default `"unknown"` matches the existing pattern.
4. **Existing in-memory classes are NOT deleted.** They become the test-mode fallback. Interface contracts are frozen so the Redis adapter implements them exactly.
5. **Disambiguation flow has zero impact on callers who don't use session_id.** Ignoring the new `session_id` field gets the same fresh-disambiguation behavior as today.
6. **`/api/jobs/{job_id}` continues to work in single-worker dev mode** when `REDIS_URL` is unset. Multi-worker mode requires `REDIS_URL`.
7. **No new required env vars.** `REDIS_URL` is already required for the rate limiter in production. The new `GITOPS_*_TTL_SECONDS` vars are optional with sensible defaults.

### Explicit non-guarantees

- No audit-data migration on rollout. History starts fresh from Phase 2.
- No cross-format upgrade path. Future schema changes will treat older-format records as opaque.
- No Redis-cluster sharding. Single-instance Redis only.

---

## §6 Testing

Three layers. Total ~28-29 new tests. All run as `pytest tests/ -v`.

### Layer 1 — Per-adapter unit tests with `fakeredis`

**`tests/test_redis_audit_store.py`** — 8 cases:
- `test_save_and_get_roundtrip`
- `test_cross_tenant_isolation_returns_none`
- `test_list_for_tenant_most_recent_first`
- `test_list_trim_caps_at_5000`
- `test_missing_tenant_id_raises`
- `test_save_ttl_is_30_days`
- `test_escalation_critical_record_persists`
- `test_escalation_ttl_is_90_days`

**`tests/test_redis_job_store.py`** — 6 cases:
- `test_create_and_get_roundtrip`
- `test_update_partial_preserves_other_fields`
- `test_update_refreshes_ttl_to_24h`
- `test_cross_tenant_isolation`
- `test_list_for_tenant_capped_at_1000`
- `test_missing_tenant_id_raises`

**`tests/test_redis_session_store.py`** — 5 cases:
- `test_get_or_create_returns_same_session_on_repeated_calls`
- `test_update_patches_without_replace`
- `test_sliding_ttl_resets_on_touch`
- `test_cross_tenant_isolation`
- `test_delete_then_get_returns_none_replay_protection`

### Layer 2 — Integration tests against in-memory fallback

**`tests/test_github_integration.py::TestSlice2Persistence`** — 10 cases (no fakeredis required):
- `test_audit_record_is_saved_after_successful_operation`
- `test_escalation_critical_record_after_destructive_op`
- `test_escalation_critical_record_after_blocked_op`
- `test_audit_record_lookup_by_id`
- `test_job_create_and_lookup_within_session`
- `test_disambiguation_persists_session`
- `test_disambiguation_resolves_via_session_id`
- `test_disambiguation_session_deleted_after_resolve`
- `test_cross_tenant_audit_isolation`
- `test_missing_tenant_id_at_runtime_raises_clean_error`

### Layer 3 — Client/factory tests

**`tests/test_redis_client.py`** — 3 cases:
- `test_get_redis_client_raises_on_bogus_url`
- `test_get_redis_client_returns_singleton`
- `test_factory_returns_in_memory_when_redis_url_unset`

### Existing-test updates (sync → async migration)

| File | Change | Cost |
|------|--------|------|
| `tests/test_phase5_audit.py` | Add `@pytest.mark.asyncio` and `await` to EscalationLogger calls | ~12 LoC |
| `tests/test_session.py` | Same pattern for SessionManager/SessionContext | ~12 LoC |
| `tests/test_jobs.py` | Spot-fix; most methods already async | ~6 LoC |

### Coverage targets

- Every adapter method exercised in at least one fakeredis test.
- Cross-tenant isolation tested for all three stores.
- TTL values verified for audit (30d), escalation (90d), jobs (24h sliding), sessions (30min sliding).
- Fail-closed-at-startup tested.
- In-memory fallback tested.
- Disambiguation session round-trip tested.
- Disambiguation replay protection tested.

### Gate target

**62 tests passing** (30 existing structured + 19 new adapter + 10 new integration + 3 client/config tests), zero new regressions, zero changes to the pre-existing 16 broken tests.

---

## §7 Backward compatibility plan (deep dive)

### Issue 1: Sync → async signature breaking change

The current `EscalationLogger` and `SessionManager` methods are synchronous. Redis adapters must be async (`redis.asyncio`). Same-name methods can't be both.

**Strategy:** Convert the in-memory classes to `async def` too — single interface, no dual-mode confusion. In-memory implementations are still cheap; they just `await asyncio.sleep(0)` (effectively free).

**Surface inventory:**

| File:Line | Symbol | Current | After |
|-----------|--------|---------|-------|
| `src/core/audit.py:308` | `EscalationLogger.record_critical()` | sync | `async def` |
| `src/core/audit.py:338` | `EscalationLogger.record_blocked_high()` | sync | `async def` |
| `src/core/audit.py:365` | `EscalationLogger.get_records()` | sync | `async def` |
| `src/core/audit.py:369` | `EscalationLogger.get_records_for_operation()` | sync | `async def` |
| `src/core/session.py:25` | `SessionContext.store_artifact()` | sync | `async def` |
| `src/core/session.py:40` | `SessionContext.get_artifact()` | sync | `async def` |
| `src/core/session.py:118` | `SessionManager.get_session()` | sync | `async def` |
| `src/core/session.py:130` | `SessionManager.delete_session()` | sync | `async def` |
| `src/core/audit.py:159` | `AuditLogger.get_summary()` | sync | **stays sync** (not on hot path) |
| `src/core/jobs.py:108` | `JobQueue.get_job()` | already async | unchanged |
| `src/core/jobs.py:201` | `JobQueue.cleanup_old_jobs()` | already async | unchanged |

### Issue 2: Concrete production call sites to update

| File:Line | Current | After |
|-----------|---------|-------|
| `src/agents/github/agent.py:690` | `escalation.record_critical(...)` | `await escalation.record_critical(...)` |
| `src/agents/github/agent.py:690` | `escalation.record_blocked_high(...)` | `await escalation.record_blocked_high(...)` |
| `src/agents/github/agent.py:1008` | `escalation.record_critical(...)` | `await escalation.record_critical(...)` |

Both methods are inside `async def` functions — adding `await` is mechanical.

`src/tools/scaffold.py:182` — `get_job_queue()` returns an object whose hot-path methods are already async. No change.

### Issue 3: Existing test files needing an `await` sweep

3 test files touched. Detailed per Layer-3 update list in §6.

### Issue 4: Deployment & rollback plan

The migration is **config-only** — no schema migration, no data migration. Three phases:

```
Phase 0 (current): No code change. In-memory dicts. State splits across Gunicorn × 6.

Phase 1 (deploy code, REDIS_URL still unset):
  - New code runs but factory returns in-memory singletons (the `if REDIS_URL` check).
  - Verifies no regression introduced by code changes alone.
  - Existing audit/jobs behavior IDENTICAL to today.
  - GO/NO-GO gate: existing 33+18 tests pass on the deployed image.

Phase 2 (set REDIS_URL, single API worker):
  - Set REDIS_URL in production .env.
  - Restart only ONE worker; let it serve traffic for 30min.
  - Watch logs for RedisError, health check failures, 503s.
  - Smoke-test: create_repo+confirmed → verify escalation record appears in `gitops:escalation:*` keys via redis-cli.
  - Smoke-test: HIGH risk-gate block → verify `gitops:escalation:*` blocked record.
  - Smoke-test: trigger async job → verify `/jobs/{id}` returns 200 (the bug we fixed).
  - GO/NO-GO gate: zero RedisError logs, all 3 smokes pass.

Phase 3 (full deploy, all 6 workers on Redis):
  - Roll the remaining 5 workers.
  - `/jobs/{id}` polling now works regardless of which worker handles the read.
  - Audit history persists across worker restarts.

Rollback at any phase: unset REDIS_URL → next worker restart returns to in-memory mode → no data loss (nothing relied on Redis yet).
```

### Issue 5: Verification gates

Before promoting Phase 2 to Phase 3, all must pass:

```bash
# 1. Gitops namespace populated with expected key shapes
docker exec devforge-redis redis-cli --scan --pattern 'gitops:*' | head -20

# 2. TTLs match config (audit 30d, escalation 90d, jobs 24h)
docker exec devforge-redis redis-cli ttl gitops:audit:<some-tenant>:<some-audit-id>
# Expect: 2591999 ± 60s

# 3. No cross-tenant leakage (test with two real tenants)
docker exec devforge-redis redis-cli --scan --pattern 'gitops:audit:tenant-a:*' | wc -l
docker exec devforge-redis redis-cli --scan --pattern 'gitops:audit:tenant-b:*' | wc -l

# 4. /jobs/{id} cross-worker test
JOB_ID=$(curl -s -X POST .../gateway -d '{"operation": "scaffold_repo", ...}' | jq -r .job_id)
for i in {1..20}; do curl -s .../api/jobs/$JOB_ID | jq -r .status; done
# All 20 polls should return same/progressing status (no random 404s)
```

### Issue 6: Compatibility test suite gate

Before merging Slice 2, all of these must be green:

```bash
# 1. Existing structured-call suite (30 tests)
./venv/bin/pytest tests/test_github_integration.py::TestStructuredCallMode -v

# 2. Existing audit/session/jobs unit tests with async migration applied
./venv/bin/pytest tests/test_phase5_audit.py tests/test_session.py tests/test_jobs.py -v

# 3. New Redis adapter suite (19 tests with fakeredis)
./venv/bin/pytest tests/test_redis_audit_store.py tests/test_redis_job_store.py \
                  tests/test_redis_session_store.py tests/test_redis_client.py -v

# 4. New integration suite (10 tests, in-memory fallback)
./venv/bin/pytest tests/test_github_integration.py::TestSlice2Persistence -v

# 5. End-to-end: single-worker mode (REDIS_URL unset)
unset REDIS_URL; ./venv/bin/pytest tests/test_github_integration.py -v -k structured

# 6. End-to-end: against fakeredis (REDIS_URL set to redis://fake)
REDIS_URL=redis://fakeredis-test:6379/0 ./venv/bin/pytest tests/test_github_integration.py::TestSlice2Persistence -v
```

---

## Implementation order & checkpoints

Recommended task ordering for the writing-plans output:

1. **Add config vars** — `REDIS_GITOPS_DB`, `REDIS_GITOPS_KEY_PREFIX`, three TTL ints. No behavior change. Tests must still pass.
2. **Create `src/core/redis_client.py`** with `get_redis_client()` and `tenant_key(...)` and `_dumps`/`_loads`. Write `tests/test_redis_client.py` first (TDD: 3 cases).
3. **Create `src/storage/redis_audit_store.py`** with `RedisAuditStore` + `RedisEscalationStore`. Write `tests/test_redis_audit_store.py` first (TDD: 8 cases).
4. **Create `src/storage/redis_job_store.py`**. Write `tests/test_redis_job_store.py` first (TDD: 6 cases).
5. **Create `src/storage/redis_session_store.py`**. Write `tests/test_redis_session_store.py` first (TDD: 5 cases).
6. **Convert in-memory `EscalationLogger` methods to async** in `src/core/audit.py`. Update `tests/test_phase5_audit.py` to async pattern.
7. **Convert in-memory `SessionManager`/`SessionContext` methods to async** in `src/core/session.py`. Update `tests/test_session.py`.
8. **Swap the singleton factory at bottom of `audit.py`/`jobs.py`/`session.py`** to dispatch on `settings.REDIS_URL` + `PYTEST_CURRENT_TEST`.
9. **Update `agent.py` call sites** — add `await` to 3 escalation calls (lines 690, 1008).
10. **Wire `tenant_id` through `github_agent_invoke`** — accept new optional kwarg, pass to all store calls.
11. **Implement disambiguation session save** in `agent.py` (the actual fix for Blocker #8).
12. **Implement disambiguation session restore** in `agent.py` — on next call with `context.session_id`, restore state from session, skip fuzzy_search, delete session after success.
13. **Add `TestSlice2Persistence` integration tests** in `tests/test_github_integration.py` (10 cases).
14. **Run full suite** — target 63 passing tests, zero new regressions.
15. **Live smoke against `localhost:8001`** — Phase 2 verification commands from §7 Issue 5.

Each step is independently testable and revertable. A failure at step N rolls back only step N; steps 1..N-1 remain shipped.

---

## Open follow-ups (not in scope)

- **Slice 3: Rollback execution.** Now unblocked because Slice 2 gives us persistent `audit_id → operation_record` lookup that survives worker restarts. Will get its own spec.
- **Admin endpoints to query/export audit history.** Data shape supports it; UX work needed.
- **Unify rate_limiter's Redis client factory with `get_redis_client()`.** Low value, high blast radius; deferred.
- **Redis cluster sharding.** Tenant_id prefix is a natural shard key but no cluster-aware logic is added now.

---

**End of spec.**
