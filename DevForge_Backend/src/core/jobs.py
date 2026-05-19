"""Async job queue for long-running GitHub operations.

Handles operations that exceed synchronous timeout limits.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class JobStatus(Enum):
    """Job execution status"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Background job representation"""
    
    id: str
    operation: str
    params: dict
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0  # 0-100
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    eta_seconds: Optional[int] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    audit_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "job_id": self.id,
            "operation": self.operation,
            "status": self.status.value,
            "progress": self.progress,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "started_at": datetime.fromtimestamp(self.started_at).isoformat() if self.started_at else None,
            "completed_at": datetime.fromtimestamp(self.completed_at).isoformat() if self.completed_at else None,
            "eta_seconds": self.eta_seconds,
            "result": self.result if self.status == JobStatus.COMPLETED else None,
            "error": self.error if self.status == JobStatus.FAILED else None,
            "audit_id": self.audit_id
        }


class JobQueue:
    """Async job queue with background execution"""
    
    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self.handlers: Dict[str, Callable] = {}
        self._cleanup_task = None
    
    def register_handler(self, operation: str, handler: Callable):
        """Register handler for operation type
        
        Args:
            operation: Operation name (e.g., 'bulk_close_issues')
            handler: Async function to execute
        """
        self.handlers[operation] = handler
    
    async def enqueue(
        self,
        operation: str,
        params: dict,
        audit_id: Optional[str] = None
    ) -> str:
        """Enqueue job for background execution
        
        Args:
            operation: Operation to perform
            params: Operation parameters
            audit_id: Optional audit ID for tracing
            
        Returns:
            Job ID for status tracking
        """
        job_id = f"job_{uuid.uuid4().hex[:16]}"
        
        job = Job(
            id=job_id,
            operation=operation,
            params=params,
            eta_seconds=self._estimate_duration(operation, params),
            audit_id=audit_id
        )
        
        self.jobs[job_id] = job
        
        # Start background execution
        asyncio.create_task(self._execute_job(job))
        
        return job_id
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job if found, None otherwise
        """
        return self.jobs.get(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel running job
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if cancelled, False if not found or already completed
        """
        job = self.jobs.get(job_id)
        if not job or job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            return False
        
        job.status = JobStatus.CANCELLED
        return True
    
    async def _execute_job(self, job: Job):
        """Execute job in background
        
        Args:
            job: Job to execute
        """
        handler = self.handlers.get(job.operation)
        
        if not handler:
            job.status = JobStatus.FAILED
            job.error = f"No handler registered for operation '{job.operation}'"
            job.completed_at = time.time()
            return
        
        try:
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            
            # Execute handler
            result = await handler(job.params, self._create_progress_callback(job))
            
            job.status = JobStatus.COMPLETED
            job.result = result
            job.progress = 100
            job.completed_at = time.time()
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = time.time()
    
    def _create_progress_callback(self, job: Job) -> Callable:
        """Create progress update callback for job
        
        Args:
            job: Job to update
            
        Returns:
            Callback function
        """
        def update_progress(progress: int):
            job.progress = min(max(progress, 0), 100)
        
        return update_progress
    
    def _estimate_duration(self, operation: str, params: dict) -> int:
        """Estimate job duration in seconds
        
        Args:
            operation: Operation type
            params: Operation parameters
            
        Returns:
            Estimated duration in seconds
        """
        estimates = {
            "bulk_close_issues": lambda p: len(p.get("issue_ids", [])) * 2,
            "bulk_delete_branches": lambda p: len(p.get("branch_names", [])) * 1,
            "scaffold_repo": lambda p: 30,
            "ci_analysis": lambda p: 15,
            "generate_changelog": lambda p: 10
        }
        
        estimator = estimates.get(operation, lambda p: 10)
        return estimator(params)
    
    async def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove jobs older than max_age
        
        Args:
            max_age_hours: Maximum age in hours to keep jobs
        """
        cutoff = time.time() - (max_age_hours * 3600)
        
        to_delete = [
            job_id for job_id, job in self.jobs.items()
            if job.created_at < cutoff
        ]
        
        for job_id in to_delete:
            del self.jobs[job_id]
    
    async def start_cleanup_task(self, interval_minutes: int = 60):
        """Start periodic cleanup task
        
        Args:
            interval_minutes: Cleanup interval in minutes
        """
        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval_minutes * 60)
                await self.cleanup_old_jobs()
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())


# Global job queue instance
_job_queue = None


def _should_use_redis() -> bool:
    import os
    from src.core.config import settings
    return bool(settings.REDIS_URL) and not os.environ.get("PYTEST_CURRENT_TEST")


def get_job_queue():
    """Return the active JobQueue.

    In tests or dev with no REDIS_URL: in-memory JobQueue.
    In production with REDIS_URL set: lazy Redis-backed proxy.
    """
    global _job_queue
    if _job_queue is not None:
        return _job_queue
    if _should_use_redis():
        _job_queue = _AsyncRedisJobProxy()
    else:
        _job_queue = JobQueue()
    return _job_queue


class _AsyncRedisJobProxy:
    """Lazy async proxy for RedisJobStore."""

    def __init__(self):
        from src.core.config import settings
        self._instance = None
        self._ttl = settings.GITOPS_JOB_TTL_SECONDS

    async def _resolve(self):
        if self._instance is None:
            from src.core.redis_client import get_redis_client
            from src.storage.redis_job_store import RedisJobStore
            client = await get_redis_client()
            self._instance = RedisJobStore(client=client, ttl_seconds=self._ttl)
        return self._instance

    async def create(self, *args, **kwargs):
        store = await self._resolve()
        return await store.create(*args, **kwargs)

    async def update(self, *args, **kwargs):
        store = await self._resolve()
        return await store.update(*args, **kwargs)

    async def get(self, *args, **kwargs):
        store = await self._resolve()
        return await store.get(*args, **kwargs)

    async def list_for_tenant(self, *args, **kwargs):
        store = await self._resolve()
        return await store.list_for_tenant(*args, **kwargs)
