# github_operation - Intelligent GitHub Automation Tool

**Tool Name:** `github_operation`
**Version:** 1.0.0
**Manifest Version:** 0.12.0
**Last Updated:** 2026-05-19
**Last Verified:** 2026-05-19 — aggressive live MCP verification (all 26 structured ops, 64/64 Python MCP tests), see `§Changelog` below and `docs/tools/github_operation_curl_tests.md`
**Phase:** GitOps v1.0 - 26 structured ops
**Status:** ✅ Production Ready (Hardened)

---

## Overview

The `github_operation` tool is an intelligent GitHub automation system that transforms natural language commands into sophisticated GitHub workflows. It uses a LangGraph state machine with intelligence enhancements for fuzzy repository discovery, AI-powered commit message generation, and multi-language error log parsing.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         API Gateway Layer                                │
│                    src/api/routers.py (gateway_endpoint)                │
└─────────────────────────────────────────────┬───────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        GitHub Agent (LangGraph)                          │
│                     src/agents/github/agent.py                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  StateGraph Workflow:                                             │  │
│  │    parse_github_request → enhance_with_intelligence → validate → policy_gate → risk_gate → execute    │
│  │              ↘               ↙                      ↘            │  │
│  │               handle_error ←───────────────────────────          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Components:                                                            │
│  • GitHubState dataclass (query, operation, parameters, result, etc.)  │
│  • parse_github_request() - LLM intent extraction                      │
│  • enhance_with_intelligence() - Apply fuzzy/commit/log intelligence   │
│  • execute_github_operation() - Call GitHub API via PyGithub           │
│  • github_agent_invoke() - Main entry point                            │
└─────────────────────────────────────────────────────────────────────────┘
                                              │
          ┌───────────────────────────────────┼───────────────────────────────┐
          ▼                                   ▼                               ▼
┌──────────────────────┐    ┌──────────────────────────┐    ┌─────────────────────────┐
│  Intelligence Layer  │    │    GitHub Tools Layer    │    │    Workflow Layer       │
│  src/agents/github/  │    │  src/tools/github/       │    │  src/agents/github/     │
│  intelligence/       │    │  tools.py                │    │  workflows/             │
├──────────────────────┤    ├──────────────────────────┤    ├─────────────────────────┤
│ • repo_discovery.py  │    │ • GitHubTools class      │    │ • rollback.py           │
│ • commit_generator.py│    │   - list_repos()         │    │   - RollbackMatrix      │
│ • log_parser.py      │    │   - create_repo()        │    │   - RollbackAction      │
│                      │    │   - create_issue()       │    │   - RollbackFeasibility │
│                      │    │   - commit_file()        │    │                         │
│                      │    │   - create_pull_request()│    │                         │
└──────────────────────┘    └──────────────────────────┘    └─────────────────────────┘
```

---

## File-by-File Implementation Details

### 1. Agent Core: `src/agents/github/agent.py`
**Purpose:** LangGraph state machine orchestrating GitHub operations

#### Key Components:

**`GitHubState` (dataclass):**
```python
@dataclass
class GitHubState:
    query: str                          # User's natural language query
    operation: Optional[str]            # Parsed operation type
    parameters: Optional[Dict[str, Any]] # Operation parameters
    result: Optional[Dict[str, Any]]    # Execution result
    error: Optional[str]                # Error message if failed
    context: Optional[Dict[str, Any]]   # Session context (diff, files, etc.)
    audit_id: Optional[str]             # Unique operation ID
    timeline: Optional[Any]             # Event timeline for auditing
    intent_confidence: Optional[float]  # LLM parsing confidence
    repo_confidence: Optional[float]    # Fuzzy match confidence
    commit_confidence: Optional[float]  # Commit message confidence
```

**Workflow Nodes:**
| Node | Function | Description |
|------|----------|-------------|
| `parse` | `parse_github_request()` | LLM extracts intent, operation, parameters from query (30s timeout) |
| `enhance` | `enhance_with_intelligence()` | Apply fuzzy repo, commit gen, log parsing |
| `validate` | `validate_parameters()` | Strict Pydantic validation of all parameters |
| `policy_gate` | `policy_gate_check()` | **Phase 4:** Environment-level hard blocks (Production/Staging) |
| `risk_gate` | `risk_gate_check()` | **Phase 1-3:** Severity assessment and user confirmation requirement |
| `execute` | `execute_github_operation()` | Call GitHub API via PyGithub (15s timeout) |
| `error` | `handle_error()` | Format error responses and categorize GithubExceptions |

**Entry Point:**
```python
async def github_agent_invoke(
    query: str, 
    context: Optional[Dict[str, Any]] = None,
    github_token: Optional[str] = None
) -> dict:
    """
    Main entry point for github_operation tool.
    Returns: {success, data/error, audit_id, timeline}
    """
