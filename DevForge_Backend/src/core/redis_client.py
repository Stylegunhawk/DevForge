"""Shared async Redis client factory for GitOps-backed stores (Slice 2).

Fail-closed: if REDIS_URL is configured but unreachable, get_redis_client() raises
RuntimeError on first call. There is no silent fallback in production code paths —
the singleton factories at the bottom of audit.py/jobs.py/session.py decide which
backing store to use BEFORE consulting this module.

This factory exists separately from rate_limiter.py's own Redis client because
the two subsystems may want different connection pools / databases. Future work
may unify them.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis.asyncio as redis
from redis.exceptions import RedisError

from src.core.config import settings

logger = logging.getLogger(__name__)

_client: Optional[redis.Redis] = None


def _build_client() -> redis.Redis:
    """Construct a fresh Redis client. Separated for monkeypatch in tests."""
    return redis.from_url(
        settings.REDIS_URL,
        db=settings.REDIS_GITOPS_DB,
        decode_responses=True,
        health_check_interval=30,
    )


async def get_redis_client() -> redis.Redis:
    """Return the singleton Redis client, raising RuntimeError if unreachable.

    On first call, performs a PING to fail-closed if Redis is misconfigured or
    unreachable. Subsequent calls return the cached client.
    """
    global _client
    if _client is not None:
        return _client

    if not settings.REDIS_URL:
        raise RuntimeError(
            "Redis required for gitops stores: settings.REDIS_URL is unset. "
            "Set REDIS_URL=redis://host:6379/0 or omit Redis-backed stores."
        )

    candidate = _build_client()
    try:
        await candidate.ping()
    except (RedisError, OSError) as e:
        raise RuntimeError(f"Redis required for gitops stores: ping failed: {e}") from e

    _client = candidate
    logger.info("Redis client initialized for gitops stores (db=%s)", settings.REDIS_GITOPS_DB)
    return _client


def tenant_key(store_type: str, tenant_id: str, logical_id: str) -> str:
    """Build a fully-qualified Redis key for tenant-scoped storage.

    Format: {prefix}:{store_type}:{tenant_id}:{logical_id}
    Example: gitops:audit:tenant-a:audit_20260516_abc123
    """
    if not tenant_id:
        raise ValueError("tenant_id is required for Redis-backed stores")
    if not logical_id:
        raise ValueError("logical_id is required for Redis-backed stores")
    prefix = settings.REDIS_GITOPS_KEY_PREFIX
    return f"{prefix}:{store_type}:{tenant_id}:{logical_id}"


def tenant_index_key(store_type: str, tenant_id: str) -> str:
    """Build the per-tenant LIST index key for fast list-recent queries."""
    if not tenant_id:
        raise ValueError("tenant_id is required for Redis-backed stores")
    prefix = settings.REDIS_GITOPS_KEY_PREFIX
    return f"{prefix}:{store_type}_index:{tenant_id}"


def dumps(value: Any) -> str:
    """JSON-encode a value for Redis storage. Coerces datetimes/Decimal via default=str."""
    return json.dumps(value, default=str)


def loads(value: Optional[str]) -> Any:
    """JSON-decode a Redis-stored value. Returns None if the input is None."""
    if value is None:
        return None
    return json.loads(value)
