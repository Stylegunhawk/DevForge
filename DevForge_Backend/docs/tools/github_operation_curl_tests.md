# github_operation - Gateway & MCP Curl Test Suite

**Version:** 0.9.0 (V12)
**Last Updated:** 2026-05-19
**Last Verified:** 2026-05-19 — aggressive live test of all 13 structured operations against `localhost:8001` using demo PAT on `sidcollege/testing_devforge`. Response shapes reflect actual behavior.

## Base Configuration
- Base URL: `http://localhost:8001` (adjust as needed)
- Required headers: `"Content-Type: application/json"` and `"x-api-key: <key>"` (both endpoints are gated by `APIKeyAuthMiddleware`)
- Token: `GITHUB_TOKEN` env var is an optional fallback; the per-request `context.github_token` (per-user PAT) is the canonical source
- Two endpoints accept the same tool:
  - `POST /api/gateway` — REST, returns `{success, data, message}` envelope
  - `POST /mcp` — JSON-RPC 2.0, returns `{result: {content: [{type: "text", text: "<json-string>"}], isError}}` wrapper; clients must `JSON.parse(text)` to get the agent payload
- **Response shapes in this doc are flat by default** (the gateway envelope). For MCP wrapping see [§7 MCP Equivalents](#7-mcp-equivalents).

## Envelope shape (gateway, verified 2026-05-15)

```json
{
  "success": true|false,
  "data": <agent_payload | array | null>,
  "message": "<status string>"
}
```

There is **no top-level `operation` key on the gateway envelope**. The `operation` string appears only inside the MCP payload (`result.content[0].text`) and inside the audit `timeline.operation` field.

---

## 1. Core Operations

### Test: List Repositories - Basic Request

**Description:** Basic repository listing request

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "list my repositories"
    }
  }'
```

**Expected Response (gateway envelope is flat — `data` is the repo array directly):**
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
      "clone_url": "https://github.com/sidcollege/testing_devforge.git",
      "language": null,
      "stars": 0,
      "forks": 0,
      "updated_at": "2026-02-28T13:47:15+00:00",
      "created_at": "2026-02-28T13:47:12+00:00"
    }
  ],
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Verified live 2026-05-15. Tests basic LLM intent recognition for listing repositories. Note that `list_repos` does NOT include `audit_id`/`timeline` in the data array (those appear on non-list operations).

### Test: List Repositories - With Parameters

**Description:** Repository listing with specific parameters

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "show my public repositories, only 5"
    }
  }'
```

**Expected Response (flat array, may be filtered by the visibility/limit parameters the LLM extracts):**
```json
{
  "success": true,
  "data": [
    { "name": "...", "full_name": "...", "private": false, "url": "...", "...": "..." }
  ],
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests parameter extraction from natural language. `limit` and `visibility` are extracted by the LLM into the agent's `list_repos` call.

### Test: Create Repository - Public Repo (HIGH risk — requires confirmation)

**Description:** `create_repo` is HIGH risk in `OperationRiskRegistry`. Without `context.confirmed: true`, the risk gate blocks the operation.

```bash
# Step 1: First call is BLOCKED by the risk gate
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create a new repository called my-awesome-project with description for awesome stuff",
      "context": {"github_token": "ghp_..."}
    }
  }'
```

**Expected Response (Step 1 — risk-gate block):**
```json
{
  "success": false,
  "data": {
    "audit_id": "audit_20260515_93a7ae512bf2",
    "timeline": {
      "operation": "github_operation",
      "total_duration_ms": 1464.32,
      "events": [
        {"event": "step_failed", "metadata": {"step": "risk_gate", "error": "Risk gate blocked: Operation create_repo requires: confirmed=true"}}
      ]
    }
  },
  "message": "github_operation execution failed: Risk gate blocked: Operation create_repo requires: confirmed=true"
}
```

```bash
# Step 2: Re-call with confirmed=true to execute
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create a new repository called my-awesome-project with description for awesome stuff",
      "context": {"github_token": "ghp_...", "confirmed": true}
    }
  }'