```

---

### 2. GitHub Tools: `src/tools/github/tools.py`
**Purpose:** PyGithub wrapper for GitHub API operations

#### `GitHubTools` Class Methods:

| Method | Arguments | Risk | Description |
|--------|-----------|------|-------------|
| `__init__(token)` | `token: Optional[str]` | — | Initialize PyGithub client |
| `list_repos()` | `visibility, sort, limit, page` | LOW | List user repositories (v3: `page` pagination) |
| `browse_files()` | `repo_name, path` | LOW | List repository content |
| `read_file()` | `repo_name, file_path, branch` | LOW | Read file; `branch` selects ref |
| `search_code()` | `query, repo_name` | LOW | Search code (returns `results/count/note`) |
| `list_branches()` | `repo_name` | LOW | List repo branches |
| `list_pull_requests()` | `repo_name, state, limit` | LOW | **v3** List PRs by state |
| `get_pr()` | `repo_name, pr_number` | LOW | **v3** Get single PR details |
| `list_commits()` | `repo_name, branch, limit` | LOW | **v3** List commits |
| `get_commit()` | `repo_name, sha` | LOW | **v3** Get commit details (files capped at 100) |
| `list_releases()` | `repo_name, limit` | LOW | **v3** List GitHub releases |
| `list_webhooks()` | `repo_name` | LOW | **v3** List webhooks |
| `create_issue()` | `repo_name, title, body, labels, assignees` | MEDIUM | Create issue |
| `commit_file()` | `repo_name, file_path, content, commit_message, branch, create_if_missing` | MEDIUM | Commit file |
| `create_branch()` | `repo_name, branch_name, from_branch` | MEDIUM | Create branch |
| `create_pull_request()` | `repo_name, title, head, base, body, draft` | MEDIUM | Create PR |
| `merge_pr()` | `repo_name, pr_number, merge_method, base` | MEDIUM→HIGH/CRITICAL | `base` triggers contextual escalation |
| `close_issue()` | `repo_name, issue_number` | MEDIUM | **v3** Close an issue |
| `update_issue()` | `repo_name, issue_number, title?, body?, state?, labels?, assignees?` | MEDIUM | **v3** Update issue fields |
| `add_comment()` | `repo_name, issue_number, body` | LOW | **v3** Add comment to issue |
| `create_repo()` | `name, description, private, auto_init` | HIGH | Create repo |
| `delete_branch()` | `repo_name, branch_name` | HIGH→CRITICAL | CRITICAL when branch=main/master/production |
| `create_release()` | `repo_name, tag_name, name, body, prerelease, draft` | HIGH (MEDIUM if prerelease=True) | **v3** Create release |
| `trigger_workflow()` | `repo_name, workflow_id, ref, inputs` | HIGH | **v3** Trigger Actions dispatch |
| `create_webhook()` | `repo_name, url, events, secret, content_type` | HIGH | **v3** Create webhook (SSRF-guarded) |
| `delete_webhook()` | `repo_name, webhook_id` | HIGH | **v3** Delete webhook |
| `delete_repo()` | `repo_name` | CRITICAL | Requires confirmed=true + reason |

**Convenience Functions:**
```python
list_repos(token, visibility, sort, limit)
create_repo(name, description, private, token, **kwargs)
create_issue(repo_name, title, body, token, **kwargs)
commit_file(repo_name, file_path, content, commit_message, token, **kwargs)
create_pull_request(repo_name, title, head, base, body, token, **kwargs)
```

---

### 3. Intelligence: Repo Discovery
**File:** `src/agents/github/intelligence/repo_discovery.py`  
**Purpose:** Fuzzy repository matching with confidence scoring

#### `RepoMatch` Dataclass:
```python
@dataclass
class RepoMatch:
    repo: Any              # PyGithub Repository object
    full_name: str         # e.g., "owner/repo-name"
    confidence: float      # 0.0 to 1.0
    match_type: str        # "exact", "fuzzy", "substring"
