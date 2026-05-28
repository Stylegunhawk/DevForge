# github_operation — MCP & Gateway Curl Test Suite

**Version:** 1.0.0
**Manifest Version:** 0.12.0
**Last Updated:** 2026-05-19
**Last Verified:** 2026-05-19 — Python MCP test suite 64/64 PASS, all 26 structured ops + backward compat NL + risk gate + error enrichment. Test script: `/tmp/gitops_v3_mcp_test.py`.

---

## Base Configuration

| Setting | Value |
|---------|-------|
| MCP endpoint | `POST http://localhost:8001/mcp/` |
| REST gateway | `POST http://localhost:8001/api/gateway` |
| Auth header | `x-api-key: <your-key>` |
| Content-Type | `application/json` |
| GitHub token | Per-request via `context.github_token` |

**Important: Endpoint differences**

| Feature | `POST /mcp` | `POST /api/gateway` |
|---------|-------------|---------------------|
| Protocol | JSON-RPC 2.0 | REST envelope |
| github_operation modes | NL + Structured | NL only (`query` required) |
| Response | `{result: {content: [{type:"text", text:"<json-str>"}]}}` | `{success, data, message}` |

Structured mode (`operation` key) is **MCP-only**. The REST gateway accepts only the natural-language path.

---

## Response Shapes

### MCP (`/mcp`)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [{"type": "text", "text": "{...agent JSON as string...}"}],
    "isError": false
  }
}
```

Client must `JSON.parse(result.content[0].text)` to get the agent payload. On tool errors the envelope uses `error` instead of `result`:

```json
{"jsonrpc": "2.0", "id": 1, "error": {"code": -32603, "message": "..."}}
```

### REST gateway (`/api/gateway`)

```json
{"success": true, "data": {...}, "message": "github_operation executed successfully"}
```

---

## §1 — MCP Protocol Layer

### Initialize

```bash
curl -s -X POST http://localhost:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

Expected:
```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","serverInfo":{"name":"DevForge","version":"0.9.0"},"capabilities":{"tools":{},"resources":{},"prompts":{}}}}
```

### tools/list — schema verification

```bash
curl -s -X POST http://localhost:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

The `github_operation` tool exposes a `oneOf` schema with two branches:

- **Branch 1 `Natural-language`**: requires `query` string
- **Branch 2 `Structured`**: requires `operation` (enum of 26 ops) + flat per-op params

Verified: 26 ops in the structured enum, NL branch present, 4 tools total.

### Protocol error cases

| Scenario | Payload | Expected code |
|----------|---------|--------------|
| Empty body | _(no body)_ | `-32700` Parse error |
| Malformed JSON | `{bad json}` | `-32700` Parse error |
| Wrong jsonrpc version | `"jsonrpc":"1.0"` | `-32600` Invalid Request |
| Unknown method | `"method":"foo/bar"` | `-32601` Method not found |
| Missing API key | _(omit x-api-key)_ | HTTP 401 |
| Wrong API key | `x-api-key: bad` | HTTP 401 |

---

## §2 — Structured Mode: READ ops (no confirmation required)

All structured calls: params go **flat** alongside `operation`, not nested.

```bash
# Correct ✅
{"operation":"list_branches","repo_name":"owner/repo","context":{"github_token":"..."}}

# Wrong ❌ — don't nest under "parameters"
{"operation":"list_branches","parameters":{"repo_name":"..."}}
```

### list_repos

```bash
curl -s -X POST http://localhost:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "jsonrpc":"2.0","id":1,"method":"tools/call",
    "params":{"name":"github_operation","arguments":{
      "operation":"list_repos",
      "context":{"github_token":"$GH_PAT"}
    }}
  }'
```

### list_repos with pagination

```bash
  "arguments":{"operation":"list_repos","page":2,"limit":5,"context":{"github_token":"..."}}
```

### list_branches

```bash
  "arguments":{"operation":"list_branches","repo_name":"owner/repo","context":{...}}
```

### browse_files

```bash
  "arguments":{"operation":"browse_files","repo_name":"owner/repo","path":".","context":{...}}