```

**Expected Response (Step 2 — success, flat envelope):**
```json
{
  "success": true,
  "data": {
    "name": "my-awesome-project",
    "full_name": "user/my-awesome-project",
    "description": "for awesome stuff",
    "private": false,
    "url": "https://github.com/user/my-awesome-project",
    "audit_id": "audit_...",
    "timeline": {"total_duration_ms": ..., "events": [...]}
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200 (both calls — risk-gate block is HTTP 200 with `success:false`, not a 4xx)

**Notes:** Tests two-step risk-gate flow for HIGH operations. Step 1 verified live 2026-05-15: risk gate blocks `create_repo` cleanly with `audit_id` and full timeline. Step 2 not executed in verification suite to avoid littering the demo account.

### Test: Create Repository - Private Repo (HIGH risk — requires confirmation)

**Description:** Same risk-gate flow as the public-repo test. `private:true` is extracted by the LLM from the natural-language query.

```bash
# Risk-gate block path
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create a private repository named secret-project",
      "context": {"github_token": "ghp_...", "confirmed": true}
    }
  }'
```

**Expected Response (success — flat envelope):**
```json
{
  "success": true,
  "data": {
    "name": "secret-project",
    "full_name": "user/secret-project",
    "private": true,
    "url": "https://github.com/user/secret-project",
    "audit_id": "audit_...",
    "timeline": {"events": [...]}
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests private repository creation. Same risk-gate semantics as the public-repo test — without `confirmed:true` the operation is blocked.

### Test: Create Issue - Valid Request (MEDIUM risk — no confirmation needed)

**Description:** `create_issue` is MEDIUM risk; risk gate passes without `confirmed:true`.

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create issue in testing_devforge about login failing with invalid credentials",
      "context": {"github_token": "ghp_..."}
    }
  }'
```

**Expected Response (verified live 2026-05-15 — gateway envelope is flat):**
```json
{
  "success": true,
  "data": {
    "number": 3,
    "title": "Login failing with invalid credentials",
    "body": "...",
    "state": "open",
    "url": "https://github.com/sidcollege/testing_devforge/issues/3",
    "labels": [],
    "assignees": [],
    "created_at": "2026-05-15T14:30:56+00:00"
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Verified live. Note `audit_id`/`timeline` are present on the MCP path but were not returned on the gateway envelope in the verification run for `create_issue` — if you need the audit trail, prefer MCP or inspect the agent timeline via the audit log.

### Test: Create Issue - With Labels and Assignees

**Description:** Create an issue with labels and assignees

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create bug issue in backend-service assigned to john with priority and bug labels"
    }
  }'
```

**Expected Response (flat envelope):**
```json
{
  "success": true,
  "data": {
    "number": 2,
    "title": "Bug in backend-service",
    "labels": ["bug", "priority"],
    "assignees": ["john"],
    "state": "open",
    "url": "https://github.com/user/backend-service/issues/2"
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests label and assignee extraction from natural language. `labels` and `assignees` arrays may be empty if the LLM cannot identify them — verify in the issue URL after creation.

### Test: Commit File - Create New File

**Description:** Commit a new file to a repository

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "add readme file to my-project with content # My Project"
    }
  }'
```

**Expected Response (flat envelope):**
```json
{
  "success": true,
  "data": {
    "action": "created",
    "file_path": "README.md",
    "commit_message": "Add README.md",
    "commit_sha": "...",
    "branch": "main",
    "url": "https://github.com/user/my-project/blob/main/README.md"
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests file creation with content parsing. `create_if_missing:true` is implicit when `commit_file` is called against a non-existent path (controlled by the Pydantic schema in `src/agents/github/schemas.py`).

### Test: Commit File - With Context Diff

**Description:** Commit file with diff provided in context for auto-commit message

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "commit this fix",
      "context": {
        "diff": "diff --git a/app.py b/app.py\n+print(\"Fixed login bug\")\n- print(\"Old code\")"
      }
    }
  }'
```

**Expected Response (flat envelope; `commit_confidence` lives inside `data`, not at the top level):**
```json
{
  "success": true,
  "data": {
    "action": "updated",
    "file_path": "app.py",
    "commit_message": "fix: resolve login authentication issue",
    "commit_confidence": 0.92,
    "audit_id": "audit_..."
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests commit generator with diff context. Confidence between 0.85 and 0.90 triggers the **medium-confidence draft-PR fallback** instead of a direct commit (see `agent.py:428-430`). Below 0.85 the operation is blocked by `ConfidencePolicy`.

### Test: Merge Pull Request — MEDIUM risk, no confirmation needed (feature branch)

**Description:** `merge_pr` is MEDIUM risk when `base` is not a protected branch. Passes without `confirmed`. Verified live 2026-05-19 — squash merged PR #7 on `sidcollege/testing_devforge`.

```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "github_operation",
      "arguments": {
        "operation": "merge_pr",
        "repo_name": "owner/repo",
        "pr_number": 7,
        "merge_method": "squash",
        "context": {"github_token": "ghp_..."}
      }
    }
  }'
