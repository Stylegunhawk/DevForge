# github_operation - Gateway Curl Test Suite

**Version:** 0.8.0
**Last Updated:** 2026-05-08

## Base Configuration
- Base URL: `http://localhost:8001` (adjust as needed)
- Required headers: `"Content-Type: application/json"` and `"x-api-key: <key>"` (gateway is gated by `APIKeyAuthMiddleware`)
- Sample token setup: `GITHUB_TOKEN` env var is an optional fallback; the per-request `context.github_token` (per-user PAT) is the canonical source

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

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "list_repos",
    "data": [
      {
        "name": "repo1",
        "full_name": "user/repo1",
        "description": "Repository 1",
        "private": false,
        "url": "https://github.com/user/repo1"
      }
    ]
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests basic LLM intent recognition for listing repositories

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

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "list_repos",
    "data": [...]
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests parameter extraction from natural language

### Test: Create Repository - Public Repo

**Description:** Create a new public repository

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create a new repository called my-awesome-project with description for awesome stuff"
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
      "name": "my-awesome-project",
      "full_name": "user/my-awesome-project",
      "description": "for awesome stuff",
      "private": false,
      "url": "https://github.com/user/my-awesome-project"
    }
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests repository creation with description parsing

### Test: Create Repository - Private Repo

**Description:** Create a new private repository

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create a private repository named secret-project"
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
      "name": "secret-project",
      "full_name": "user/secret-project",
      "private": true,
      "url": "https://github.com/user/secret-project"
    }
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests private repository creation

### Test: Create Issue - Valid Request

**Description:** Create an issue in a repository

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create issue in my-project about login failing with invalid credentials"
    }
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "create_issue",
    "data": {
      "number": 1,
      "title": "Login failing with invalid credentials",
      "state": "open",
      "url": "https://github.com/user/my-project/issues/1"
    }
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests issue creation with title parsing

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

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "create_issue",
    "data": {
      "number": 2,
      "title": "Bug in backend-service",
      "labels": ["bug", "priority"],
      "assignees": ["john"]
    }
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests label and assignee extraction

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

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "commit_file",
    "data": {
      "action": "created",
      "file_path": "README.md",
      "commit_message": "Add README.md"
    }
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests file creation with content parsing

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

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "commit_file",
    "data": {
      "action": "updated",
      "commit_message": "fix: resolve login authentication issue"
    },
    "commit_confidence": 0.92
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests commit generator with diff context

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

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "create_issue",
    "data": {
      "repo_name": "user/backend-api"
    }
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests exact repository name matching

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

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "create_issue",
    "data": {
      "repo_name": "user/backend-api"
    }
  },
  "repo_confidence": 0.92,
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests fuzzy matching algorithm with typo correction

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

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "create_issue",
    "data": {
      "title": "[ZeroDivisionError] division by zero (app.py:10)",
      "labels": ["bug", "python", "P1-high"],
      "body": "## Error Details\n\n**Type:** `ZeroDivisionError`\n**Message:** division by zero\n**Language:** python\n**Location:** `app.py:10` in `main()`\n\n## Root Cause Analysis\nThe error occurs when attempting to divide by zero..."
    }
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests Python stack trace parsing and issue creation

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

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "operation": "create_issue",
    "data": {
      "title": "[TypeError] Cannot read property '\''x'\'' of undefined (app.js:15)",
      "labels": ["bug", "javascript", "P1-high"]
    }
  },
  "message": "github_operation executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests JavaScript error parsing

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

### Test: Missing Name Field

**Description:** Missing required "name" field. `GatewayRequest.name` is a required `str` in Pydantic, so the request fails validation before reaching the `SUPPORTED_TOOLS` lookup.

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

**Expected Response:**
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "name"],
      "msg": "Field required"
    }
  ]
}
```

**Expected HTTP Status:** 422

**Notes:** Tests required field validation at the Pydantic layer.

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

**Expected Response:**
```json
{
  "success": false,
  "data": null,
  "message": "Tool '\''nonexistent_tool'\'' not found. Available tools: [\"generate_data\", \"github_operation\", \"refine_prompt\", \"generate_cheatsheet\"]"
}
```

**Expected HTTP Status:** 400

**Notes:** Tests tool name validation. Available tools list reflects the actual `SUPPORTED_TOOLS` registration in `src/api/routers/__init__.py`.

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

**Description:** Test with null arguments. The gateway coerces `None` to `{}` (`args = gateway_req.arguments or {}`), so the request reaches the `github_operation` handler and fails on the missing `query` parameter.

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": null
  }'
```

**Expected Response:**
```json
{
  "success": false,
  "data": null,
  "message": "github_operation requires '\''query'\'' parameter"
}
```

**Expected HTTP Status:** 400

**Notes:** Tests null argument handling — null is silently coerced to `{}`, then the missing `query` is reported.

### Test: Wrong HTTP Method

**Description:** Use GET instead of POST

```bash
curl -X GET http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <key>" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "list repos"
    }
  }'
```

**Expected Response:**
```json
{"detail":"Method Not Allowed"}
```

**Expected HTTP Status:** 405

**Notes:** Tests HTTP method validation
