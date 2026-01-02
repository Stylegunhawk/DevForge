"""Session context management for multi-turn conversations.

Stores artifacts and conversation state between Lobe Chat tool calls.
Supports multiple storage backends (memory, redis, postgres).
"""

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
    
    def store_artifact(self, key: str, value: Any, ttl: int = 1800):
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
    
    def get_artifact(self, key: str) -> Optional[Any]:
        """Retrieve stored artifact if not expired
        
        Args:
            key: Artifact identifier
            
        Returns:
            Artifact value if found and not expired, None otherwise
        """
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
    
    def add_to_history(self, entry: dict):
        """Add entry to conversation history"""
        self.history.append({
            **entry,
            "timestamp": datetime.now().isoformat()
        })
        self.last_accessed = time.time()
    
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
    
    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get session by ID
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionContext if found and not expired, None otherwise
        """
        self._cleanup_expired()
        return self.sessions.get(session_id)
    
    def delete_session(self, session_id: str):
        """Delete session by ID"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
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


# Global session manager instance
_session_manager = None


def get_session_manager() -> SessionManager:
    """Get global session manager singleton"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