```

**Expected Response (parse `result.content[0].text`):**
```json
{
  "success": true,
  "operation": "merge_pr",
  "data": {
    "merged": true,
    "message": "Pull Request successfully merged",
    "sha": "9faaacfa0fe31f28817da4f4bc670e687f91af40",
    "pr_number": 7,
    "repo_name": "owner/repo"
  },
  "audit_id": "audit_20260519_...",
  "timeline": {"total_duration_ms": 3931.14, "events": [...]}
}
```

**Expected HTTP Status:** 200

**Notes:** Verified live 2026-05-19. `merge_method` accepts `"merge"` (default), `"squash"`, or `"rebase"`. The optional `commit_title` and `commit_message` fields override the merge commit message. The `base` parameter is only used by the risk gate for escalation logic — it is **not** passed to the GitHub API.

---

### Test: Merge Pull Request — HIGH risk blocked (merging into main)

**Description:** `merge_pr` escalates to HIGH risk when `base` is `"main"` or `"master"`. Blocked without `confirmed: true`.

```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "github_operation",
      "arguments": {
        "operation": "merge_pr",
        "repo_name": "owner/repo",
        "pr_number": 7,
        "base": "main",
        "context": {"github_token": "ghp_..."}
      }
    }
  }'
```

**Expected Response (risk-gate block — JSON-RPC error, not result.content):**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "Risk gate blocked: Operation merge_pr requires: confirmed=true"
  }
}
```

**Expected HTTP Status:** 200

**Notes:** Verified live 2026-05-19. To proceed, add `"confirmed": true` inside `context`. If `base` is `"production"` or matches `"release/*"`, the operation escalates to CRITICAL and requires both `confirmed: true` and a non-empty `reason` string.

---

### Test: Read File — with branch parameter

**Description:** `read_file` now accepts an optional `branch` parameter to read from a specific ref. Before v0.9.0 this parameter was missing and the field was silently ignored — all reads went to the default branch.

```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "github_operation",
      "arguments": {
        "operation": "read_file",
        "repo_name": "owner/repo",
        "file_path": "src/pipeline_test.py",
        "branch": "main",
        "context": {"github_token": "ghp_..."}
      }
    }
  }'
```

**Expected Response (parse `result.content[0].text`):**
```json
{
  "success": true,
  "operation": "read_file",
  "data": {
    "file_path": "src/pipeline_test.py",
    "content": "# Pipeline E2E test\ndef hello():\n    return \"pipeline works\"\n",
    "encoding": "utf-8",
    "size": 62,
    "sha": "...",
    "url": "https://github.com/owner/repo/blob/main/src/pipeline_test.py"
  }
}
```

**Expected HTTP Status:** 200

**Notes:** Verified live 2026-05-19. If `branch` is omitted, GitHub returns the file at the repository's default branch. `branch` accepts any valid Git ref: branch name, tag, or commit SHA.

---

## 2. Intelligence Layer Testing

### Test: Fuzzy Repository Matching - Exact Match

**Description:** Repository name exact match

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create issue in backend-api about database connection"
    }
  }'
```

**Expected Response (flat — the resolved repo full_name appears in the issue URL, not as a separate field):**
```json
{
  "success": true,
  "data": {
    "number": 1,
    "title": "Database connection",
    "url": "https://github.com/user/backend-api/issues/1",
    "state": "open"
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests exact repository name matching. `RepoDiscovery.fuzzy_search()` returns `confidence: 1.0, match_type: "exact"`.

### Test: Fuzzy Repository Matching - Close Match

**Description:** Repository name fuzzy match with high confidence

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create issue in bakend-api about database connection"
    }
  }'