```

#### `RepoDiscovery` Class:

| Method | Description |
|--------|-------------|
| `fuzzy_search(query, max_results=5)` | Multi-strategy matching (exact → substring → Levenshtein) |
| `_exact_match(query)` | Fallback exact match when fuzzy disabled |
| `_get_cached_repos()` | Get repos with TTL caching (default: 1hr) |
| `_levenshtein_similarity(s1, s2)` | Calculate string similarity (0.0-1.0) |
| `get_best_match(query, confidence_threshold=0.85)` | Return best match if above threshold |
| `format_disambiguation_response(matches)` | Format options for user clarification |

**Matching Pipeline:**
1. **Exact match** → confidence: 1.0
2. **Substring match** → confidence: 0.7-0.9 (based on length difference)
3. **Levenshtein fuzzy** → confidence: 0.5-0.8 (similarity ratio)

---

### 4. Intelligence: Commit Generator
**File:** `src/agents/github/intelligence/commit_generator.py`  
**Purpose:** AI-generated Conventional Commits from git diffs

#### `ChangeType` Enum:
```python
class ChangeType(Enum):
    FEAT = "feat"       # New feature
    FIX = "fix"         # Bug fix
    DOCS = "docs"       # Documentation
    STYLE = "style"     # Formatting
    REFACTOR = "refactor"
    PERF = "perf"       # Performance
    TEST = "test"       # Tests
    CHORE = "chore"     # Maintenance
    CI = "ci"           # CI/CD
    BUILD = "build"     # Build system
```

#### `DiffAnalysis` Dataclass:
```python
@dataclass
class DiffAnalysis:
    files: List[str]    # Modified files
    additions: int      # Lines added
    deletions: int      # Lines deleted
    summary: str        # Brief summary
    file_types: set     # File extensions
```

#### `CommitMessage` Dataclass:
```python
@dataclass
class CommitMessage:
    text: str                    # Full message
    type: ChangeType             # Conventional type
    scope: Optional[str]         # Scope (e.g., "auth")
    description: str             # Short description
    body: Optional[str]          # Extended body
    confidence: float            # 0.0-1.0
    
    def to_conventional_format(self) -> str:
        # Returns: "feat(auth): add login endpoint"
