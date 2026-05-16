# github_operation — Structured-Call Mode Design

**Date:** 2026-05-15
**Status:** Draft — pending user review
**Scope:** Sub-project A of the "github_operation production-readiness + official-MCP alignment" initiative
**Endpoint scope:** `POST /mcp` only (the `/api/gateway` REST endpoint is intentionally not in scope)
**Branch:** `rag_resolve`
**Author:** generated via the `superpowers:brainstorming` skill

---

## Goal (one sentence)

Let MCP callers invoke `github_operation` with a typed `operation` + structured parameters that bypass the LLM intent-classification step, while preserving the existing natural-language `query` entry point byte-for-byte for current callers.

## Why now

1. **Latency.** Today every `github_operation` MCP call pays a 1–2 s LLM intent-classify cost. For the dashboard's typed forms (where the user already picked an operation from a dropdown), this cost is pure waste. Verified in the 2026-05-15 live test: `create_issue` natural-language path took ~2.4 s end-to-end, of which ~1.4 s was the LLM parse step.
2. **Foundation for sub-project B (flat `gh.<operation>` MCP tools).** Each flat tool will be a thin wrapper that hand-constructs the structured `arguments` and calls the same MCP `tools/call` handler. Without the structured-call mode, the flat surface would have to duplicate parsing logic.
3. **Determinism for tests & agents.** Agents that compose `github_operation` calls programmatically (Cursor, IDE extensions, future workflow runners) get strict typed contracts instead of relying on the LLM correctly inferring intent from a phrasing they construct.
4. **Official GitHub MCP server alignment.** The official `github/github-mcp-server` exposes each operation as its own tool with structured inputs — no natural-language layer. Sub-project A is the structural prerequisite to match that shape (sub-project B does the literal naming alignment).

## Non-goals

- No change to `/api/gateway` semantics. Gateway callers continue to use the natural-language `query` path only.
- No new operations. The 12 operations in `src/agents/github/schemas.py` are the surface; expansion (org/team management, security alerts, code scanning, projects) is sub-project E.
- No rollback execution. `RollbackMatrix` remains metadata-only; sub-project D will implement actual rollback dispatch.
- No MCP resources or prompts. `gh://owner/repo/path` resources and `release_notes` prompt templates are sub-project F.
- No tool annotations (`readOnlyHint`/`destructiveHint`/`idempotentHint`). Sub-project C handles MCP envelope hardening including annotations.
- No latency SLO. The structured path will be faster than the natural-language path (data flow §3 estimates 5–10× reduction for `create_issue` with explicit title), but this design does not commit to a numeric p50/p99 target.

---

## §1 Architecture

The structured-call mode is **a new branch inside the existing `parse_github_request` LangGraph node**, not a parallel graph or parallel function. Every call (structured or natural-language) traverses the same nodes in the same order:

```
parse_github_request
  → enhance_with_intelligence
  → validate_parameters
  → policy_gate_check
  → risk_gate_check
  → execute_github_operation
  → handle_error (on any node failure)
```

What changes in each node:

- **`parse_github_request`** dispatches on the shape of the incoming `arguments`:
  - If `query` is present → call the supervisor LLM as today, populate `state.operation` + `state.parameters`, set `state.intent_confidence = <LLM-returned score>`, set `state.entry_method = "natural_language"`.
  - If `operation` is present → skip the LLM call entirely. Populate `state.operation` + `state.parameters` directly from the typed input. Set `state.intent_confidence = 1.0`. Set `state.entry_method = "structured"`.
- **`enhance_with_intelligence`** adds three "skip-if-already-supplied" guards that activate only when `state.entry_method == "structured"`:
  - **Fuzzy repo skip:** if `state.parameters["repo"]` matches the regex `^[^/]+/[^/]+$` (exact `owner/repo` form), skip `RepoDiscovery.fuzzy_search`. Otherwise, fuzzy_search runs as in the natural-language path. This matches the §4 "forgiving fuzzy" decision — substring or typo repos still resolve via Levenshtein, even for structured callers.
  - **Commit-generator skip:** if `state.parameters["commit_message"]` is non-empty (truthy), skip `CommitGenerator` even when `context.diff` is present.
  - **Log-parser skip:** if `state.parameters["title"]` is non-empty (truthy), skip `LogParser` even when `context.error_log` is present.
- **`validate_parameters`, `policy_gate_check`, `risk_gate_check`, `execute_github_operation`, `handle_error`** are **unchanged**. The risk gate already operates on `state.parameters` (not `state.query`), so HIGH/CRITICAL ops still require `context.confirmed=true` regardless of entry method.