```

**Expected Response (verified live 2026-05-15 with the typo `testin_devfroge` → `testing_devforge`):**
```json
{
  "success": true,
  "data": {
    "number": 6,
    "title": "Database connection",
    "url": "https://github.com/sidcollege/testing_devforge/issues/6",
    "state": "open"
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests fuzzy matching with typo correction (Levenshtein path). `repo_confidence` is internal agent state and **not exposed on the gateway envelope** — older docs that placed it at the top level were incorrect.

### Test: Fuzzy Repository Matching - Multiple Matches

**Description:** Multiple repositories match query, expect disambiguation

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create issue in api-repo about authentication"
    }
  }'
```

**Expected Response:**
```json
{
  "success": false,
  "data": {
    "status": "needs_clarification",
    "message": "Multiple repositories match your query:",
    "options": [
      {
        "full_name": "user/api-backend",
        "name": "api-backend",
        "confidence": 0.85,
        "match_type": "fuzzy"
      },
      {
        "full_name": "user/api-frontend",
        "name": "api-frontend", 
        "confidence": 0.82,
        "match_type": "fuzzy"
      }
    ]
  },
  "message": "github_operation execution failed: Multiple repositories match your query"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests disambiguation response when multiple matches found

### Test: Fuzzy Repository Matching - Below Threshold

**Description:** Repository name confidence too low — agent returns `needs_clarification` disambiguation (via `format_disambiguation_response`), not a `rejected` payload. The 65% rejection banner only fires for low *intent* confidence in `format_rejection`.

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create issue in apx about something"
    }
  }'
```

**Expected Response:**
```json
{
  "success": false,
  "data": {
    "status": "needs_clarification",
    "message": "Multiple repositories match your query:",
    "options": [
      {
        "full_name": "user/apex-service",
        "name": "apex-service",
        "confidence": 0.62,
        "match_type": "fuzzy"
      },
      {
        "full_name": "user/api-x",
        "name": "api-x",
        "confidence": 0.58,
        "match_type": "fuzzy"
      }
    ]
  },
  "message": "github_operation execution failed: Multiple repositories match your query"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests `get_best_match` falling below the 0.85 confidence threshold — returns disambiguation options to the user.

### Test: Log Parser - Python Stack Trace

**Description:** Parse Python error log to create issue

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create issue from this error",
      "context": {
        "error_log": "Traceback (most recent call last):\n  File \"app.py\", line 10, in main\n    result = 1/0\nZeroDivisionError: division by zero"
      }
    }
  }'
```

**Expected Response (verified live 2026-05-15 via MCP — gateway envelope is flat):**
```json
{
  "success": true,
  "data": {
    "number": 5,
    "title": "[ZeroDivisionError] division by zero (app.py:42)",
    "body": "## Error Details\n\n**Type:** `ZeroDivisionError`  \n**Message:** division by zero  \n**Language:** python\n**Location:** `app.py:42` in `main()`\n\n## Stack Trace\n\n```python\nTraceback (most recent call last):\n  File \"app.py\", line 42, in main\n    result = 1/0\nZeroDivisionError: division by zero\n```\n",
    "state": "open",
    "url": "https://github.com/sidcollege/testing_devforge/issues/5",
    "labels": ["bug", "P1-high", "python"],
    "assignees": [],
    "created_at": "2026-05-15T14:47:54+00:00",
    "audit_id": "audit_20260515_33ad36a0877e",
    "timeline": {"total_duration_ms": 3687.76, "events": [...]}
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Verified live. Tests Python stack trace parsing and issue creation. Labels are auto-suggested by `_suggest_labels()` based on the error type and language.

### Test: Log Parser - JavaScript Error

**Description:** Parse JavaScript error log to create issue

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "make an issue for this js error",
      "context": {
        "error_log": "TypeError: Cannot read property '\''x'\'' of undefined\n    at Object.myFunction (app.js:15:10)"
      }
    }
  }'
```

**Expected Response (flat envelope; same shape as the Python case):**
```json
{
  "success": true,
  "data": {
    "number": 2,
    "title": "[TypeError] Cannot read property '\''x'\'' of undefined (app.js:15)",
    "body": "...",
    "state": "open",
    "url": "https://github.com/user/repo/issues/2",
    "labels": ["bug", "P1-high", "javascript"],
    "assignees": []
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests JavaScript error parsing. Same labelling pattern as Python — `[bug, P1-high, <language>]`.

---

## 3. Confidence Gating

### Test: Low Intent Confidence

**Description:** Query with low intent classification confidence

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "do something with github"
    }
  }'
