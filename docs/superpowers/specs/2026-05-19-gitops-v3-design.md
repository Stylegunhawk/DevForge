# GitOps v3 — Market-Competitive Production Expansion Design

**Date:** 2026-05-19
**Author:** Sid / Claude Code
**Status:** Approved — ready for implementation plan
**Prior versions:** v0.9 (Redis persistence + merge_pr) — see `2026-05-16-gitops-redis-persistence-design.md`
**Target version:** `github_operation` 1.0.0

---

## Goal

Expand `github_operation` from 13 structured ops to 26 by addressing all P0/P1/P2 gaps identified in the post-v0.9 production-readiness review. Result: a tool competitive with GitHub CLI and Copilot workspace integrations — covering PR inspection, full issue CRUD, commit history, releases, CI/CD triggers, and webhook management — with backward-compatible structured-call mode for all new ops.

---

## Context

### What exists at v0.9

- **13 structured ops:** `browse_files`, `commit_file`, `create_branch`, `create_issue`, `create_pull_request`, `create_repo`, `delete_branch`, `delete_repo`, `list_branches`, `list_repos`, `merge_pr`, `read_file`, `search_code`
- **3 NL-only ops:** `scaffold_repo`, `generate_changelog`, `analyze_ci_failure`
- **Risk gate:** static table + contextual escalation for `merge_pr`, `delete_branch`, `commit_file`
- **Redis persistence:** `RedisAuditStore`, `RedisEscalationStore`, `RedisJobStore`, `RedisSessionStore`
- **In-memory fallback** when Redis unavailable (test environments)

### Gaps addressed in v3

| Priority | Gap | Resolution |
|----------|-----|-----------|
| P0 | `list_pull_requests` / `get_pr` missing | Add as structured ops |
| P0 | PAT scope errors return raw GitHub 403 | `_SCOPE_MAP` + `_enrich_github_error()` helper |
| P0 | `search_code` doesn't disclose indexing lag | Add `note` field to success response |
| P1 | `close_issue` / `update_issue` / `add_comment` missing | Add as structured ops |
| P1 | `list_repos` capped at 100 (no pagination) | Add `page` param to schema and PyGithub call |
| P2 | `get_commit` / `list_commits` missing | Add as structured ops |
| P2 | Release management missing | `create_release` + `list_releases` |
| P2 | GitHub Actions trigger missing | `trigger_workflow` |
| P2 | Webhook management missing | `create_webhook`, `list_webhooks`, `delete_webhook` |
| P2 | Session TTL hardcoded at 3600s | `GITOPS_SESSION_TTL_SECONDS` env var + per-request override |

---

## Architecture

### Approach: In-place expansion

All new methods added directly to the existing `GitHubTools` class in `tools.py`. No module splitting. `tools.py` grows from ~1000 to ~1600 lines, organized by `# === <Domain> Operations ===` region dividers. Matches every existing pattern, zero refactoring risk.

### File change summary

| File | Change |
|------|--------|
| `src/tools/github/tools.py` | +13 methods; +`_SCOPE_MAP` dict; +`_enrich_github_error()` helper; update `list_repos()` pagination |
| `src/agents/github/schemas.py` | +13 Pydantic schema classes; `_STRUCTURED_CALL_OPERATIONS` 13→26; `SCHEMA_MAP` +13 entries |
| `src/agents/github/agent.py` | +13 `elif operation ==` dispatch branches in `execute_github_operation()` |
| `src/core/risk.py` | +13 entries in `_STATIC_RISK_TABLE`; +2 contextual escalation rules |
| `src/core/config.py` | +`GITOPS_SESSION_TTL_SECONDS: int = Field(default=3600, gt=0)` |
| `src/storage/redis_session_store.py` | Use `settings.GITOPS_SESSION_TTL_SECONDS`; accept `ttl_override` from context |
| `src/api/routers/__init__.py` | Update `TOOL_DESCRIPTIONS["github_operation"]` to document 26 ops |
| `tests/test_github_integration.py` | +13 new op mock tests; +scope error tests; enum count 13→26 |
| `docs/tools/github_operation.md` | Bump to v1.0.0; add all new ops; changelog entry |
| `docs/tools/github_operation_curl_tests.md` | Add curl test sections for new ops (v13) |
| `DevForge_Backend/CLAUDE.md` | Update version row to `1.0.0` |

---

