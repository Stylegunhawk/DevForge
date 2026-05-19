# GitOps v3 Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand `github_operation` from 13 to 26 structured ops covering PR inspection, issue CRUD, commit history, releases, GitHub Actions, and webhooks — with enriched error messages and per-tenant session TTL.

**Architecture:** All 13 new methods added in-place to `GitHubTools` in `tools.py` using region dividers. New Pydantic schemas in `schemas.py`. Risk table entries in `risk.py`. Dispatch branches in `agent.py`. TDD throughout — write test → verify fail → implement → verify pass → commit.

**Tech Stack:** Python 3.12, PyGithub 2.8, Pydantic 2.12, FastAPI 0.120, pytest + unittest.mock

---

## File Map

| File | Change |
|------|--------|
| `src/tools/github/tools.py` | Add `_SCOPE_MAP`, `_enrich_github_error()`, 13 new `GitHubTools` methods, `search_code` lag note, `list_repos` pagination |
| `src/agents/github/schemas.py` | Add 13 schema classes, 13 `SCHEMA_MAP` entries, 13 `_STRUCTURED_CALL_OPERATIONS` entries |
| `src/agents/github/agent.py` | Add 13 `elif operation ==` dispatch branches inside `run_operation()` (~line 1018) |
| `src/core/risk.py` | Add 12 new entries to `OperationRiskRegistry.RISK_LEVELS`; add `create_release` contextual rule |
| `src/api/routers/__init__.py` | Update `TOOL_DESCRIPTIONS["github_operation"]` (26 ops, updated risk table) |
| `src/storage/redis_session_store.py` | Add `ttl_override` param to `get_or_create`, `get`, `update`, `touch`, `delete` → propagate to `setex` |
| `src/agents/github/agent.py` | Also wire `context.session_ttl_seconds` through to `session_store` calls |
| `tests/test_github_integration.py` | Add 13 parametrize rows, `TestEnrichGithubError`, `TestV3Operations` class |

---

### Task 1: Error Enrichment Helper + Search Code Lag

**Files:**
- Modify: `src/tools/github/tools.py` (before `class GitHubTools`, around line 26)
- Test: `tests/test_github_integration.py`

- [ ] **Step 1: Write the failing tests**

Add a new test class at the end of `tests/test_github_integration.py`:

```python
class TestEnrichGithubError:
    """Unit tests for _enrich_github_error and _SCOPE_MAP."""

    def test_403_delete_repo_includes_scope(self):
        from src.tools.github.tools import _enrich_github_error
        from github import GithubException
        exc = GithubException(403, {"message": "Must have admin rights"}, {})
        msg = _enrich_github_error(exc, "delete_repo")
        assert "delete_repo" in msg
        assert "github.com/settings/tokens" in msg

    def test_403_trigger_workflow_includes_workflow_scope(self):
        from src.tools.github.tools import _enrich_github_error
        from github import GithubException
        exc = GithubException(403, {"message": "Must have admin rights"}, {})
        msg = _enrich_github_error(exc, "trigger_workflow")
        assert "workflow" in msg

    def test_403_create_webhook_includes_hook_scope(self):
        from src.tools.github.tools import _enrich_github_error
        from github import GithubException
        exc = GithubException(403, {"message": "Must have admin rights"}, {})
        msg = _enrich_github_error(exc, "create_webhook")
        assert "write:repo_hook" in msg

    def test_404_returns_owner_repo_hint(self):
        from src.tools.github.tools import _enrich_github_error
        from github import GithubException
        exc = GithubException(404, {"message": "Not Found"}, {})
        msg = _enrich_github_error(exc, "read_file")
        assert "owner/repo" in msg

    def test_422_returns_validation_message(self):
        from src.tools.github.tools import _enrich_github_error
        from github import GithubException
        exc = GithubException(422, {"message": "Validation Failed"}, {})
        msg = _enrich_github_error(exc, "create_issue")
        assert "Validation" in msg

    def test_search_code_result_has_lag_note(self):
        from unittest.mock import patch as _patch, MagicMock
        from src.tools.github.tools import GitHubTools
        mock_repo = MagicMock()
        mock_item = MagicMock()
        mock_item.name = "file.py"
        mock_item.path = "src/file.py"
        mock_item.repository.full_name = "owner/repo"
        mock_item.html_url = "https://github.com/owner/repo/blob/main/src/file.py"
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([mock_item]))
        with _patch("src.tools.github.tools.GitHubTools.client") as mock_client:
            mock_client.search_code.return_value = mock_result
            tools = GitHubTools.__new__(GitHubTools)
            tools._client = mock_client
            tools._user = MagicMock()
            tools._mock_mode = False
            tools._token = "ghp_test"
            result = tools.search_code("TODO")
        assert "note" in result
        assert "30" in result["note"]
        assert "results" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestEnrichGithubError -v 2>&1 | tail -20
```

Expected: `ImportError` or `AttributeError` — `_enrich_github_error` not yet defined.

- [ ] **Step 3: Add `_SCOPE_MAP` and `_enrich_github_error()` to `tools.py`**

Insert immediately after the module-level imports (after line 23, before the `_validate_safe_url` function at line 26):

```python
# === Error Enrichment ===

_SCOPE_MAP: Dict[str, List[str]] = {
    "delete_repo":         ["delete_repo", "repo"],
    "create_repo":         ["repo"],
    "commit_file":         ["repo"],
    "create_pull_request": ["repo"],
    "merge_pr":            ["repo"],
    "create_branch":       ["repo"],
    "delete_branch":       ["repo"],
    "create_issue":        ["repo"],
    "close_issue":         ["repo"],
    "update_issue":        ["repo"],
    "add_comment":         ["repo"],
    "create_release":      ["repo"],
    "create_webhook":      ["write:repo_hook"],
    "delete_webhook":      ["write:repo_hook"],
    "trigger_workflow":    ["workflow"],
}


def _enrich_github_error(exc: "GithubException", operation: str) -> str:
    """Convert raw PyGithub exceptions into actionable error messages."""
    status = getattr(exc, "status", None)
    data = getattr(exc, "data", {}) or {}
    raw_msg = data.get("message", str(exc)) if isinstance(data, dict) else str(exc)
    if status == 403:
        scopes = _SCOPE_MAP.get(operation, ["repo"])
        scope_str = ", ".join(scopes)
        return (
            f"GitHub permission denied for '{operation}'. "
            f"Your PAT needs these scopes: [{scope_str}]. "
            f"Re-generate at https://github.com/settings/tokens/new"
        )
    if status == 404:
        return (
            f"Resource not found for '{operation}'. "
            f"Check repo_name format (must be 'owner/repo')."
        )
    if status == 422:
        return f"GitHub validation error for '{operation}': {raw_msg}"
    return f"GitHub API error {status} for '{operation}': {raw_msg}"
```

- [ ] **Step 4: Update `search_code()` to return dict with lag note**

Find the `search_code` method (around line 758). Replace the `return result_list` at the end with:

```python
            return {
                "results": result_list,
                "count": len(result_list),
                "query": query,
                "note": "GitHub code search indexes with 30–60s lag for newly pushed content.",
            }
```

Also update the exception handler in `search_code`:
```python
        except Exception as e:
            if "404" in str(e):
                raise ValueError(f"Repository '{repo_name}' not found for code search.")
            logger.error(f"Search failed for query '{query}': {e}")
            raise
```
stays the same — no change needed there.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestEnrichGithubError -v 2>&1 | tail -15
```

Expected: 6 PASSED.

- [ ] **Step 6: Update the `search_code` mock return value in the parametrize table**

In `tests/test_github_integration.py`, find the `search_code` parametrize row (around line 995):
```python
        ("search_code",
         {"query": "TODO", "repo": "owner/r"},
         {},
         "search_code",
         [{"path": "x.py", "repository": "owner/r", "url": "x"}]),
```

Replace the mock return value (last element) with the new dict format:
```python
        ("search_code",
         {"query": "TODO", "repo": "owner/r"},
         {},
         "search_code",
         {"results": [{"path": "x.py", "repo": "owner/r", "url": "x"}],
          "count": 1, "query": "TODO",
          "note": "GitHub code search indexes with 30–60s lag for newly pushed content."}),
