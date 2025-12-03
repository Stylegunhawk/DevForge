# github_operation - GitHub Automation Tool

**Tool Name:** `github_operation`  
**Version:** 0.7.0  
**Phase:** 3.3 (GitHub Operations)  
**Status:** ✅ Production Ready

---

## Overview

The `github_operation` tool automates GitHub repository operations using natural language commands. It integrates with GitHub's API via PyGithub to perform common developer workflows like listing repos, creating issues, committing files, and opening pull requests.

---

## Features

- ✅ Natural language query parsing
- ✅ List repositories with filters
- ✅ Create repositories
- ✅ Create and manage issues
- ✅ Commit files to repositories
- ✅ Create pull requests
- ✅ Token-based authentication
- ✅ LLM-powered intent detection

---

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | ✅ Yes | Natural language description of GitHub action |

### Query Examples

- `"list my repos"`
- `"list public repositories"`
- `"create a new repository called my-project"`
- `"create issue in my-repo titled 'Bug fix'"`
- `"commit hello.py to my-repo"`
- `"create PR from feature-branch to main in my-repo"`

---

## Setup

### GitHub Token Configuration

1. Generate a Personal Access Token (PAT) at https://github.com/settings/tokens
2. Required scopes:
   - `repo` - Full repository access
   - `admin:org` - Organization operations (optional)
3. Add to `.env` file:

```bash
GITHUB_TOKEN=ghp_your_token_here
GITHUB_USERNAME=your_username
```

---

## API Usage

### List Repositories

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "list my repositories"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "operation": "list_repos",
    "repos": [
      {
        "name": "my-project",
        "full_name": "username/my-project",
        "private": false,
        "url": "https://github.com/username/my-project"
      }
    ]
  }
}
```

### Create Repository

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create a new repository called awesome-project with description 'My awesome project'"
    }
  }'
```

### Create Issue

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create an issue in my-repo titled 'Fix login bug' with body 'Users cannot login with special characters in password'"
    }
  }'
```

### Commit File

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "commit README.md to my-repo with message 'Update documentation'"
    }
  }'
```

### Create Pull Request

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create a pull request from feature-auth to main in my-repo titled 'Add authentication'"
    }
  }'
```

---

## Lobe Chat Usage

### List Repos
```
"Show me all my GitHub repositories"
"What are my public repos?"
```

### Create Repo
```
"Create a new GitHub repository called 'demo-app' with description 'Demo application'"
```

### Create Issue
```
"Create a bug report in my-project about the login issue"
```

### Workflow Automation
```
"Create an issue for refactoring the auth module in backend-api repo"
```

---

## Supported Operations

### 1. List Repositories

**Query patterns:**
- `"list my repos"`
- `"show all repositories"`
- `"list public repos"`
- `"show private repositories"`

**Filters:**
- Public/Private
- Affiliation (owner, collaborator, member)
- Sorted by (created, updated, pushed, full_name)

### 2. Create Repository

**Query pattern:**
```
"create [repo_name] with description '[desc]' [private/public]"
```

**Options:**
- Repository name (required)
- Description (optional)
- Private/Public (default: public)
- Initialize with README (default: true)

### 3. Create Issue

**Query pattern:**
```
"create issue in [repo] titled '[title]' with body '[body]'"
```

**Fields:**
- Title (required)
- Body/Description (optional)
- Labels (optional)
- Assignees (optional)

### 4. Commit File

**Query pattern:**
```
"commit [file_path] to [repo] with message '[msg]'"
```

**Parameters:**
- File path (required)
- Commit message (required)
- Branch (default: main)
- Create/Update file

### 5. Create Pull Request

**Query pattern:**
```
"create PR from [head] to [base] in [repo] titled '[title]'"
```

**Fields:**
- Head branch (source)
- Base branch (target)
- Title (required)
- Body (optional)

---

## Natural Language Processing

The tool uses an LLM (`qwen3-coder:480b-cloud`) to parse natural language queries:

```
User Query: "create an issue in my-repo about the login bug"
    ↓