```

**Expected Response:**
```json
{
  "success": false,
  "data": {
    "status": "needs_confirmation",
    "confidence": 0.75,
    "threshold": 0.85,
    "reason": "Low confidence (0.75 < 0.85) - user confirmation required",
    "message": "Confidence below threshold (75% < 85%)\n\nPlease review and confirm:",
    "instruction": "Respond with '\''yes'\'' to proceed or '\''no'\'' to cancel"
  },
  "message": "github_operation execution failed: Low confidence - needs confirmation"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests intent classification confidence gating

### Test: Low Commit Confidence

**Description:** Commit with low confidence triggers draft PR creation

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "commit these changes",
      "context": {
        "diff": "minimal changes"
      }
    }
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "create_pull_request",
    "data": {
      "title": "WIP: Update files",
      "draft": true
    },
    "_create_draft_reason": "Medium commit confidence - creating draft PR instead"
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests medium confidence handling for commits

---

## 4. Phase 2 Tools

The Phase 2 specialized tools (`generate_changelog`, `analyze_ci_failure`, `scaffold_repo`) are **not** registered as standalone gateway tool names. They are commented out in `SUPPORTED_TOOLS` (`src/api/routers/__init__.py`). They are only reachable by sending `"name": "github_operation"` with a natural-language `query` that the LLM can route to the corresponding internal `operation` string. The agent then dispatches to `generate_changelog_invoke` / `analyze_ci_failure_invoke` / `scaffold_repository_invoke`.

> **Note:** The agent emits `scaffold_repo` as the operation name (matches `agent.py` and `schemas.py`). The `manifests/devforge.json` entry name is `scaffold_repository` — this is a known mismatch.

### Test: Changelog Generator (via github_operation)

**Description:** Generate changelog between tags by routing through the LLM-driven `github_operation` tool.

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "generate a changelog for user/my-project from tag v1.0.0 to v1.1.0"
    }
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "generate_changelog",
    "changelog": "# Changelog: v1.0.0 -> v1.1.0\n\n**Generated:** 2024-01-15 10:30:45\n**Total Changes:** 12 commits\n\n---\n\n## Features\n\n- **auth**: add OAuth support ([abc123](https://github.com/user/my-project/commit/abc123)) by @dev1\n\n## Bug Fixes\n\n- fix null pointer in login ([def456](https://github.com/user/my-project/commit/def456)) by @dev2",
    "from_tag": "v1.0.0",
    "to_tag": "v1.1.0"
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests LLM routing into the internal `generate_changelog` operation.

### Test: CI Diagnostics (via github_operation)

**Description:** Analyze a CI failure by routing through the LLM-driven `github_operation` tool.

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "analyze the CI failure in user/my-project for run id 123456789"
    }
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "analyze_ci_failure",
    "repo": "user/my-project",
    "failures": [
      {
        "type": "test_failure",
        "message": "AssertionError: Expected 200, got 500",
        "severity": "high"
      }
    ],
    "suggested_fixes": [
      {
        "title": "Fix test assertion",
        "description": "Update test to expect correct status code",
        "confidence": 0.92,
        "auto_fixable": true,
        "commands": ["npm test"]
      }
    ],
    "auto_fixable_count": 1
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests LLM routing into the internal `analyze_ci_failure` operation.

### Test: Repository Scaffolder (via github_operation)

**Description:** Scaffold a new repository from a template by routing through the LLM-driven `github_operation` tool.

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "scaffold a new fastapi microservice repo called new-microservice for user management"
    }
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "scaffold_repo",
    "repo_url": "https://github.com/user/new-microservice",
    "repo_name": "user/new-microservice",
    "template_used": "fastapi",
    "files_created": 4,
    "ci_workflows": 1
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests LLM routing into the internal `scaffold_repo` operation. The manifest entry name is `scaffold_repository`.

---

## 5. Error Handling Matrix

### Test: Needs Clarification Response

**Description:** Trigger needs_clarification response

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create repo api"
    }
  }'
```

**Expected Response:**
```json
{
  "success": false,
  "data": {
    "status": "needs_clarification",
    "message": "Multiple repositories match your query:",
    "options": [...]
  },
  "message": "github_operation execution failed: Multiple repositories match your query"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests disambiguation flow

### Test: Malformed JSON

**Description:** Send malformed JSON payload. FastAPI / Pydantic intercepts the request before the gateway handler runs and returns its own 422 validation error.

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "missing closing brace"
  }'