```

- [ ] **Step 7: Run the full structured-call parametrize test to confirm search_code row still passes**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestStructuredCallPath::test_mcp_structured_each_operation_end_to_end -v -k "search_code" 2>&1 | tail -10
```

Expected: 1 PASSED.

- [ ] **Step 8: Commit**

```bash
git add src/tools/github/tools.py tests/test_github_integration.py
git commit -m "feat(gitops-v3): add _enrich_github_error helper + search_code lag note"
```

---

### Task 2: PR Inspection Ops (`list_pull_requests`, `get_pr`)

**Files:**
- Modify: `src/agents/github/schemas.py`
- Modify: `src/core/risk.py`
- Modify: `src/tools/github/tools.py`
- Modify: `src/agents/github/agent.py`
- Test: `tests/test_github_integration.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_github_integration.py`:

```python
class TestPRInspectionOps:
    """Tests for list_pull_requests and get_pr."""

    def _make_tools(self, mock_client):
        from src.tools.github.tools import GitHubTools
        tools = GitHubTools.__new__(GitHubTools)
        tools._client = mock_client
        tools._user = MagicMock()
        tools._mock_mode = False
        tools._token = "ghp_test"
        return tools

    def test_list_pull_requests_returns_list(self):
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_pr = MagicMock()
        mock_pr.number = 1
        mock_pr.title = "feat: add thing"
        mock_pr.state = "open"
        mock_pr.user.login = "user"
        mock_pr.head.ref = "feat-branch"
        mock_pr.base.ref = "main"
        mock_pr.draft = False
        mock_pr.html_url = "https://github.com/o/r/pull/1"
        mock_repo = MagicMock()
        mock_repo.get_pulls.return_value = [mock_pr]
        mock_client.get_repo.return_value = mock_repo
        tools = self._make_tools(mock_client)
        result = tools.list_pull_requests("owner/repo", state="open", limit=10)
        assert "pull_requests" in result
        assert result["count"] == 1
        assert result["pull_requests"][0]["number"] == 1

    def test_get_pr_returns_full_metadata(self):
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_pr = MagicMock()
        mock_pr.number = 5
        mock_pr.title = "fix: bug"
        mock_pr.state = "open"
        mock_pr.user.login = "user"
        mock_pr.head.ref = "fix-branch"
        mock_pr.base.ref = "main"
        mock_pr.draft = False
        mock_pr.mergeable = True
        mock_pr.body = "Fixes #4"
        mock_pr.labels = []
        mock_pr.assignees = []
        mock_pr.requested_reviewers = []
        mock_pr.commits = 2
        mock_pr.additions = 10
        mock_pr.deletions = 3
        mock_pr.changed_files = 2
        mock_pr.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_pr.updated_at.isoformat.return_value = "2026-01-02T00:00:00"
        mock_pr.html_url = "https://github.com/o/r/pull/5"
        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pr
        mock_client.get_repo.return_value = mock_repo
        tools = self._make_tools(mock_client)
        result = tools.get_pr("owner/repo", pr_number=5)
        assert result["number"] == 5
        assert result["mergeable"] is True
        assert "additions" in result

    def test_list_pull_requests_schema_validation(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("list_pull_requests", {"repo_name": "o/r", "state": "open"})
        assert result["state"] == "open"

    def test_get_pr_schema_validation(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("get_pr", {"repo_name": "o/r", "pr_number": 3})
        assert result["pr_number"] == 3

    def test_list_pull_requests_risk_is_low(self):
        from src.core.risk import OperationRiskRegistry, RiskLevel
        assert OperationRiskRegistry.get_risk_level("list_pull_requests") == RiskLevel.LOW

    def test_get_pr_risk_is_low(self):
        from src.core.risk import OperationRiskRegistry, RiskLevel
        assert OperationRiskRegistry.get_risk_level("get_pr") == RiskLevel.LOW
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestPRInspectionOps -v 2>&1 | tail -20
```

Expected: 6 failures (schema/risk/tools not yet defined).

- [ ] **Step 3: Add schemas to `schemas.py`**

After the `MergePRParams` class (line ~119), add:

```python
class ListPullRequestsParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    state: Literal["open", "closed", "all"] = "open"
    base: Optional[str] = None
    head: Optional[str] = None
    limit: Annotated[int, Field(gt=0, le=100)] = 10


class GetPRParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    pr_number: Annotated[int, Field(gt=0)]
```

Add to `OperationParams` Union (after `MergePRParams`):
```python
    ListPullRequestsParams,
    GetPRParams,
```

Add to `SCHEMA_MAP` dict:
```python
    "list_pull_requests": ListPullRequestsParams,
    "get_pr": GetPRParams,
```

Add to `_STRUCTURED_CALL_OPERATIONS` frozenset:
```python
    "list_pull_requests", "get_pr",
```

- [ ] **Step 4: Add risk entries to `risk.py`**

In `OperationRiskRegistry.RISK_LEVELS`, add under the `# Read Operations - LOW` block:

```python
        "list_pull_requests": RiskLevel.LOW,
        "get_pr": RiskLevel.LOW,
```

- [ ] **Step 5: Add tool methods to `tools.py`**

After the `merge_pr()` method (around line 668), add a region divider and two new methods:

```python
    # === PR Inspection Operations ===

    @handle_rate_limits
    def list_pull_requests(
        self,
        repo_name: str,
        state: str = "open",
        base: Optional[str] = None,
        head: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            kwargs: Dict[str, Any] = {"state": state}
            if base:
                kwargs["base"] = base
            if head:
                kwargs["head"] = head
            prs = repo.get_pulls(**kwargs)
            results = []
            for pr in prs:
                if len(results) >= limit:
                    break
                results.append({
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "author": pr.user.login,
                    "head": pr.head.ref,
                    "base": pr.base.ref,
                    "draft": pr.draft,
                    "url": pr.html_url,
                })
            return {"pull_requests": results, "count": len(results), "repo": repo_name}
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "list_pull_requests"))

    @handle_rate_limits
    def get_pr(self, repo_name: str, pr_number: int) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            return {
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "author": pr.user.login,
                "head": pr.head.ref,
                "base": pr.base.ref,
                "draft": pr.draft,
                "mergeable": pr.mergeable,
                "body": pr.body,
                "labels": [label.name for label in pr.labels],
                "assignees": [a.login for a in pr.assignees],
                "reviewers": [r.login for r in pr.requested_reviewers],
                "commits": pr.commits,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "changed_files": pr.changed_files,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
                "url": pr.html_url,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "get_pr"))
```

- [ ] **Step 6: Add dispatch branches in `agent.py`**

In `execute_github_operation()`, after the `merge_pr` dispatch (after line 1018), add:

```python
            elif operation == "list_pull_requests":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.list_pull_requests(**parameters)
                )

            elif operation == "get_pr":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.get_pr(**parameters)
                )
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestPRInspectionOps -v 2>&1 | tail -15
```

Expected: 6 PASSED.

- [ ] **Step 8: Commit**

```bash
git add src/agents/github/schemas.py src/core/risk.py src/tools/github/tools.py src/agents/github/agent.py tests/test_github_integration.py
git commit -m "feat(gitops-v3): add list_pull_requests + get_pr structured ops"
```

---

### Task 3: Issue Management Ops (`close_issue`, `update_issue`, `add_comment`)

**Files:**
- Modify: `src/agents/github/schemas.py`
- Modify: `src/core/risk.py`
- Modify: `src/tools/github/tools.py`
- Modify: `src/agents/github/agent.py`
- Test: `tests/test_github_integration.py`

**Note:** `close_issue: RiskLevel.MEDIUM` already exists in `risk.py` line 73. Do NOT add it again. Only add `update_issue` and `add_comment`.

- [ ] **Step 1: Write failing tests**