```

#### `CommitGenerator` Class:

| Method | Description |
|--------|-------------|
| `generate(repo, diff, max_length=72)` | Main entry: analyze diff → generate message |
| `_analyze_diff(diff)` | Parse diff for files, additions, deletions |
| `_infer_change_type(analysis)` | Infer type from file patterns |
| `_build_prompt(analysis, change_type, max_length)` | Build LLM prompt |
| `_parse_llm_response(response, change_type, analysis)` | Extract message from LLM response |
| `_fallback_generation(analysis, change_type)` | Rule-based fallback (confidence: 0.60) |

**Type Inference Rules:**
- Files in `tests/` → TEST
- `.md` files → DOCS
- `.yml` in `.github/` → CI
- `requirements.txt`, `package.json` → BUILD
- More deletions than additions → REFACTOR
- More additions → FEAT

---

### 5. Intelligence: Log Parser
**File:** `src/agents/github/intelligence/log_parser.py`  
**Purpose:** Multi-language stack trace parsing for issue creation

#### `Language` Enum:
```python
class Language(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    JAVA = "java"
    GO = "go"
    UNKNOWN = "unknown"
```

#### `StackTrace` Dataclass:
```python
@dataclass
class StackTrace:
    language: Language
    error_type: str        # e.g., "ValueError"
    message: str           # Error message
    file: Optional[str]    # File path
    line: Optional[int]    # Line number
    function: Optional[str] # Function name
    stack_frames: List[dict]
    raw_trace: str
```

#### `ParsedIssue` Dataclass:
```python
@dataclass
class ParsedIssue:
    title: str           # Formatted issue title
    body: str            # Markdown body
    labels: List[str]    # Suggested labels
    stack_trace: StackTrace
    root_cause: Optional[str]  # LLM-inferred root cause
```

#### `LogParser` Class:

| Method | Description |
|--------|-------------|
| `parse(log, language=None)` | Main entry: detect language → parse → format issue |
| `_detect_language(log)` | Auto-detect from patterns |
| `_parse_python_trace(log)` | Parse Python Traceback |
| `_parse_js_trace(log)` | Parse JavaScript/Node.js |
| `_parse_java_trace(log)` | Parse Java Exception |
| `_parse_go_trace(log)` | Parse Go panic |
| `_parse_generic_trace(log)` | Fallback generic parsing |
| `_infer_root_cause(trace)` | LLM analysis for root cause |
| `_suggest_labels(trace, root_cause)` | Auto-suggest labels |
| `_format_title(trace)` | Format issue title |
| `_format_body(trace, root_cause)` | Format markdown body |

**Language Detection Patterns:**
- Python: "Traceback", `File "`, `line `
- JavaScript: `at `, `.js:`, `Error:`, `TypeError:`
- Java: "Exception in thread", `.java:`
- Go: `panic:`, `goroutine`

---

### 6. Workflows: Rollback Matrix
**File:** `src/agents/github/workflows/rollback.py`  
**Purpose:** Rollback feasibility and compensating actions

#### `RollbackFeasibility` Enum:
```python
class RollbackFeasibility(Enum):
    IMMEDIATE = "immediate"       # Can rollback immediately
    COMPENSATING = "compensating" # Requires compensating action
    MANUAL = "manual"             # Requires manual intervention
    IMPOSSIBLE = "impossible"     # Cannot be undone
```

#### `RollbackMatrix.MATRIX`:

| Operation | Feasibility | Rollback Action | Prechecks |
|-----------|-------------|-----------------|-----------|
| `create_branch` | IMMEDIATE | `delete_branch` | branch_not_protected, no_open_prs |
| `commit` | IMMEDIATE | `revert_commit` | branch_not_protected, commit_not_merged |
| `push` | IMMEDIATE | `force_push_reset` | branch_not_protected, no_open_prs (5min window) |
| `create_pull_request` | IMMEDIATE | `close_pr` | pr_not_merged |
| `merge_pr` | COMPENSATING | - | create_revert_pr |
| `delete_branch` | IMMEDIATE | `restore_from_reflog` | within_reflog_window (48hr) |
| `close_issue` | IMMEDIATE | `reopen_issue` | - |
| `delete_repository` | IMPOSSIBLE | - | - |
| `force_push` | MANUAL | - | notify_team_and_restore_backup |

---

## Phase 2 Specialized Tools

### 7. Changelog Generator
**File:** `src/tools/changelog.py`  
**Tool:** `generate_changelog`

#### `ChangelogGenerator` Class:

| Method | Description |
|--------|-------------|
| `generate(repo, from_tag, to_tag="HEAD", format="markdown")` | Generate changelog between tags |
| `_fetch_commits(repo, from_tag, to_tag)` | Fetch commits via GitHub API |
| `_categorize_commits(commits)` | Categorize by Conventional Commits type |
| `_format_markdown(categorized, from_tag, to_tag)` | Format as markdown |

**Categories:**
- 🚀 Features (`feat`)
- 🐛 Bug Fixes (`fix`)
- 📚 Documentation (`docs`)
- 🎨 Styling (`style`)
- ♻️ Refactoring (`refactor`)
- ⚡ Performance (`perf`)
- 🧪 Tests (`test`)
- 🔧 Maintenance (`chore`)

---

### 8. CI Diagnostics
**File:** `src/tools/ci_diagnostics.py`  
**Tool:** `analyze_ci_failure`

#### Key Dataclasses:
```python
@dataclass
class FailurePattern:
    type: str           # dependency, test, lint, build, timeout
    message: str
    line: Optional[int]
    file: Optional[str]
    severity: str       # critical, high, medium, low

@dataclass
class SuggestedFix:
    title: str
    description: str
    confidence: float
    auto_fixable: bool      # Controlled by policy
    commands: Optional[List[str]]
    file_changes: Optional[Dict[str, str]]
```

#### `CIAnalyzer` Class:

| Method | Description |
|--------|-------------|
| `analyze(repo, run_id=None, pr_number=None)` | Analyze CI failure |
| `_fetch_logs(repo, run_id, pr_number)` | Fetch workflow logs |
| `_extract_failure_patterns(logs)` | Pattern matching for failures |
| `_suggest_fixes(failures, logs)` | LLM-powered fix suggestions |
| `_get_fallback_fixes(failures)` | Rule-based fallback fixes |
| `_generate_summary(failures, fixes)` | Human-readable summary |

**Failure Pattern Detection:**
- `ModuleNotFoundError` → dependency failure
- `pytest` failed → test failure
- `eslint` errors → lint failure
- Build timeouts → timeout failure

---

### 9. Repository Scaffolder
**File:** `src/tools/scaffold.py`  
**Tool:** `scaffold_repo`

> **Note:** The agent dispatches the operation as `scaffold_repo` (matches `agent.py` and `schemas.py`). The `manifests/devforge.json` entry name is `scaffold_repository` — this is a known mismatch between the manifest entry and the LLM-emitted operation string.

#### Built-in Templates:

| Template | Description | Files |
|----------|-------------|-------|
| `fastapi` | FastAPI microservice | main.py, requirements.txt, Dockerfile, .github/workflows/ci.yml |
| `react` | React frontend | package.json, src/App.js, public/index.html |
| `nextjs` | Next.js app | package.json, pages/index.js, next.config.js |
| `microservice` | Generic microservice | Dockerfile, docker-compose.yml, .github/workflows/ |
| `docs` | Documentation site | mkdocs.yml, docs/index.md |

#### `RepositoryScaffolder` Class:

| Method | Description |
|--------|-------------|
| `scaffold(name, template, description=None, private=False, force=False)` | Main entry with guardrails |
| `_execute_scaffold(owner, name, template, description, private, timeline)` | Execute scaffolding steps |

**Production Guardrails:**
1. **Token Scope Validation** - Check `admin:org` for org repos
2. **Input Sanitization** - Validate repo name, description
3. **Idempotency Check** - Detect existing repos
4. **Async Fallback** - Large templates queue async job

---

---

## Risk Model & Security (Phases 1-5)

The GitOps tool implements a multi-layered security model involving environment-level policies, contextual risk assessment, and mandatory user confirmation.

### 1. Risk Levels
Every operation is assigned a base risk level in the `OperationRiskRegistry`.

| Risk Level | Requirement | Examples |
|------------|-------------|----------|
| **`LOW`** | None | `list_repos`, `browse_files`, `list_branches` |
| **`MEDIUM`** | None | `create_issue`, `create_branch`, `merge_pr` (feature branch) |
| **`HIGH`** | `confirmed: true` | `create_repo`, `delete_branch` (non-protected), `force_push` |
| **`CRITICAL`** | `confirmed: true` + `reason: "..."` | `delete_repo`, `delete_branch` (main), `merge_pr` (production) |

### 2. Contextual Risk Escalation
Risk levels are dynamically escalated based on the parameters of the operation. If a contextual rule matches, the **highest** risk level between the registry and the rule wins.

*   **`merge_pr`**:
    *   Into `main`, `master`: **HIGH**
    *   Into `production`, `release/*`: **CRITICAL**
*   **`delete_branch`**:
    *   `main`, `master`, `production`: **CRITICAL**

### 3. Policy Gate (Phase 4)
Runs before the risk gate. Blocks operations based on environment configuration.

| Var / Env | Mode | Policy |
|-----------|------|--------|
| `GITOPS_PROTECTED_MODE=true` | All | Blocks **HIGH** and **CRITICAL** operations entirely. |
| `GITOPS_ENV=production` | Prod | Blocks `delete_repo`, `force_push`, and deleting `main`/`master`. |
| `GITOPS_ENV=staging` | Staging | Blocks `delete_repo`. Requires confirmation for `force_push`. |
| `GITOPS_ENV=development` | Dev | Permissive. Defers all security to the Risk Gate. |

### 4. Audit & Escalation (Phase 5)
All high-risk attempts are logged to a dedicated escalation channel (`src/core/audit.py`).
- **CRITICAL**: Logs all attempts (blocked or executed).
- **HIGH**: Logs all blocked attempts.
- **Sanitization**: Tokens, passwords, and keys are automatically redacted (`[REDACTED]`) before logging.
- **Privacy**: Raw tokens are never stored; only truncated SHA-256 hashes for correlation.

---

## API Request Format

Two endpoints accept `github_operation`. Both require `x-api-key`. **Per-request `context.github_token`** is the canonical PAT path; the server-level `GITHUB_TOKEN` env var is an optional fallback.

### Gateway (REST) — `POST /api/gateway`

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <dev_api_key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "list my repos",
      "context": {"github_token": "ghp_…"}
    }
  }'