```

**Expected Response (FastAPI/Pydantic shape):**
```json
{
  "detail": [
    {
      "type": "json_invalid",
      "loc": ["body", 0],
      "msg": "JSON decode error",
      "input": {},
      "ctx": {"error": "Expecting ',' delimiter"}
    }
  ]
}
```

**Expected HTTP Status:** 422

**Notes:** Confirms FastAPI's built-in JSON validation runs ahead of the gateway handler — there is no custom "Invalid JSON payload" 400.

### Test: Missing Name Field (and `apiName` alias)

**Description:** `GatewayRequest` accepts **either** `name` or `apiName`. Omitting both fails Pydantic validation before reaching the `SUPPORTED_TOOLS` lookup.

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "arguments": {
      "query": "list repos"
    }
  }'
```

**Expected Response (verified live 2026-05-15):**
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "Value error, Either 'name' or 'apiName' must be provided",
      "input": {"arguments": {"query": "list repos"}},
      "ctx": {"error": {}}
    }
  ]
}
```

**Expected HTTP Status:** 422

**Notes:** Tests required-field validation at the Pydantic layer. The `apiName` alias was added to support MCP-discovery clients that emit camelCase keys. Older docs that expected HTTP 400 with `"Tool 'None' not found"` were incorrect — that path is unreachable because Pydantic rejects the request first.

### Test: Wrong Tool Name

**Description:** Non-existent tool name

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "nonexistent_tool",
    "arguments": {
      "query": "some query"
    }
  }'
```

**Expected Response (verified live 2026-05-15 — Python-style list literal in the message body):**
```json
{
  "success": false,
  "data": null,
  "message": "Tool '\''nonexistent_tool'\'' not found. Available tools: ['\''generate_data'\'', '\''github_operation'\'', '\''refine_prompt'\'', '\''generate_cheatsheet'\'']"
}
```

**Expected HTTP Status:** 400

**Notes:** Tests tool name validation. Available tools list reflects the actual `SUPPORTED_TOOLS` registration in `src/api/routers/__init__.py:45-49`. Note: the message renders the list via Python `str()` so the elements are single-quoted — this is a string format quirk, not a JSON array.

---

## 6. Edge Case & Security Testing

### Test: Extremely Long Query

**Description:** Test with very long query string

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "list repositories and then create a new repository with a very long description that exceeds normal limits and includes special characters like @#$%^&*()_+-={}[]|\\:;\"'\''<>?,./ and repeated words repeated words repeated words to test truncation and processing limits"
    }
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "data": {...},
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests input length handling

### Test: Invalid Characters in Input

**Description:** Test with potentially problematic characters

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create repo \"test; DROP TABLE users; --\""
    }
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "create_repo",
    "data": {
      "name": "test; DROP TABLE users; --",
      "full_name": "user/test; DROP TABLE users; --"
    }
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests SQL injection-like input sanitization

### Test: Null Arguments

**Description:** `arguments: null` no longer reaches the handler. `GatewayRequest` now has a Pydantic validator that rejects `None` upfront. This is a tightening from earlier behavior where `None` was silently coerced to `{}`.

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": null
  }'
```

**Expected Response (verified live 2026-05-15):**
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "arguments"],
      "msg": "Value error, '\''arguments'\'' must be str or dict, got NoneType",
      "input": null,
      "ctx": {"error": {}}
    }
  ]
}
```

**Expected HTTP Status:** 422

**Notes:** Tests Pydantic-level rejection of null `arguments`. Older docs that expected HTTP 400 with `"github_operation requires 'query' parameter"` are now stale — that path is unreachable because the request fails validation before reaching the handler.

### Test: Wrong HTTP Method

**Description:** Use GET instead of POST

```bash
curl -X GET http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>"
```

**Expected Response:**
```json
{"detail":"Method Not Allowed"}
```

**Expected HTTP Status:** 405

**Notes:** Tests HTTP method validation. Same response on `/mcp`.

### Test: Missing x-api-key Header

**Description:** Omit the `x-api-key` header — the request is rejected by `APIKeyAuthMiddleware` before reaching any route handler.

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github_operation",
    "arguments": {"query": "list repos"}
  }'
