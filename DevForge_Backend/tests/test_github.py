import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from github import GithubException

from src.tools.github.tools import (
    GitHubTools,
    list_repos,
    create_repo,
    create_issue,
    commit_file,
    create_pull_request,
)
from src.agents.github.agent import (
    github_agent_invoke,
    parse_github_request,
    execute_github_operation,
    GitHubState,
)


# Fixtures
@pytest.fixture
def mock_github_client():
    """Mock GitHub client."""
    with patch("src.tools.github.tools.Github") as mock:
        client = Mock()
        user = Mock()
        user.login = "testuser"
        client.get_user.return_value = user
        mock.return_value = client
        yield client


@pytest.fixture
def github_tools_instance(mock_github_client):
    """GitHub tools instance with mocked client."""
    return GitHubTools(token="test_token")


# Unit Tests for GitHubTools
class TestGitHubTools:
    """Test GitHub tools functionality."""
    
    def test_initialization_without_token(self):
        """Test that initialization fails without token."""
        with patch("src.tools.github.tools.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = None
            with pytest.raises(ValueError, match="GitHub token required"):
                GitHubTools()
    
    def test_list_repos(self, github_tools_instance, mock_github_client):
        """Test listing repositories."""
        # Mock repository data
        mock_repo = Mock()
        mock_repo.name = "test-repo"
        mock_repo.full_name = "testuser/test-repo"
        mock_repo.description = "Test repository"
        mock_repo.private = False
        mock_repo.html_url = "https://github.com/testuser/test-repo"
        mock_repo.clone_url = "https://github.com/testuser/test-repo.git"
        mock_repo.language = "Python"
        mock_repo.stargazers_count = 10
        mock_repo.forks_count = 5
        mock_repo.updated_at = None
        mock_repo.created_at = None
        
        user = mock_github_client.get_user.return_value
        user.get_repos.return_value = [mock_repo]
        
        result = github_tools_instance.list_repos(limit=1)
        
        assert len(result) == 1
        assert result[0]["name"] == "test-repo"
        assert result[0]["full_name"] == "testuser/test-repo"
        assert result[0]["stars"] == 10
        user.get_repos.assert_called_once()
    
    def test_list_repos_with_filters(self, github_tools_instance, mock_github_client):
        """Test listing repositories with filters."""
        user = mock_github_client.get_user.return_value
        user.get_repos.return_value = []
        
        github_tools_instance.list_repos(visibility="private", sort="created", limit=5)
        
        user.get_repos.assert_called_once_with(visibility="private", sort="created")
    
    def test_list_repos_github_exception(self, github_tools_instance, mock_github_client):
        """Test handling GitHub API errors in list_repos."""
        user = mock_github_client.get_user.return_value
        user.get_repos.side_effect = GithubException(404, {"message": "Not found"})
        
        with pytest.raises(GithubException):
            github_tools_instance.list_repos()
    
    def test_create_repo(self, github_tools_instance, mock_github_client):
        """Test creating a repository."""
        mock_repo = Mock()
        mock_repo.name = "new-repo"
        mock_repo.full_name = "testuser/new-repo"
        mock_repo.description = "New repository"
        mock_repo.private = False
        mock_repo.html_url = "https://github.com/testuser/new-repo"
        mock_repo.clone_url = "https://github.com/testuser/new-repo.git"
        mock_repo.created_at = None
        
        user = mock_github_client.get_user.return_value
        user.create_repo.return_value = mock_repo
        
        result = github_tools_instance.create_repo(
            name="new-repo",
            description="New repository",
            private=False
        )
        
        assert result["name"] == "new-repo"
        assert result["full_name"] == "testuser/new-repo"
        assert result["private"] is False
        user.create_repo.assert_called_once()
    
    def test_create_issue(self, github_tools_instance, mock_github_client):
        """Test creating an issue."""
        mock_issue = Mock()
        mock_issue.number = 1
        mock_issue.title = "Test issue"
        mock_issue.body = "Issue body"
        mock_issue.state = "open"
        mock_issue.html_url = "https://github.com/testuser/test-repo/issues/1"
        mock_issue.labels = []
        mock_issue.assignees = []
        mock_issue.created_at = None
        
        mock_repo = Mock()
        mock_repo.create_issue.return_value = mock_issue
        mock_github_client.get_repo.return_value = mock_repo
        
        result = github_tools_instance.create_issue(
            repo_name="test-repo",
            title="Test issue",
            body="Issue body"
        )
        
        assert result["number"] == 1
        assert result["title"] == "Test issue"
        assert result["state"] == "open"
        mock_github_client.get_repo.assert_called_once_with("testuser/test-repo")
    
    def test_create_issue_with_full_repo_name(self, github_tools_instance, mock_github_client):
        """Test creating issue with owner/repo format."""
        mock_issue = Mock()
        mock_issue.number = 1
        mock_issue.title = "Test"
        mock_issue.body = ""
        mock_issue.state = "open"
        mock_issue.html_url = "https://github.com/owner/repo/issues/1"
        mock_issue.labels = []
        mock_issue.assignees = []
        mock_issue.created_at = None
        
        mock_repo = Mock()
        mock_repo.create_issue.return_value = mock_issue
        mock_github_client.get_repo.return_value = mock_repo
        
        github_tools_instance.create_issue(
            repo_name="owner/repo",
            title="Test"
        )
        
        mock_github_client.get_repo.assert_called_once_with("owner/repo")
    
    def test_commit_file_new(self, github_tools_instance, mock_github_client):
        """Test committing a new file."""
        mock_repo = Mock()
        mock_repo.get_contents.side_effect = GithubException(404, {"message": "Not found"})
        
        mock_commit = Mock()
        mock_commit.sha = "abc123"
        mock_commit.html_url = "https://github.com/testuser/test-repo/commit/abc123"
        
        mock_repo.create_file.return_value = {"commit": mock_commit}
        mock_github_client.get_repo.return_value = mock_repo
        
        result = github_tools_instance.commit_file(
            repo_name="test-repo",
            file_path="test.py",
            content="print('hello')",
            commit_message="Add test file"
        )
        
        assert result["action"] == "created"
        assert result["file_path"] == "test.py"
        assert result["commit_sha"] == "abc123"
        mock_repo.create_file.assert_called_once()
    
    def test_commit_file_update(self, github_tools_instance, mock_github_client):
        """Test updating an existing file."""
        mock_existing = Mock()
        mock_existing.sha = "old_sha"
        
        mock_repo = Mock()
        mock_repo.get_contents.return_value = mock_existing
        
        mock_commit = Mock()
        mock_commit.sha = "new_sha"
        mock_commit.html_url = "https://github.com/testuser/test-repo/commit/new_sha"
        
        mock_repo.update_file.return_value = {"commit": mock_commit}
        mock_github_client.get_repo.return_value = mock_repo
        
        result = github_tools_instance.commit_file(
            repo_name="test-repo",
            file_path="test.py",
            content="print('updated')",
            commit_message="Update test file"
        )
        
        assert result["action"] == "updated"
        assert result["commit_sha"] == "new_sha"
        mock_repo.update_file.assert_called_once()
    
    def test_create_pull_request(self, github_tools_instance, mock_github_client):
        """Test creating a pull request."""
        mock_pr = Mock()
        mock_pr.number = 1
        mock_pr.title = "Test PR"
        mock_pr.body = "PR body"
        mock_pr.state = "open"
        mock_pr.draft = False
        mock_pr.head = Mock(ref="feature")
        mock_pr.base = Mock(ref="main")
        mock_pr.html_url = "https://github.com/testuser/test-repo/pull/1"
        mock_pr.created_at = None
        
        mock_repo = Mock()
        mock_repo.create_pull.return_value = mock_pr
        mock_github_client.get_repo.return_value = mock_repo
        
        result = github_tools_instance.create_pull_request(
            repo_name="test-repo",
            title="Test PR",
            head="feature",
            base="main",
            body="PR body"
        )
        
        assert result["number"] == 1
        assert result["title"] == "Test PR"
        assert result["head"] == "feature"
        assert result["base"] == "main"
        mock_repo.create_pull.assert_called_once()


# Unit Tests for GitHub Agent
class TestGitHubAgent:
    """Test GitHub agent workflow."""
    
    @pytest.mark.asyncio
    async def test_parse_list_repos_request(self):
        """Test parsing list repos request."""
        state: GitHubState = {
            "query": "List my repositories",
            "operation": None,
            "parameters": None,
            "result": None,
            "error": None,
        }
        
        # Mock model router and LLM response
        mock_response = '{"operation": "list_repos", "parameters": {"limit": 10}}'
        
        with patch("src.agents.github.agent.ModelRouter") as MockRouter:
            mock_router = MockRouter.return_value
            mock_router.select_model_by_task.return_value = "qwen3-coder:480b-cloud"
            # Use AsyncMock for async function
            mock_router.invoke_with_fallback = MagicMock(side_effect=lambda *args, **kwargs: asyncio.sleep(0, result=mock_response))
            
            # Helper to wrap in coroutine
            async def mock_invoke(*args, **kwargs):
                return mock_response
            mock_router.invoke_with_fallback.side_effect = mock_invoke

            result = await parse_github_request(state)
            
            assert result["operation"] == "list_repos"
            assert result["parameters"]["limit"] == 10
            assert result["error"] is None
    
    @pytest.mark.asyncio
    async def test_parse_create_repo_request(self):
        """Test parsing create repo request."""
        state: GitHubState = {
            "query": "Create a new repository called 'awesome-project'",
            "operation": None,
            "parameters": None,
            "result": None,
            "error": None,
        }
        
        mock_response = '{"operation": "create_repo", "parameters": {"name": "awesome-project"}}'
        
        with patch("src.agents.github.agent.ModelRouter") as MockRouter:
            mock_router = MockRouter.return_value
            mock_router.select_model_by_task.return_value = "qwen3-coder:480b-cloud"
            
            async def mock_invoke(*args, **kwargs):
                return mock_response
            mock_router.invoke_with_fallback.side_effect = mock_invoke
            
            result = await parse_github_request(state)
            
            assert result["operation"] == "create_repo"
            assert result["parameters"]["name"] == "awesome-project"
    
    @pytest.mark.asyncio
    async def test_parse_request_error(self):
        """Test parsing request with LLM error."""
        state: GitHubState = {
            "query": "Do something",
            "operation": None,
            "parameters": None,
            "result": None,
            "error": None,
        }
        
        with patch("src.agents.github.agent.ModelRouter") as MockRouter:
            mock_router = MockRouter.return_value
            mock_router.select_model_by_task.side_effect = Exception("Model unavailable")
            
            result = await parse_github_request(state)
            
            assert result["error"] is not None
            assert "Failed to parse" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_list_repos_operation(self):
        """Test executing list repos operation."""
        state: GitHubState = {
            "query": "List repos",
            "operation": "list_repos",
            "parameters": {"limit": 5},
            "result": None,
            "error": None,
        }
        
        mock_repos = [{"name": "repo1"}, {"name": "repo2"}]
        
        with patch("src.agents.github.agent.github_tools.list_repos", return_value=mock_repos):
            result = await execute_github_operation(state)
            
            assert result["result"]["success"] is True
            assert result["result"]["operation"] == "list_repos"
            assert result["result"]["data"] == mock_repos
    
    @pytest.mark.asyncio
    async def test_execute_create_repo_operation(self):
        """Test executing create repo operation."""
        state: GitHubState = {
            "query": "Create repo",
            "operation": "create_repo",
            "parameters": {"name": "new-repo"},
            "result": None,
            "error": None,
        }
        
        mock_repo = {"name": "new-repo", "url": "https://github.com/user/new-repo"}
        
        with patch("src.agents.github.agent.github_tools.create_repo", return_value=mock_repo):
            result = await execute_github_operation(state)
            
            assert result["result"]["success"] is True
            assert result["result"]["data"]["name"] == "new-repo"
    
    @pytest.mark.asyncio
    async def test_execute_operation_error(self):
        """Test handling errors during operation execution."""
        state: GitHubState = {
            "query": "Create repo",
            "operation": "create_repo",
            "parameters": {"name": "test"},
            "result": None,
            "error": None,
        }
        
        with patch("src.agents.github.agent.github_tools.create_repo", side_effect=Exception("API error")):
            result = await execute_github_operation(state)
            
            assert result["error"] is not None
            assert result["result"]["success"] is False
            assert "API error" in result["result"]["error"]
    
    @pytest.mark.asyncio
    async def test_execute_unknown_operation(self):
        """Test handling unknown operation."""
        state: GitHubState = {
            "query": "Unknown",
            "operation": "unknown_op",
            "parameters": {},
            "result": None,
            "error": None,
        }
        
        result = await execute_github_operation(state)
        
        assert result["error"] is not None
        assert "Unknown GitHub operation" in result["error"]


# Integration Tests
class TestGitHubAgentIntegration:
    """Test full GitHub agent workflow."""
    
    @pytest.mark.asyncio
    async def test_full_list_repos_workflow(self):
        """Test complete workflow for listing repos."""
        query = "Show me my repositories"
        
        mock_repos = [
            {"name": "repo1", "stars": 10},
            {"name": "repo2", "stars": 5}
        ]
        
        mock_llm_response = '{"operation": "list_repos", "parameters": {"limit": 10}}'
        
        with patch("src.agents.github.agent.ModelRouter") as MockRouter, \
             patch("src.agents.github.agent.github_tools.list_repos", return_value=mock_repos):
            
            mock_router = MockRouter.return_value
            mock_router.select_model_by_task.return_value = "qwen3-coder:480b-cloud"
            
            async def mock_invoke(*args, **kwargs):
                return mock_llm_response
            mock_router.invoke_with_fallback.side_effect = mock_invoke
            
            result = await github_agent_invoke(query)
            
            assert result["success"] is True
            assert result["operation"] == "list_repos"
            assert len(result["data"]) == 2
    
    @pytest.mark.asyncio
    async def test_full_create_issue_workflow(self):
        """Test complete workflow for creating an issue."""
        query = "Create an issue in my-repo with title 'Bug fix needed'"
        
        mock_issue = {
            "number": 42,
            "title": "Bug fix needed",
            "url": "https://github.com/user/my-repo/issues/42"
        }
        
        mock_llm_response = '''{
            "operation": "create_issue",
            "parameters": {
                "repo_name": "my-repo",
                "title": "Bug fix needed"
            }
        }'''
        
        with patch("src.agents.github.agent.ModelRouter") as MockRouter, \
             patch("src.agents.github.agent.github_tools.create_issue", return_value=mock_issue):
            
            mock_router = MockRouter.return_value
            mock_router.select_model_by_task.return_value = "qwen3-coder:480b-cloud"
            
            async def mock_invoke(*args, **kwargs):
                return mock_llm_response
            mock_router.invoke_with_fallback.side_effect = mock_invoke
            
            result = await github_agent_invoke(query)
            
            assert result["success"] is True
            assert result["data"]["number"] == 42


# Convenience Function Tests
class TestConvenienceFunctions:
    """Test convenience wrapper functions."""
    
    def test_list_repos_convenience(self, mock_github_client):
        """Test list_repos convenience function."""
        user = mock_github_client.get_user.return_value
        user.get_repos.return_value = []
        
        with patch("src.tools.github.tools.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "test_token"
            result = list_repos(limit=5)
            
            assert isinstance(result, list)
    
    def test_create_repo_convenience(self, mock_github_client):
        """Test create_repo convenience function."""
        mock_repo = Mock()
        mock_repo.name = "test"
        mock_repo.full_name = "user/test"
        mock_repo.description = None
        mock_repo.private = False
        mock_repo.html_url = "https://github.com/user/test"
        mock_repo.clone_url = "https://github.com/user/test.git"
        mock_repo.created_at = None
        
        user = mock_github_client.get_user.return_value
        user.create_repo.return_value = mock_repo
        
        with patch("src.tools.github.tools.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "test_token"
            result = create_repo(name="test")
            
            assert result["name"] == "test"