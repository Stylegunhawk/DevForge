"""Session context management for multi-turn conversations.

Stores artifacts and conversation state between Lobe Chat tool calls.
Supports multiple storage backends (memory, redis, postgres).
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SessionContext:
    """Store context across tool calls within a session"""
    
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    history: List[dict] = field(default_factory=list)
    artifacts: Dict[str, dict] = field(default_factory=dict)
    user_id: Optional[str] = None
    
    async def store_artifact(self, key: str, value: Any, ttl: int = 1800):
        """Store artifact for later use (default: 30min TTL)

        Args:
            key: Artifact identifier (e.g., 'last_diff', 'last_repo')
            value: Artifact content
            ttl: Time-to-live in seconds
        """
        self.artifacts[key] = {
            "value": value,
            "timestamp": time.time(),
            "ttl": ttl
        }
        self.last_accessed = time.time()
        await asyncio.sleep(0)

    async def get_artifact(self, key: str) -> Optional[Any]:
        """Retrieve stored artifact if not expired

        Args:
            key: Artifact identifier

        Returns:
            Artifact value if found and not expired, None otherwise
        """
        await asyncio.sleep(0)
        if key not in self.artifacts:
            return None

        artifact = self.artifacts[key]
        elapsed = time.time() - artifact["timestamp"]

        if elapsed > artifact["ttl"]:
            # Expired - remove it
            del self.artifacts[key]
            return None

        self.last_accessed = time.time()
        return artifact["value"]

    async def add_to_history(self, entry: dict):
        """Add entry to conversation history"""
        self.history.append({
            **entry,
            "timestamp": datetime.now().isoformat()
        })
        self.last_accessed = time.time()
        await asyncio.sleep(0)
    
    def is_expired(self, session_ttl: int = 1800) -> bool:
        """Check if session has expired
        
        Args:
            session_ttl: Session TTL in seconds (default: 30min)
        """
        return (time.time() - self.last_accessed) > session_ttl


class SessionManager:
    """Manage session contexts with automatic cleanup"""
    
    def __init__(self, session_ttl: int = 1800):
        self.sessions: Dict[str, SessionContext] = {}
        self.session_ttl = session_ttl
    
    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> SessionContext:
        """Get existing session or create new one
        
        Args:
            session_id: Optional session ID to retrieve
            user_id: Optional user ID for new sessions
            
        Returns:
            SessionContext instance
        """
        # Cleanup expired sessions
        self._cleanup_expired()
        
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            session.last_accessed = time.time()
            return session
        
        # Create new session
        new_session_id = session_id or f"session_{uuid.uuid4().hex[:16]}"
        session = SessionContext(
            session_id=new_session_id,
            user_id=user_id
        )
        self.sessions[new_session_id] = session
        return session
    
    async def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get session by ID

        Args:
            session_id: Session identifier

        Returns:
            SessionContext if found and not expired, None otherwise
        """
        await asyncio.sleep(0)
        self._cleanup_expired()
        return self.sessions.get(session_id)

    async def delete_session(self, session_id: str):
        """Delete session by ID"""
        if session_id in self.sessions:
            del self.sessions[session_id]
        await asyncio.sleep(0)
    
    def _cleanup_expired(self):
        """Remove expired sessions"""
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired(self.session_ttl)
        ]
        
        for sid in expired:
            del self.sessions[sid]
    
    def get_active_session_count(self) -> int:
        """Get count of active sessions"""
        self._cleanup_expired()
        return len(self.sessions)

    # --- Redis-compatible interface (tenant_id ignored for in-memory) ---

    async def get_or_create(
        self,
        session_id: str,
        tenant_id: str,
        initial: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Async alias matching RedisSessionStore interface."""
        await asyncio.sleep(0)
        ctx = self.get_or_create_session(session_id=session_id)
        # Seed artifacts from initial dict if this is a brand-new session
        if initial and not ctx.artifacts:
            for k, v in initial.items():
                ctx.artifacts[k] = {"value": v, "timestamp": time.time(), "ttl": self.session_ttl}
            ctx.artifacts["__initial__"] = {"value": initial, "timestamp": time.time(), "ttl": self.session_ttl}
        # Return a plain dict snapshot (matches Redis adapter contract)
        return {k: a["value"] for k, a in ctx.artifacts.items() if k != "__initial__"}

    async def get(
        self,
        session_id: str,
        tenant_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Async alias matching RedisSessionStore interface."""
        await asyncio.sleep(0)
        ctx = self.sessions.get(session_id)
        if ctx is None or ctx.is_expired(self.session_ttl):
            return None
        return {k: a["value"] for k, a in ctx.artifacts.items() if k != "__initial__"}

    async def delete(self, session_id: str, tenant_id: str) -> None:
        """Async alias matching RedisSessionStore interface."""
        if session_id in self.sessions:
            del self.sessions[session_id]
        await asyncio.sleep(0)


# Global session manager instance
_session_manager = None


def _should_use_redis() -> bool:
    import os
    from src.core.config import settings
    return bool(settings.REDIS_URL) and not os.environ.get("PYTEST_CURRENT_TEST")


def get_session_manager():
    """Return the active SessionManager.

    In tests or dev with no REDIS_URL: in-memory SessionManager.
    In production with REDIS_URL set: lazy Redis-backed proxy.
    """
    global _session_manager
    if _session_manager is not None:
        return _session_manager
    if _should_use_redis():
        _session_manager = _AsyncRedisSessionProxy()
    else:
        _session_manager = SessionManager()
    return _session_manager


class _AsyncRedisSessionProxy:
    """Lazy async proxy for RedisSessionStore."""

    def __init__(self):
        from src.core.config import settings
        self._instance = None
        self._ttl = settings.GITOPS_SESSION_TTL

    async def _resolve(self):
        if self._instance is None:
            from src.core.redis_client import get_redis_client
            from src.storage.redis_session_store import RedisSessionStore
            client = await get_redis_client()
            self._instance = RedisSessionStore(client=client, ttl_seconds=self._ttl)
        return self._instance

    async def get_or_create(self, session_id: str, tenant_id: str, initial=None):
        store = await self._resolve()
        return await store.get_or_create(session_id, tenant_id, initial)

    async def get(self, session_id: str, tenant_id: str):
        store = await self._resolve()
        return await store.get(session_id, tenant_id)

    async def update(self, session_id: str, tenant_id: str, patch: dict):
        store = await self._resolve()
        return await store.update(session_id, tenant_id, patch)

    async def touch(self, session_id: str, tenant_id: str) -> bool:
        store = await self._resolve()
        return await store.touch(session_id, tenant_id)

    async def delete(self, session_id: str, tenant_id: str):
        store = await self._resolve()
        return await store.delete(session_id, tenant_id)
