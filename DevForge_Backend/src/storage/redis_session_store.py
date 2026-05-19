"""Redis-backed adapter for SessionManager (Slice 2).

Sessions support disambiguation across two MCP calls: first call returns options +
session_id, second call passes session_id back to skip fuzzy_search. After the
second call resolves, the session is deleted (replay protection).

Key layout:
  gitops:session:{tenant_id}:{session_id}    STRING (JSON)   sliding TTL 30min
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import redis.asyncio as redis

from src.core.redis_client import tenant_key, dumps, loads

logger = logging.getLogger(__name__)


class RedisSessionStore:
    """Persists short-lived session state keyed by tenant_id + session_id."""

    def __init__(self, client: redis.Redis, ttl_seconds: int):
        self._client = client
        self._ttl = ttl_seconds

    async def get_or_create(
        self,
        session_id: str,
        tenant_id: str,
        initial: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        key = tenant_key("session", tenant_id, session_id)
        existing = await self._client.get(key)
        if existing is not None:
            # Refresh sliding TTL on read
            await self._client.expire(key, self._ttl)
            return loads(existing)
        seed = dict(initial or {})
        seed.setdefault("created_at", datetime.now().isoformat())
        await self._client.set(key, dumps(seed), ex=self._ttl)
        return seed

    async def get(self, session_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        key = tenant_key("session", tenant_id, session_id)
        raw = await self._client.get(key)
        if raw is None:
            return None
        # Sliding TTL on every read
        await self._client.expire(key, self._ttl)
        return loads(raw)

    async def update(
        self,
        session_id: str,
        tenant_id: str,
        patch: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        key = tenant_key("session", tenant_id, session_id)
        existing = await self._client.get(key)
        if existing is None:
            return None
        merged = {**loads(existing), **patch}
        merged["updated_at"] = datetime.now().isoformat()
        await self._client.set(key, dumps(merged), ex=self._ttl)
        return merged

    async def touch(self, session_id: str, tenant_id: str) -> bool:
        """Refresh the sliding TTL without changing the payload."""
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        key = tenant_key("session", tenant_id, session_id)
        return bool(await self._client.expire(key, self._ttl))

    async def delete(self, session_id: str, tenant_id: str) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        key = tenant_key("session", tenant_id, session_id)
        await self._client.delete(key)