## New Operations

### P0: PR Inspection

#### `list_pull_requests`

**Schema:**
```python
class ListPullRequestsParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    state: Literal["open", "closed", "all"] = "open"
    base: Optional[str] = None    # filter by target branch
    head: Optional[str] = None    # filter by source branch (owner:branch format)
    limit: Annotated[int, Field(gt=0, le=100)] = 10
```

**Tool method:**
```python
def list_pull_requests(self, repo_name, state="open", base=None, head=None, limit=10):
    repo = self.client.get_repo(repo_name)
    kwargs = {"state": state}
    if base: kwargs["base"] = base
    if head: kwargs["head"] = head
    prs = repo.get_pulls(**kwargs)
    results = [{"number": pr.number, "title": pr.title, "state": pr.state,
                "author": pr.user.login, "head": pr.head.ref, "base": pr.base.ref,
                "draft": pr.draft, "url": pr.html_url} for pr in prs[:limit]]
    return {"pull_requests": results, "count": len(results), "repo": repo_name}
```

**Risk:** LOW

---

#### `get_pr`

**Schema:**
```python
class GetPRParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    pr_number: Annotated[int, Field(gt=0)]
```

**Tool method:** `repo.get_pull(pr_number)` — returns full PR metadata including mergeable, additions/deletions, changed_files, reviewers.

**Risk:** LOW

---

### P0: Error Enrichment

**`_SCOPE_MAP`** (module-level in `tools.py`):
```python
_SCOPE_MAP: Dict[str, List[str]] = {
    "delete_repo":        ["delete_repo", "repo"],
    "create_repo":        ["repo"],
    "commit_file":        ["repo"],
    "create_pull_request":["repo"],
    "merge_pr":           ["repo"],
    "create_branch":      ["repo"],
    "delete_branch":      ["repo"],
    "create_issue":       ["repo"],
    "close_issue":        ["repo"],
    "update_issue":       ["repo"],
    "add_comment":        ["repo"],
    "create_release":     ["repo"],
    "create_webhook":     ["write:repo_hook"],
    "delete_webhook":     ["write:repo_hook"],
    "trigger_workflow":   ["workflow"],
}
```

**`_enrich_github_error(exc, operation)`** (module-level function in `tools.py`):
- `exc.status == 403` → `"GitHub permission denied for '{op}'. Your PAT needs: [{scopes}]. Re-generate at https://github.com/settings/tokens/new"`
- `exc.status == 404` → `"Resource not found for '{op}'. Check repo_name format (must be 'owner/repo')."`
- `exc.status == 422` → `"GitHub validation error for '{op}': {exc.data['message']}"`
- else → `"GitHub API error {exc.status} for '{op}': {message}"`

All existing tool methods are updated to use `_enrich_github_error()` instead of `str(e)` (backfill).

---

### P0: Search Code Lag Disclosure

`search_code()` success response gains:
```python
"note": "GitHub code search indexes with 30–60s lag for newly pushed content."
```

---

### P1: Issue Management

#### `close_issue`

```python
class CloseIssueParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    issue_number: Annotated[int, Field(gt=0)]
```

Tool: `repo.get_issue(n).edit(state="closed")`. **Risk:** MEDIUM.

---

#### `update_issue`

```python
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
```

Tool: `repo.get_issue(n).edit(**kwargs)` — only passes non-None fields. **Risk:** MEDIUM.

---

#### `add_comment`

```python
class AddCommentParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    issue_number: Annotated[int, Field(gt=0)]  # works for both issues and PRs
    body: Annotated[str, Field(min_length=1)]
```

Tool: `repo.get_issue(n).create_comment(body)`. **Risk:** LOW (editable/deletable).

---

### P1: Pagination Fix for `list_repos`

`ListReposParams` gains:
```python
page: Annotated[int, Field(gt=0)] = 1  # 1-indexed page
```

`GitHubTools.list_repos()` uses `PaginatedList.get_page(page - 1)` instead of slicing. Default `page=1` is backward-compatible.

---

### P2: Commit History

#### `list_commits`

```python
class ListCommitsParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    branch: str = "main"
    limit: Annotated[int, Field(gt=0, le=100)] = 20
    author: Optional[str] = None
    since: Optional[str] = None   # ISO 8601
    until: Optional[str] = None   # ISO 8601
```

