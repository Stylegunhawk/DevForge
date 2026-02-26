# github_operation - Gateway Curl Test Suite

## Base Configuration
- Base URL: `http://localhost:8000` (adjust as needed)
- Required headers: `"Content-Type: application/json"`
- Sample token setup: Requires `GITHUB_TOKEN` environment variable configured in backend

---

## 1. Core Operations

### Test: List Repositories - Basic Request

**Description:** Basic repository listing request

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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

**Description:** Repository name confidence too low

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
    "status": "rejected",
    "message": "❌ Cannot proceed safely\n\nConfidence score (65%) is too low. Please:\n1. Provide more specific information\n2. Use exact repository/resource names\n3. Add additional context"
  },
  "message": "github_operation execution failed: Confidence too low"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests confidence threshold enforcement

### Test: Log Parser - Python Stack Trace

**Description:** Parse Python error log to create issue

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
    "message": "⚠️ Confidence below threshold (75% < 85%)\n\nPlease review and confirm:",
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
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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

### Test: Changelog Generator

**Description:** Generate changelog between tags

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_changelog",
    "arguments": {
      "repo": "user/my-project",
      "from_tag": "v1.0.0",
      "to_tag": "v1.1.0"
    }
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "changelog": "# Changelog: v1.0.0 → v1.1.0\n\n**Generated:** 2024-01-15 10:30:45\n**Total Changes:** 12 commits\n\n---\n\n## ✨ Features\n\n- **auth**: add OAuth support ([abc123](https://github.com/user/my-project/commit/abc123)) by @dev1\n\n## 🐛 Bug Fixes\n\n- fix null pointer in login ([def456](https://github.com/user/my-project/commit/def456)) by @dev2",
    "from_tag": "v1.0.0",
    "to_tag": "v1.1.0"
  },
  "message": "generate_changelog executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests changelog generation tool

### Test: CI Diagnostics

**Description:** Analyze CI failure

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "analyze_ci_failure",
    "arguments": {
      "repo": "user/my-project",
      "run_id": 123456789
    }
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
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
  "message": "analyze_ci_failure executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests CI diagnostics tool

### Test: Repository Scaffolder

**Description:** Scaffold new repository from template

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "scaffold_repository",
    "arguments": {
      "name": "new-microservice",
      "template": "fastapi",
      "description": "New microservice for user management"
    }
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "repo_url": "https://github.com/user/new-microservice",
    "repo_name": "user/new-microservice",
    "template_used": "fastapi",
    "files_created": 4,
    "ci_workflows": 1
  },
  "message": "scaffold_repository executed successfully"
}
```

**Expected HTTP Status:** 200

**Notes:** Tests repository scaffolding tool

---

## 5. Error Handling Matrix

### Test: Needs Clarification Response

**Description:** Trigger needs_clarification response

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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

**Description:** Send malformed JSON payload

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "missing closing brace"
  }'
```

**Expected Response:**
```json
{
  "success": false,
  "data": null,
  "message": "github_operation execution error: Invalid JSON payload"
}
```

**Expected HTTP Status:** 400

**Notes:** Tests JSON validation

### Test: Missing Name Field

**Description:** Missing required "name" field

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "query": "list repos"
    }
  }'
```

**Expected Response:**
```json
{
  "success": false,
  "data": null,
  "message": "Tool '\''None'\'' not found. Available tools: [...]"
}
```

**Expected HTTP Status:** 400

**Notes:** Tests required field validation

### Test: Wrong Tool Name

**Description:** Non-existent tool name

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
  "message": "Tool '\''nonexistent_tool'\'' not found. Available tools: [\"generate_data\", \"retrieve_docs\", \"github_operation\", ...]"
}
```

**Expected HTTP Status:** 400

**Notes:** Tests tool name validation

---

## 6. Edge Case & Security Testing

### Test: Extremely Long Query

**Description:** Test with very long query string

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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

**Description:** Test with null arguments

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
  "message": "github_operation execution error: Arguments cannot be null"
}
```

**Expected HTTP Status:** 400

**Notes:** Tests null argument handling

### Test: Missing Content-Type Header

**Description:** Test without Content-Type header

```bash
curl -X POST http://localhost:8000/api/gateway \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "list repos"
    }
  }'
```

**Expected Response:**
```json
{
  "success": false,
  "data": null,
  "message": "github_operation execution error: Content-Type must be application/json"
}
```

**Expected HTTP Status:** 400

**Notes:** Tests content type validation

### Test: Wrong HTTP Method

**Description:** Use GET instead of POST

```bash
curl -X GET http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
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