The MCP tool registration (`tools/list` response for `github_operation`) gets one update: `inputSchema` becomes a `oneOf` union of two branches — the existing `{query, context}` shape and the new `{operation, ...params, context}` shape. Per-operation parameter schemas already exist in `src/agents/github/schemas.py` (used by `validate_op_params`); we expose them as a `dict[str, type[BaseModel]]` constant for the union builder to introspect at import time.

**Backward-compatibility guarantee:** every call shape that worked before this change produces a byte-identical response after this change. The single observable diff is one additive metadata field on every audit-timeline event: `entry_method: "natural_language" | "structured"`. Existing clients that ignore unknown JSON keys (every well-behaved client) are unaffected.

---

## §2 Components — concrete changes per file

| File | Change | Estimated LoC | Notes |
|------|--------|---------------|-------|
| `src/api/routers/__init__.py` (MCP `tools/call` handler around line 1177-1200) | Drop the current `if not query: -32602` guard on the github_operation branch. Accept either `query` or `operation` in `arguments`. Forward the entire `arguments` dict to `github_agent_invoke`. | ~15 | Symmetry with the agent's new signature. **Note:** existing `/api/gateway` handler (`routers/__init__.py:712-730`) is **NOT** touched — gateway callers continue to need `query`. |
| `src/api/routers/__init__.py` (`TOOL_DESCRIPTIONS` registration for `github_operation`) | Update `inputSchema` from `{type:"object", properties:{query:{type:"string"}, context:{type:"object"}}, required:["query"]}` to a `oneOf` union with two branches. Description string gains a one-line note: "Either `query` (natural-language) or `operation` (structured)." | ~60 | The structured branch enumerates the 12 valid operation names in `enum`. Per-op parameter schemas live in `schemas.OPERATION_SCHEMAS` and are enforced at runtime by `validate_op_params` — we do **not** inline 12 sub-schemas into the `oneOf` because it would bloat `tools/list` payload by ~4 KB. The runtime Pydantic enforcement is the source of truth. |
| `src/agents/github/agent.py` — `GitHubState` dataclass (around line 47-65) | Add `entry_method: Literal["natural_language", "structured"] = "natural_language"`. | ~2 | Defaulted so existing call sites continue compiling. |
| `src/agents/github/agent.py` — `parse_github_request()` (around line 156-280) | Top-of-function branch on `state.entry_method` (set by `github_agent_invoke` before graph entry). When `entry_method == "structured"`: `state.operation` and `state.parameters` are already populated by the invoke entry point; set `state.intent_confidence = 1.0`, emit an audit event `step_complete` with `metadata: {step: "llm_classify", skipped: true, reason: "structured_call"}`, return state. Otherwise (`entry_method == "natural_language"`) run the LLM exactly as today. | ~30 | The branch trigger is `entry_method`, not the truthiness of `state.operation` — this avoids the trap where a future change might pre-set `state.operation` for some other reason and accidentally skip the LLM. |
| `src/agents/github/agent.py` — `enhance_with_intelligence()` (around line 380-450) | Add three guards at the top of their respective branches, each gated on `state.entry_method == "structured"`: (a) skip `RepoDiscovery.fuzzy_search` when `state.parameters.get("repo")` matches `^[^/]+/[^/]+$`; (b) skip `CommitGenerator.generate` when `state.parameters.get("commit_message")` is truthy; (c) skip `LogParser.parse` when `state.parameters.get("title")` is truthy. Each emits a `step_skipped` audit event so the timeline records the optimization. | ~25 | Per §4 decision: in all other cases (substring repo, no commit_message, no title) the enhance step runs identically to the natural-language path — the "forgiving fuzzy" behavior. |
| `src/agents/github/agent.py` — `github_agent_invoke()` signature (around line 1170-1196) | Add optional kwargs `operation: Optional[str] = None` and `parameters: Optional[Dict[str, Any]] = None`. When both are provided, pre-populate `GitHubState.operation`/`state.parameters` before constructing the graph runner. Add an internal assertion: `assert (query is None) != (operation is None)` — exactly one of `query`/`operation` must be set. | ~20 | Public-API evolution is additive. All existing call sites in `routers/__init__.py` and tests work unchanged. |
| `src/agents/github/schemas.py` | Refactor: extract the per-op Pydantic model lookup currently inside `validate_op_params` into a module-level constant `OPERATION_SCHEMAS: dict[str, type[BaseModel]]`. `validate_op_params` rewrites to `model_cls = OPERATION_SCHEMAS.get(operation); if not model_cls: raise ValueError(...)`. | ~15 | Pure refactor — no behavior change. Exposes the lookup for the `tools/list` `oneOf` enum builder. |
| `src/core/audit.py` | No schema change. Audit event metadata is already a `dict[str, Any]`. Pass `entry_method` through as another metadata key on `operation_start` and each step event. | 0 | Verified by reading `audit.py:55-100`. |
| `src/api/routers/__init__.py` — `arguments`-level validation for MCP `github_operation` | Add a Pydantic model `GithubOperationArgs(BaseModel)` with `query: Optional[str] = None`, `operation: Optional[Literal[<12 ops>]] = None`, plus a `model_validator` that enforces exactly-one-of and per-op required-field checks via `OPERATION_SCHEMAS`. Used only inside the MCP handler — not at the `GatewayRequest` outer envelope. | ~40 | Catches the `-32602` validation errors before `github_agent_invoke` runs; gives the caller a clean error message with the operation enum list. |
| `tests/test_github_integration.py` | New test class `TestStructuredCallMode` — 12 happy-path tests (one per operation), 5 negative-path tests, 3 risk-gate-parity tests, 4 selective-enhance guard tests, 1 natural-language regression snapshot test, 1 `tools/list` schema snapshot test. | ~250 | See §6 for full breakdown. |