```

> **Important:** Use `"name"` (or alias `"apiName"`), not `"tool_name"`. Both fields are validated by `GatewayRequest` Pydantic model; either must be provided.

### MCP (JSON-RPC 2.0) — `POST /mcp`

```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: <dev_api_key>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "github_operation",
      "arguments": {
        "query": "list my repos",
        "context": {"github_token": "ghp_…"}
      }
    }
  }'
```

---

### Response Structure — Gateway success path

Verified 2026-05-15 against live `localhost:8001/api/gateway`. The envelope is **flat** — `data` is the agent payload directly (an array for `list_repos`, an object for `create_issue`/`commit_file`/etc.).

```json
{
  "success": true,
  "data": [
    {
      "name": "testing_devforge",
      "full_name": "sidcollege/testing_devforge",
      "description": null,
      "private": false,
      "url": "https://github.com/sidcollege/testing_devforge",
      "clone_url": "...",
      "language": null,
      "stars": 0,
      "forks": 0,
      "updated_at": "...",
      "created_at": "..."
    }
  ],
  "message": "github_operation executed successfully"
}
```

For non-list operations the agent attaches `audit_id` and `timeline` inside `data`:

```json
{
  "success": true,
  "data": {
    "number": 3,
    "title": "...",
    "url": "https://github.com/owner/repo/issues/3",
    "audit_id": "audit_20260515_115d0e5be729",
    "timeline": {"total_duration_ms": 2394.99, "events": [...]}
  },
  "message": "github_operation executed successfully"
}
```

> **Important:** there is **no top-level `operation` key on the gateway envelope** — the operation type lives only inside the agent payload (e.g., audit timeline events). Older docs that showed `data:{operation:"list_repos", data:[...]}` were incorrect.

### Response Structure — MCP success path

MCP wraps the same agent payload inside the standard JSON-RPC `result.content[0].text` field as a **JSON-encoded string**:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\n  \"success\": true,\n  \"operation\": \"create_issue\",\n  \"data\": {...},\n  \"audit_id\": \"...\",\n  \"timeline\": {...}\n}"
      }
    ],
    "isError": false
  }
}
```

