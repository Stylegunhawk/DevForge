"""Redis-backed adapters for AuditLogger and EscalationLogger (Slice 2).

Both stores share the same per-tenant LIST-index pattern so list-recent queries
are O(returned) instead of O(records-across-all-tenants).

Key layout:
  gitops:audit:{tenant_id}:{audit_id}        STRING (JSON)   TTL 30d
  gitops:audit_index:{tenant_id}             LIST<audit_id>  TTL 30d; LTRIM 5000
  gitops:escalation:{tenant_id}:{audit_id}   STRING (JSON)   TTL 90d
  gitops:escalation_index:{tenant_id}        LIST<audit_id>  TTL 90d; LTRIM 5000
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from src.core.redis_client import tenant_key, tenant_index_key, dumps, loads

logger = logging.getLogger(__name__)

_AUDIT_INDEX_CAP = 5000
_ESCALATION_INDEX_CAP = 5000


class RedisAuditStore:
    """Persists audit timeline records keyed by tenant_id + audit_id."""

    def __init__(self, client: redis.Redis, ttl_seconds: int):
        self._client = client
        self._ttl = ttl_seconds

    async def save(self, audit_id: str, tenant_id: str, record: Dict[str, Any]) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        key = tenant_key("audit", tenant_id, audit_id)
        index = tenant_index_key("audit", tenant_id)
        pipe = self._client.pipeline()
        pipe.set(key, dumps(record), ex=self._ttl)
        pipe.lpush(index, audit_id)
        pipe.ltrim(index, 0, _AUDIT_INDEX_CAP - 1)
        pipe.expire(index, self._ttl)
        await pipe.execute()

    async def get(self, audit_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        key = tenant_key("audit", tenant_id, audit_id)
        return loads(await self._client.get(key))

    async def list_for_tenant(self, tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        index = tenant_index_key("audit", tenant_id)
        audit_ids = await self._client.lrange(index, 0, limit - 1)
        if not audit_ids:
            return []
        keys = [tenant_key("audit", tenant_id, aid) for aid in audit_ids]
        raw = await self._client.mget(*keys)
        return [loads(v) for v in raw if v is not None]


class RedisEscalationStore:
    """Append-only escalation records for HIGH/CRITICAL outcomes."""

    def __init__(self, client: redis.Redis, ttl_seconds: int):
        self._client = client
        self._ttl = ttl_seconds

    async def record_critical(
        self,
        audit_id: str,
        tenant_id: str,
        operation: str,
        parameters: Optional[Dict[str, Any]] = None,
        outcome: str = "blocked",
        token_hash: Optional[str] = None,
        confirmed: bool = False,
        reason: str = "",
        policy_checked: bool = True,
    ) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        record = self._build_record(
            audit_id=audit_id, operation=operation, parameters=parameters,
            risk_level="CRITICAL", outcome=outcome, token_hash=token_hash,
            confirmed=confirmed, reason=reason, policy_checked=policy_checked,
        )
        await self._save_record(audit_id, tenant_id, record)
        logger.warning(
            "[ESCALATION:CRITICAL] %s | outcome=%s | audit=%s | tenant=%s",
            operation, outcome, audit_id, tenant_id,
        )

    async def record_blocked_high(
        self,
        audit_id: str,
        tenant_id: str,
        operation: str,
        parameters: Optional[Dict[str, Any]] = None,
        token_hash: Optional[str] = None,
        confirmed: bool = False,
        policy_checked: bool = True,
    ) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        record = self._build_record(
            audit_id=audit_id, operation=operation, parameters=parameters,
            risk_level="HIGH", outcome="blocked", token_hash=token_hash,
            confirmed=confirmed, policy_checked=policy_checked,
        )
        await self._save_record(audit_id, tenant_id, record)
        logger.warning(
            "[ESCALATION:HIGH:BLOCKED] %s | audit=%s | tenant=%s",
            operation, audit_id, tenant_id,
        )

    async def get_records_for_tenant(
        self, tenant_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        index = tenant_index_key("escalation", tenant_id)
        ids = await self._client.lrange(index, 0, limit - 1)
        if not ids:
            return []
        keys = [tenant_key("escalation", tenant_id, aid) for aid in ids]
        raw = await self._client.mget(*keys)
        return [loads(v) for v in raw if v is not None]

    def _build_record(
        self, audit_id, operation, parameters, risk_level, outcome,
        token_hash, confirmed=False, reason="", policy_checked=True,
    ) -> Dict[str, Any]:
        return {
            "severity": risk_level.upper(),
            "operation": operation,
            "parameters": _redact(parameters or {}),
            "token_hash": token_hash,
            "timestamp": datetime.now().isoformat(),
            "confirmed": confirmed,
            "reason": reason,
            "policy_checked": policy_checked,
            "risk_level": risk_level.upper(),
            "outcome": outcome,
            "audit_id": audit_id,
        }

    async def _save_record(self, audit_id: str, tenant_id: str, record: Dict[str, Any]) -> None:
        key = tenant_key("escalation", tenant_id, audit_id)
        index = tenant_index_key("escalation", tenant_id)
        pipe = self._client.pipeline()
        pipe.set(key, dumps(record), ex=self._ttl)
        pipe.lpush(index, audit_id)
        pipe.ltrim(index, 0, _ESCALATION_INDEX_CAP - 1)
        pipe.expire(index, self._ttl)
        await pipe.execute()


_SENSITIVE_KEYS = {"token", "password", "secret", "key", "credential", "github_token", "api_key"}


def _redact(params: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive parameter values before storage. Mirrors core/audit.py _sanitize_params."""
    out: Dict[str, Any] = {}
    for k, v in params.items():
        if isinstance(k, str) and any(s in k.lower() for s in _SENSITIVE_KEYS):
            out[k] = "[REDACTED]"
        else:
            out[k] = v
    return out