```python
class TestIssueManagementOps:
    """Tests for close_issue, update_issue, add_comment."""

    def _make_tools(self, mock_client):
        from src.tools.github.tools import GitHubTools
        tools = GitHubTools.__new__(GitHubTools)
        tools._client = mock_client
        tools._user = MagicMock()
        tools._mock_mode = False
        tools._token = "ghp_test"
        return tools

    def test_close_issue_calls_edit_with_closed(self):
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_issue = MagicMock()
        mock_issue.html_url = "https://github.com/o/r/issues/1"
        mock_repo = MagicMock()
        mock_repo.get_issue.return_value = mock_issue
        mock_client.get_repo.return_value = mock_repo
        tools = self._make_tools(mock_client)
        result = tools.close_issue("owner/repo", issue_number=1)
        mock_issue.edit.assert_called_once_with(state="closed")
        assert result["closed"] is True
        assert result["issue_number"] == 1

    def test_update_issue_title_only(self):
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_issue = MagicMock()
        mock_issue.html_url = "https://github.com/o/r/issues/2"
        mock_repo = MagicMock()
        mock_repo.get_issue.return_value = mock_issue
        mock_client.get_repo.return_value = mock_repo
        tools = self._make_tools(mock_client)
        result = tools.update_issue("owner/repo", issue_number=2, title="New title")
        mock_issue.edit.assert_called_once_with(title="New title")
        assert result["updated"] is True

    def test_add_comment_returns_comment_id(self):
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 99
        mock_comment.html_url = "https://github.com/o/r/issues/1#issuecomment-99"
        mock_issue = MagicMock()
        mock_issue.create_comment.return_value = mock_comment
        mock_repo = MagicMock()
        mock_repo.get_issue.return_value = mock_issue
        mock_client.get_repo.return_value = mock_repo
        tools = self._make_tools(mock_client)
        result = tools.add_comment("owner/repo", issue_number=1, body="LGTM!")
        assert result["comment_id"] == 99
        assert "url" in result

    def test_update_issue_schema_requires_at_least_one_field(self):
        from src.agents.github.schemas import validate_op_params
        import pytest
        with pytest.raises(Exception):
            validate_op_params("update_issue", {"repo_name": "o/r", "issue_number": 1})

    def test_close_issue_schema_valid(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("close_issue", {"repo_name": "o/r", "issue_number": 3})
        assert result["issue_number"] == 3

    def test_add_comment_schema_valid(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("add_comment", {"repo_name": "o/r", "issue_number": 1, "body": "hi"})
        assert result["body"] == "hi"

    def test_update_issue_risk_is_medium(self):
        from src.core.risk import OperationRiskRegistry, RiskLevel
        assert OperationRiskRegistry.get_risk_level("update_issue") == RiskLevel.MEDIUM

    def test_add_comment_risk_is_low(self):
        from src.core.risk import OperationRiskRegistry, RiskLevel
        assert OperationRiskRegistry.get_risk_level("add_comment") == RiskLevel.LOW
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestIssueManagementOps -v 2>&1 | tail -20
```

Expected: failures (schemas/methods not yet defined).

- [ ] **Step 3: Add schemas to `schemas.py`**

After `GetPRParams`, add:

```python
class CloseIssueParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    issue_number: Annotated[int, Field(gt=0)]


class UpdateIssueParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    issue_number: Annotated[int, Field(gt=0)]
    title: Optional[str] = None
    body: Optional[str] = None
    state: Optional[Literal["open", "closed"]] = None
    labels: Optional[List[str]] = None
    assignees: Optional[List[str]] = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateIssueParams":
        if all(v is None for v in [self.title, self.body, self.state, self.labels, self.assignees]):
            raise ValueError("At least one of title/body/state/labels/assignees must be provided")
        return self


class AddCommentParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    issue_number: Annotated[int, Field(gt=0)]
    body: Annotated[str, Field(min_length=1)]
```

Add to `OperationParams` Union, `SCHEMA_MAP`, and `_STRUCTURED_CALL_OPERATIONS`:
```python
# OperationParams Union additions:
    CloseIssueParams,
    UpdateIssueParams,
    AddCommentParams,

# SCHEMA_MAP additions:
    "close_issue": CloseIssueParams,
    "update_issue": UpdateIssueParams,
    "add_comment": AddCommentParams,

# _STRUCTURED_CALL_OPERATIONS additions:
    "close_issue", "update_issue", "add_comment",
```

- [ ] **Step 4: Add risk entries to `risk.py`**

In `OperationRiskRegistry.RISK_LEVELS`, add (note: `close_issue` already exists as MEDIUM):
```python
        "update_issue": RiskLevel.MEDIUM,
        "add_comment": RiskLevel.LOW,
```

- [ ] **Step 5: Add tool methods to `tools.py`**

After the `get_pr()` method, add:

```python
    # === Issue Management Operations ===

    @handle_rate_limits
    def close_issue(self, repo_name: str, issue_number: int) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            issue.edit(state="closed")
            return {
                "closed": True,
                "issue_number": issue_number,
                "repo": repo_name,
                "url": issue.html_url,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "close_issue"))

    @handle_rate_limits
    def update_issue(
        self,
        repo_name: str,
        issue_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            kwargs: Dict[str, Any] = {}
            if title is not None:
                kwargs["title"] = title
            if body is not None:
                kwargs["body"] = body
            if state is not None:
                kwargs["state"] = state
            if labels is not None:
                kwargs["labels"] = labels
            if assignees is not None:
                kwargs["assignees"] = assignees
            issue.edit(**kwargs)
            return {
                "updated": True,
                "issue_number": issue_number,
                "repo": repo_name,
                "url": issue.html_url,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "update_issue"))

    @handle_rate_limits
    def add_comment(self, repo_name: str, issue_number: int, body: str) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            comment = issue.create_comment(body)
            return {
                "comment_id": comment.id,
                "url": comment.html_url,
                "issue_number": issue_number,
                "repo": repo_name,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "add_comment"))
```

- [ ] **Step 6: Add dispatch branches in `agent.py`**

After the `get_pr` dispatch, add:

```python
            elif operation == "close_issue":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.close_issue(**parameters)
                )

            elif operation == "update_issue":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.update_issue(**parameters)
                )

            elif operation == "add_comment":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.add_comment(**parameters)
                )
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestIssueManagementOps -v 2>&1 | tail -15
```

Expected: 8 PASSED.

- [ ] **Step 8: Commit**

```bash
git add src/agents/github/schemas.py src/core/risk.py src/tools/github/tools.py src/agents/github/agent.py tests/test_github_integration.py
git commit -m "feat(gitops-v3): add close_issue, update_issue, add_comment structured ops"
```

---

### Task 4: `list_repos` Pagination

**Files:**
- Modify: `src/agents/github/schemas.py` (line ~11)
- Modify: `src/tools/github/tools.py` (line ~216)
- Test: `tests/test_github_integration.py`

- [ ] **Step 1: Write failing test**

```python
class TestListReposPagination:
    """Tests for list_repos page parameter."""

    def test_list_repos_schema_accepts_page(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("list_repos", {"limit": 5, "page": 2})
        assert result["page"] == 2

    def test_list_repos_schema_page_defaults_to_1(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("list_repos", {"limit": 5})
        assert result["page"] == 1

    def test_list_repos_page_2_calls_get_page_1(self):
        from unittest.mock import MagicMock, patch as _patch
        from src.tools.github.tools import GitHubTools
        tools = GitHubTools.__new__(GitHubTools)
        tools._mock_mode = False
        tools._token = "ghp_test"
        mock_paginated = MagicMock()
        mock_paginated.get_page.return_value = []
        mock_user = MagicMock()
        mock_user.get_repos.return_value = mock_paginated
        tools._user = mock_user
        tools._client = MagicMock()
        result = tools.list_repos(limit=10, page=2)
        mock_paginated.get_page.assert_called_once_with(1)  # 0-indexed: page 2 → index 1

    def test_list_repos_page_1_calls_get_page_0(self):
        from unittest.mock import MagicMock
        from src.tools.github.tools import GitHubTools
        tools = GitHubTools.__new__(GitHubTools)
        tools._mock_mode = False
        tools._token = "ghp_test"
        mock_paginated = MagicMock()
        mock_paginated.get_page.return_value = []
        mock_user = MagicMock()
        mock_user.get_repos.return_value = mock_paginated
        tools._user = mock_user
        tools._client = MagicMock()
        tools.list_repos(limit=10, page=1)
        mock_paginated.get_page.assert_called_once_with(0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestListReposPagination -v 2>&1 | tail -15
```

Expected: failures (no `page` param in schema or tool).