```

**Expected Response (verified live 2026-05-15):**
```json
{"success": false, "detail": "API Key missing"}
```

**Expected HTTP Status:** 401

**Notes:** Same response on `/mcp`. Both endpoints are gated by the same middleware.

---

## 7. MCP Equivalents

Every gateway call above has a corresponding `/mcp` JSON-RPC form. The agent payload is identical; the envelope differs.

### Envelope shape

```json
{
  "jsonrpc": "2.0",
  "id": <int>,
  "result": {
    "content": [{"type": "text", "text": "<JSON-encoded agent payload>"}],
    "isError": false
  }
}
```

Clients must `JSON.parse(result.content[0].text)` to get the agent payload. **Risk-gate blocks bypass `result.content` entirely** and return a JSON-RPC `error` envelope (see below).

### Test: tools/list — verify registered tools

```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

**Expected (verified live 2026-05-15):** tools array contains exactly `[generate_data, github_operation, refine_prompt, generate_cheatsheet]`. Phase-2 tool names (`generate_changelog`, `analyze_ci_failure`, `scaffold_repository`) are **NOT** in the list.

### Test: MCP tools/call — list_repos

```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 11,
    "method": "tools/call",
    "params": {
      "name": "github_operation",
      "arguments": {
        "query": "list my repositories",
        "context": {"github_token": "ghp_..."}
      }
    }
  }'
```

**Expected Response (parse `result.content[0].text` to get the agent payload):**
```json
{
  "jsonrpc": "2.0",
  "id": 11,
  "result": {
    "content": [
      {"type": "text", "text": "{\"success\": true, \"operation\": \"list_repos\", \"data\": [...], \"audit_id\": \"audit_...\", \"timeline\": {...}}"}
    ],
    "isError": false
  }
}
```

> **Note:** The MCP payload **includes a top-level `operation` key** inside the JSON string (e.g., `"operation": "list_repos"`). The gateway envelope does not.

### Test: MCP risk-gate block — HIGH operation without confirmed

```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 13,
    "method": "tools/call",
    "params": {
      "name": "github_operation",
      "arguments": {
        "query": "create a new public repository named demo-repo",
        "context": {"github_token": "ghp_..."}
      }
    }
  }'
```

**Expected Response (verified live 2026-05-15 — JSON-RPC error, NOT result.content):**
```json
{
  "jsonrpc": "2.0",
  "id": 13,
  "error": {
    "code": -32603,
    "message": "Risk gate blocked: Operation create_repo requires: confirmed=true"
  }
}
```

> **CRITICAL for frontend integrators:** the MCP path collapses every risk-gate block to a JSON-RPC `-32603` error. The `audit_id` and `timeline` payload that the gateway path returns on blocks is **NOT** available on `/mcp`. If you need the audit trail on blocked operations, use `/api/gateway` instead.

### Test: MCP risk-gate block — CRITICAL operation without confirmed/reason

```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 14,
    "method": "tools/call",
    "params": {
      "name": "github_operation",
      "arguments": {
        "query": "delete the repository owner/some-repo",
        "context": {"github_token": "ghp_..."}
      }
    }
  }'
```

**Expected Response (verified live):**
```json
{
  "jsonrpc": "2.0",
  "id": 14,
  "error": {
    "code": -32603,
    "message": "Risk gate blocked: Operation delete_repo requires: confirmed=true, reason (non-empty string)"
  }
}
```

### Test: MCP wrong tool name

```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 16,
    "method": "tools/call",
    "params": {"name": "nonexistent_tool", "arguments": {}}
  }'
```

**Expected Response (verified live):**
```json
{
  "jsonrpc": "2.0",
  "id": 16,
  "error": {
    "code": -32602,
    "message": "Tool not found: nonexistent_tool"
  }
}
```

> Compare to the gateway path which returns HTTP 400 with the full available-tools list in the message. MCP returns just the JSON-RPC `-32602` "Invalid params" code with a bare name.

### Test: MCP Phase-2 tool names are NOT callable

`name: "generate_changelog"`, `name: "analyze_ci_failure"`, `name: "scaffold_repository"` all return `-32602 "Tool not found: <name>"` on MCP. They are only reachable as **internal operation strings** that the LLM may pick when you call `name: "github_operation"` with a natural-language query like _"generate a changelog from v1.0.0 to v1.1.0 for user/my-project"_.

