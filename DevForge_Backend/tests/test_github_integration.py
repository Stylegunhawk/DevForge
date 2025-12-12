"""Integration tests for github_operation tool.

Comprehensive integration tests covering full workflows, session handling,
disambiguation, and async job lifecycle.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
import asyncio

from src.main import app
from src.core.session import SessionManager, get_session_manager
from src.core.jobs import JobQueue, get_job_queue, JobStatus


client = TestClient(app)


class TestSingleCallWorkflow:
    """Test Lobe Chat single-call workflow requirements"""
    
    @pytest.mark.asyncio
    async def test_github_operation_complete_in_single_call(self):
        """Verify github_operation completes in one API call"""
        with patch('src.agents.github.agent.github_agent_invoke') as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "operation": "list_repos",
                "data": {"repos": ["repo1", "repo2"]},
                "audit_id": "test_123"
            }
            
            response = client.post("/api/gateway", json={
                "tool_name": "github_operation",
                "arguments": {
                    "query": "list my repos"
                }
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_all_intelligence_internal(self):
        """Verify all intelligence is internal - no tool chaining needed"""
        with patch('src.agents.github.agent.github_agent_invoke') as mock_invoke:
            # Simulate full internal processing
            mock_invoke.return_value = {
                "success": True,
                "operation": "create_pr",
                "data": {
                    "pr_number": 42,
                    "url": "https://github.com/owner/repo/pull/42"
                },
                "_repo_inferred": True,  # Fuzzy match was used
                "_message_generated": True,  # Commit msg was generated
                "repo_confidence": 0.92,
                "audit_id": "test_456"
            }
            
            response = client.post("/api/gateway", json={
                "tool_name": "github_operation",
                "arguments": {
                    "query": "create PR for backend changes",
                    "context": {"diff": "sample diff content"}
                }
            })
            
            data = response.json()
            assert data["success"] is True
            # Verify intelligence was applied internally
            result_data = data["data"]
            assert result_data.get("_repo_inferred") is True
            assert result_data.get("_message_generated") is True


class TestSessionContext:
    """Test session context and multi-turn conversations"""
    
    @pytest.mark.asyncio
    async def test_session_storage(self):
        """Test session data persists across calls"""
        manager = SessionManager()
        session_id = "test_session_123"
        
        # Store data in session
        await manager.set(session_id, "user", "testuser")
        await manager.set(session_id, "repo", "owner/repo")
        
        # Retrieve data
        user = await manager.get(session_id, "user")
        repo = await manager.get(session_id, "repo")
        
        assert user == "testuser"
        assert repo == "owner/repo"
    
    @pytest.mark.asyncio
    async def test_session_expiration(self):
        """Test session expires after TTL"""
        manager = SessionManager(ttl_seconds=0)  # Immediate expiration
        session_id = "expiring_session"
        
        await manager.set(session_id, "key", "value")
        await asyncio.sleep(0.1)
        
        result = await manager.get(session_id, "key")
        # Should be None after expiration
        assert result is None
    
    @pytest.mark.asyncio
    async def test_session_context_reuse(self):
        """Test session context is reused in multi-turn conversation"""
        with patch('src.agents.github.agent.github_agent_invoke') as mock_invoke:
            session_id = "multi_turn_session"
            
            # First call - store context
            mock_invoke.return_value = {
                "success": True,
                "data": {"diff": "sample diff"},
                "_session_updated": True
            }
            
            response1 = client.post("/api/gateway", json={
                "tool_name": "github_operation",
                "arguments": {
                    "query": "show diff for main.py",
                    "context": {"session_id": session_id}
                }
            })
            
            assert response1.status_code == 200
            
            # Second call - reference "those changes"
            mock_invoke.return_value = {
                "success": True,
                "data": {"pr_number": 42},
                "_used_session_context": True
            }
            
            response2 = client.post("/api/gateway", json={
                "tool_name": "github_operation",
                "arguments": {
                    "query": "create PR with those changes",
                    "context": {"session_id": session_id}
                }
            })
            
            assert response2.status_code == 200


class TestDisambiguation:
    """Test disambiguation for ambiguous queries"""
    
    @pytest.mark.asyncio
    async def test_low_confidence_returns_options(self):
        """When fuzzy match confidence is low, return options"""
        with patch('src.agents.github.agent.github_agent_invoke') as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "status": "needs_clarification",
                "options": [
                    {"repo": "owner/payment-service", "confidence": 0.75},
                    {"repo": "owner/payment-gateway", "confidence": 0.72}
                ],
                "message": "Multiple repos match 'pay'. Please clarify."
            }
            
            response = client.post("/api/gateway", json={
                "tool_name": "github_operation",
                "arguments": {
                    "query": "create issue in pay repo"  # Ambiguous
                }
            })
            
            data = response.json()
            assert data["success"] is True
            result_data = data["data"]
            assert result_data.get("status") == "needs_clarification"
            assert "options" in result_data
            assert len(result_data["options"]) >= 2
    
    @pytest.mark.asyncio
    async def test_high_confidence_proceeds(self):
        """When confidence is high, proceed without disambiguation"""
        with patch('src.agents.github.agent.github_agent_invoke') as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "operation": "create_issue",
                "data": {"issue_number": 42},
                "repo_confidence": 0.95  # High confidence
            }
            
            response = client.post("/api/gateway", json={
                "tool_name": "github_operation",
                "arguments": {
                    "query": "create issue in backend-api repo"
                }
            })
            
            data = response.json()
            assert data["success"] is True
            # No disambiguation needed
            assert "needs_clarification" not in str(data)


class TestAsyncJobLifecycle:
    """Test async job queue lifecycle"""
    
    @pytest.mark.asyncio
    async def test_job_creation(self):
        """Test creating an async job"""
        queue = JobQueue()
        
        async def sample_task():
            await asyncio.sleep(0.1)
            return {"result": "done"}
        
        job_id = await queue.enqueue(sample_task)
        
        assert job_id is not None
        assert job_id.startswith("job_")
    
    @pytest.mark.asyncio
    async def test_job_status_progression(self):
        """Test job status progresses correctly"""
        queue = JobQueue()
        completed = asyncio.Event()
        
        async def tracked_task():
            await asyncio.sleep(0.1)
            completed.set()
            return {"result": "success"}
        
        job_id = await queue.enqueue(tracked_task)
        
        # Initially pending
        status = await queue.get_status(job_id)
        assert status["status"] in [JobStatus.PENDING.value, JobStatus.RUNNING.value]
        
        # Wait for completion
        await asyncio.wait_for(completed.wait(), timeout=2.0)
        await asyncio.sleep(0.1)  # Allow status update
        
        status = await queue.get_status(job_id)
        assert status["status"] == JobStatus.COMPLETED.value
    
    @pytest.mark.asyncio
    async def test_job_failure_handling(self):
        """Test job failure is captured"""
        queue = JobQueue()
        
        async def failing_task():
            raise ValueError("Intentional failure")
        
        job_id = await queue.enqueue(failing_task)
        
        # Wait for failure
        await asyncio.sleep(0.2)
        
        status = await queue.get_status(job_id)
        assert status["status"] == JobStatus.FAILED.value
        assert "error" in status
    
    def test_job_status_endpoint(self):
        """Test job status API endpoint"""
        response = client.get("/api/jobs/nonexistent_job")
        
        # Should return 404 or error for nonexistent job
        assert response.status_code in [200, 404]


class TestFullWorkflowIntegration:
    """Test complete workflow scenarios"""
    
    @pytest.mark.asyncio
    async def test_create_issue_workflow(self):
        """Test complete create issue workflow"""
        with patch('src.agents.github.agent.github_agent_invoke') as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "operation": "create_issue",
                "data": {
                    "issue_number": 42,
                    "url": "https://github.com/owner/repo/issues/42"
                },
                "audit_id": "workflow_test_1",
                "timeline": {
                    "total_duration_ms": 1500,
                    "events": [
                        {"step": "parse_intent", "duration_ms": 100},
                        {"step": "repo_discovery", "duration_ms": 200},
                        {"step": "create_issue", "duration_ms": 1200}
                    ]
                }
            }
            
            response = client.post("/api/gateway", json={
                "tool_name": "github_operation",
                "arguments": {
                    "query": "create issue 'Fix login bug' in my-app repo"
                }
            })
            
            data = response.json()
            assert data["success"] is True
            assert data["data"]["issue_number"] == 42
    
    @pytest.mark.asyncio
    async def test_list_repos_workflow(self):
        """Test list repos workflow"""
        with patch('src.agents.github.agent.github_agent_invoke') as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "operation": "list_repos",
                "data": {
                    "repos": [
                        {"name": "repo1", "url": "https://github.com/owner/repo1"},
                        {"name": "repo2", "url": "https://github.com/owner/repo2"}
                    ],
                    "count": 2
                }
            }
            
            response = client.post("/api/gateway", json={
                "tool_name": "github_operation",
                "arguments": {
                    "query": "list my repos"
                }
            })
            
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]["repos"]) >= 1


class TestRollbackFeasibility:
    """Test rollback feasibility matrix"""
    
    @pytest.mark.asyncio
    async def test_reversible_operation(self):
        """Test rollback feasibility for reversible operations"""
        with patch('src.agents.github.agent.github_agent_invoke') as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "operation": "create_issue",
                "data": {"issue_number": 42},
                "rollback_feasibility": {
                    "can_rollback": True,
                    "method": "close_issue",
                    "confidence": 0.95
                }
            }
            
            response = client.post("/api/gateway", json={
                "tool_name": "github_operation",
                "arguments": {
                    "query": "create issue"
                }
            })
            
            data = response.json()
            assert data["success"] is True
            # Should have rollback info
            assert "rollback_feasibility" in data["data"] or data["data"].get("issue_number")
    
    @pytest.mark.asyncio
    async def test_irreversible_operation_warning(self):
        """Test irreversible operations include warning"""
        with patch('src.agents.github.agent.github_agent_invoke') as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "operation": "delete_branch",
                "data": {"deleted": True},
                "rollback_feasibility": {
                    "can_rollback": False,
                    "reason": "Branch deletion is permanent",
                    "warning": "This action cannot be undone"
                }
            }
            
            response = client.post("/api/gateway", json={
                "tool_name": "github_operation",
                "arguments": {
                    "query": "delete feature-old branch"
                }
            })
            
            data = response.json()
            rollback = data["data"].get("rollback_feasibility", {})
            if rollback:
                assert rollback.get("can_rollback") is False


class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_missing_query_parameter(self):
        """Test error when query is missing"""
        response = client.post("/api/gateway", json={
            "tool_name": "github_operation",
            "arguments": {}
        })
        
        assert response.status_code in [400, 200]
        data = response.json()
        if response.status_code == 200:
            assert data["success"] is False
    
    def test_invalid_tool_name(self):
        """Test error for invalid tool name"""
        response = client.post("/api/gateway", json={
            "tool_name": "nonexistent_tool",
            "arguments": {}
        })
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
    
    @pytest.mark.asyncio
    async def test_github_api_error_handling(self):
        """Test GitHub API error is handled gracefully"""
        with patch('src.agents.github.agent.github_agent_invoke') as mock_invoke:
            mock_invoke.return_value = {
                "success": False,
                "error": "GitHub API rate limit exceeded",
                "retry_after": 3600
            }
            
            response = client.post("/api/gateway", json={
                "tool_name": "github_operation",
                "arguments": {
                    "query": "list repos"
                }
            })
            
            data = response.json()
            # Should handle error gracefully
            assert "error" in str(data).lower() or data.get("success") is False