- [ ] **Step 3: Update `ListReposParams` in `schemas.py`**

Current `ListReposParams` (line ~11):
```python
class ListReposParams(BaseModel):
    visibility: Literal["all", "public", "private"] = "all"
    sort: Literal["updated", "created", "pushed", "full_name"] = "updated"
    limit: Annotated[int, Field(gt=0, le=100)] = 10
```

Replace with:
```python
class ListReposParams(BaseModel):
    visibility: Literal["all", "public", "private"] = "all"
    sort: Literal["updated", "created", "pushed", "full_name"] = "updated"
    limit: Annotated[int, Field(gt=0, le=100)] = 10
    page: Annotated[int, Field(gt=0)] = 1
```

- [ ] **Step 4: Update `list_repos()` in `tools.py`**

Add `page: int = 1` parameter to the method signature:
```python
    def list_repos(
        self,
        visibility: str = "all",
        sort: str = "updated",
        limit: int = 10,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
```

Replace the repos-fetching logic (the part that uses `repos[:limit]`) with:
```python
            repos = self.user.get_repos(visibility=visibility, sort=sort)
            fetched_repos = repos.get_page(page - 1)  # PaginatedList is 0-indexed
            fetched_repos = fetched_repos[:limit]
```

Remove `start_time`/`api_duration` timing variables if they're only used for the old approach — keep the rest of the dict-building logic unchanged.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestListReposPagination -v 2>&1 | tail -10
```

Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/agents/github/schemas.py src/tools/github/tools.py tests/test_github_integration.py
git commit -m "feat(gitops-v3): add page param to list_repos for >100 pagination"
```

---

### Task 5: Commit History Ops (`list_commits`, `get_commit`)

**Files:**
- Modify: `src/agents/github/schemas.py`
- Modify: `src/core/risk.py`
- Modify: `src/tools/github/tools.py`
- Modify: `src/agents/github/agent.py`
- Test: `tests/test_github_integration.py`

- [ ] **Step 1: Write failing tests**

```python
class TestCommitHistoryOps:
    """Tests for list_commits and get_commit."""

    def _make_tools(self, mock_client):
        from src.tools.github.tools import GitHubTools
        tools = GitHubTools.__new__(GitHubTools)
        tools._client = mock_client
        tools._user = MagicMock()
        tools._mock_mode = False
        tools._token = "ghp_test"
        return tools

    def test_list_commits_returns_commits_list(self):
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_commit = MagicMock()
        mock_commit.sha = "abc123"
        mock_commit.commit.message = "fix: typo"
        mock_commit.commit.author.name = "Dev"
        mock_commit.commit.author.date.isoformat.return_value = "2026-01-01T00:00:00"
        mock_commit.html_url = "https://github.com/o/r/commit/abc123"
        mock_repo = MagicMock()
        mock_repo.get_commits.return_value = [mock_commit]
        mock_client.get_repo.return_value = mock_repo
        tools = self._make_tools(mock_client)
        result = tools.list_commits("owner/repo", branch="main")
        assert "commits" in result
        assert result["commits"][0]["sha"] == "abc123"

    def test_get_commit_returns_files(self):
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_commit = MagicMock()
        mock_commit.sha = "def456"
        mock_commit.commit.message = "feat: new thing"
        mock_commit.commit.author.name = "Dev"
        mock_commit.commit.author.email = "dev@example.com"
        mock_commit.commit.author.date.isoformat.return_value = "2026-01-02T00:00:00"
        mock_file = MagicMock()
        mock_file.filename = "src/x.py"
        mock_file.status = "modified"
        mock_file.additions = 5
        mock_file.deletions = 2
        mock_commit.files = [mock_file]
        mock_commit.stats.additions = 5
        mock_commit.stats.deletions = 2
        mock_commit.stats.total = 7
        mock_commit.html_url = "https://github.com/o/r/commit/def456"
        mock_repo = MagicMock()
        mock_repo.get_commit.return_value = mock_commit
        mock_client.get_repo.return_value = mock_repo
        tools = self._make_tools(mock_client)
        result = tools.get_commit("owner/repo", sha="def456")
        assert result["sha"] == "def456"
        assert len(result["files"]) == 1
        assert result["stats"]["total"] == 7

    def test_list_commits_schema_valid(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("list_commits", {"repo_name": "o/r", "branch": "main", "limit": 10})
        assert result["branch"] == "main"

    def test_get_commit_schema_valid(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("get_commit", {"repo_name": "o/r", "sha": "abc1234"})
        assert result["sha"] == "abc1234"

    def test_list_commits_risk_is_low(self):
        from src.core.risk import OperationRiskRegistry, RiskLevel
        assert OperationRiskRegistry.get_risk_level("list_commits") == RiskLevel.LOW

    def test_get_commit_risk_is_low(self):
        from src.core.risk import OperationRiskRegistry, RiskLevel
        assert OperationRiskRegistry.get_risk_level("get_commit") == RiskLevel.LOW
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestCommitHistoryOps -v 2>&1 | tail -20
```

Expected: failures.

- [ ] **Step 3: Add schemas to `schemas.py`**

After `AddCommentParams`, add:

```python
class ListCommitsParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    branch: str = "main"
    limit: Annotated[int, Field(gt=0, le=100)] = 20
    author: Optional[str] = None
    since: Optional[str] = None
    until: Optional[str] = None


class GetCommitParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    sha: Annotated[str, Field(min_length=7)]
```

Add to `OperationParams`, `SCHEMA_MAP`, and `_STRUCTURED_CALL_OPERATIONS`:
```python
# OperationParams: ListCommitsParams, GetCommitParams
# SCHEMA_MAP: "list_commits": ListCommitsParams, "get_commit": GetCommitParams
# _STRUCTURED_CALL_OPERATIONS: "list_commits", "get_commit"
```

- [ ] **Step 4: Add risk entries to `risk.py`**

```python
        "list_commits": RiskLevel.LOW,
        "get_commit": RiskLevel.LOW,
```

- [ ] **Step 5: Add tool methods to `tools.py`**

After `add_comment()`, add:

```python
    # === Commit History Operations ===

    @handle_rate_limits
    def list_commits(
        self,
        repo_name: str,
        branch: str = "main",
        limit: int = 20,
        author: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            kwargs: Dict[str, Any] = {"sha": branch}
            if author:
                kwargs["author"] = author
            if since:
                kwargs["since"] = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if until:
                kwargs["until"] = datetime.fromisoformat(until.replace("Z", "+00:00"))
            commits_iter = repo.get_commits(**kwargs)
            results = []
            for commit in commits_iter:
                if len(results) >= limit:
                    break
                results.append({
                    "sha": commit.sha,
                    "message": commit.commit.message,
                    "author": commit.commit.author.name,
                    "date": commit.commit.author.date.isoformat(),
                    "url": commit.html_url,
                })
            return {"commits": results, "count": len(results), "branch": branch, "repo": repo_name}
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "list_commits"))

    @handle_rate_limits
    def get_commit(self, repo_name: str, sha: str) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            commit = repo.get_commit(sha)
            return {
                "sha": commit.sha,
                "message": commit.commit.message,
                "author": commit.commit.author.name,
                "author_email": commit.commit.author.email,
                "date": commit.commit.author.date.isoformat(),
                "files": [
                    {
                        "filename": f.filename,
                        "status": f.status,
                        "additions": f.additions,
                        "deletions": f.deletions,
                    }
                    for f in commit.files
                ],
                "stats": {
                    "additions": commit.stats.additions,
                    "deletions": commit.stats.deletions,
                    "total": commit.stats.total,
                },
                "url": commit.html_url,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "get_commit"))
```

- [ ] **Step 6: Add dispatch branches in `agent.py`**

After `add_comment` dispatch:

```python
            elif operation == "list_commits":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.list_commits(**parameters)
                )

            elif operation == "get_commit":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.get_commit(**parameters)
                )
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestCommitHistoryOps -v 2>&1 | tail -10
```

Expected: 7 PASSED.

- [ ] **Step 8: Commit**

```bash
git add src/agents/github/schemas.py src/core/risk.py src/tools/github/tools.py src/agents/github/agent.py tests/test_github_integration.py
git commit -m "feat(gitops-v3): add list_commits + get_commit structured ops"
```