Tool: `repo.get_commits(sha=branch, ...)`. Returns sha, message, author, date, url per commit. **Risk:** LOW.

---

#### `get_commit`

```python
class GetCommitParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    sha: Annotated[str, Field(min_length=7)]
```

Tool: `repo.get_commit(sha)`. Returns full commit metadata + files changed + stats. **Risk:** LOW.

---

### P2: Release Management

#### `list_releases`

```python
class ListReleasesParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    limit: Annotated[int, Field(gt=0, le=50)] = 10
```

Tool: `repo.get_releases()[:limit]`. Returns id, tag_name, name, draft, prerelease, dates, url. **Risk:** LOW.

---

#### `create_release`

```python
class CreateReleaseParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    tag_name: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    body: str = ""
    draft: bool = False
    prerelease: bool = False
    target_commitish: str = "main"
```

Tool: `repo.create_git_release(tag, name, message, draft, prerelease, target_commitish)`.

**Risk:**
- Static: HIGH (publishes artifact, triggers release webhooks)
- Contextual: `prerelease=True` → MEDIUM (pre-releases are lower visibility, no `confirmed` required)

---

### P2: GitHub Actions

#### `trigger_workflow`

```python
class TriggerWorkflowParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    workflow_id: Annotated[str, Field(min_length=1)]  # "ci.yml" or numeric ID string
    ref: str = "main"
    inputs: Optional[Dict[str, str]] = None
```

Tool: `repo.get_workflow(workflow_id).create_dispatch(ref, inputs)`. Handles both filename and numeric ID.

**Risk:** HIGH (`confirmed=true` required — triggers CI/CD runs consuming Actions minutes).

---

### P2: Webhook Management

#### `create_webhook`

```python
class CreateWebhookParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    url: Annotated[str, Field(min_length=1)]
    events: List[str] = ["push"]
    content_type: Literal["json", "form"] = "json"
    active: bool = True
    secret: Optional[str] = None   # HMAC secret; never logged
```

`url` passes through `_validate_safe_url()` (existing SSRF guard, same as `commit_file.file_url`).

Tool: `repo.create_hook("web", config, events, active)`. **Risk:** HIGH.

---

#### `list_webhooks`

```python
class ListWebhooksParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
```

Tool: `repo.get_hooks()`. Returns id, name, events, active, url — webhook secrets excluded from response. **Risk:** LOW.

---

#### `delete_webhook`

```python
class DeleteWebhookParams(BaseModel):
    repo_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]
    hook_id: Annotated[int, Field(gt=0)]
```

Tool: `repo.get_hook(hook_id).delete()`. **Risk:** HIGH (`confirmed=true` required).

---

### P2: Per-Tenant Session TTL

**`src/core/config.py`:**
```python
GITOPS_SESSION_TTL_SECONDS: int = Field(default=3600, gt=0)
```

**`RedisSessionStore.save_session()`:**
```python
def save_session(self, tenant_id: str, session_data: dict, ttl_override: Optional[int] = None) -> None:
    ttl = ttl_override if ttl_override is not None else settings.GITOPS_SESSION_TTL_SECONDS
    self._client.setex(self._key(tenant_id), ttl, json.dumps(session_data))
```

**Agent wiring:** Extract `context.get("session_ttl_seconds")` in `agent.py` and pass as `ttl_override` when calling `session_store.save_session()`.

---

## Full Risk Gate Table (v3)