Clients must `JSON.parse(result.content[0].text)` to access the agent payload. The MCP payload **does** include a top-level `operation` key (the gateway envelope does not).

### Response Structure — Error paths

| Condition | Gateway response | MCP response |
|-----------|------------------|--------------|
| Wrong tool name | HTTP 400 `{success:false, data:null, message:"Tool 'x' not found. Available tools: [...]"}` | JSON-RPC `error.code = -32602`, message `"Tool not found: x"` |
| Missing `name`/`apiName` | HTTP 422 Pydantic `Either 'name' or 'apiName' must be provided` | (gateway-only) |
| Malformed JSON | HTTP 422 Pydantic `json_invalid` | HTTP 422 Pydantic `json_invalid` |
| `arguments: null` | HTTP 422 Pydantic `'arguments' must be str or dict, got NoneType` | (gateway-only) |
| Missing `x-api-key` | HTTP 401 `{success:false, detail:"API Key missing"}` | HTTP 401 same |
| GET instead of POST | HTTP 405 `{detail:"Method Not Allowed"}` | HTTP 405 same |
| **Risk-gate blocks (HIGH/CRITICAL)** | HTTP 200 `{success:false, data:{audit_id, timeline}, message:"Risk gate blocked: ..."}` | **JSON-RPC `error.code = -32603`** with `message:"Risk gate blocked: ..."` — does **not** flow through `result.content` |
| Disambiguation (multiple repo matches) | HTTP 200 `{success:false, data:{status:"needs_clarification", options:[...]}, message:"Multiple repositories match your query:"}` | Wrapped inside `result.content[0].text` as JSON string |

> **Frontend integrators:** the MCP path collapses every risk-gate block to a JSON-RPC `-32603` error. If you need the `audit_id`/`timeline` payload from blocked ops, call `/api/gateway` instead — the MCP envelope does not surface them on blocks.

---

## Configuration

### Required Environment Variables

```bash
# GitHub PAT — Required at request time, normally supplied via context.github_token
# (per-user/per-connection PAT). The server-level env var is an optional fallback only.
GITHUB_TOKEN=ghp_your_token_here

# Optional
GITHUB_USERNAME=your_username
```

### Feature Toggles

```bash
# Intelligence Features (all in src/core/config.py)
GITOPS_ENABLE_FUZZY_SEARCH=true
GITOPS_ENABLE_COMMIT_GEN=true
GITOPS_ENABLE_LOG_PARSING=true
GITOPS_ENABLE_WORKFLOWS=true
GITOPS_ENABLE_ROLLBACK=true
GITOPS_ENABLE_ASYNC_JOBS=true

# Thresholds
GITOPS_FUZZY_THRESHOLD=0.85
GITOPS_AUTO_FIX_THRESHOLD=0.95

# Performance
GITOPS_REPO_CACHE_TTL=3600    # 1 hour
GITOPS_SESSION_TTL=1800       # 30 minutes
GITOPS_LLM_TIMEOUT=10         # parse_github_request LLM timeout (s)
GITOPS_UNDO_WINDOW_MINUTES=30
GITOPS_JOB_CLEANUP_HOURS=24

# Storage (memory | redis | postgres)
GITOPS_STORAGE=memory

# Policy / Environment (read via os.getenv in src/core/policy.py)
GITOPS_PROTECTED_MODE=false
GITOPS_ENV=development
```

> **Note:** Confidence gating is enabled by default via `Feature.CONFIDENCE_GATING` in `src/core/features.py:46` (hard-coded `True`, no env binding). The 0.90 commit-message confidence threshold is hard-coded in `ConfidencePolicy.THRESHOLDS["commit_message"]` (`src/core/confidence.py:42`). There are no `GITOPS_ENABLE_CONFIDENCE_GATING` or `GITOPS_COMMIT_CONFIDENCE_THRESHOLD` env vars.

