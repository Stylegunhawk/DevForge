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

import json as _json


def parse_mcp_payload(mcp_response_dict: dict) -> dict:
    """
    Extract the agent payload from a JSON-RPC tools/call response.
    Returns the parsed dict from result.content[0].text, or the error envelope if present.
    """
    if "error" in mcp_response_dict:
        return {"_jsonrpc_error": mcp_response_dict["error"]}
    result = mcp_response_dict.get("result", {})
    content = result.get("content", [])
    if not content:
        return {"_empty_content": True, "_result": result}
    text = content[0].get("text", "{}")
    return _json.loads(text)


def assert_matches_snapshot(actual: dict, fixture_path: str, ignore_paths: list[str]) -> None:
    """
    Compare actual dict against JSON fixture, ignoring volatile paths
    (timestamps, audit_ids). Fails with a clear diff.

    ignore_paths uses dotted form: "timeline.events[*].timestamp"
    """
    import re
    import pathlib

    def _scrub(obj, paths):
        for path in paths:
            parts = path.split(".")
            _scrub_path(obj, parts)
        return obj

    def _scrub_path(obj, parts):
        if not parts:
            return
        head, *rest = parts
        if head.endswith("[*]"):
            key = head[:-3]
            arr = obj.get(key) if isinstance(obj, dict) else None
            if isinstance(arr, list):
                for el in arr:
                    if rest:
                        _scrub_path(el, rest)
        else:
            if isinstance(obj, dict) and head in obj:
                if not rest:
                    obj[head] = "<scrubbed>"
                else:
                    _scrub_path(obj[head], rest)

    import copy
    actual_scrubbed = _scrub(copy.deepcopy(actual), ignore_paths)
    fixture_full_path = pathlib.Path(__file__).parent / fixture_path
    if not fixture_full_path.exists():
        fixture_full_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_full_path.write_text(_json.dumps(actual_scrubbed, indent=2, sort_keys=True))
        return  # First run captures
    expected = _json.loads(fixture_full_path.read_text())
    if actual_scrubbed != expected:
        diff_msg = (
            f"Snapshot mismatch.\nFixture: {fixture_full_path}\n"
            f"Actual: {_json.dumps(actual_scrubbed, indent=2, sort_keys=True)[:500]}\n"
            f"Expected: {_json.dumps(expected, indent=2, sort_keys=True)[:500]}"
        )
        raise AssertionError(diff_msg)


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


class TestNaturalLanguageRegression:
    """Snapshot test — locks in the current NL path happy-path response shape."""

    @pytest.mark.asyncio
    async def test_nl_list_repos_snapshot(self, patch_github_operation):
        mock_invoke = AsyncMock(return_value={
            "success": True,
            "operation": "list_repos",
            "data": [
                {"name": "repo1", "full_name": "user/repo1", "private": False,
                 "url": "https://github.com/user/repo1", "stars": 0, "forks": 0,
                 "description": None, "language": None,
                 "clone_url": "https://github.com/user/repo1.git",
                 "updated_at": "2026-01-01T00:00:00Z",
                 "created_at": "2026-01-01T00:00:00Z"}
            ],
            "audit_id": "audit_test_baseline",
            "timeline": {
                "audit_id": "audit_test_baseline",
                "operation": "github_operation",
                "start_time": "2026-05-15T00:00:00Z",
                "total_duration_ms": 1500.0,
                "events": [
                    {"event": "operation_start",
                     "timestamp": "2026-05-15T00:00:00.001Z",
                     "description": "Parsing: list my repositories",
                     "duration_ms": None,
                     "metadata": {}}
                ],
                "event_count": 1
            }
        })
        with patch_github_operation(mock_invoke):
            response = client.post(
                "/mcp",
                headers={"x-api-key": "df_test"},
                json={
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "github_operation",
                               "arguments": {"query": "list my repositories",
                                             "context": {"github_token": "ghp_test"}}}
                }
            )
        assert response.status_code == 200
        payload = parse_mcp_payload(response.json())
        # Sanity: this should NOT be a -32603 error envelope anymore
        assert "_jsonrpc_error" not in payload, f"Expected happy path, got: {payload}"
        assert payload.get("success") is True
        assert_matches_snapshot(
            payload,
            "fixtures/nl_list_repos_baseline.json",
            ignore_paths=[
                "timeline.events[*].timestamp",
                "timeline.start_time",
                "timeline.total_duration_ms",
                "audit_id",
            ]
        )


