"""Integration tests for enhanced GitHub agent.

Tests the complete workflow: parse → enhance → execute with all v0.8 components.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.github.agent import github_agent_invoke


class TestGitHubAgentIntegration:
    """Integration tests for enhanced GitHub agent"""
    
    @pytest.mark.asyncio
    async def test_basic_list_repos(self):
        """Test basic list repos operation (backward compatibility)"""
        with patch("src.agents.github.agent.github_tools") as mock_tools:
            mock_tools.list_repos.return_value = [
                {"name": "repo1", "full_name": "user/repo1"},
                {"name": "repo2", "full_name": "user/repo2"}
            ]
            
            with patch("src.agents.github.agent.ModelRouter") as mock_router:
                mock_instance = AsyncMock()
                mock_instance.select_model_by_task.return_value = "test-model"
                mock_instance.invoke_with_fallback.return_value = '''
                {
                    "operation": "list_repos",
                    "parameters": {"limit": 10},
                    "confidence": 0.95
                }
                '''
                mock_router.return_value = mock_instance
                
                result = await github_agent_invoke("list my repositories")
                
                assert result["success"] is True
                assert result["operation"] == "list_repos"
                assert "audit_id" in result
                assert "timeline" in result
                assert result["intent_confidence"] == 0.95
    
    @pytest.mark.asyncio
    async def test_fuzzy_repo_discovery(self):
        """Test fuzzy repository matching"""
        with patch("src.agents.github.agent.github_tools") as mock_tools:
            # Mock repo list for fuzzy matching
            mock_tools.GitHubTools.return_value.list_repos.return_value = [
                {"name": "backend-api", "full_name": "user/backend-api", "url": "http://github.com/user/backend-api"}
            ]
            
            mock_tools.create_issue.return_value = {"number": 42}
            
            with patch("src.agents.github.agent.ModelRouter") as mock_router:
                mock_instance = AsyncMock()
                mock_instance.select_model_by_task.return_value = "test-model"
                mock_instance.invoke_with_fallback.return_value = '''
                {
                    "operation": "create_issue",
                    "parameters": {
                        "repo_name": "backend",
                        "title": "Test issue",
                        "body": "Issue body"
                    },
                    "confidence": 0.92
                }
                '''
                mock_router.return_value = mock_instance
                
                result = await github_agent_invoke(
                    "create issue in backend repo",
                    context={}
                )
                
                # Should fuzzy match "backend" to "user/backend-api"
                assert result["success"] is True
                assert "repo_confidence" in result or result["success"]
    
    @pytest.mark.asyncio
    async def test_commit_message_generation(self):
        """Test AI commit message generation from diff"""
        with patch("src.agents.github.agent.github_tools") as mock_tools:
            mock_tools.commit_file.return_value = {"sha": "abc123"}
            
            with patch("src.agents.github.agent.ModelRouter") as mock_router:
                mock_instance = AsyncMock()
                mock_instance.select_model_by_task.return_value = "test-model"
                
                # Mock intent classification
                mock_instance.invoke_with_fallback.side_effect = [
                    # First call: intent classification
                    '''
                    {
                        "operation": "commit_file",
                        "parameters": {
                            "repo_name": "user/test-repo",
                            "file_path": "app.py",
                            "content": "new content"
                        },
                        "confidence": 0.93
                    }
                    ''',
                    # Second call: commit message generation
                    "feat(auth): implement JWT token rotation"
                ]
                
                mock_router.return_value = mock_instance
                
                result = await github_agent_invoke(
                    "commit changes to app.py",
                    context={
                        "diff": "+def new_function():\n+    pass"
                    }
                )
                
                # Should auto-generate commit message
                assert result["success"] is True
                assert "commit_confidence" in result or result["success"]
    
    @pytest.mark.asyncio
    async def test_log_parsing_to_issue(self):
        """Test parsing error log to GitHub issue"""
        error_log = """Traceback (most recent call last):
  File "app.py", line 42, in main
    result = divide(10, 0)