**Total estimated diff: ~210 LoC added/modified in production code (sum of the row estimates above), ~250 LoC new tests, 0 LoC deleted from production paths.** No production file grows by more than +60 LoC; the test file grows by ~250.

---

## §3 Data flow

### Natural-language path (unchanged)

```
client → POST /mcp { method: tools/call, params: { name: "github_operation",
                                                    arguments: { query, context } } }
  → MCP handler reads arguments
  → github_agent_invoke(query=..., context=...)
  → GitHubState(query=..., entry_method="natural_language")
  → parse_github_request: supervisor LLM extracts operation+params, sets intent_confidence
  → enhance_with_intelligence:
       • fuzzy_search ALWAYS runs (even on exact owner/repo — no skip in NL path)
       • CommitGenerator IF context.diff present (unconditional in NL path)
       • LogParser IF context.error_log present (unconditional in NL path)
  → validate_parameters → policy_gate_check → risk_gate_check → execute_github_operation
  → response: { result: { content: [{type:"text", text:"<json>"}], isError } }
```

### Structured path (new)

```
client → POST /mcp { method: tools/call, params: { name: "github_operation",
                                                    arguments: { operation, ...typed_params, context } } }
  → MCP handler reads arguments
  → GithubOperationArgs Pydantic validates:
       • exactly one of (query, operation) must be set                    → -32602 if both/neither
       • operation must be in the 12-op enum                               → -32602 if unknown
       • per-op required fields present (via OPERATION_SCHEMAS lookup)     → -32602 if missing
       • per-op field types correct                                        → -32602 if wrong type
  → github_agent_invoke(operation=..., parameters=..., context=...)
  → GitHubState(operation=..., parameters=..., entry_method="structured", intent_confidence=1.0)
  → parse_github_request: EARLY-RETURN (no LLM call)
       emits audit event {step: "llm_classify", skipped: true, reason: "structured_call"}
  → enhance_with_intelligence (selective):
       IF repo matches "owner/repo" exact → skip fuzzy_search                (audit: step_skipped)
       IF parameters.commit_message provided → skip CommitGenerator         (audit: step_skipped)
       IF parameters.title provided → skip LogParser                         (audit: step_skipped)
       Otherwise: enhancements run identically to natural-language path
  → validate_parameters → policy_gate_check → risk_gate_check → execute_github_operation
  → response: same shape as NL path; audit timeline has entry_method="structured" on every event
```

### Latency estimates

Based on the 2026-05-15 live verification run (`/mcp` calls against `localhost:8001`, `create_issue` natural-language took ~2.4 s end-to-end; `list_repos` natural-language took ~1.5 s):