LLM Parsing
    ↓
Extracted Intent:
{
  "operation": "create_issue",
  "repo": "my-repo",
  "title": "Login Bug",
  "body": "Issue regarding login functionality"
}
    ↓
GitHub API Call
    ↓
Response
```

---

## Use Cases

### 1. Automated Issue Creation
```
"Create technical debt issues for refactoring in all my active projects"
```

### 2. Repository Management
```
"List all my private repositories that haven't been updated in 6 months"
```

### 3. Quick Commits
```
"Commit the updated config.json file to production-app"
```

### 4. PR Workflow
```
"Create a pull request from dev to staging in my-api repository"
```

### 5. Team Coordination
```
"Create an issue in team-docs about updating the onboarding guide"
```

---

## Error Handling

### Missing Token

```bash
# No GITHUB_TOKEN in .env
```

**Response:**
```json
{
  "success": false,
  "message": "GitHub token not configured. Set GITHUB_TOKEN in .env"
}
```

### Repository Not Found

```json
{
  "query": "create issue in nonexistent-repo"
}
```

**Response:**
```json
{
  "success": false,
  "message": "Repository not found: nonexistent-repo"
}
```

### Invalid Permissions

```json
{
  "query": "delete repository important-repo"  // Not supported
}
```

**Response:**
```json
{
  "success": false,
  "message": "Operation not permitted or unsupported"
}
```

---

## Security Best Practices

1. **Token Storage**
   - Never commit tokens to git
   - Use `.env` files (add to `.gitignore`)
   - Rotate tokens regularly

2. **Scope Limitation**
   - Use minimum required scopes
   - Avoid `admin` scopes unless needed

3. **Access Control**
   - Use personal tokens for personal repos
   - Use organization tokens for team repos

4. **Audit Logging**
   - All operations are logged server-side
   - Review GitHub audit log regularly

---

## Implementation Details

### Technology Stack
- **PyGithub** 2.1.1+ - GitHub API wrapper
- **LangChain** - LLM integration for query parsing
- **Model:** `qwen3-coder:480b-cloud` (code-focused LLM)

### Code Location
- Agent: `src/agents/github/agent.py`
- Tools: `src/tools/github/tools.py`
- Tests: `tests/test_github.py`

---

## Examples

### List Filtered Repos

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "list my public repositories sorted by update date"
    }
  }'
```

### Create Private Repo

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create a private repository called internal-tools"
    }
  }'
```

### Bug Report Issue

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "create a bug report in my-app titled 'Memory leak in auth service' with high priority label"
    }
  }'
```

---

## Testing

### Run Tests
```bash
pytest tests/test_github.py -v
```

### Test Coverage
- ✅ Repository operations (10 tests)
- ✅ Issue creation
- ✅ File commits
- ✅ Pull requests
- ✅ Error handling

### Mock Testing
Tests use mock PyGithub objects to avoid real API calls.

---

## Rate Limits

GitHub API has rate limits:
- **Authenticated:** 5,000 requests/hour
- **Unauthenticated:** 60 requests/hour

**Best Practices:**
- Always use authentication
- Cache repository lists
- Batch operations when possible

---

## Troubleshooting

**Issue:** "401 Unauthorized"  
**Solution:** Check GITHUB_TOKEN is valid and has correct scopes

**Issue:** "404 Not Found"  
**Solution:** Verify repository name includes owner (e.g., `username/repo`)

**Issue:** Slow query parsing  
**Solution:** Use more specific natural language queries

---

## Related Tools

- `generate_data` - Generate mock repository data
- `refine_prompt` - Optimize GitHub operation queries (use `code` domain)

---

**Last Updated:** December 2, 2025  
**Maintainer:** DevForge Team  
**Feedback:** Create an issue in the repository