---

## 8. Live verification matrix (2026-05-19)

| Scenario | `/api/gateway` | `/mcp` |
|----------|----------------|--------|
| Wrong tool name | HTTP 400 `{success:false, data:null, message:"Tool 'x' not found. Available tools: [...]"}` | JSON-RPC `error.code = -32602`, `message:"Tool not found: x"` |
| Missing `name`/`apiName` | HTTP 422 Pydantic `"Either 'name' or 'apiName' must be provided"` | (gateway-only) |
| Malformed JSON | HTTP 422 Pydantic `json_invalid` | HTTP 422 same |
| `arguments: null` | HTTP 422 Pydantic `"'arguments' must be str or dict, got NoneType"` | (gateway-only) |
| Missing `x-api-key` | HTTP 401 `{success:false, detail:"API Key missing"}` | HTTP 401 same |
| GET instead of POST | HTTP 405 `{detail:"Method Not Allowed"}` | HTTP 405 same |
| Risk-gate block (HIGH) | HTTP 200 `{success:false, data:{audit_id, timeline}, message:"Risk gate blocked: ..."}` | JSON-RPC `error.code = -32603`, no `audit_id` exposed |
| Risk-gate block (CRITICAL) | Same as HIGH | Same as HIGH |
| Disambiguation (multi-repo match) | HTTP 200 `{success:false, data:{...}, message:"Multiple repositories match your query:"}` | Wrapped inside `result.content[0].text` |
| Successful operation | `{success:true, data:<flat agent payload>, message:"github_operation executed successfully"}` | `{result:{content:[{type:"text",text:"<json>"}],isError:false}}` — JSON string contains `operation` key |

### Live-verified operations (2026-05-19 — `sidcollege/testing_devforge` with demo PAT)

| Operation | Call type | Result |
|-----------|-----------|--------|
| `list_repos` | NL | ✅ |
| `create_branch` | structured | ✅ `pipeline-e2e-test` from `main` |
| `commit_file` | structured | ✅ `src/pipeline_test.py` on feature branch |
| `read_file` (with `branch`) | structured | ✅ read from `main` after merge |
| `create_pull_request` | structured | ✅ PR #8 created |
| `merge_pr` (squash, feature branch) | structured | ✅ PR #7 merged, SHA `9faaacfa` |
| `merge_pr` (`base=main`) blocked | structured | ✅ HIGH gate fires without `confirmed` |
| `merge_pr` (full merge, PR #8) | structured | ✅ SHA `4d2347ade0b9` |
| `delete_branch` blocked | structured | ✅ HIGH gate fires without `confirmed` |
| `delete_branch` with `confirmed=true` | structured | ✅ `delete-me-test` deleted |
| `delete_branch main` | structured | ✅ CRITICAL gate fires (needs `confirmed`+`reason`) |
| `delete_repo` | structured | ✅ CRITICAL gate fires without `confirmed`+`reason` |
| `generate_changelog` | NL | ✅ 4 commits in markdown |
| `browse_files` | structured | ✅ root listing with `src/` dir |
| `search_code` | structured | ✅ (GitHub search index lag normal) |

---

## 9. Changelog

| Date | Change |
|------|--------|
| 2026-05-19 (V12) | **v0.9.0.** Added `merge_pr` tests (MEDIUM pass, HIGH block on `base=main`, CRITICAL escalation on `base=production`). Added `read_file` with `branch` parameter test. Updated §8 verification matrix with full live-verified op table (13 structured ops). Noted `None.lower()` bug fix in contextual risk gate. |
| 2026-05-15 | Live MCP + gateway verification. Updated all response shapes to match live behavior (flat `data` on gateway, wrapped on MCP). Documented MCP risk-gate error shape (`-32603`). Removed fabricated `repo_confidence` top-level field. Added §7 MCP Equivalents and §8 verification matrix. Tightened §5 to reflect Pydantic-level validation (HTTP 422 for malformed JSON, missing `name`, null `arguments`). Added `apiName` alias note. Added missing `x-api-key` test. |
| 2026-05-08 | Initial doc-vs-code review by `_reviews/github_operation_review.md` flagged port mismatches, missing `x-api-key`, fabricated Phase-2 gateway calls, and other drift. Most issues resolved in this revision. |