| Stage | Natural-language | Structured (exact repo, all params) | Structured (fuzzy repo) |
|-------|------------------|--------------------------------------|--------------------------|
| Pydantic validation | ~5 ms | ~10 ms (slightly more — `GithubOperationArgs` runs `OPERATION_SCHEMAS` lookup) | ~10 ms |
| `parse_github_request` LLM | 1000–2000 ms | 0 ms (early return) | 0 ms |
| `enhance` — fuzzy_search (cached) | 50–200 ms | 0 ms (skipped) | 50–200 ms |
| `enhance` — LogParser LLM (when error_log present, title not set) | 1000–2000 ms | 0 ms (skipped if title set) | 0 ms (skipped if title set) |
| `validate + policy + risk` | ~10 ms | ~10 ms | ~10 ms |
| GitHub API call | 200–800 ms | 200–800 ms | 200–800 ms |
| **Total — typical `create_issue` (no log parsing)** | **~1500–3000 ms** | **~220–820 ms** | **~270–1020 ms** |

The structured path's win is the 1–2 s LLM intent-classify call, plus optionally another 1–2 s for LogParser/CommitGenerator when those aren't needed.

### Audit telemetry diff

```diff
 {
   "event": "operation_start",
   "timestamp": "2026-05-15T14:30:56.000Z",
   "description": "Parsing: create_issue (structured)",
   "metadata": {
+    "entry_method": "structured"
   }
 }
```

Single additive field on every event. Enables operational queries:
- "what % of MCP calls use the structured path?"
- "do structured callers hit risk-gate blocks more or less often than NL callers?"
- "what's the actual p50 latency win we get from structured calls?"

---

## §4 Error handling (MCP-only)

All structured-call errors return JSON-RPC `error` envelopes on `POST /mcp`. No errors flow through `result.content` — clients can rely on `if "error" in response` as a single error-detection rule.