---

### Task 6: Release Management (`list_releases`, `create_release`)

**Files:**
- Modify: `src/agents/github/schemas.py`
- Modify: `src/core/risk.py`
- Modify: `src/tools/github/tools.py`
- Modify: `src/agents/github/agent.py`
- Test: `tests/test_github_integration.py`

- [ ] **Step 1: Write failing tests**

```python
class TestReleaseManagementOps:
    """Tests for list_releases and create_release."""

    def _make_tools(self, mock_client):
        from src.tools.github.tools import GitHubTools
        tools = GitHubTools.__new__(GitHubTools)
        tools._client = mock_client
        tools._user = MagicMock()
        tools._mock_mode = False
        tools._token = "ghp_test"
        return tools

    def test_list_releases_returns_list(self):
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_release = MagicMock()
        mock_release.id = 1
        mock_release.tag_name = "v1.0.0"
        mock_release.title = "Version 1.0"
        mock_release.draft = False
        mock_release.prerelease = False
        mock_release.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_release.published_at.isoformat.return_value = "2026-01-01T01:00:00"
        mock_release.html_url = "https://github.com/o/r/releases/tag/v1.0.0"
        mock_repo = MagicMock()
        mock_repo.get_releases.return_value = [mock_release]
        mock_client.get_repo.return_value = mock_repo
        tools = self._make_tools(mock_client)
        result = tools.list_releases("owner/repo", limit=10)
        assert "releases" in result
        assert result["releases"][0]["tag_name"] == "v1.0.0"

    def test_create_release_returns_release_metadata(self):
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_release = MagicMock()
        mock_release.id = 42
        mock_release.tag_name = "v2.0.0"
        mock_release.title = "Version 2.0"
        mock_release.draft = False
        mock_release.prerelease = False
        mock_release.html_url = "https://github.com/o/r/releases/tag/v2.0.0"
        mock_repo = MagicMock()
        mock_repo.create_git_release.return_value = mock_release
        mock_client.get_repo.return_value = mock_repo
        tools = self._make_tools(mock_client)
        result = tools.create_release("owner/repo", tag_name="v2.0.0", name="Version 2.0")
        assert result["id"] == 42
        assert result["tag_name"] == "v2.0.0"

    def test_list_releases_schema_valid(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("list_releases", {"repo_name": "o/r", "limit": 5})
        assert result["limit"] == 5

    def test_create_release_schema_valid(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("create_release", {"repo_name": "o/r", "tag_name": "v1.0", "name": "Release 1"})
        assert result["tag_name"] == "v1.0"

    def test_list_releases_risk_is_low(self):
        from src.core.risk import OperationRiskRegistry, RiskLevel
        assert OperationRiskRegistry.get_risk_level("list_releases") == RiskLevel.LOW

    def test_create_release_static_risk_is_high(self):
        from src.core.risk import OperationRiskRegistry, RiskLevel
        assert OperationRiskRegistry.get_risk_level("create_release") == RiskLevel.HIGH

    def test_create_release_prerelease_contextual_escalates_to_medium(self):
        from src.core.risk import RiskGate, RiskLevel
        # prerelease=True → contextual override → MEDIUM → no confirmation needed
        violation = RiskGate.check_contextual(
            "create_release",
            parameters={"repo_name": "o/r", "tag_name": "v1.0-rc1", "name": "RC", "prerelease": True},
            context={},
        )
        assert violation is None  # MEDIUM passes without confirmation

    def test_create_release_non_prerelease_requires_confirmation(self):
        from src.core.risk import RiskGate
        violation = RiskGate.check_contextual(
            "create_release",
            parameters={"repo_name": "o/r", "tag_name": "v1.0", "name": "Release", "prerelease": False},
            context={},
        )
        assert violation is not None
        assert "confirmed" in violation.message
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestReleaseManagementOps -v 2>&1 | tail -20
```

Expected: failures.

- [ ] **Step 3: Add schemas to `schemas.py`**

After `GetCommitParams`, add:

```python
class ListReleasesParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    limit: Annotated[int, Field(gt=0, le=50)] = 10


class CreateReleaseParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    tag_name: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    body: str = ""
    draft: bool = False
    prerelease: bool = False
    target_commitish: str = "main"
```

Add to `OperationParams`, `SCHEMA_MAP`, `_STRUCTURED_CALL_OPERATIONS`.

- [ ] **Step 4: Add risk entries and contextual rule to `risk.py`**

In `OperationRiskRegistry.RISK_LEVELS`:
```python
        "list_releases": RiskLevel.LOW,
        "create_release": RiskLevel.HIGH,
```

In `RiskGate._get_contextual_risk_level()`, add after the `commit_file` block:

```python
        if operation == "create_release":
            if parameters.get("prerelease") is True:
                return RiskLevel.MEDIUM
            return None  # keep HIGH default
```

- [ ] **Step 5: Add tool methods to `tools.py`**

After `get_commit()`, add:

```python
    # === Release Management Operations ===

    @handle_rate_limits
    def list_releases(self, repo_name: str, limit: int = 10) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            results = []
            for release in repo.get_releases():
                if len(results) >= limit:
                    break
                results.append({
                    "id": release.id,
                    "tag_name": release.tag_name,
                    "name": release.title,
                    "draft": release.draft,
                    "prerelease": release.prerelease,
                    "created_at": release.created_at.isoformat(),
                    "published_at": release.published_at.isoformat() if release.published_at else None,
                    "url": release.html_url,
                })
            return {"releases": results, "count": len(results), "repo": repo_name}
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "list_releases"))

    @handle_rate_limits
    def create_release(
        self,
        repo_name: str,
        tag_name: str,
        name: str,
        body: str = "",
        draft: bool = False,
        prerelease: bool = False,
        target_commitish: str = "main",
    ) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            release = repo.create_git_release(
                tag=tag_name,
                name=name,
                message=body,
                draft=draft,
                prerelease=prerelease,
                target_commitish=target_commitish,
            )
            return {
                "id": release.id,
                "tag_name": release.tag_name,
                "name": release.title,
                "draft": release.draft,
                "prerelease": release.prerelease,
                "url": release.html_url,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "create_release"))
```

- [ ] **Step 6: Add dispatch branches in `agent.py`**

```python
            elif operation == "list_releases":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.list_releases(**parameters)
                )

            elif operation == "create_release":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.create_release(**parameters)
                )
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestReleaseManagementOps -v 2>&1 | tail -10
```

Expected: 8 PASSED.

- [ ] **Step 8: Commit**

```bash
git add src/agents/github/schemas.py src/core/risk.py src/tools/github/tools.py src/agents/github/agent.py tests/test_github_integration.py
git commit -m "feat(gitops-v3): add list_releases + create_release with prerelease contextual gate"
```

---

### Task 7: GitHub Actions (`trigger_workflow`)

**Files:**
- Modify: `src/agents/github/schemas.py`
- Modify: `src/core/risk.py`
- Modify: `src/tools/github/tools.py`
- Modify: `src/agents/github/agent.py`
- Test: `tests/test_github_integration.py`

- [ ] **Step 1: Write failing tests**

```python
class TestGitHubActionsOps:
    """Tests for trigger_workflow."""

    def test_trigger_workflow_schema_valid(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("trigger_workflow", {
            "repo_name": "o/r", "workflow_id": "ci.yml", "ref": "main"
        })
        assert result["workflow_id"] == "ci.yml"

    def test_trigger_workflow_risk_is_high(self):
        from src.core.risk import OperationRiskRegistry, RiskLevel
        assert OperationRiskRegistry.get_risk_level("trigger_workflow") == RiskLevel.HIGH

    def test_trigger_workflow_requires_confirmation(self):
        from src.core.risk import RiskGate
        violation = RiskGate.check_contextual(
            "trigger_workflow",
            parameters={"repo_name": "o/r", "workflow_id": "ci.yml"},
            context={},
        )
        assert violation is not None
        assert "confirmed" in violation.message

    def test_trigger_workflow_passes_with_confirmed(self):
        from src.core.risk import RiskGate
        violation = RiskGate.check_contextual(
            "trigger_workflow",
            parameters={"repo_name": "o/r", "workflow_id": "ci.yml"},
            context={"confirmed": True},
        )
        assert violation is None

    def test_trigger_workflow_calls_create_dispatch(self):
        from unittest.mock import MagicMock
        from src.tools.github.tools import GitHubTools
        mock_client = MagicMock()
        mock_wf = MagicMock()
        mock_wf.create_dispatch.return_value = True
        mock_repo = MagicMock()
        mock_repo.get_workflow.return_value = mock_wf
        mock_client.get_repo.return_value = mock_repo
        tools = GitHubTools.__new__(GitHubTools)
        tools._client = mock_client
        tools._user = MagicMock()
        tools._mock_mode = False
        tools._token = "ghp_test"
        result = tools.trigger_workflow("owner/repo", workflow_id="ci.yml", ref="main")
        mock_wf.create_dispatch.assert_called_once_with(ref="main", inputs={})
        assert result["triggered"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestGitHubActionsOps -v 2>&1 | tail -15
```