```

### read_file

```bash
  "arguments":{"operation":"read_file","repo_name":"owner/repo","file_path":"README.md","context":{...}}
```

Read from non-default branch:
```bash
  "arguments":{"operation":"read_file","repo_name":"owner/repo","file_path":"src/main.py","branch":"develop","context":{...}}
```

### search_code

```bash
  "arguments":{"operation":"search_code","query":"def authenticate","repo_name":"owner/repo","context":{...}}
```

Response includes `results`, `count`, `query`, `note` (lag warning for freshly-pushed code).

### list_pull_requests (v3)

```bash
  "arguments":{"operation":"list_pull_requests","repo_name":"owner/repo","state":"open","limit":10,"context":{...}}
```

`state`: `"open"` | `"closed"` | `"all"` (default: `"open"`)

### get_pr (v3)

```bash
  "arguments":{"operation":"get_pr","repo_name":"owner/repo","pr_number":42,"context":{...}}
```

Returns 404-enriched error if PR doesn't exist.

### list_commits (v3)

```bash
  "arguments":{"operation":"list_commits","repo_name":"owner/repo","branch":"main","limit":20,"context":{...}}
```

### get_commit (v3)

```bash
  "arguments":{"operation":"get_commit","repo_name":"owner/repo","sha":"abc1234def5678","context":{...}}
```

SHA must be ≥ 7 characters. Files list is capped at 100 entries; `files_truncated: true` flag set when repo commit has >100 files.

### list_releases (v3)

```bash
  "arguments":{"operation":"list_releases","repo_name":"owner/repo","limit":10,"context":{...}}
```

### list_webhooks (v3)

```bash
  "arguments":{"operation":"list_webhooks","repo_name":"owner/repo","context":{...}}
```

---

## §3 — Structured Mode: MEDIUM ops (no confirmation required)

### create_issue

```bash
  "arguments":{"operation":"create_issue","repo_name":"owner/repo","title":"Bug: login fails","body":"Steps to reproduce...","labels":["bug"],"context":{...}}
```

### add_comment (v3)

```bash
  "arguments":{"operation":"add_comment","repo_name":"owner/repo","issue_number":42,"body":"Comment text","context":{...}}
```

Note: `add_comment` is LOW risk (no confirmation) despite being a write operation.

### update_issue (v3)

```bash
  "arguments":{"operation":"update_issue","repo_name":"owner/repo","issue_number":42,"title":"New title","state":"closed","context":{...}}
```

At least one of `title`, `body`, `state`, `labels`, `assignees` is required. Omitting all returns `-32602`.

### close_issue (v3)

```bash
  "arguments":{"operation":"close_issue","repo_name":"owner/repo","issue_number":42,"context":{...}}
```

### commit_file

```bash
  "arguments":{"operation":"commit_file","repo_name":"owner/repo","file_path":"docs/README.md","content":"# Hello","commit_message":"docs: update README","branch":"feature/docs","context":{...}}
```

**Note:** `commit_file` to `main`/`master`/`production` is contextually escalated to HIGH and requires `risk_confirmed: true`.

### create_branch

```bash
  "arguments":{"operation":"create_branch","repo_name":"owner/repo","branch_name":"feature/my-feature","from_branch":"main","context":{...}}
```

### create_pull_request

```bash
  "arguments":{"operation":"create_pull_request","repo_name":"owner/repo","title":"feat: my feature","head":"feature/my-feature","base":"main","body":"Description","context":{...}}
```

### merge_pr

```bash
  "arguments":{"operation":"merge_pr","repo_name":"owner/repo","pr_number":42,"merge_method":"squash","base":"main","context":{"github_token":"...","risk_confirmed":true}}
```

`merge_pr` is MEDIUM by default but **contextually escalated** based on `base`:
- `base="main"` or `base="master"` → HIGH (requires `risk_confirmed: true`)
- `base="production"` or `base="release/*"` → CRITICAL (requires `risk_confirmed: true` + `risk_reason: "..."`)
- Any other base → MEDIUM (no confirmation)

---

## §4 — Risk Gate: HIGH ops (require `risk_confirmed: true`)

All HIGH ops are blocked without explicit confirmation.

### create_repo

```bash
  "arguments":{"operation":"create_repo","name":"my-new-repo","description":"Test","private":true,
    "context":{"github_token":"...","risk_confirmed":true}}