| Operation | Static | Contextual Escalation | confirmed required |
|-----------|--------|----------------------|-------------------|
| `browse_files`, `read_file`, `list_repos`, `list_branches`, `search_code` | LOW | — | No |
| `list_pull_requests`, `get_pr`, `add_comment` | LOW | — | No |
| `list_commits`, `get_commit`, `list_releases`, `list_webhooks` | LOW | — | No |
| `create_issue`, `commit_file`, `create_branch`, `create_pull_request` | MEDIUM | `commit_file` to main/master/prod → HIGH | No / Yes (contextual) |
| `close_issue`, `update_issue` | MEDIUM | — | No |
| `merge_pr` | MEDIUM | base=main/master → HIGH; base=prod/release/* → CRITICAL | No / Yes (contextual) |
| `create_release` | HIGH | `prerelease=True` → MEDIUM | Yes (unless prerelease) |
| `create_repo`, `scaffold_repo`, `delete_branch`, `trigger_workflow` | HIGH | `delete_branch` main/master/prod → CRITICAL | Yes |
| `create_webhook`, `delete_webhook` | HIGH | — | Yes |
| `delete_repo` | CRITICAL | — | Yes + reason |

---

## Data Flow (new structured call)

```
POST /mcp { operation: "list_pull_requests", repo_name: "owner/repo",
            state: "open", context: { github_token: "ghp_..." } }
→ GithubOperationArgs validates (ListPullRequestsParams schema)
→ risk_gate_check(): LOW → pass through, no confirmation gate
→ execute_github_operation(): elif operation == "list_pull_requests"
→ GitHubTools.list_pull_requests(repo_name, state, limit)
→ PyGithub repo.get_pulls(state="open")
→ { "pull_requests": [...], "count": N, "repo": "owner/repo" }
```

---

## Error Handling — Before / After

**Before (raw):**
```json
{"success": false, "error": "403 {\"message\": \"Must have admin rights to Repository.\"}"}
```

**After (enriched):**
```json
{
  "success": false,
  "error": "GitHub permission denied for 'delete_repo'. Your PAT needs these scopes: [delete_repo, repo]. Re-generate at https://github.com/settings/tokens/new"
}
```

---

## Testing Strategy

```python
# 1. Parametrized happy-path for all 13 new ops (mock PyGithub)
@pytest.mark.parametrize("operation,params", [
    ("list_pull_requests", {"repo_name": "o/r", "state": "open"}),
    ("get_pr",             {"repo_name": "o/r", "pr_number": 1}),
    ("close_issue",        {"repo_name": "o/r", "issue_number": 1}),
    ("update_issue",       {"repo_name": "o/r", "issue_number": 1, "title": "t"}),
    ("add_comment",        {"repo_name": "o/r", "issue_number": 1, "body": "hi"}),
    ("list_commits",       {"repo_name": "o/r"}),
    ("get_commit",         {"repo_name": "o/r", "sha": "abc1234"}),
    ("list_releases",      {"repo_name": "o/r"}),
    ("create_release",     {"repo_name": "o/r", "tag_name": "v1.0", "name": "R"}),
    ("trigger_workflow",   {"repo_name": "o/r", "workflow_id": "ci.yml"}),
    ("create_webhook",     {"repo_name": "o/r", "url": "https://example.com/h"}),
    ("list_webhooks",      {"repo_name": "o/r"}),
    ("delete_webhook",     {"repo_name": "o/r", "hook_id": 1}),
])

# 2. Scope error enrichment: mock GithubException(403) for each write op
#    assert response contains scope name + github.com/settings/tokens

# 3. tools/list enum count: update 13 → 26

# 4. Risk gate: create_release/trigger_workflow/create_webhook/delete_webhook
#    without confirmed=True → blocked with risk gate message

# 5. create_release prerelease=True → MEDIUM → no confirmation required

# 6. list_repos page=2 → get_page(1) called (not slicing)

# 7. context.session_ttl_seconds=1800 → RedisSessionStore saved with ex=1800

# 8. search_code result contains "note" with "30" in the string

# 9. update_issue with no fields → ValidationError (model_validator)
```

---

## Backward Compatibility

All changes are additive:
- New ops in `_STRUCTURED_CALL_OPERATIONS` — existing callers unaffected
- `list_repos` page=1 (default) — same result as before
- `GITOPS_SESSION_TTL_SECONDS=3600` default — preserves current behavior
- `_enrich_github_error()` changes error message text format but not `success: false` structure
- JSON Schema enum in `tools/list` expands 13→26 — MCP clients discover dynamically

---

## Changelog Entry

```
### v1.0.0 — 2026-05-19
- +13 new structured ops: list_pull_requests, get_pr, close_issue, update_issue,
  add_comment, list_commits, get_commit, list_releases, create_release,
  trigger_workflow, create_webhook, list_webhooks, delete_webhook
- list_repos: +page param for pagination beyond first 100
- _SCOPE_MAP + _enrich_github_error(): 403s now surface required PAT scopes + link
- search_code: indexing lag disclosure note added to success response
- GITOPS_SESSION_TTL_SECONDS env var + per-request context.session_ttl_seconds override
- create_release: prerelease=True contextual risk gate (MEDIUM, no confirmation)
- All 26 GitHubTools methods backfilled to use _enrich_github_error()
```