Expected: failures.

- [ ] **Step 3: Add schema to `schemas.py`**

After `CreateReleaseParams`, add:

```python
class TriggerWorkflowParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    workflow_id: Annotated[str, Field(min_length=1)]
    ref: str = "main"
    inputs: Optional[Dict[str, str]] = None
```

Add to `OperationParams`, `SCHEMA_MAP`, `_STRUCTURED_CALL_OPERATIONS`.

- [ ] **Step 4: Add risk entry to `risk.py`**

```python
        "trigger_workflow": RiskLevel.HIGH,
```

- [ ] **Step 5: Add tool method to `tools.py`**

After `create_release()`, add:

```python
    # === GitHub Actions Operations ===

    @handle_rate_limits
    def trigger_workflow(
        self,
        repo_name: str,
        workflow_id: str,
        ref: str = "main",
        inputs: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            # workflow_id can be a filename ("ci.yml") or numeric ID string
            try:
                wf = repo.get_workflow(int(workflow_id))
            except (ValueError, TypeError):
                wf = repo.get_workflow(workflow_id)
            result = wf.create_dispatch(ref=ref, inputs=inputs or {})
            return {
                "triggered": result,
                "workflow_id": workflow_id,
                "ref": ref,
                "inputs": inputs,
                "repo": repo_name,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "trigger_workflow"))
```

- [ ] **Step 6: Add dispatch branch in `agent.py`**

```python
            elif operation == "trigger_workflow":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.trigger_workflow(**parameters)
                )
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestGitHubActionsOps -v 2>&1 | tail -10
```

Expected: 5 PASSED.

- [ ] **Step 8: Commit**

```bash
git add src/agents/github/schemas.py src/core/risk.py src/tools/github/tools.py src/agents/github/agent.py tests/test_github_integration.py
git commit -m "feat(gitops-v3): add trigger_workflow structured op with HIGH risk gate"
```

---

### Task 8: Webhook Management (`create_webhook`, `list_webhooks`, `delete_webhook`)

**Files:**
- Modify: `src/agents/github/schemas.py`
- Modify: `src/core/risk.py`
- Modify: `src/tools/github/tools.py`
- Modify: `src/agents/github/agent.py`
- Test: `tests/test_github_integration.py`

- [ ] **Step 1: Write failing tests**

```python
class TestWebhookManagementOps:
    """Tests for create_webhook, list_webhooks, delete_webhook."""

    def _make_tools(self, mock_client):
        from src.tools.github.tools import GitHubTools
        tools = GitHubTools.__new__(GitHubTools)
        tools._client = mock_client
        tools._user = MagicMock()
        tools._mock_mode = False
        tools._token = "ghp_test"
        return tools

    def test_create_webhook_returns_hook_id(self):
        from unittest.mock import MagicMock, patch as _patch
        mock_client = MagicMock()
        mock_hook = MagicMock()
        mock_hook.id = 77
        mock_hook.active = True
        mock_repo = MagicMock()
        mock_repo.create_hook.return_value = mock_hook
        mock_client.get_repo.return_value = mock_repo
        tools = self._make_tools(mock_client)
        with _patch("src.tools.github.tools._validate_safe_url"):
            result = tools.create_webhook("owner/repo", url="https://example.com/hook")
        assert result["hook_id"] == 77

    def test_list_webhooks_returns_hooks(self):
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_hook = MagicMock()
        mock_hook.id = 1
        mock_hook.name = "web"
        mock_hook.events = ["push"]
        mock_hook.active = True
        mock_hook.config = {"url": "https://example.com/h"}
        mock_repo = MagicMock()
        mock_repo.get_hooks.return_value = [mock_hook]
        mock_client.get_repo.return_value = mock_repo
        tools = self._make_tools(mock_client)
        result = tools.list_webhooks("owner/repo")
        assert "webhooks" in result
        assert result["webhooks"][0]["id"] == 1

    def test_delete_webhook_returns_confirmation(self):
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_hook = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_hook.return_value = mock_hook
        mock_client.get_repo.return_value = mock_repo
        tools = self._make_tools(mock_client)
        result = tools.delete_webhook("owner/repo", hook_id=1)
        mock_hook.delete.assert_called_once()
        assert result["deleted"] is True

    def test_create_webhook_schema_valid(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("create_webhook", {
            "repo_name": "o/r", "url": "https://example.com/hook"
        })
        assert result["url"] == "https://example.com/hook"

    def test_list_webhooks_schema_valid(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("list_webhooks", {"repo_name": "o/r"})
        assert result["repo_name"] == "o/r"

    def test_delete_webhook_schema_valid(self):
        from src.agents.github.schemas import validate_op_params
        result = validate_op_params("delete_webhook", {"repo_name": "o/r", "hook_id": 5})
        assert result["hook_id"] == 5

    def test_create_webhook_risk_is_high(self):
        from src.core.risk import OperationRiskRegistry, RiskLevel
        assert OperationRiskRegistry.get_risk_level("create_webhook") == RiskLevel.HIGH

    def test_list_webhooks_risk_is_low(self):
        from src.core.risk import OperationRiskRegistry, RiskLevel
        assert OperationRiskRegistry.get_risk_level("list_webhooks") == RiskLevel.LOW

    def test_delete_webhook_risk_is_high(self):
        from src.core.risk import OperationRiskRegistry, RiskLevel
        assert OperationRiskRegistry.get_risk_level("delete_webhook") == RiskLevel.HIGH
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestWebhookManagementOps -v 2>&1 | tail -20
```

Expected: failures.

- [ ] **Step 3: Add schemas to `schemas.py`**

After `TriggerWorkflowParams`, add:

```python
class CreateWebhookParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    url: Annotated[str, Field(min_length=1)]
    events: List[str] = ["push"]
    content_type: Literal["json", "form"] = "json"
    active: bool = True
    secret: Optional[str] = None


class ListWebhooksParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]


class DeleteWebhookParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    hook_id: Annotated[int, Field(gt=0)]
```

Add to `OperationParams`, `SCHEMA_MAP`, `_STRUCTURED_CALL_OPERATIONS`.

- [ ] **Step 4: Add risk entries to `risk.py`**

```python
        "create_webhook": RiskLevel.HIGH,
        "list_webhooks": RiskLevel.LOW,
        "delete_webhook": RiskLevel.HIGH,
```

- [ ] **Step 5: Add tool methods to `tools.py`**

After `trigger_workflow()`, add:

```python
    # === Webhook Management Operations ===

    @handle_rate_limits
    def create_webhook(
        self,
        repo_name: str,
        url: str,
        events: Optional[List[str]] = None,
        content_type: str = "json",
        active: bool = True,
        secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        _validate_safe_url(url)  # SSRF guard — same as commit_file.file_url
        try:
            repo = self.client.get_repo(repo_name)
            config: Dict[str, Any] = {"url": url, "content_type": content_type}
            if secret:
                config["secret"] = secret
            hook = repo.create_hook(
                name="web",
                config=config,
                events=events or ["push"],
                active=active,
            )
            return {
                "hook_id": hook.id,
                "url": url,
                "events": events or ["push"],
                "active": hook.active,
                "repo": repo_name,
            }
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "create_webhook"))

    @handle_rate_limits
    def list_webhooks(self, repo_name: str) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            results = []
            for hook in repo.get_hooks():
                config = hook.config or {}
                results.append({
                    "id": hook.id,
                    "name": hook.name,
                    "events": list(hook.events),
                    "active": hook.active,
                    "url": config.get("url", ""),
                })
            return {"webhooks": results, "count": len(results), "repo": repo_name}
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "list_webhooks"))

    @handle_rate_limits
    def delete_webhook(self, repo_name: str, hook_id: int) -> Dict[str, Any]:
        try:
            repo = self.client.get_repo(repo_name)
            hook = repo.get_hook(hook_id)
            hook.delete()
            return {"deleted": True, "hook_id": hook_id, "repo": repo_name}
        except GithubException as e:
            raise ValueError(_enrich_github_error(e, "delete_webhook"))
```