```

Without `risk_confirmed: true`:
```json
{"error":{"code":-32603,"message":"Operation create_repo requires: confirmed=true"}}
```

### delete_branch

```bash
  "arguments":{"operation":"delete_branch","repo_name":"owner/repo","branch_name":"feature/old",
    "context":{"github_token":"...","risk_confirmed":true}}
```

**Contextual escalation:** `branch_name="main"` | `"master"` | `"production"` → CRITICAL (needs `risk_confirmed` + `risk_reason`).

### create_release (v3)

```bash
  "arguments":{"operation":"create_release","repo_name":"owner/repo","tag_name":"v1.2.0","name":"Release v1.2.0","body":"Changes...","prerelease":false,
    "context":{"github_token":"...","risk_confirmed":true}}
```

**Prerelease downgrade:** `prerelease: true` drops risk to MEDIUM — no confirmation needed:
```bash
  "arguments":{"operation":"create_release","repo_name":"owner/repo","tag_name":"v1.2.0-rc1","name":"RC1","prerelease":true,
    "context":{"github_token":"..."}}
```

### trigger_workflow (v3)

```bash
  "arguments":{"operation":"trigger_workflow","repo_name":"owner/repo","workflow_id":"ci.yml","ref":"main","inputs":{"env":"staging"},
    "context":{"github_token":"...","risk_confirmed":true}}
```

### create_webhook (v3)

```bash
  "arguments":{"operation":"create_webhook","repo_name":"owner/repo","url":"https://your-server.com/hook","events":["push","pull_request"],"secret":"<webhook-secret>",
    "context":{"github_token":"...","risk_confirmed":true}}
```

The `url` is SSRF-guarded: private IPs (`10.x`, `172.16-31.x`, `192.168.x`, `127.x`, `169.254.x`) are rejected with a `ValueError` before any network call.

### delete_webhook (v3)

```bash
  "arguments":{"operation":"delete_webhook","repo_name":"owner/repo","webhook_id":123456,
    "context":{"github_token":"...","risk_confirmed":true}}
```

---

## §5 — Risk Gate: CRITICAL ops (require `risk_confirmed: true` AND `risk_reason`)

### delete_repo

```bash
  "arguments":{"operation":"delete_repo","repo_name":"owner/repo",
    "context":{"github_token":"...","risk_confirmed":true,"risk_reason":"Decommissioning old test repo after migration"}}