---

## Workflow Sequence

```
1. User Query: "create issue in backend about login bug"
                              │
2. API Gateway (routers.py)   │
   └─ Validate request        │
   └─ Route to github_agent_invoke()
                              │
3. GitHub Agent (agent.py)    ▼
   ┌─────────────────────────────────────────────┐
   │  Node: parse_github_request                  │
   │  - LLM extracts intent, operation, params   │
   │  - Sets intent_confidence                   │
   └─────────────────────────────────────────────┘
                              │
   ┌─────────────────────────────────────────────┐
   │  Node: enhance_with_intelligence            │
   │  - RepoDiscovery.fuzzy_search("backend")   │
   │  - Sets repo_confidence                     │
   │  - CommitGenerator (if diff provided)       │
   │  - LogParser (if error_log provided)        │
   └─────────────────────────────────────────────┘
                              │
    ┌─────────────────────────────────────────────┐
    │  Node: validate_parameters (Phase 4)         │
    │  - Pydantic schema enforcement              │
    │  - Strict type and constraint checking       │
    └─────────────────────────────────────────────┘
                               │
    ┌─────────────────────────────────────────────┐
    │  Node: policy_gate_check (Phase 4)          │
    │  - Environment-level hard blocks            │
    │  - GITOPS_PROTECTED_MODE / GITOPS_ENV       │
    └─────────────────────────────────────────────┘
                               │
    ┌─────────────────────────────────────────────┐
    │  Node: risk_gate_check (Phase 1-3)          │
    │  - Severity assessment (LOW/MED/HIGH/CRIT)  │
    │  - Requires confirmed/reason for HIGH+      │
    └─────────────────────────────────────────────┘
                               │
    ┌─────────────────────────────────────────────┐
    │  Node: execute_github_operation             │
    │  - GitHubTools.create_issue()              │
    │  - Track audit timeline & Rollback context   │
    └─────────────────────────────────────────────┘
                              │
4. Response with audit_id, timeline, confidence scores
```

---

## Error Handling

### Error Types

| Status | Description |
|--------|-------------|
| `needs_clarification` | Low confidence, user input required |
| `permission_error` | Token lacks required scopes |
| `confidence_too_low` | Operation rejected for safety |
| `not_found` | Repository/resource not found |
| `rate_limited` | GitHub API rate limit exceeded |

### Example Error Response