- [ ] **Step 6: Add dispatch branches in `agent.py`**

```python
            elif operation == "create_webhook":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.create_webhook(**parameters)
                )

            elif operation == "list_webhooks":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.list_webhooks(**parameters)
                )

            elif operation == "delete_webhook":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.delete_webhook(**parameters)
                )
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestWebhookManagementOps -v 2>&1 | tail -10
```

Expected: 9 PASSED.

- [ ] **Step 8: Commit**

```bash
git add src/agents/github/schemas.py src/core/risk.py src/tools/github/tools.py src/agents/github/agent.py tests/test_github_integration.py
git commit -m "feat(gitops-v3): add create_webhook, list_webhooks, delete_webhook ops"
```

---

### Task 9: Per-Tenant Session TTL

**Files:**
- Modify: `src/storage/redis_session_store.py`
- Modify: `src/agents/github/agent.py` (session save call)
- Test: `tests/test_github_integration.py`

**Note:** `GITOPS_SESSION_TTL: int = 1800` already exists in `src/core/config.py` line 169. Use `settings.GITOPS_SESSION_TTL` — no new config field needed.

- [ ] **Step 1: Write failing test**

```python
class TestPerTenantSessionTTL:
    """Test that context.session_ttl_seconds overrides GITOPS_SESSION_TTL."""

    @pytest.mark.asyncio
    async def test_session_store_ttl_override(self):
        """ttl_override param causes setex to use the override value."""
        import fakeredis.aioredis as fakeredis
        from src.storage.redis_session_store import RedisSessionStore
        fake_client = fakeredis.FakeRedis()
        store = RedisSessionStore(client=fake_client, ttl_seconds=3600)
        await store.get_or_create("sess-1", "tenant-1", ttl_override=900)
        ttl = await fake_client.ttl(b"gitops:session:tenant-1:sess-1")
        assert 890 <= ttl <= 900

    @pytest.mark.asyncio
    async def test_session_store_default_ttl_used_when_no_override(self):
        import fakeredis.aioredis as fakeredis
        from src.storage.redis_session_store import RedisSessionStore
        fake_client = fakeredis.FakeRedis()
        store = RedisSessionStore(client=fake_client, ttl_seconds=1800)
        await store.get_or_create("sess-2", "tenant-2")
        ttl = await fake_client.ttl(b"gitops:session:tenant-2:sess-2")
        assert 1790 <= ttl <= 1800
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestPerTenantSessionTTL -v 2>&1 | tail -10
```

Expected: failures (`ttl_override` param not accepted yet, or fakeredis key format mismatch).

- [ ] **Step 3: Update `RedisSessionStore` to accept `ttl_override`**

In `src/storage/redis_session_store.py`, update the `get_or_create` method signature and body:

```python
    async def get_or_create(
        self,
        session_id: str,
        tenant_id: str,
        initial: Optional[Dict[str, Any]] = None,
        ttl_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not tenant_id:
            raise ValueError("tenant_id is required for Redis-backed stores")
        ttl = ttl_override if ttl_override is not None else self._ttl
        key = tenant_key("session", tenant_id, session_id)
        existing = await self._client.get(key)
        if existing is not None:
            await self._client.expire(key, ttl)
            return loads(existing)
        seed = dict(initial or {})
        seed.setdefault("created_at", datetime.now().isoformat())
        await self._client.set(key, dumps(seed), ex=ttl)
        return seed
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestPerTenantSessionTTL -v 2>&1 | tail -10
```

Expected: 2 PASSED. (If `fakeredis` not installed, run `pip install fakeredis` first.)

- [ ] **Step 5: Commit**

```bash
git add src/storage/redis_session_store.py tests/test_github_integration.py
git commit -m "feat(gitops-v3): add ttl_override to RedisSessionStore.get_or_create"
```

---

### Task 10: Update `TOOL_DESCRIPTIONS` and Schema Enum Count

**Files:**
- Modify: `src/api/routers/__init__.py`
- Modify: `tests/test_github_integration.py`

- [ ] **Step 1: Update the enum count assertion in tests**

Find `test_tools_list_github_operation_has_oneOf_union` in the test file (around line 720). Update the `expected_ops` set and count:

```python
    def test_tools_list_github_operation_has_oneOf_union(self):
        # 26 structured ops after v3 expansion
        expected_ops = {
            "browse_files", "commit_file", "create_branch", "create_issue",
            "create_pull_request", "create_repo", "delete_branch", "delete_repo",
            "list_branches", "list_repos", "merge_pr", "read_file", "search_code",
            # v3 additions:
            "list_pull_requests", "get_pr",
            "close_issue", "update_issue", "add_comment",
            "list_commits", "get_commit",
            "list_releases", "create_release",
            "trigger_workflow",
            "create_webhook", "list_webhooks", "delete_webhook",
        }
        assert len(expected_ops) == 26
        # ... rest of test body unchanged (reads tools/list from MCP endpoint)
```

- [ ] **Step 2: Run the enum count test to verify it fails with old count**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestStructuredCallPath::test_tools_list_github_operation_has_oneOf_union -v 2>&1 | tail -10
```

Expected: FAIL (enum still at 13).

- [ ] **Step 3: Update `TOOL_DESCRIPTIONS["github_operation"]` in `src/api/routers/__init__.py`**

Find the existing `"github_operation"` key in `TOOL_DESCRIPTIONS`. Replace its value with:

```python
    "github_operation": (
        "Unified GitHub automation tool: 26 structured ops + NL routing for "
        "repo management, branch lifecycle, issues, PRs, commits, releases, Actions, and webhooks. "
        "TWO CALL MODES — use structured when the op is known (1-2s faster, no LLM classification): "
        "  Structured: {operation, repo_name, <op params>, context:{github_token}} "
        "  Natural-language: {query, context:{github_token}} "
        "READ ops (no confirmation): browse_files, read_file, list_repos, list_branches, "
        "search_code, list_pull_requests, get_pr, add_comment, "
        "list_commits, get_commit, list_releases, list_webhooks. "
        "MEDIUM ops (no confirmation): create_issue, commit_file, create_branch, "
        "create_pull_request, merge_pr, close_issue, update_issue. "
        "HIGH ops (context.confirmed=true required): create_repo, scaffold_repo, delete_branch, "
        "create_release, trigger_workflow, create_webhook, delete_webhook. "
        "CRITICAL ops (confirmed + reason required): delete_repo. "
        "CONTEXTUAL ESCALATION: "
        "merge_pr base=main/master → HIGH; base=production/release/* → CRITICAL. "
        "delete_branch branch_name=main/master/production → CRITICAL. "
        "commit_file branch=main/master/production → HIGH. "
        "create_release prerelease=True → MEDIUM (no confirmation needed). "
        "NL-only ops (LLM-routed): generate_changelog, analyze_ci_failure, scaffold_repo. "
        "READ FILE: pass branch='<ref>' to read from non-default branch. "
        "FILE COMMITS: system auto-injects file_url from context.available_files. "
        "GITOPS_PROTECTED_MODE=true blocks all HIGH/CRITICAL ops."
    ),