| Failure | JSON-RPC code | Message format | Notes |
|---------|---------------|----------------|-------|
| Both `query` AND `operation` present | `-32602` (Invalid params) | `"Cannot specify both 'query' and 'operation' — pick one"` | Caught by `GithubOperationArgs` model_validator, before `github_agent_invoke` runs. No audit event. |
| Neither `query` nor `operation` present | `-32602` | `"Must specify either 'query' or 'operation' in arguments"` | Same validator. |
| `operation` is not one of the 12 known ops | `-32602` | `"Unknown operation 'foo'. Valid operations: [list_repos, create_repo, create_issue, commit_file, create_pull_request, browse_files, read_file, search_code, list_branches, create_branch, delete_branch, delete_repo]"` | Caught by `Literal[<12-op enum>]` constraint on the `operation` field. |
| Required param missing for op (e.g. `create_issue` without `title`) | `-32602` | `"Operation 'create_issue' missing required field: 'title'"` (Pydantic ValidationError formatted) | Caught by per-op Pydantic model in `OPERATION_SCHEMAS`. Audit event emitted at `validate` node if it reaches that far (it shouldn't — `GithubOperationArgs` runs the same check earlier). |
| Wrong type for param (e.g. `body: 42`) | `-32602` | `"Operation 'create_issue' field 'body': Input should be a valid string"` | Same Pydantic path. |
| Risk-gate block (HIGH without `confirmed`, CRITICAL without `confirmed+reason`) | `-32603` (Internal error — existing code) | `"Risk gate blocked: Operation create_repo requires: confirmed=true"` | **Unchanged** — same code path and message as today's natural-language path. Audit timeline carries `audit_id` and `entry_method:"structured"`. The `audit_id` is still NOT surfaced in the JSON-RPC error envelope (sub-project C will fix this). |
| Policy gate block (`GITOPS_PROTECTED_MODE=true` + HIGH op) | `-32603` | `"Policy gate blocked: HIGH operations disabled in protected mode"` | Unchanged. |
| Fuzzy disambiguation (multi-repo match — only when caller passed substring/typo repo) | wrapped in `result.content` with `isError:false`, payload `{success:false, status:"needs_clarification", options:[...]}` | n/a | Unchanged. Structured callers who pass exact `owner/repo` never hit this. **Per §4 "forgiving fuzzy" decision**, substring repos in structured calls fall back to the same disambiguation behavior as natural-language calls. |
| GitHub API 404 / 401 / 403 / 5xx | wrapped in `result.content` with `isError:true`, payload `{success:false, status:"not_found"\|"permission_error"\|"rate_limited", audit_id, timeline}` | n/a | Unchanged. Same `_handle_github_exception` path. |
| Missing `context.github_token` | wrapped in `result.content` with `isError:true`, payload `{success:false, message:"GitHub token required..."}` | n/a | Unchanged. |

### Non-changes

1. Structured calls do **not** bypass `ConfidencePolicy`. `intent_confidence = 1.0` for structured calls means they automatically pass the 0.85 intent threshold, but `commit_message` confidence (the 0.85–0.90 medium-draft-PR band) still applies if `CommitGenerator` ran. If the caller supplied `commit_message` explicitly, the band check is irrelevant because `CommitGenerator` was skipped.
2. The risk gate's contextual escalation rules (`merge_pr` into `main`/`master` → HIGH, `delete_branch` of `main`/`master` → CRITICAL) operate on `state.parameters` — structured callers can't escape these by passing the typed input.

---

## §5 Backward compatibility — strict guarantees

1. **Byte-identical responses for existing call shapes.** A `query`-only call to `/mcp` produces a response body identical to today's — same `audit_id` format, same timeline event count, same event ordering, same message strings. The only diff in the audit timeline is one additive metadata field `entry_method: "natural_language"` on each event. Clients that ignore unknown JSON keys are unaffected (this is all well-behaved JSON clients).
2. **`tools/list` payload remains valid for strict clients.** The change from `{type:"object", properties:{query:{type:"string"}}, required:["query"]}` to `{type:"object", oneOf:[…]}` is valid JSON Schema 2020-12 (the MCP spec's schema dialect). Cursor, Claude Desktop, and the official MCP inspector parse `oneOf` correctly. Clients that pre-date `oneOf` support are out of spec — explicitly not engineered for.
3. **`/api/gateway` continues to accept only `query`.** Per user-imposed §2 scope constraint. A gateway caller passing `arguments: {operation: "create_issue", ...}` gets the same `"github_operation requires 'query' parameter"` 400 error as today. No `GatewayRequest` Pydantic changes.
4. **Natural-language path is bit-equivalent.** When `query` is present, `parse_github_request` runs the LLM exactly as today; `enhance_with_intelligence` runs all three enhancements (fuzzy_search, commit_gen, log_parser) unconditionally. The new "skip-if-already-supplied" guards only activate when `state.entry_method == "structured"`. **This is the single invariant that prevents accidental regressions** — guards are gated on `entry_method`, not on the value of `state.parameters`. Enforced by the natural-language regression snapshot test in §6.
5. **`github_agent_invoke()` evolves additively.** New optional kwargs `operation` and `parameters` default to `None`. All existing call sites in `routers/__init__.py` and tests continue to work without changes. Internal validator: `assert (query is None) != (operation is None)`.
6. **Schema introspection is read-only and import-time.** Building the `oneOf` union from `schemas.OPERATION_SCHEMAS` happens once at import time during the `TOOL_DESCRIPTIONS` initialization. The per-op Pydantic models in `validate_op_params` are unchanged — we just expose a `dict[op_name, model_cls]` for the union builder to walk.

### Explicit non-guarantee

This design does **not** commit to a latency SLO for the natural-language path. The new branch-check at the top of `parse_github_request` adds maybe 100 nanoseconds; immeasurable. But if a future change to the parse node accidentally regresses NL latency, the §6 tests catch *correctness* regressions, not *latency* regressions. A latency SLO can be added in sub-project C.

---

## §6 Testing

Three layers. All run as part of `pytest tests/ -v`. **MCP-only test surface** per §2 scope.

### Layer 1 — Unit tests in `tests/test_github_integration.py`

New test class `TestStructuredCallMode`. Each test is a real HTTP call to `localhost:8001/mcp` using `httpx.AsyncClient`, with the test API key (`df_…`) and a mock PAT. A `MockGitHubClient` is injected via FastAPI dependency override so unit tests do not hit real GitHub.

**Happy-path: one test per operation (12 cases)**

```python
@pytest.mark.parametrize("operation,parameters,context_extras", [
    ("list_repos", {"visibility": "public", "limit": 5}, {}),
    ("create_issue", {"repo": "owner/r", "title": "x", "body": "y"}, {}),
    ("commit_file", {"repo": "owner/r", "file_path": "x.py", "content": "print(1)",
                     "commit_message": "feat: x"}, {}),
    ("create_pull_request", {"repo": "owner/r", "title": "x", "head": "feat", "base": "main"}, {}),
    ("browse_files", {"repo": "owner/r", "path": ""}, {}),
    ("read_file", {"repo": "owner/r", "file_path": "README.md"}, {}),
    ("search_code", {"query": "TODO", "repo": "owner/r"}, {}),
    ("list_branches", {"repo": "owner/r"}, {}),
    ("create_branch", {"repo": "owner/r", "branch_name": "feat", "from_branch": "main"}, {}),
    ("create_repo", {"name": "demo"}, {"confirmed": True}),
    ("delete_branch", {"repo": "owner/r", "branch_name": "feat"}, {"confirmed": True}),
    ("delete_repo", {"repo": "owner/r"}, {"confirmed": True, "reason": "test cleanup"}),
])
async def test_structured_call_each_operation(mcp_client, operation, parameters, context_extras):
    response = await mcp_client.call(
        "github_operation",
        arguments={"operation": operation, **parameters,
                   "context": {"github_token": "ghp_test", **context_extras}}
    )
    payload = parse_mcp_payload(response)
    assert payload["success"] is True
    assert payload["operation"] == operation
    assert payload["audit_id"].startswith("audit_")
    # KEY ASSERTION: every timeline event records the structured entry method
    timeline = payload["timeline"]
    assert all(
        e["metadata"].get("entry_method") == "structured"
        for e in timeline["events"]
    )
    # KEY ASSERTION: the LLM classify step recorded itself as skipped
    classify_event = next(e for e in timeline["events"]
                          if e["metadata"].get("step") == "llm_classify")
    assert classify_event["metadata"].get("skipped") is True
    assert classify_event["metadata"].get("reason") == "structured_call"
```

**Negative-path: structured-call rejections (5 cases)**

```python
# 1. Both query and operation present
async def test_rejects_both_query_and_operation(mcp_client):
    resp = await mcp_client.call(
        "github_operation",
        arguments={"query": "x", "operation": "list_repos"}
    )
    assert resp["error"]["code"] == -32602
    assert "Cannot specify both" in resp["error"]["message"]

# 2. Neither query nor operation
async def test_rejects_missing_both(mcp_client):
    resp = await mcp_client.call("github_operation", arguments={})
    assert resp["error"]["code"] == -32602
    assert "Must specify either" in resp["error"]["message"]

# 3. Unknown operation name
async def test_rejects_unknown_operation(mcp_client):
    resp = await mcp_client.call(
        "github_operation",
        arguments={"operation": "foo_bar_baz"}
    )
    assert resp["error"]["code"] == -32602
    assert "Unknown operation 'foo_bar_baz'" in resp["error"]["message"]
    for op in ["list_repos", "create_issue", "delete_repo"]:
        assert op in resp["error"]["message"]

# 4. Missing required field for op
async def test_rejects_missing_required_field(mcp_client):
    resp = await mcp_client.call(
        "github_operation",
        arguments={"operation": "create_issue", "repo": "owner/r"}  # no title
    )
    assert resp["error"]["code"] == -32602
    assert "title" in resp["error"]["message"]

# 5. Wrong type for field
async def test_rejects_wrong_type(mcp_client):
    resp = await mcp_client.call(
        "github_operation",
        arguments={"operation": "create_issue", "repo": "owner/r",
                   "title": 42, "body": "x"}
    )
    assert resp["error"]["code"] == -32602
    assert "title" in resp["error"]["message"]
```

**Risk-gate parity: structured calls hit the same gate (3 cases)**

```python
async def test_structured_create_repo_blocked_without_confirmed(mcp_client):
    resp = await mcp_client.call(
        "github_operation",
        arguments={"operation": "create_repo", "name": "demo",
                   "context": {"github_token": "ghp_test"}}
    )
    assert resp["error"]["code"] == -32603
    assert "Risk gate blocked" in resp["error"]["message"]
    assert "confirmed=true" in resp["error"]["message"]

async def test_structured_delete_repo_blocked_without_reason(mcp_client):
    resp = await mcp_client.call(
        "github_operation",
        arguments={"operation": "delete_repo", "repo": "owner/r",
                   "context": {"github_token": "ghp_test", "confirmed": True}}
    )
    assert resp["error"]["code"] == -32603
    assert "reason (non-empty string)" in resp["error"]["message"]

async def test_structured_delete_branch_main_escalates_to_critical(mcp_client):
    resp = await mcp_client.call(
        "github_operation",
        arguments={"operation": "delete_branch", "repo": "owner/r", "branch_name": "main",
                   "context": {"github_token": "ghp_test", "confirmed": True}}
    )
    # main-branch contextual escalation should require reason just like delete_repo
    assert resp["error"]["code"] == -32603
    assert "reason" in resp["error"]["message"]
```

**Selective-enhance: guards work correctly (4 cases)**

```python
async def test_skips_fuzzy_when_repo_is_exact(mcp_client):
    with patch("src.agents.github.intelligence.repo_discovery.RepoDiscovery.fuzzy_search") as spy:
        await mcp_client.call(
            "github_operation",
            arguments={"operation": "create_issue",
                       "repo": "sidcollege/testing_devforge",
                       "title": "x", "body": "y",
                       "context": {"github_token": "ghp_test"}}
        )
        spy.assert_not_called()

async def test_runs_fuzzy_when_repo_is_substring(mcp_client):
    # Forgiving-fuzzy decision: substring repos in structured calls still resolve via Levenshtein
    with patch("src.agents.github.intelligence.repo_discovery.RepoDiscovery.fuzzy_search") as spy:
        spy.return_value = [...]  # one match returned
        await mcp_client.call(
            "github_operation",
            arguments={"operation": "create_issue", "repo": "testing",
                       "title": "x", "body": "y",
                       "context": {"github_token": "ghp_test"}}
        )
        spy.assert_called_once()

async def test_skips_log_parser_when_title_provided(mcp_client):
    # error_log in context but title set → log_parser must not run
    with patch("src.agents.github.intelligence.log_parser.LogParser.parse") as spy:
        await mcp_client.call(
            "github_operation",
            arguments={"operation": "create_issue", "repo": "owner/r",
                       "title": "I have a title", "body": "y",
                       "context": {"github_token": "ghp_test", "error_log": "Traceback..."}}
        )
        spy.assert_not_called()

async def test_runs_log_parser_when_title_missing(mcp_client):
    # error_log present, no title → log_parser must run to derive title/body
    with patch("src.agents.github.intelligence.log_parser.LogParser.parse") as spy:
        spy.return_value = ParsedIssue(
            title="[ZeroDivisionError] ...", body="...", labels=[...], ...
        )
        await mcp_client.call(
            "github_operation",
            arguments={"operation": "create_issue", "repo": "owner/r",
                       "context": {"github_token": "ghp_test",
                                    "error_log": "Traceback..."}}
        )
        spy.assert_called_once()
```

**Natural-language regression suite (1 test, the backward-compat tripwire)**

```python
async def test_natural_language_path_unchanged(mcp_client):
    # Snapshot test — capture current NL behavior for one canonical call.
    # Fails if ANY field other than the new entry_method or timestamps changes.
    resp = await mcp_client.call(
        "github_operation",
        arguments={"query": "list my repositories",
                   "context": {"github_token": "ghp_test"}}
    )
    payload = parse_mcp_payload(resp)
    # New invariant: NL calls record entry_method="natural_language"
    assert payload["timeline"]["events"][0]["metadata"]["entry_method"] == "natural_language"
    # All other fields snapshot-matched against fixtures/nl_list_repos_baseline.json
    assert_matches_snapshot(
        payload,
        "tests/fixtures/nl_list_repos_baseline.json",
        ignore_paths=["timeline.events[*].timestamp",
                      "timeline.start_time",
                      "timeline.total_duration_ms",
                      "audit_id"]
    )
```

### Layer 2 — Snapshot test for `tools/list` schema

```python
async def test_tools_list_inputSchema_has_oneOf_union(mcp_client):
    resp = await mcp_client.call_jsonrpc("tools/list", id=1)
    github_tool = next(t for t in resp["result"]["tools"] if t["name"] == "github_operation")
    schema = github_tool["inputSchema"]
    assert "oneOf" in schema
    assert len(schema["oneOf"]) == 2

    query_branch = next(b for b in schema["oneOf"] if "query" in b.get("required", []))
    structured_branch = next(b for b in schema["oneOf"] if "operation" in b.get("required", []))

    # Structured branch enumerates exactly the 12 ops we support
    op_enum = structured_branch["properties"]["operation"]["enum"]
    assert set(op_enum) == {
        "list_repos", "create_repo", "create_issue", "commit_file",
        "create_pull_request", "browse_files", "read_file", "search_code",
        "list_branches", "create_branch", "delete_branch", "delete_repo"
    }
```

### Layer 3 — Latency benchmark (informational, not a CI gate)

```python
@pytest.mark.benchmark
@pytest.mark.skipif(not os.getenv("GITOPS_BENCHMARK"),
                    reason="latency benchmark — set GITOPS_BENCHMARK=1 to run")
async def test_structured_path_p50_under_500ms(mcp_client):
    """
    Run 50 structured create_issue calls against the mock GitHub backend.
    Assert p50 < 500ms (vs ~2000ms estimated for natural-language).
    Runs locally before each release; not a CI gate (would flake under CI variance).
    """
    durations = []
    for _ in range(50):
        t0 = time.perf_counter()
        await mcp_client.call(
            "github_operation",
            arguments={"operation": "create_issue", "repo": "owner/r",
                       "title": "x", "body": "y",
                       "context": {"github_token": "ghp_test"}}
        )
        durations.append((time.perf_counter() - t0) * 1000)
    durations.sort()
    p50 = durations[25]
    assert p50 < 500, f"structured p50={p50:.0f}ms exceeds 500ms threshold"
```

### Coverage targets
- Every new branch in `parse_github_request` and `enhance_with_intelligence` covered.
- Every operation in `schemas.OPERATION_SCHEMAS` (12 ops) exercised at least once through the structured path.
- Every JSON-RPC error code returned by the spec (`-32602` validation, `-32603` risk/policy) covered with at least one test.
- One natural-language regression snapshot test that fails if any byte-level change occurs in the NL path beyond the new `entry_method` field.

### Test counts
- New tests: **26 cases** (12 happy-path + 5 negative + 3 risk-gate + 4 selective-enhance + 1 NL regression + 1 schema snapshot)
- Existing tests: **68 cases** (must continue to pass, unchanged)
- Benchmark: **1 case** (opt-in, not CI-gated)

---

## Implementation order & checkpoints

Recommended order for the writing-plans implementation plan:

1. **Refactor `schemas.py`** to expose `OPERATION_SCHEMAS: dict[str, type[BaseModel]]`. Pure refactor; existing tests must still pass. Commit checkpoint: ~15 LoC change, 0 behavior change.
2. **Add `entry_method` to `GitHubState`** with default `"natural_language"`. Update `audit.py` callers to pass it through. Existing tests must still pass. Commit checkpoint: ~5 LoC.
3. **Evolve `github_agent_invoke()` signature** to accept `operation`/`parameters` kwargs. Add the exactly-one-of assertion. All existing call sites continue to compile and pass. Commit checkpoint: ~20 LoC.
4. **Branch inside `parse_github_request`** to early-return on structured calls. Add the LLM classify "skipped" audit event. Commit checkpoint: ~30 LoC, NL regression test must pass.
5. **Add the three guards to `enhance_with_intelligence`**, each gated on `entry_method == "structured"`. Commit checkpoint: ~25 LoC, all four selective-enhance tests pass.
6. **Add `GithubOperationArgs` Pydantic model** in the MCP handler. Wire up the `-32602` validation paths. Commit checkpoint: ~40 LoC, all five negative-path tests pass.
7. **Update `TOOL_DESCRIPTIONS` `inputSchema`** to the `oneOf` union. Commit checkpoint: ~60 LoC, `tools/list` snapshot test passes.
8. **Wire MCP handler** to forward structured args into `github_agent_invoke`. Commit checkpoint: ~15 LoC, all 12 happy-path tests pass.
9. **Run full test suite** (68 existing + 26 new + 1 schema snapshot = 95 tests). All pass. Manual smoke test through live `/mcp` with the demo PAT.

Each step is independently testable and revertable. A failure at step N rolls back only step N; steps 1-(N-1) remain shipped.

---

## Open questions / future work

- **Tool annotations** (`readOnlyHint: true` on `list_repos`/`browse_files`/`read_file`/`search_code`/`list_branches`; `destructiveHint: true` on `delete_repo`/`delete_branch`; `idempotentHint: true` on `commit_file` with deterministic content) — sub-project C.
- **MCP `audit_id` surfacing on `-32603` risk-gate blocks** — sub-project C. Today blocked operations on `/mcp` lose access to the audit timeline. Solution: include `audit_id` in the JSON-RPC error `data` field.
- **Flat `gh.<operation>` tool surface** (sub-project B) — each flat tool becomes a thin wrapper that hand-constructs the structured `arguments` and dispatches into this design's structured path. No new business logic.
- **Rollback execution** (sub-project D) — `RollbackMatrix.MATRIX` becomes executable, with a new MCP tool `gh.rollback` that takes an `audit_id` and dispatches the recorded compensating action.
- **Operation coverage** (sub-project E) — generate per-op Pydantic schemas from GitHub's OpenAPI spec to reach the official server's ~80 operations. Codegen project.
- **MCP resources & prompts** (sub-project F) — `gh://owner/repo/path` content URIs and guided workflow prompts (`release_notes`, `triage_issue`).

---

**End of spec.**
