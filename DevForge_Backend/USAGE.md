# DevForge Tools - Usage Guide

## Phase 2: Specialized GitOps Tools (v0.8.0)

This guide covers the three specialized GitHub automation tools introduced in Phase 2.

---

## Tool 1: `generate_changelog`

Generate release notes and changelogs from git history between tags or commits.

### Required GitHub Token Scopes
- `repo` (read access to repository)

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `repo` | string | ✅ | - | Repository name (format: `user/repo` or `org/repo`) |
| `from_tag` | string | ✅ | - | Start tag or commit SHA |
| `to_tag` | string | ❌ | `HEAD` | End tag or commit SHA |
| `format` | string | ❌ | `markdown` | Output format (`markdown` or `json`) |

### Example cURL Request

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "generate_changelog",
    "arguments": {
      "repo": "myorg/myapp",
      "from_tag": "v1.0.0",
      "to_tag": "v1.1.0",
      "format": "markdown"
    }
  }'
```

### Example Response

```json
{
  "success": true,
  "changelog": "# Changelog: v1.0.0 → v1.1.0\n\n## ✨ Features\n- **auth**: implement JWT rotation\n...",
  "commits_analyzed": 42,
  "categories": ["✨ Features", "🐛 Bug Fixes", "📚 Documentation"],
  "audit_id": "audit_20251212_abc123",
  "timeline": {...}
}
```

### Features
- **Conventional Commits Parsing**: Automatically categorizes commits by type (feat, fix, docs, etc.)
- **Categorized Output**: Groups changes into user-friendly categories with emojis
- **Multiple Formats**: Supports both Markdown and JSON output
- **Audit Trail**: Every operation tracked with `audit_id` and timeline

---

## Tool 2: `analyze_ci_failure`

Analyze CI/CD pipeline failures and suggest fixes with auto-fix policy enforcement.

### Required GitHub Token Scopes
- `repo` (read access to workflows)
- `actions:read` (read workflow runs - may be included in `repo`)

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `repo` | string | ✅ | - | Repository name (format: `user/repo`) |
| `run_id` | integer | ❌ | latest failed | Specific workflow run ID to analyze |
| `pr_number` | integer | ❌ | - | PR number (alternative to `run_id`) |

### Example cURL Request

```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "analyze_ci_failure",
    "arguments": {
      "repo": "myorg/myapp",
      "run_id": 12345678
    }
  }'
```

### Example Response

```json
{
  "success": true,
  "failures": [
    {
      "type": "test_failure",
      "message": "AssertionError: Login test failed",
      "severity": "high"
    }
  ],
  "suggested_fixes": [
    {
      "title": "Fix login test assertion",
      "description": "Update test expectations to match new authentication flow",
      "confidence": 0.92,
      "auto_fixable": false,
      "commands": null
    }
  ],
  "auto_fixable_count": 0,
  "high_confidence_count": 1,
  "audit_id": "audit_20251212_def456"
}
```

### Auto-Fix Policy

Fixes are marked as `auto_fixable: true` **only if**:
1. Confidence ≥ **0.95** (95% or higher)
2. Type is one of: `["format", "dependency_patch", "lint"]`

All other fixes require manual review or will be suggested as draft PRs.

**Environment Variables:**
```bash
GITOPS_AUTO_FIX_THRESHOLD=0.95  # Minimum confidence for auto-fix
GITOPS_AUTO_FIX_TYPES=format,dependency_patch,lint  # Comma-separated allowed types
```

---

## Tool 3: `scaffold_repository`

Create new repositories from templates with CI/CD setup, token validation, and idempotency checks.

### Required GitHub Token Scopes
- `repo` (full repository access)
- `admin:org` (if creating in organization)
- `delete_repo` (for rollback on failure)

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | ✅ | - | Repository name (lowercase, hyphens/underscores/dots only) |
| `template` | string | ✅ | - | Template: `fastapi`, `react`, `nextjs`, `microservice`, `docs` |
| `description` | string | ❌ | (template desc) | Repository description (max 200 chars) |
| `private` | boolean | ❌ | `false` | Whether repository should be private |
| `force` | boolean | ❌ | `false` | Force creation even if repo exists |

### Example cURL Request

```bash
curl -X POST localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "scaffold_repository",
    "arguments": {
      "name": "my-new-api",
      "template": "fastapi",
      "description": "My new FastAPI microservice",
      "private": false
    }
  }'
```

### Example Response (Sync)

```json
{
  "success": true,
  "repo_url": "https://github.com/myorg/my-new-api",
  "repo_name": "myorg/my-new-api",
  "template_used": "fastapi",
  "files_created": 4,
  "ci_workflows": 1,
  "clone_url": "https://github.com/myorg/my-new-api.git",
  "audit_id": "audit_20251212_ghi789"
}
```

### Example Response (Async - Large Template)

```json
{
  "success": true,
  "mode": "async",
  "job_id": "job_abc123",
  "status_endpoint": "/api/jobs/job_abc123",
  "message": "Large template (127 files). Job enqueued.",
  "audit_id": "audit_20251212_jkl012"
}
```

### Templates Available

| Template | Description | Files | CI |
|----------|-------------|-------|-------------|
| `fastapi` | FastAPI microservice with PostgreSQL | `main.py`, `requirements.txt`, `README` | ✅ Python CI |
| `react` | React application with TypeScript | `package.json`, configs | ✅ Node CI |
| `nextjs` | Next.js application | `package.json`, Next config | ✅ Build CI |
| `microservice` | Generic microservice with Docker | `Dockerfile`, `requirements.txt` | ❌ |
| `docs` | Documentation site with mkdocs | `mkdocs.yml`, `docs/` | ❌ |

### Security Features

1. **Token Scope Validation**: Checks required scopes before execution
2. **Idempotency**: Returns error if repo exists (unless `force=true`)
3. **Input Sanitization**:
   - Repo name: `^[a-z0-9._-]+$` regex
   - Description: Max 200 chars, HTML stripped
4. **Async Fallback**: Templates >50 files automatically enqueued as async jobs
5. **Rollback on Failure**: Deletes repo if CI setup fails

### Environment Variables

```bash
MAX_SYNC_WORK_UNITS=50  # Threshold for async fallback
WORK_UNIT_TIMEOUT_SECONDS=10  # Max time per work unit
```

---

## Error Handling

All tools follow standardized error responses:

```json
{
  "success": false,
  "error": "Error message here",
  "audit_id": "audit_20251212_xyz",
  "timeline": {...}
}
```

Common errors:
- `PermissionError`: Missing GitHub token scopes
- `ValueError`: Invalid input (repo name, template, etc.)
- `Exception`: GitHub API errors, network issues

---

## Monitoring Async Jobs

For async operations (large scaffolds), monitor job status:

```bash
curl http://localhost:8000/api/jobs/{job_id}
```

Response:
```json
{
  "job_id": "job_abc123",
  "status": "completed",
  "progress": 100,
  "result": {...},
  "created_at": "2025-12-12T12:00:00",
  "completed_at": "2025-12-12T12:01:30"
}
```

---

**Last Updated:** December 12, 2025  
**Version:** DevForge v0.8.0