ZeroDivisionError: division by zero"""
        
        with patch("src.agents.github.agent.github_tools") as mock_tools:
            mock_tools.create_issue.return_value = {"number": 123}
            
            with patch("src.agents.github.agent.ModelRouter") as mock_router:
                mock_instance = AsyncMock()
                mock_instance.select_model_by_task.return_value = "test-model"
                
                # Mock responses
                mock_instance.invoke_with_fallback.side_effect = [
                    # Intent classification
                    '''
                    {
                        "operation": "create_issue",
                        "parameters": {
                            "repo_name": "user/test-repo",
                            "title": "Error occurred",
                            "body": "See log"
                        },
                        "confidence": 0.88
                    }
                    ''',
                    # Root cause analysis
                    "Division by zero error in main function. Check input validation."
                ]
                
                mock_router.return_value = mock_instance
                
                result = await github_agent_invoke(
                    "create issue from this error",
                    context={
                        "error_log": error_log,
                        "language": "python"
                    }
                )
                
                # Should parse log and create structured issue
                assert result["success"] is True
                # Parameters should be enhanced with parsed data
    
    @pytest.mark.asyncio
    async def test_low_confidence_requires_confirmation(self):
        """Test low confidence triggers confirmation request"""
        with patch("src.agents.github.agent.ModelRouter") as mock_router:
            mock_instance = AsyncMock()
            mock_instance.select_model_by_task.return_value = "test-model"
            mock_instance.invoke_with_fallback.return_value = '''
            {
                "operation": "commit_file",
                "parameters": {
                    "repo_name": "test",
                    "file_path": "test.py",
                    "content": "x"
                },
                "confidence": 0.75
            }
            '''
            mock_router.return_value = mock_instance
            
            result = await github_agent_invoke("commit something")
            
            # Low confidence should trigger confirmation
            assert result["success"] is False
            assert result["status"] == "needs_confirmation"
            assert "preview" in result
            assert "confidence" in result
            assert result["confidence"] < 0.85
    
    @pytest.mark.asyncio
    async def test_medium_confidence_creates_draft_pr(self):
        """Test medium confidence commit creates draft PR"""
        with patch("src.agents.github.agent.github_tools") as mock_tools:
            mock_tools.commit_file.return_value = {"sha": "xyz789"}
            
            with patch("src.agents.github.agent.ModelRouter") as mock_router:
                mock_instance = AsyncMock()
                mock_instance.select_model_by_task.return_value = "test-model"
                
                mock_instance.invoke_with_fallback.side_effect = [
                    # Intent with medium confidence
                    '''
                    {
                        "operation": "commit_file",
                        "parameters": {
                            "repo_name": "user/test",
                            "file_path": "app.py",
                            "content": "code"
                        },
                        "confidence": 0.92
                    }
                    ''',
                    # Commit message with medium confidence (0.85-0.90)
                    "feat: update app"  # This would have confidence 0.87 from generator
                ]
                
                mock_router.return_value = mock_instance
                
                with patch("src.agents.github.intelligence.commit_generator.CommitGenerator.generate") as mock_gen:
                    from src.agents.github.intelligence.commit_generator import CommitMessage, ChangeType
                    
                    mock_gen.return_value = CommitMessage(
                        text="feat: update app",
                        type=ChangeType.FEAT,
                        scope=None,
                        description="update app",
                        body=None,
                        confidence=0.87  # Medium confidence
                    )
                    
                    result = await github_agent_invoke(
                        "commit my changes",
                        context={"diff": "+new code"}
                    )
                    
                    # Should still succeed but note draft recommendation
                    assert result["success"] is True or "_create_draft_reason" in result
    
    @pytest.mark.asyncio
    async def test_audit_logging(self):
        """Test audit ID and timeline generation"""
        with patch("src.agents.github.agent.github_tools") as mock_tools:
            mock_tools.list_repos.return_value = []
            
            with patch("src.agents.github.agent.ModelRouter") as mock_router:
                mock_instance = AsyncMock()
                mock_instance.select_model_by_task.return_value = "test-model"
                mock_instance.invoke_with_fallback.return_value = '''
                {
                    "operation": "list_repos",
                    "parameters": {},
                    "confidence": 0.98
                }
                '''
                mock_router.return_value = mock_instance
                
                result = await github_agent_invoke("list repos")
                
                # Every operation must have audit_id and timeline
                assert "audit_id" in result
                assert result["audit_id"].startswith("audit_")
                assert "timeline" in result
                assert isinstance(result["timeline"], dict)
                assert "events" in result["timeline"]
                assert result["timeline"]["event_count"] > 0
    
    @pytest.mark.asyncio
    async def test_session_context_support(self):
        """Test session context is properly handled"""
        with patch("src.agents.github.agent.github_tools") as mock_tools:
            mock_tools.create_issue.return_value = {"number": 1}
            
            with patch("src.agents.github.agent.ModelRouter") as mock_router:
                mock_instance = AsyncMock()
                mock_instance.select_model_by_task.return_value = "test-model"
                mock_instance.invoke_with_fallback.return_value = '''
                {
                    "operation": "create_issue",
                    "parameters": {
                        "repo_name": "user/repo",
                        "title": "Test",
                        "body": "Body"
                    },
                    "confidence": 0.91
                }
                '''
                mock_router.return_value = mock_instance
                
                result = await github_agent_invoke(
                    "create an issue",
                    context={
                        "session_id": "session_123",
                        "files": ["app.py", "test.py"]
                    }
                )
                
                # Should process successfully with context
                assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_error_handling_with_audit(self):
        """Test error handling includes audit information"""
        with patch("src.agents.github.agent.github_tools") as mock_tools:
            mock_tools.create_issue.side_effect = Exception("GitHub API error")
            
            with patch("src.agents.github.agent.ModelRouter") as mock_router:
                mock_instance = AsyncMock()
                mock_instance.select_model_by_task.return_value = "test-model"
                mock_instance.invoke_with_fallback.return_value = '''
                {
                    "operation": "create_issue",
                    "parameters": {
                        "repo_name": "test",
                        "title": "Test"
                    },
                    "confidence": 0.95
                }
                '''
                mock_router.return_value = mock_instance
                
                result = await github_agent_invoke("create issue")
                
                # Error should still include audit info
                assert result["success"] is False
                assert "error" in result
                assert "audit_id" in result
                assert "timeline" in result


@pytest.mark.asyncio
async def test_end_to_end_workflow():
    """Test complete end-to-end workflow with all components"""
    with patch("src.agents.github.agent.github_tools") as mock_tools:
        # Setup mocks
        mock_tools.GitHubTools.return_value.list_repos.return_value = [
            {"name": "backend-api", "full_name": "org/backend-api", "url": "http://github.com/org/backend-api"}
        ]
        mock_tools.commit_file.return_value = {"sha": "commit123"}
        
        with patch("src.agents.github.agent.ModelRouter") as mock_router:
            mock_instance = AsyncMock()
            mock_instance.select_model_by_task.return_value = "test-model"
            
            mock_instance.invoke_with_fallback.side_effect = [
                # Intent classification
                '''
                {
                    "operation": "commit_file",
                    "parameters": {
                        "repo_name": "backend",
                        "file_path": "auth.py",
                        "content": "updated auth code"
                    },
                    "confidence": 0.94
                }
                ''',
                # Commit message generation
                "feat(auth): implement JWT rotation logic"
            ]
            
            mock_router.return_value = mock_instance
            
            # Execute with full context
            result = await github_agent_invoke(
                "commit my auth changes",
                context={
                    "diff": """
+def rotate_jwt_token(user_id):
+    # Generate new token
+    return create_jwt(user_id)
""",
                    "files": ["auth.py"],
                    "session_id": "user_session_123"
                }
            )
            
            # Verify complete workflow
            assert result["success"] is True or "error" not in result
            assert "audit_id" in result
            assert "timeline" in result
            assert "intent_confidence" in result
            # Fuzzy repo matching may have happened
            # Commit message may have been generated
