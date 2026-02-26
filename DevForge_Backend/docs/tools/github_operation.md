# github_operation - Intelligent GitHub Automation Tool

**Tool Name:** `github_operation`  
**Version:** 0.8.2  
**Phase:** GitOps v0.8 - Production Hardening  
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
│  │    parse_github_request → enhance_with_intelligence → validate → execute    │
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
**Lines:** 558 | **Purpose:** LangGraph state machine orchestrating GitHub operations

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
| `validate` | `validate_parameters()` | **Phase 4:** Strict Pydantic validation of all parameters |
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
**Lines:** 423 | **Purpose:** PyGithub wrapper for GitHub API operations

#### `GitHubTools` Class Methods:

| Method | Arguments | Description |
|--------|-----------|-------------|
| `__init__(token)` | `token: Optional[str]` | Initialize PyGithub client |
| `list_repos()` | `visibility, sort, limit` | List user repositories |
| `create_repo()` | `name, description, private, auto_init, gitignore_template, license_template` | Create new repository |
| `create_issue()` | `repo_name, title, body, labels, assignees` | Create issue in repository |
| `commit_file()` | `repo_name, file_path, content, commit_message, branch, create_if_missing` | Commit file to repository |
| `create_pull_request()` | `repo_name, title, head, base, body, draft` | Create pull request |
| `browse_files()` | `repo_name, path` | List repository content (file tree) |
| `read_file()` | `repo_name, file_path` | Read content of a specific file |
| `search_code()` | `query, repo_name` | Search code across repository |

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
**Lines:** 230 | **Purpose:** Fuzzy repository matching with confidence scoring

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
**Lines:** 335 | **Purpose:** AI-generated Conventional Commits from git diffs

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
**Lines:** 487 | **Purpose:** Multi-language stack trace parsing for issue creation

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
**Lines:** 234 | **Purpose:** Rollback feasibility and compensating actions

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
**Lines:** 272 | **Tool:** `generate_changelog`

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
**Lines:** 455 | **Tool:** `analyze_ci_failure`

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
**Lines:** 355 | **Tool:** `scaffold_repository`

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

## API Request Format

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "list my repos"
    }
  }'
```

> **Important:** Use `"name"` field (not `"tool_name"`).

### Response Structure

```json
{
  "success": true,
  "data": {
    "operation": "list_repos",
    "repos": [...],
    "audit_id": "audit_20251212_abc123",
    "timeline": {
      "total_duration_ms": 1250,
      "events": [...]
    }
  },
  "message": "Listed 10 repositories",
  "tool": "github_operation",
  "execution_time": 1.25
}
```

---

## Configuration

### Required Environment Variables

```bash
# Required
GITHUB_TOKEN=ghp_your_token_here

# Optional
GITHUB_USERNAME=your_username
```

### Feature Toggles

```bash
# Intelligence Features
GITOPS_ENABLE_FUZZY_SEARCH=true
GITOPS_ENABLE_COMMIT_GEN=true
GITOPS_ENABLE_LOG_PARSING=true
GITOPS_ENABLE_CONFIDENCE_GATING=true

# Thresholds
GITOPS_FUZZY_THRESHOLD=0.85
GITOPS_COMMIT_CONFIDENCE_THRESHOLD=0.90

# Performance
GITOPS_REPO_CACHE_TTL=3600    # 1 hour
GITOPS_SESSION_TTL=1800       # 30 minutes
```

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

# Specific test files
pytest tests/test_repo_discovery.py -v     # 18 tests
pytest tests/test_commit_generator.py -v   # 20 tests
pytest tests/test_log_parser.py -v         # 18 tests
pytest tests/test_github_integration.py -v # 20 tests
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

**Version:** 0.8.2  
**Last Updated:** February 26, 2026  
**Maintainer:** DevForge Team



