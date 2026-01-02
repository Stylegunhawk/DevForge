"""Tests for session management functionality.

Tests session creation, artifact storage, TTL expiration, and cleanup.
"""

import pytest
import time
from src.core.session import SessionContext, SessionManager


class TestSessionContext:
    """Test SessionContext functionality"""
    
    def test_create_session(self):
        """Test session creation"""
        session = SessionContext(session_id="test_123")
        
        assert session.session_id == "test_123"
        assert len(session.artifacts) == 0
        assert len(session.history) == 0
    
    def test_store_and_retrieve_artifact(self):
        """Test storing and retrieving artifacts"""
        session = SessionContext(session_id="test_123")
        
        # Store artifact
        session.store_artifact("last_diff", "diff content here", ttl=60)
        
        # Retrieve artifact
        value = session.get_artifact("last_diff")
        assert value == "diff content here"
    
    def test_artifact_expiration(self):
        """Test artifact TTL expiration"""
        session = SessionContext(session_id="test_123")
        
        # Store with 1 second TTL
        session.store_artifact("temp", "expires soon", ttl=1)
        
        # Should exist immediately
        assert session.get_artifact("temp") == "expires soon"
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be None after expiration
        assert session.get_artifact("temp") is None
    
    def test_nonexistent_artifact(self):
        """Test retrieving nonexistent artifact"""
        session = SessionContext(session_id="test_123")
        
        assert session.get_artifact("doesnt_exist") is None
    
    def test_history_tracking(self):
        """Test conversation history tracking"""
        session = SessionContext(session_id="test_123")
        
        session.add_to_history({"operation": "create_pr", "result": "success"})
        session.add_to_history({"operation": "commit", "result": "success"})
        
        assert len(session.history) == 2
        assert session.history[0]["operation"] == "create_pr"
        assert "timestamp" in session.history[0]
    
    def test_session_expiration(self):
        """Test session expiration check"""
        session = SessionContext(session_id="test_123")
        
        # Session should not be expired immediately
        assert not session.is_expired(session_ttl=60)
        
        # Set last_accessed to past
        session.last_accessed = time.time() - 70
        
        # Session should now be expired
        assert session.is_expired(session_ttl=60)


class TestSessionManager:
    """Test SessionManager functionality"""
    
    def test_create_new_session(self):
        """Test creating new session"""
        manager = SessionManager()
        
        session = manager.get_or_create_session(user_id="user_123")
        
        assert session.session_id.startswith("session_")
        assert session.user_id == "user_123"
        assert len(manager.sessions) == 1
    
    def test_retrieve_existing_session(self):
        """Test retrieving existing session"""
        manager = SessionManager()
        
        # Create session
        session1 = manager.get_or_create_session(session_id="test_session")
        session1.store_artifact("data", "test value")
        
        # Retrieve same session
        session2 = manager.get_or_create_session(session_id="test_session")
        
        assert session1 is session2
        assert session2.get_artifact("data") == "test value"
    
    def test_get_session(self):
        """Test get_session method"""
        manager = SessionManager()
        
        # Create session
        session = manager.get_or_create_session(session_id="test_session")
        
        # Get session
        retrieved = manager.get_session("test_session")
        assert retrieved is session
        
        # Get nonexistent session
        assert manager.get_session("doesnt_exist") is None
    
    def test_delete_session(self):
        """Test session deletion"""
        manager = SessionManager()
        
        session = manager.get_or_create_session(session_id="test_session")
        assert "test_session" in manager.sessions
        
        manager.delete_session("test_session")
        assert "test_session" not in manager.sessions
    
    def test_cleanup_expired_sessions(self):
        """Test automatic cleanup of expired sessions"""
        manager = SessionManager(session_ttl=1)
        
        # Create sessions
        session1 = manager.get_or_create_session(session_id="active")
        session2 = manager.get_or_create_session(session_id="expired")
        
        # Make session2 expired
        session2.last_accessed = time.time() - 2
        
        # Force cleanup
        manager._cleanup_expired()
        
        assert "active" in manager.sessions
        assert "expired" not in manager.sessions
    
    def test_active_session_count(self):
        """Test counting active sessions"""
        manager = SessionManager(session_ttl=1)
        
        # Create sessions
        manager.get_or_create_session(session_id="session1")
        manager.get_or_create_session(session_id="session2")
        session3 = manager.get_or_create_session(session_id="session3")
        
        # Expire one session
        session3.last_accessed = time.time() - 2
        
        # Should count only non-expired
        assert manager.get_active_session_count() == 2


@pytest.mark.asyncio
async def test_concurrent_session_access():
    """Test concurrent access to same session"""
    import asyncio
    
    manager = SessionManager()
    session = manager.get_or_create_session(session_id="shared")
    
    async def store_artifact(key, value):
        session.store_artifact(key, value)
        await asyncio.sleep(0.01)
    
    # Concurrent writes
    await asyncio.gather(
        store_artifact("key1", "value1"),
        store_artifact("key2", "value2"),
        store_artifact("key3", "value3")
    )
    
    # All artifacts should be stored
    assert session.get_artifact("key1") == "value1"
    assert session.get_artifact("key2") == "value2"
    assert session.get_artifact("key3") == "value3"
