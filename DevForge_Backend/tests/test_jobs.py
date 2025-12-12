"""Tests for async job queue functionality.

Tests job enqueueing, execution, status tracking, and cleanup.
"""

import pytest
import asyncio
import time
from src.core.jobs import Job, JobQueue, JobStatus


class TestJob:
    """Test Job dataclass"""
    
    def test_job_creation(self):
        """Test creating a job"""
        job = Job(
            id="job_123",
            operation="test_op",
            params={"key": "value"}
        )
        
        assert job.id == "job_123"
        assert job.operation == "test_op"
        assert job.status == JobStatus.QUEUED
        assert job.progress == 0
    
    def test_job_to_dict(self):
        """Test job serialization"""
        job = Job(
            id="job_123",
            operation="test_op",
            params={"key": "value"},
            audit_id="audit_789"
        )
        
        job_dict = job.to_dict()
        
        assert job_dict["job_id"] == "job_123"
        assert job_dict["operation"] == "test_op"
        assert job_dict["status"] == "queued"
        assert job_dict["progress"] == 0
        assert job_dict["audit_id"] == "audit_789"


class TestJobQueue:
    """Test JobQueue functionality"""
    
    @pytest.mark.asyncio
    async def test_enqueue_job(self):
        """Test enqueueing a job"""
        queue = JobQueue()
        
        # Register handler
        async def test_handler(params, progress_callback):
            return {"result": "success"}
        
        queue.register_handler("test_op", test_handler)
        
        # Enqueue job
        job_id = await queue.enqueue("test_op", {"param": "value"})
        
        assert job_id.startswith("job_")
        assert job_id in queue.jobs
    
    @pytest.mark.asyncio
    async def test_job_execution(self):
        """Test job execution"""
        queue = JobQueue()
        
        # Register handler
        async def test_handler(params, progress_callback):
            progress_callback(50)
            await asyncio.sleep(0.1)
            progress_callback(100)
            return {"result": "completed"}
        
        queue.register_handler("test_op", test_handler)
        
        # Enqueue and wait
        job_id = await queue.enqueue("test_op", {"param": "value"})
        
        # Wait for completion
        await asyncio.sleep(0.2)
        
        job = await queue.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
        assert job.result == {"result": "completed"}
        assert job.progress == 100
    
    @pytest.mark.asyncio
    async def test_job_failure(self):
        """Test job failure handling"""
        queue = JobQueue()
        
        # Register failing handler
        async def failing_handler(params, progress_callback):
            raise ValueError("Test error")
        
        queue.register_handler("failing_op", failing_handler)
        
        # Enqueue and wait
        job_id = await queue.enqueue("failing_op", {})
        await asyncio.sleep(0.1)
        
        job = await queue.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert "Test error" in job.error
    
    @pytest.mark.asyncio
    async def test_unknown_operation(self):
        """Test job with unknown operation"""
        queue = JobQueue()
        
        job_id = await queue.enqueue("unknown_op", {})
        await asyncio.sleep(0.1)
        
        job = await queue.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert "No handler registered" in job.error
    
    @pytest.mark.asyncio
    async def test_cancel_job(self):
        """Test job cancellation"""
        queue = JobQueue()
        
        job_id = await queue.enqueue("test_op", {})
        
        # Cancel before execution
        cancelled = await queue.cancel_job(job_id)
        assert cancelled
        
        job = await queue.get_job(job_id)
        assert job.status == JobStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_cancel_completed_job(self):
        """Test cannot cancel completed job"""
        queue = JobQueue()
        
        async def quick_handler(params, progress_callback):
            return {"done": True}
        
        queue.register_handler("quick_op", quick_handler)
        
        job_id = await queue.enqueue("quick_op", {})
        await asyncio.sleep(0.1)
        
        # Try to cancel completed job
        cancelled = await queue.cancel_job(job_id)
        assert not cancelled
    
    def test_estimate_duration(self):
        """Test job duration estimation"""
        queue = JobQueue()
        
        # Test with known operations
        assert queue._estimate_duration("bulk_close_issues", {"issue_ids": [1, 2, 3]}) == 6
        assert queue._estimate_duration("scaffold_repo", {}) == 30
        assert queue._estimate_duration("unknown_op", {}) == 10
    
    @pytest.mark.asyncio
    async def test_cleanup_old_jobs(self):
        """Test job cleanup"""
        queue = JobQueue()
        
        # Create jobs with different ages
        job1_id = await queue.enqueue("test_op", {})
        job2_id = await queue.enqueue("test_op", {})
        
        # Make job1 old
        queue.jobs[job1_id].created_at = time.time() - (25 * 3600)
        
        # Cleanup jobs older than 24 hours
        await queue.cleanup_old_jobs(max_age_hours=24)
        
        assert job1_id not in queue.jobs
        assert job2_id in queue.jobs
    
    @pytest.mark.asyncio
    async def test_progress_callback(self):
        """Test progress callback updates"""
        queue = JobQueue()
        
        async def progress_handler(params, progress_callback):
            progress_callback(25)
            await asyncio.sleep(0.05)
            progress_callback(50)
            await asyncio.sleep(0.05)
            progress_callback(75)
            await asyncio.sleep(0.05)
            progress_callback(100)
            return {"done": True}
        
        queue.register_handler("progress_op", progress_handler)
        
        job_id = await queue.enqueue("progress_op", {})
        
        # Check progress updates
        await asyncio.sleep(0.06)
        job = await queue.get_job(job_id)
        assert job.progress >= 25
        
        # Wait for completion
        await asyncio.sleep(0.2)
        job = await queue.get_job(job_id)
        assert job.progress == 100


@pytest.mark.asyncio
async def test_concurrent_job_execution():
    """Test multiple jobs executing concurrently"""
    queue = JobQueue()
    
    async def test_handler(params, progress_callback):
        await asyncio.sleep(0.1)
        return {"id": params["id"]}
    
    queue.register_handler("concurrent_op", test_handler)
    
    # Enqueue multiple jobs
    job_ids = []
    for i in range(5):
        job_id = await queue.enqueue("concurrent_op", {"id": i})
        job_ids.append(job_id)
    
    # Wait for all to complete
    await asyncio.sleep(0.3)
    
    # All should be completed
    for job_id in job_ids:
        job = await queue.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