```

Without both fields:
- No confirm, no reason → `"requires: confirmed=true, reason (non-empty string)"`
- Confirm only → `"requires: reason (non-empty string)"`
- Reason only → `"requires: confirmed=true"`

### force_push

`force_push` is NL-only (not in structured schema). CRITICAL risk gate still fires via the NL path.

---

## §6 — Contextual Risk Escalation Summary

| Operation | Default Risk | Contextual Condition | Escalated Risk |
|-----------|-------------|---------------------|----------------|
| `merge_pr` | MEDIUM | `base` = `main`/`master` | HIGH |
| `merge_pr` | MEDIUM | `base` = `production`/`release/*` | CRITICAL |
| `delete_branch` | HIGH | `branch_name` = `main`/`master`/`production` | CRITICAL |
| `delete_branch` | HIGH | `branch_name` matches `release/*` | HIGH (same) |
| `commit_file` | MEDIUM | `branch` = `main`/`master`/`production` | HIGH |
| `create_release` | HIGH | `prerelease` = `true` | MEDIUM (downgrade) |

---

## §7 — Error Enrichment (403 / 404 / 422)

Errors from GitHub API are enriched with actionable guidance by `_enrich_github_error()`:

### 403 — Permission denied

```json
{"error":{"code":-32603,"message":"GitHub permission denied for 'create_webhook'. Your PAT needs: [write:repo_hook]. Re-generate at https://github.com/settings/tokens/new"}}
```

PAT scope map by operation:
| Operation | Required scope |
|-----------|---------------|
| `delete_repo` | `delete_repo`, `repo` |
| `create_webhook`, `delete_webhook` | `write:repo_hook` |
| `trigger_workflow` | `workflow` |
| all others | `repo` |

### 404 — Resource not found

```json
{"error":{"code":-32603,"message":"Resource not found for 'list_branches'. Check repo_name format (must be 'owner/repo')."}}
```

### 422 — Validation error

```json
{"error":{"code":-32603,"message":"GitHub validation error for 'create_branch': Reference already exists"}}
```

---

## §8 — Schema Validation Errors (-32602)

| Violation | Example | Response |
|-----------|---------|----------|
| Unknown operation | `"operation":"nonexistent"` | `-32602 Unknown operation '...'` |
| No query and no operation | `{}` | `-32602 Must specify either 'query' or 'operation'` |
| Both query+operation (op has no query field) | `"query":"...", "operation":"list_repos"` | `-32602 Cannot specify both` |
| Missing required param | `list_branches` without `repo_name` | `-32602 'repo_name': Field required` |
| page=0 | `"page":0` | `-32602 'page': Input should be greater than 0` |
| update_issue no fields | no title/body/state/labels/assignees | `-32602 at_least_one_field` |
| get_commit short SHA | `"sha":"abc"` (< 7 chars) | `-32602 String should have at least 7 characters` |

---

## §9 — Backward Compat: Natural Language Mode

NL mode still works via both `/mcp` and `/api/gateway`. All v3 ops are reachable via NL.

### MCP NL call

```bash
curl -s -X POST http://localhost:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "jsonrpc":"2.0","id":1,"method":"tools/call",
    "params":{"name":"github_operation","arguments":{
      "query":"list pull requests in owner/repo",
      "context":{"github_token":"$GH_PAT"}
    }}
  }'
```

### REST gateway NL call

```bash
curl -s -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "name":"github_operation",
    "arguments":{
      "query":"list my repositories",
      "context":{"github_token":"$GH_PAT"}
    }
  }'
```

**Note:** REST gateway requires `query`. Structured mode (`operation` key) only works via `/mcp`.

### NL queries verified live (2026-05-19)

| Query | Route detected |
|-------|---------------|
| `"list my repositories"` | `list_repos` |
| `"list branches in owner/repo"` | `list_branches` |
| `"list pull requests in owner/repo"` | `list_pull_requests` |
| `"list commits in owner/repo on main branch"` | `list_commits` |
| `"read file README.md from owner/repo"` | `read_file` |
| `"search for 'def ' in owner/repo"` | `search_code` |

---

## §10 — Live Test Results (2026-05-19)

Run: `./venv/bin/python3 /tmp/gitops_v3_mcp_test.py`

| Section | Tests | Result |
|---------|-------|--------|
| Protocol layer (initialize, error codes) | 4 | ✅ 4/4 |
| tools/list schema (26 ops, oneOf, all v3+legacy) | 5 | ✅ 5/5 |
| READ structured ops | 11 | ✅ 11/11 |
| PR + commit inspection | 4 | ✅ 4/4 |
| MEDIUM ops (issue lifecycle) | 4 | ✅ 4/4 |
| Risk gate HIGH ops blocked without confirm | 7 | ✅ 7/7 |
| Contextual escalation (merge/delete to protected branches) | 5 | ✅ 5/5 |
| CRITICAL ops blocked | 3 | ✅ 3/3 |
| Prerelease risk downgrade (HIGH→MEDIUM) | 2 | ✅ 2/2 |
| HIGH ops with confirmed=true pass gate | 1 | ✅ 1/1 |
| NL backward compat (6 live GitHub calls) | 6 | ✅ 6/6 |
| Schema validation errors (-32602) | 8 | ✅ 8/8 |
| Error enrichment (403 PAT hint, 404 format hint) | 2 | ✅ 2/2 |
| Auth edge cases (bad key, missing key) | 2 | ✅ 2/2 |
| **TOTAL** | **64** | **✅ 64/64** |

**Observation:** `force_push` is registered in `OperationRiskRegistry` (CRITICAL) but is not in `_STRUCTURED_CALL_OPERATIONS` — it is NL-only by design. The risk gate still enforces CRITICAL for it via the NL path.