class TestStructuredCallMode:
    """Tests for the new structured-call path on the MCP endpoint."""

    @pytest.mark.asyncio
    async def test_nl_path_records_entry_method_natural_language(self, patch_github_operation):
        """An NL call (query-only) must record entry_method='natural_language' in audit."""
        from unittest.mock import AsyncMock
        mock_invoke = AsyncMock(return_value={
            "success": True,
            "operation": "list_repos",
            "data": [],
            "audit_id": "audit_test_3",
            "timeline": {
                "audit_id": "audit_test_3", "operation": "github_operation",
                "start_time": "2026-05-15T00:00:00Z", "total_duration_ms": 100.0,
                "events": [{
                    "event": "operation_start",
                    "timestamp": "2026-05-15T00:00:00.001Z",
                    "description": "Parsing",
                    "duration_ms": None,
                    "metadata": {"entry_method": "natural_language"}
                }],
                "event_count": 1
            }
        })
        with patch_github_operation(mock_invoke):
            response = client.post(
                "/mcp",
                headers={"x-api-key": "df_test"},
                json={
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "github_operation",
                               "arguments": {"query": "list repos",
                                             "context": {"github_token": "ghp_test"}}}
                }
            )
        assert response.status_code == 200
        payload = parse_mcp_payload(response.json())
        assert payload["timeline"]["events"][0]["metadata"]["entry_method"] == "natural_language"

    @pytest.mark.asyncio
    async def test_invoke_rejects_both_query_and_operation(self):
        """github_agent_invoke must reject the case where both query and operation are non-empty."""
        from src.agents.github.agent import github_agent_invoke

        with pytest.raises(ValueError, match="exactly one"):
            await github_agent_invoke(
                query="list repos",
                operation="list_repos",
                parameters={},
                context={"github_token": "ghp_test"},
            )

    @pytest.mark.asyncio
    async def test_invoke_rejects_neither(self):
        """github_agent_invoke must reject the case where both query and operation are absent."""
        from src.agents.github.agent import github_agent_invoke

        with pytest.raises(ValueError, match="exactly one"):
            await github_agent_invoke(
                query=None,
                operation=None,
                parameters=None,
                context={"github_token": "ghp_test"},
            )

    @pytest.mark.asyncio
    async def test_structured_call_skips_llm_classify(self):
        """A structured call must NOT call the supervisor LLM. The audit timeline must
        record a 'step_complete' event with metadata.skipped=true for llm_classify."""
        from src.agents.github.agent import github_agent_invoke
        from unittest.mock import patch as _patch

        # Patch the LLM classifier call site — it MUST NOT be called for structured paths.
        # The LLM is called via router.invoke_with_usage inside parse_github_request.
        # We use a sentinel side_effect so if the LLM IS called, the test fails loudly.
        from unittest.mock import AsyncMock
        sentinel_llm = AsyncMock(side_effect=AssertionError(
            "LLM was called on a structured path — parse_github_request did not skip"
        ))

        with _patch(
            "src.core.model_router.ModelRouter.invoke_with_usage",
            sentinel_llm
        ):
            # Also mock the GitHub API tool so we don't hit the network on execute
            with _patch(
                "src.tools.github.tools.GitHubTools.list_repos",
                return_value=[]
            ):
                result = await github_agent_invoke(
                    operation="list_repos",
                    parameters={"visibility": "all", "limit": 10},
                    context={"github_token": "ghp_test"},
                )

        # Verify the audit timeline recorded the skip
        timeline_events = result["timeline"]["events"]
        classify_event = next(
            (e for e in timeline_events if e.get("metadata", {}).get("step") == "llm_classify"),
            None,
        )
        assert classify_event is not None, (
            f"Expected an llm_classify event in timeline. Got events: {[e.get('event') for e in timeline_events]}"
        )
        assert classify_event["metadata"].get("skipped") is True, (
            f"Expected metadata.skipped=True on llm_classify event. Got: {classify_event['metadata']}"
        )
        assert classify_event["metadata"].get("reason") == "structured_call"

    @pytest.mark.asyncio
    async def test_structured_skips_fuzzy_when_repo_is_exact(self):
        """Structured call with exact owner/repo must NOT call RepoDiscovery.fuzzy_search."""
        from src.agents.github.agent import github_agent_invoke
        from unittest.mock import patch as _patch

        with _patch('src.agents.github.intelligence.repo_discovery.RepoDiscovery.fuzzy_search') as fuzzy_spy:
            with _patch('src.tools.github.tools.GitHubTools.create_issue') as mock_create:
                mock_create.return_value = {"number": 1, "title": "x", "url": "https://github.com/owner/exact-repo/issues/1"}
                await github_agent_invoke(
                    operation="create_issue",
                    parameters={"repo": "owner/exact-repo", "title": "x", "body": "y"},
                    context={"github_token": "ghp_test"},
                )
        fuzzy_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_structured_runs_fuzzy_when_repo_is_substring(self):
        """Structured call with non-exact repo (substring/typo) SHOULD still call fuzzy_search
        (forgiving-fuzzy policy)."""
        from src.agents.github.agent import github_agent_invoke
        from src.agents.github.intelligence.repo_discovery import RepoMatch
        from unittest.mock import patch as _patch

        with _patch('src.agents.github.intelligence.repo_discovery.RepoDiscovery.fuzzy_search') as fuzzy_spy:
            # Return a high-confidence single match so the agent picks it and proceeds
            fuzzy_spy.return_value = [
                RepoMatch(repo=None, full_name="owner/resolved-repo", confidence=0.95, match_type="substring")
            ]
            with _patch('src.tools.github.tools.GitHubTools.create_issue') as mock_create:
                mock_create.return_value = {"number": 1, "title": "x", "url": "..."}
                await github_agent_invoke(
                    operation="create_issue",
                    parameters={"repo": "exact-repo", "title": "x", "body": "y"},  # no slash
                    context={"github_token": "ghp_test"},
                )
        fuzzy_spy.assert_called_once()

    def test_tools_list_github_operation_has_oneOf_union(self):
        """tools/list inputSchema for github_operation must expose both NL and structured shapes."""
        response = client.post("/mcp",
            headers={"x-api-key": "df_test"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert response.status_code == 200
        tools = response.json()["result"]["tools"]
        gh_tool = next((t for t in tools if t["name"] == "github_operation"), None)
        assert gh_tool is not None, "github_operation not registered in tools/list"
        schema = gh_tool["inputSchema"]
        assert "oneOf" in schema, f"Expected oneOf union in inputSchema. Got keys: {list(schema.keys())}"
        assert len(schema["oneOf"]) == 2, f"Expected exactly 2 branches. Got: {len(schema['oneOf'])}"

        # Branch 1: NL shape (query required)
        query_branch = next(
            (b for b in schema["oneOf"] if "query" in b.get("required", [])),
            None,
        )
        assert query_branch is not None, f"No branch with 'query' required. oneOf: {schema['oneOf']}"
        assert query_branch["properties"]["query"]["type"] == "string"

        # Branch 2: structured shape (operation required, enum of 12 ops)
        struct_branch = next(
            (b for b in schema["oneOf"] if "operation" in b.get("required", [])),
            None,
        )
        assert struct_branch is not None, f"No branch with 'operation' required. oneOf: {schema['oneOf']}"
        op_enum = struct_branch["properties"]["operation"]["enum"]
        expected_ops = {"list_repos", "create_repo", "create_issue", "commit_file",
                        "create_pull_request", "browse_files", "read_file", "search_code",
                        "list_branches", "create_branch", "delete_branch", "delete_repo"}
        assert set(op_enum) == expected_ops, f"enum mismatch. Got: {set(op_enum)}"

    @pytest.mark.asyncio
    async def test_structured_skips_commit_gen_when_message_provided(self):
        """If commit_message is provided in parameters, CommitGenerator must NOT run
        even when context.diff is present."""
        from src.agents.github.agent import github_agent_invoke
        from unittest.mock import patch as _patch

        with _patch('src.agents.github.intelligence.commit_generator.CommitGenerator.generate') as gen_spy:
            with _patch('src.tools.github.tools.GitHubTools.commit_file') as mock_commit:
                mock_commit.return_value = {"action": "updated", "commit_sha": "abc",
                                            "file_path": "x.py", "commit_message": "feat: explicit message"}
                await github_agent_invoke(
                    operation="commit_file",
                    parameters={
                        "repo": "owner/r", "file_path": "x.py",
                        "content": "print(1)",
                        "commit_message": "feat: explicit message",
                    },
                    context={"github_token": "ghp_test",
                             "diff": "diff --git a/x.py b/x.py\n+print(1)"},
                )
        gen_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_structured_skips_log_parser_when_title_provided(self):
        """If title is provided in parameters, LogParser must NOT run even when
        context.error_log is present."""
        from src.agents.github.agent import github_agent_invoke
        from unittest.mock import patch as _patch

        with _patch('src.agents.github.intelligence.log_parser.LogParser.parse') as parse_spy:
            with _patch('src.tools.github.tools.GitHubTools.create_issue') as mock_create:
                mock_create.return_value = {"number": 1, "title": "explicit title",
                                            "url": "https://github.com/owner/r/issues/1"}
                await github_agent_invoke(
                    operation="create_issue",
                    parameters={"repo": "owner/r", "title": "explicit title", "body": "y"},
                    context={"github_token": "ghp_test",
                             "error_log": "Traceback (most recent call last):\n  File 'x.py', line 1\nZeroDivisionError: division by zero"},
                )
        parse_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_structured_runs_log_parser_when_title_missing(self):
        """If title is NOT provided but error_log is, LogParser MUST run to derive title/body."""
        from src.agents.github.agent import github_agent_invoke
        from src.agents.github.intelligence.log_parser import ParsedIssue, StackTrace, Language
        from unittest.mock import patch as _patch

        with _patch('src.agents.github.intelligence.log_parser.LogParser.parse') as parse_spy:
            parse_spy.return_value = ParsedIssue(
                title="[ZeroDivisionError] division by zero (x.py:1)",
                body="...",
                labels=["bug", "python", "P1-high"],
                stack_trace=StackTrace(
                    language=Language.PYTHON, error_type="ZeroDivisionError",
                    message="division by zero", file="x.py", line=1, function=None,
                    stack_frames=[], raw_trace=""
                ),
                root_cause=None,
            )
            with _patch('src.tools.github.tools.GitHubTools.create_issue') as mock_create:
                mock_create.return_value = {"number": 1, "title": "...", "url": "..."}
                await github_agent_invoke(
                    operation="create_issue",
                    parameters={"repo": "owner/r"},  # NO title, NO body
                    context={"github_token": "ghp_test",
                             "error_log": "Traceback (most recent call last):\n  File 'x.py', line 1\nZeroDivisionError: division by zero"},
                )
        parse_spy.assert_called_once()

    def test_mcp_rejects_both_query_and_operation(self):
        response = client.post("/mcp",
            headers={"x-api-key": "df_test"},
            json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "github_operation",
                           "arguments": {"query": "x", "operation": "list_repos",
                                         "context": {"github_token": "ghp_test"}}}
            })
        body = response.json()
        assert "error" in body, f"Expected JSON-RPC error envelope. Got: {body}"
        assert body["error"]["code"] == -32602
        assert "Cannot specify both" in body["error"]["message"]

    def test_mcp_rejects_neither_query_nor_operation(self):
        response = client.post("/mcp",
            headers={"x-api-key": "df_test"},
            json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "github_operation",
                           "arguments": {"context": {"github_token": "ghp_test"}}}
            })
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == -32602
        assert "Must specify either" in body["error"]["message"]

    def test_mcp_rejects_unknown_operation(self):
        response = client.post("/mcp",
            headers={"x-api-key": "df_test"},
            json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "github_operation",
                           "arguments": {"operation": "foo_bar_baz",
                                         "context": {"github_token": "ghp_test"}}}
            })
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == -32602
        assert "Unknown operation 'foo_bar_baz'" in body["error"]["message"]
        # Message must enumerate at least a few valid ops
        for op in ["list_repos", "create_issue", "delete_repo"]:
            assert op in body["error"]["message"], f"Missing '{op}' in error message: {body['error']['message']}"

    def test_mcp_rejects_missing_required_field(self):
        response = client.post("/mcp",
            headers={"x-api-key": "df_test"},
            json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "github_operation",
                           "arguments": {"operation": "create_issue", "repo": "owner/r",
                                         "context": {"github_token": "ghp_test"}}}
            })
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == -32602
        # Pydantic's ValidationError for missing required field "title"
        msg = body["error"]["message"].lower()
        assert "title" in msg, f"Expected 'title' to be flagged in error: {body['error']['message']}"

    def test_mcp_structured_create_issue_happy_path(self):
        """End-to-end: MCP /mcp tools/call with operation=create_issue and full typed params.
        Expect success, with audit timeline showing entry_method='structured' and a skipped
        llm_classify event."""
        from unittest.mock import patch as _patch
        with _patch('src.tools.github.tools.GitHubTools.create_issue') as mock_create:
            mock_create.return_value = {
                "number": 42,
                "title": "structured probe",
                "body": "from MCP structured call",
                "state": "open",
                "url": "https://github.com/owner/r/issues/42",
                "labels": [],
                "assignees": [],
                "created_at": "2026-05-15T00:00:00Z",
            }
            response = client.post("/mcp",
                headers={"x-api-key": "df_test"},
                json={
                    "jsonrpc": "2.0", "id": 42, "method": "tools/call",
                    "params": {
                        "name": "github_operation",
                        "arguments": {
                            "operation": "create_issue",
                            "repo": "owner/r",
                            "title": "structured probe",
                            "body": "from MCP structured call",
                            "context": {"github_token": "ghp_test"},
                        },
                    },
                })
        assert response.status_code == 200
        body = response.json()
        # Should NOT be a JSON-RPC error envelope
        assert "error" not in body, f"Unexpected JSON-RPC error: {body.get('error')}"
        # Should have result.content[0].text containing the agent payload as a JSON string
        result = body.get("result")
        assert result is not None, f"Missing result: {body}"
        payload = parse_mcp_payload(body)
        assert payload.get("success") is True, f"Expected success=True. Got: {payload}"
        assert payload.get("operation") == "create_issue"
        assert payload["data"]["number"] == 42

        # Every audit event records entry_method=structured
        events = payload["timeline"]["events"]
        entry_methods = set(
            e.get("metadata", {}).get("entry_method") for e in events
        )
        assert entry_methods == {"structured"}, (
            f"Expected all events to have entry_method='structured', got: {entry_methods}"
        )

        # The llm_classify event recorded itself as skipped
        classify = next(
            (e for e in events if e.get("metadata", {}).get("step") == "llm_classify"),
            None,
        )
        assert classify is not None, f"No llm_classify event in timeline. Events: {[e.get('event') for e in events]}"
        assert classify["metadata"].get("skipped") is True

        # The GitHub API was called (mock_create)
        mock_create.assert_called_once()
        # Title should appear in the kwargs or positional args
        call_str = repr(mock_create.call_args)
        assert "structured probe" in call_str, f"title not in call_args: {call_str}"

    # All 12 structured-call operations sweeping the MCP handler end-to-end.
    # Each row mocks the corresponding GitHubTools method, asserts a clean
    # success envelope, and confirms the audit timeline records entry_method=structured.
    @pytest.mark.parametrize("operation,parameters,context_extras,mock_attr,mock_return", [
        ("list_repos",
         {"visibility": "public", "limit": 3},
         {},
         "list_repos",
         [{"name": "r1", "full_name": "u/r1", "url": "x", "private": False, "stars": 0,
           "forks": 0, "description": None, "language": None, "clone_url": "x",
           "updated_at": "2026-01-01T00:00:00Z", "created_at": "2026-01-01T00:00:00Z"}]),
        ("create_repo",
         {"name": "demo-probe"},
         {"confirmed": True},
         "create_repo",
         {"name": "demo-probe", "full_name": "u/demo-probe", "url": "x", "private": False}),
        ("create_issue",
         {"repo": "owner/r", "title": "probe", "body": "b"},
         {},
         "create_issue",
         {"number": 1, "title": "probe", "url": "x", "state": "open", "labels": [], "assignees": []}),
        # commit_file to a non-protected branch stays MEDIUM (no confirmation needed).
        # Contextual rule in src/core/risk.py:218-220 escalates main/master/production to HIGH.
        ("commit_file",
         {"repo": "owner/r", "file_path": "x.py", "content": "print(1)",
          "commit_message": "feat: probe", "branch": "feat-probe"},
         {},
         "commit_file",
         {"action": "created", "file_path": "x.py", "commit_sha": "abc", "commit_message": "feat: probe"}),
        ("create_pull_request",
         {"repo": "owner/r", "title": "probe", "head": "feat", "base": "main"},
         {},
         "create_pull_request",
         {"number": 1, "title": "probe", "url": "x", "state": "open", "draft": False}),
        ("browse_files",
         {"repo": "owner/r", "path": "/"},
         {},
         "browse_files",
         [{"name": "README.md", "path": "README.md", "type": "file", "size": 100, "url": "x"}]),
        ("read_file",
         {"repo": "owner/r", "file_path": "README.md"},
         {},
         "read_file",
         {"path": "README.md", "content": "# probe", "size": 8}),
        ("search_code",
         {"query": "TODO", "repo": "owner/r"},
         {},
         "search_code",
         [{"path": "x.py", "repository": "owner/r", "url": "x"}]),
        ("list_branches",
         {"repo": "owner/r"},
         {},
         "list_branches",
         [{"name": "main", "sha": "abc", "protected": False}]),
        ("create_branch",
         {"repo": "owner/r", "branch_name": "feat-probe", "from_branch": "main"},
         {},
         "create_branch",
         {"name": "feat-probe", "sha": "abc"}),
        ("delete_branch",
         {"repo": "owner/r", "branch_name": "feat-probe"},
         {"confirmed": True},
         "delete_branch",
         {"deleted": "feat-probe"}),
        ("delete_repo",
         {"repo": "owner/probe-repo"},
         {"confirmed": True, "reason": "test cleanup"},
         "delete_repo",
         {"deleted": "owner/probe-repo"}),
    ])
    def test_mcp_structured_each_operation_end_to_end(
        self, operation, parameters, context_extras, mock_attr, mock_return
    ):
        """End-to-end MCP smoke for every structured-call operation.

        Each parametrized case patches the corresponding GitHubTools method, sends
        an MCP tools/call with the structured envelope, and verifies a clean success
        response with entry_method=structured propagated through the audit timeline.
        """
        from unittest.mock import patch as _patch
        mock_target = f"src.tools.github.tools.GitHubTools.{mock_attr}"
        ctx = {"github_token": "ghp_test", **context_extras}
        args = {"operation": operation, **parameters, "context": ctx}

        with _patch(mock_target) as mock_fn:
            mock_fn.return_value = mock_return
            response = client.post(
                "/mcp",
                headers={"x-api-key": "df_test"},
                json={
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "github_operation", "arguments": args},
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert "error" not in body, (
            f"Unexpected JSON-RPC error for {operation}: {body.get('error')}"
        )
        payload = parse_mcp_payload(body)
        assert payload.get("success") is True, (
            f"Expected success=True for {operation}. Got: {payload}"
        )
        assert payload.get("operation") == operation

        events = payload["timeline"]["events"]
        entry_methods = {e.get("metadata", {}).get("entry_method") for e in events}
        assert entry_methods == {"structured"}, (
            f"For {operation}, expected all entry_method='structured', got: {entry_methods}"
        )

        classify = next(
            (e for e in events if e.get("metadata", {}).get("step") == "llm_classify"),
            None,
        )
        assert classify is not None, f"No llm_classify event for {operation}"
        assert classify["metadata"].get("skipped") is True, (
            f"llm_classify event for {operation} did not record skipped=True"
        )

        mock_fn.assert_called_once()

    def test_structured_create_repo_blocked_without_confirmed(self):
        """HIGH-risk create_repo via structured path must hit the risk gate just like NL."""
        response = client.post("/mcp",
            headers={"x-api-key": "df_test"},
            json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {
                    "name": "github_operation",
                    "arguments": {
                        "operation": "create_repo",
                        "name": "demo-probe",
                        "context": {"github_token": "ghp_test"},
                    },
                },
            })
        body = response.json()
        # Either JSON-RPC error envelope (preferred) OR result.content with success=false
        # are valid risk-block responses. The risk-gate path produces -32603 per the plan.
        if "error" in body:
            assert body["error"]["code"] == -32603, f"Expected -32603, got: {body['error']}"
            assert "Risk gate blocked" in body["error"]["message"]
            assert "confirmed=true" in body["error"]["message"]
        else:
            # If wrapped in result.content with isError=true, parse the inner payload
            payload = parse_mcp_payload(body)
            assert payload.get("success") is False
            msg = (payload.get("message") or "") + " " + (payload.get("error") or "")
            assert "Risk gate blocked" in msg, f"Expected risk-gate block. Got: {payload}"
            assert "confirmed=true" in msg

    def test_structured_delete_repo_blocked_without_reason(self):
        """CRITICAL delete_repo with confirmed=true but no reason — still blocked."""
        response = client.post("/mcp",
            headers={"x-api-key": "df_test"},
            json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {
                    "name": "github_operation",
                    "arguments": {
                        "operation": "delete_repo",
                        "repo": "owner/some-repo",
                        "context": {"github_token": "ghp_test", "confirmed": True},
                    },
                },
            })
        body = response.json()
        if "error" in body:
            assert body["error"]["code"] == -32603
            assert "reason" in body["error"]["message"].lower()
        else:
            payload = parse_mcp_payload(body)
            assert payload.get("success") is False
            msg = (payload.get("message") or "") + " " + (payload.get("error") or "")
            assert "reason" in msg.lower(), f"Expected 'reason' in message. Got: {payload}"

    def test_structured_delete_branch_main_escalates_to_critical(self):
        """Contextual escalation: delete_branch of main/master must escalate to CRITICAL
        (which requires confirmed+reason)."""
        response = client.post("/mcp",
            headers={"x-api-key": "df_test"},
            json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {
                    "name": "github_operation",
                    "arguments": {
                        "operation": "delete_branch",
                        "repo": "owner/r",
                        "branch_name": "main",
                        "context": {"github_token": "ghp_test", "confirmed": True},
                    },
                },
            })
        body = response.json()
        # Risk-gate block expected. Either form is acceptable (-32603 OR wrapped failure).
        if "error" in body:
            assert body["error"]["code"] == -32603
            # Either "Risk gate" or "reason" mentioned
            msg = body["error"]["message"]
            assert "Risk gate" in msg or "reason" in msg.lower(), f"Got: {msg}"
        else:
            payload = parse_mcp_payload(body)
            assert payload.get("success") is False
            msg = (payload.get("message") or "") + " " + (payload.get("error") or "")
            assert "Risk gate" in msg or "reason" in msg.lower()