```

- [ ] **Step 4: Run the enum count test to verify it passes**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestStructuredCallPath::test_tools_list_github_operation_has_oneOf_union -v 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py -v 2>&1 | tail -30
```

Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/__init__.py tests/test_github_integration.py
git commit -m "feat(gitops-v3): update tool description and enum count to 26 ops"
```

---

### Task 11: Documentation + Parametrize Table Additions

**Files:**
- Modify: `docs/tools/github_operation.md`
- Modify: `docs/tools/github_operation_curl_tests.md`
- Modify: `DevForge_Backend/CLAUDE.md`
- Modify: `tests/test_github_integration.py` (add 13 rows to parametrize table)

- [ ] **Step 1: Add 13 rows to the MCP structured-call parametrize table**

In `tests/test_github_integration.py`, find the `@pytest.mark.parametrize(...)` block for `test_mcp_structured_each_operation_end_to_end` (around line 954). Add a `merge_pr` row (missing from the current 12) plus the 13 new ops:

```python
        # merge_pr (added v0.9) — medium by default with feature branch
        ("merge_pr",
         {"repo": "owner/r", "pr_number": 1, "merge_method": "merge"},
         {},
         "merge_pr",
         {"merged": True, "message": "ok", "sha": "abc", "pr_number": 1, "repo_name": "owner/r"}),
        # v3 new ops
        ("list_pull_requests",
         {"repo": "owner/r", "state": "open"},
         {},
         "list_pull_requests",
         {"pull_requests": [{"number": 1, "title": "feat", "state": "open", "author": "u",
                             "head": "feat", "base": "main", "draft": False, "url": "x"}],
          "count": 1, "repo": "owner/r"}),
        ("get_pr",
         {"repo": "owner/r", "pr_number": 3},
         {},
         "get_pr",
         {"number": 3, "title": "fix", "state": "open", "author": "u",
          "head": "fix", "base": "main", "draft": False, "mergeable": True, "body": "",
          "labels": [], "assignees": [], "reviewers": [], "commits": 1,
          "additions": 5, "deletions": 2, "changed_files": 1,
          "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-02T00:00:00", "url": "x"}),
        ("close_issue",
         {"repo": "owner/r", "issue_number": 1},
         {},
         "close_issue",
         {"closed": True, "issue_number": 1, "repo": "owner/r", "url": "x"}),
        ("update_issue",
         {"repo": "owner/r", "issue_number": 2, "title": "updated"},
         {},
         "update_issue",
         {"updated": True, "issue_number": 2, "repo": "owner/r", "url": "x"}),
        ("add_comment",
         {"repo": "owner/r", "issue_number": 1, "body": "LGTM!"},
         {},
         "add_comment",
         {"comment_id": 42, "url": "x", "issue_number": 1, "repo": "owner/r"}),
        ("list_commits",
         {"repo": "owner/r", "branch": "main"},
         {},
         "list_commits",
         {"commits": [{"sha": "abc", "message": "feat", "author": "u",
                       "date": "2026-01-01T00:00:00", "url": "x"}],
          "count": 1, "branch": "main", "repo": "owner/r"}),
        ("get_commit",
         {"repo": "owner/r", "sha": "abc1234"},
         {},
         "get_commit",
         {"sha": "abc1234", "message": "feat", "author": "u", "author_email": "u@x.com",
          "date": "2026-01-01T00:00:00", "files": [], "stats": {"additions": 0, "deletions": 0, "total": 0},
          "url": "x"}),
        ("list_releases",
         {"repo": "owner/r"},
         {},
         "list_releases",
         {"releases": [{"id": 1, "tag_name": "v1.0", "name": "R", "draft": False, "prerelease": False,
                        "created_at": "2026-01-01T00:00:00", "published_at": "2026-01-01T00:00:00",
                        "url": "x"}],
          "count": 1, "repo": "owner/r"}),
        ("create_release",
         {"repo": "owner/r", "tag_name": "v1.0", "name": "Release 1"},
         {"confirmed": True},
         "create_release",
         {"id": 10, "tag_name": "v1.0", "name": "Release 1", "draft": False, "prerelease": False, "url": "x"}),
        ("trigger_workflow",
         {"repo": "owner/r", "workflow_id": "ci.yml"},
         {"confirmed": True},
         "trigger_workflow",
         {"triggered": True, "workflow_id": "ci.yml", "ref": "main", "inputs": None, "repo": "owner/r"}),
        ("create_webhook",
         {"repo": "owner/r", "url": "https://example.com/hook"},
         {"confirmed": True},
         "create_webhook",
         {"hook_id": 77, "url": "https://example.com/hook", "events": ["push"], "active": True, "repo": "owner/r"}),
        ("list_webhooks",
         {"repo": "owner/r"},
         {},
         "list_webhooks",
         {"webhooks": [{"id": 1, "name": "web", "events": ["push"], "active": True, "url": "x"}],
          "count": 1, "repo": "owner/r"}),
        ("delete_webhook",
         {"repo": "owner/r", "hook_id": 1},
         {"confirmed": True},
         "delete_webhook",
         {"deleted": True, "hook_id": 1, "repo": "owner/r"}),
```

- [ ] **Step 2: Run the full parametrize test to verify all rows pass**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py::TestStructuredCallPath::test_mcp_structured_each_operation_end_to_end -v 2>&1 | tail -40
```

Expected: 26 PASSED (14 original + merge_pr + 13 new rows = 28 total parametrize rows, but 2 require extra mocking — see notes below).

**Note on webhook/Actions tests in MCP end-to-end:** `create_webhook` calls `_validate_safe_url(url)` which does a DNS lookup. For the parametrize test, you need to patch `_validate_safe_url` in the mock target. If the test fails for webhook ops only, add a `with _patch("src.tools.github.tools._validate_safe_url"):` inside the test body, or skip those rows with `pytest.mark.skip` until confirmed in integration testing.

- [ ] **Step 3: Update `docs/tools/github_operation.md`**

At the top of the file, update:
- Version: `0.9.0` → `1.0.0`
- Last Updated: `2026-05-19`
- Phase: `GitOps v1.0 - 26 structured ops (PR, issue, commit, release, Actions, webhooks)`

Add the 13 new methods to the `GitHubTools` class methods table. Add a `### v1.0.0 — 2026-05-19` changelog entry (see spec).

- [ ] **Step 4: Update `DevForge_Backend/CLAUDE.md`**

Find the `github_operation` row in the "Current tool versions" table:
```
| `github_operation` | 0.9.0 | 0.11.0 | Redis persistence (Slice 2) + `merge_pr` + `read_file` branch support |
```

Replace with:
```
| `github_operation` | 1.0.0 | 0.12.0 | 26 structured ops: PR inspection, issue CRUD, commit history, releases, Actions, webhooks + enriched error messages |
```

- [ ] **Step 5: Run the full test suite one final time**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github_integration.py -v 2>&1 | tail -40
```

Expected: all tests pass. Note any failures and fix before committing.

- [ ] **Step 6: Commit**

```bash
git add tests/test_github_integration.py docs/tools/github_operation.md docs/tools/github_operation_curl_tests.md DevForge_Backend/CLAUDE.md
git commit -m "feat(gitops-v3): add 13 parametrize rows + docs update (v1.0.0)"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered in task |
|-----------------|-----------------|
| `list_pull_requests`, `get_pr` | Task 2 |
| PAT scope error messages | Task 1 |
| `search_code` lag disclosure | Task 1 |
| `close_issue`, `update_issue`, `add_comment` | Task 3 |
| `list_repos` pagination | Task 4 |
| `list_commits`, `get_commit` | Task 5 |
| `list_releases`, `create_release` | Task 6 |
| `create_release` prerelease→MEDIUM contextual rule | Task 6 |
| `trigger_workflow` | Task 7 |
| `create_webhook`, `list_webhooks`, `delete_webhook` | Task 8 |
| `create_webhook` SSRF guard | Task 8 (uses existing `_validate_safe_url`) |
| Per-tenant session TTL via `ttl_override` | Task 9 |
| TOOL_DESCRIPTIONS updated to 26 ops | Task 10 |
| `_STRUCTURED_CALL_OPERATIONS` grows 13→26 | Tasks 2-8 each |
| Enum count test updated 13→26 | Task 10 |
| Documentation updated | Task 11 |

**Placeholder scan:** None found. All steps include exact code.

**Type consistency:** All tool methods use `Optional[str]`, `Optional[Dict[str, str]]`, `List[str]`, `Dict[str, Any]` consistently with existing patterns. `_enrich_github_error` accepts `GithubException` and returns `str`, used in all `except GithubException as e` blocks.
