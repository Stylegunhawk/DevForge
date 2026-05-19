"""Redis-backed adapter for JobQueue (Slice 2).

Uses Redis HASH for per-job state (cheap partial updates via HSET) and a per-tenant
LIST index capped at 1000 entries for list-recent.

Key layout:
  gitops:job:{tenant_id}:{job_id}      HASH                TTL 24h refreshed on update
  gitops:job_index:{tenant_id}         LIST<job_id>        TTL 24h; LTRIM 1000
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from src.core.redis_client import tenant_key, tenant_index_key, dumps, loads

logger = logging.getLogger(__name__)

_JOB_INDEX_CAP = 1000


class RedisJobStore:
    """Persists async job state keyed by tenant_id + job_id."""

    def __init__(self, client: redis.Redis, ttl_seconds: int):
        self._client = client
        self._ttl = ttl_seconds

    async def create(
        self,
        job_id: str,
        tenant_id: str,
        payload: Dict[str, Any],
    ) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        key = tenant_key("job", tenant_id, job_id)
        index = tenant_index_key("job", tenant_id)
        now = datetime.now().isoformat()
        pipe = self._client.pipeline()
        pipe.hset(key, mapping={
            "status": "pending",
            "payload": dumps(payload),
            "created_at": now,
            "updated_at": now,
        })
        pipe.expire(key, self._ttl)
        pipe.lpush(index, job_id)
        pipe.ltrim(index, 0, _JOB_INDEX_CAP - 1)
        pipe.expire(index, self._ttl)
        await pipe.execute()

    async def update(
        self,
        job_id: str,
        tenant_id: str,
        status: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        key = tenant_key("job", tenant_id, job_id)
        fields: Dict[str, str] = {"updated_at": datetime.now().isoformat()}
        if status is not None:
            fields["status"] = status
        if result is not None:
            fields["result"] = dumps(result)
        pipe = self._client.pipeline()
        pipe.hset(key, mapping=fields)
        pipe.expire(key, self._ttl)
        await pipe.execute()

    async def get(self, job_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        key = tenant_key("job", tenant_id, job_id)
        data = await self._client.hgetall(key)
        if not data:
            return None
        return data

    async def list_for_tenant(self, tenant_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        index = tenant_index_key("job", tenant_id)
        ids = await self._client.lrange(index, 0, limit - 1)
        out: List[Dict[str, Any]] = []
        for job_id in ids:
            data = await self._client.hgetall(tenant_key("job", tenant_id, job_id))
            if data:
                out.append(data)
        return out
