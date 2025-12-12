"""Audit logging and timeline tracking for GitOps operations.

Provides audit_id generation, timeline tracking, and audit log storage.
"""

import time
import uuid
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EventType(Enum):
    """Timeline event types"""
    OPERATION_START = "operation_start"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    STEP_FAILED = "step_failed"
    LLM_CALL = "llm_call"
    API_CALL = "api_call"
    ROLLBACK_START = "rollback_start"
    ROLLBACK_COMPLETE = "rollback_complete"
    OPERATION_COMPLETE = "operation_complete"
    OPERATION_FAILED = "operation_failed"


@dataclass
class TimelineEvent:
    """Single timeline event"""
    event_type: EventType
    timestamp: float
    description: str
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "event": self.event_type.value,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "description": self.description,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata
        }


class Timeline:
    """Track execution timeline for operations"""
    
    def __init__(self, audit_id: str, operation: str):
        self.audit_id = audit_id
        self.operation = operation
        self.events: List[TimelineEvent] = []
        self.start_time = time.time()
        self._step_timers: Dict[str, float] = {}
    
    def add_event(
        self,
        event_type: EventType,
        description: str,
        **metadata
    ):
        """Add event to timeline
        
        Args:
            event_type: Type of event
            description: Human-readable description
            **metadata: Additional event metadata
        """
        self.events.append(TimelineEvent(
            event_type=event_type,
            timestamp=time.time(),
            description=description,
            metadata=metadata
        ))
    
    def start_step(self, step_name: str, description: str = None):
        """Mark step start and begin timing
        
        Args:
            step_name: Step identifier
            description: Optional description
        """
        self._step_timers[step_name] = time.time()
        self.add_event(
            EventType.STEP_START,
            description or f"Starting {step_name}",
            step=step_name
        )
    
    def complete_step(self, step_name: str, description: str = None, **metadata):
        """Mark step completion with duration
        
        Args:
            step_name: Step identifier
            description: Optional description
            **metadata: Additional metadata
        """
        start_time = self._step_timers.pop(step_name, None)
        duration_ms = None
        
        if start_time:
            duration_ms = (time.time() - start_time) * 1000
        
        event = TimelineEvent(
            event_type=EventType.STEP_COMPLETE,
            timestamp=time.time(),
            description=description or f"Completed {step_name}",
            duration_ms=duration_ms,
            metadata={**metadata, "step": step_name}
        )
        self.events.append(event)
    
    def fail_step(self, step_name: str, error: str):
        """Mark step failure
        
        Args:
            step_name: Step identifier
            error: Error message
        """
        start_time = self._step_timers.pop(step_name, None)
        duration_ms = None
        
        if start_time:
            duration_ms = (time.time() - start_time) * 1000
        
        event = TimelineEvent(
            event_type=EventType.STEP_FAILED,
            timestamp=time.time(),
            description=f"Failed {step_name}: {error}",
            duration_ms=duration_ms,
            metadata={"step": step_name, "error": error}
        )
        self.events.append(event)
    
    def to_dict(self) -> dict:
        """Export timeline as dictionary
        
        Returns:
            Timeline data
        """
        total_duration_ms = (time.time() - self.start_time) * 1000
        
        return {
            "audit_id": self.audit_id,
            "operation": self.operation,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "total_duration_ms": round(total_duration_ms, 2),
            "events": [e.to_dict() for e in self.events],
            "event_count": len(self.events)
        }
    
    def get_summary(self) -> str:
        """Get human-readable summary
        
        Returns:
            Summary string
        """
        total_duration = (time.time() - self.start_time) * 1000
        step_count = sum(1 for e in self.events if e.event_type == EventType.STEP_COMPLETE)
        
        return f"Completed {step_count} steps in {total_duration:.0f}ms"


def generate_audit_id() -> str:
    """Generate unique audit ID
    
    Returns:
        Audit ID in format: audit_YYYYMMDD_<random>
    """
    date_prefix = datetime.now().strftime("%Y%m%d")
    random_suffix = uuid.uuid4().hex[:12]
    return f"audit_{date_prefix}_{random_suffix}"


class AuditLogger:
    """Store and retrieve audit logs"""
    
    def __init__(self):
        self._logs: Dict[str, dict] = {}
    
    async def store(self, audit_id: str, log_data: dict):
        """Store audit log
        
        Args:
            audit_id: Audit identifier
            log_data: Log data to store
        """
        self._logs[audit_id] = {
            **log_data,
            "stored_at": datetime.now().isoformat()
        }
    
    async def retrieve(self, audit_id: str) -> Optional[dict]:
        """Retrieve audit log
        
        Args:
            audit_id: Audit identifier
            
        Returns:
            Log data if found, None otherwise
        """
        return self._logs.get(audit_id)
    
    async def store_timeline(self, timeline: Timeline):
        """Store timeline as audit log
        
        Args:
            timeline: Timeline object
        """
        await self.store(timeline.audit_id, {
            "audit_id": timeline.audit_id,
            "operation": timeline.operation,
            "timeline": timeline.to_dict()
        })


# Global audit logger instance
_audit_logger = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger singleton"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