```json
{
  "success": false,
  "data": {
    "status": "needs_clarification",
    "options": [
      {"repo": "org/backend-api", "confidence": 0.82},
      {"repo": "org/backend-worker", "confidence": 0.78}
    ]
  },
  "message": "Multiple repositories match 'backend'",
  "audit_id": "audit_20251212_abc"
}
```

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Specific test files (68 tests total)
pytest tests/test_repo_discovery.py -v     # 13 tests
pytest tests/test_commit_generator.py -v   # 19 tests
pytest tests/test_log_parser.py -v         # 18 tests
pytest tests/test_github_integration.py -v # 18 tests
```

---

## Related Files

| Category | Files |
|----------|-------|
| **Agent Core** | `src/agents/github/agent.py` |
| **GitHub API** | `src/tools/github/tools.py` |
| **Intelligence** | `src/agents/github/intelligence/repo_discovery.py`, `commit_generator.py`, `log_parser.py` |
| **Workflows** | `src/agents/github/workflows/rollback.py` |
| **Phase 2 Tools** | `src/tools/changelog.py`, `ci_diagnostics.py`, `scaffold.py` |
| **Core Services** | `src/core/audit.py`, `src/core/confidence.py`, `src/core/session.py` |
| **Tests** | `tests/test_repo_discovery.py`, `test_commit_generator.py`, `test_log_parser.py`, `test_github_integration.py` |

---

**Version:** 1.0.0
**Manifest Version:** 0.12.0
**Last Updated:** 2026-05-19
**Maintainer:** DevForge Team

---

## Changelog

### 2026-05-19 — v1.0.0: GitOps v3 Expansion

**v1.0.0 (2026-05-19):** 26 structured ops — PR inspection, issue CRUD, commit history, release management, GitHub Actions, webhook management. Error enrichment with PAT scope guidance.

**New operations (13 added):** `merge_pr`, `list_pull_requests`, `get_pr`, `close_issue`, `update_issue`, `add_comment`, `list_commits`, `get_commit`, `list_releases`, `create_release`, `trigger_workflow`, `list_webhooks`, `delete_webhook` (+ `create_webhook` via `TestWebhookManagementOps`).

**Structured operation count:** 13 → **26**

**Test suite:** 25 parametrize rows in `test_mcp_structured_each_operation_end_to_end`, all passing.

---

### 2026-05-19 — v0.9.0: Slice 2 Redis Persistence + merge_pr + bug fixes

**New features:**
- **`merge_pr` fully implemented** — `GitHubTools.merge_pr()`, `MergePRParams` schema, dispatch in `execute_github_operation`. Structured-call mode and NL path both work. Supports `merge_method: merge|squash|rebase`, optional `commit_title`/`commit_message`. Verified live: squash merge of PR #7 on `sidcollege/testing_devforge`.
- **`read_file` branch support** — `ReadFileParams.branch: Optional[str]` added; `GitHubTools.read_file()` now accepts `branch` and passes `ref=branch` to `get_contents()`. Previously the parameter was silently ignored.
- **Slice 2 Redis persistence** — All GitOps stores now have Redis-backed implementations behind lazy proxy factories: `RedisAuditStore`, `RedisEscalationStore`, `RedisJobStore`, `RedisSessionStore`. In-memory fallback auto-engages when `REDIS_URL` is unset or under pytest. Key layout: `gitops:{type}:{tenant_id}:{id}`. New env vars: `REDIS_SESSION_TTL` (default 1800s).
- **Disambiguation session persistence** — Multi-match repo responses now save a session (`session_id` key in response). Second call with `context.session_id` + `context.selected_repo` restores parameters and skips fuzzy search. Sessions delete after use (replay protection).

**Bug fixes:**
- **`None.lower()` crash in contextual risk gate** — `parameters.get("base", "")` returned `None` when `base` was an explicit `None` from `model_dump()`. Fixed all three occurrences in `_get_contextual_risk_level` (`merge_pr.base`, `delete_branch.branch_name`, `commit_file.branch`) to use `(parameters.get(key) or "").lower()`.
- **`from github import NotSet` import error in `merge_pr`** — Redundant local import shadowed the correct file-level `from github.GithubObject import NotSet`. Removed the local import.
- **`EscalationLogger` methods now async** — All `record_critical`, `record_blocked_high`, `get_records*` methods are `async def` with `await asyncio.sleep(0)` for in-memory implementations. Call sites in `agent.py` updated with `await`.

**Structured operation count:** 12 → **13** (added `merge_pr`)

**Test suite:** 66 Slice 2 + risk tests pass. 16 pre-existing failures unchanged (API key middleware scope).

### 2026-05-15 — Live verification + doc reconciliation

- **Verified** every documented claim against `localhost:8001` (gateway + MCP) using the demo PAT. See `_reviews/github_operation_review_verification_2026-05-15.md` for the verification log.
- **Removed** fabricated `merge_pr()` row from the `GitHubTools` method table (no method, no schema, no dispatch — only forward-looking metadata in `RiskRegistry`/`RollbackMatrix`).
- **Removed** non-existent env vars `GITOPS_ENABLE_CONFIDENCE_GATING` and `GITOPS_COMMIT_CONFIDENCE_THRESHOLD` from the feature-toggles section. Confidence gating is hard-coded `True` via `Feature.CONFIDENCE_GATING`; the 0.90 commit-message threshold is in `ConfidencePolicy.THRESHOLDS`.
- **Added** missing env vars: `GITOPS_ENABLE_WORKFLOWS`, `GITOPS_ENABLE_ROLLBACK`, `GITOPS_ENABLE_ASYNC_JOBS`, `GITOPS_AUTO_FIX_THRESHOLD`, `GITOPS_LLM_TIMEOUT`, `GITOPS_UNDO_WINDOW_MINUTES`, `GITOPS_JOB_CLEANUP_HOURS`, `GITOPS_STORAGE`.
- **Documented** the MCP-vs-gateway response shape divergence in the API Request Format section (gateway = flat `data`, MCP = `result.content[0].text` JSON string, risk-gate blocks on MCP collapse to JSON-RPC `error -32603`).
- **Replaced** the aspirational response-structure example with the live-verified gateway envelope shape (no top-level `operation` key).
- **Added** `apiName` alias note on the request format — `GatewayRequest` now accepts either `name` or `apiName`.
- **Documented** the corresponding Pydantic-tightening on `arguments: null` (now HTTP 422 instead of silent coercion).

### 2026-05-08 — Initial review baseline

- See `_reviews/github_operation_review.md`. Diverged verdict; most P0/P1 items have been resolved in this revision. Outstanding: `scaffold_repo`/`scaffold_repository` manifest mismatch, MCP Phase-2 names still not gateway-callable (by design, documented).



