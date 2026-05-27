# MCP SDK Migration Design

**Date:** 2026-05-27
**Branch:** `mcp_sdk_migration`
**Status:** Design approved, pending implementation plan

## Goal

Replace the hand-rolled JSON-RPC 2.0 `/mcp` endpoint in `src/api/routers/__init__.py` with an implementation built on the official Model Context Protocol Python SDK (`mcp` package, FastMCP high-level API). Same external contract; less code to maintain; modern protocol revision; free progress-notification support.

## Non-goals

- Refactor `/api/gateway` (REST). Stays untouched; continues to maintain its own copy of the rate-limit / analytics / token-strip plumbing.
- Add OAuth/bearer-token MCP auth. Keep `x-api-key`.
- Change tool semantics, agent code, or behavior visible to existing clients.
- Add or remove tools.
- Reorganize the remaining bloat in `src/api/routers/__init__.py` (RAG admin, analytics, manifest serving). Future cleanup.

**Code-block convention:** `...` inside Python snippets below means "verbatim from the existing implementation, see source file lines cited in section E." Snippets are not the complete code — they show the shape and call signatures so the implementation plan can fill them in.

## Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Adopt official MCP Python SDK (`mcp` package, FastMCP API) | Maintained protocol implementation; free progress notifications, content blocks, error framing |
| 2 | Streamable HTTP transport only (spec 2025-06-18) | Modern transport; works with Claude Desktop / Claude Code / Cursor / MCP Inspector; no need to support legacy HTTP+SSE clients |
| 3 | `/api/gateway` REST endpoint untouched | Minimum blast radius; non-MCP REST clients keep working |
| 4 | Replace `/mcp` in place, single commit set, no feature flag | Clean diff, no dead code; behavior contract is unchanged so rollback risk is low |
| 5 | Hybrid input schemas: Pydantic models for 3 simple tools; explicit `oneOf` JSON for `github_operation` | Typed validation where it helps; preserve the hand-tuned union schema where Pydantic would distort it |

## Current state (what's being replaced)

`src/api/routers/__init__.py` (1,722 lines) currently hosts five disjoint concerns: MCP, REST gateway, RAG admin/analytics/observability, manifest, and async-job status. The MCP slice is:

- `mcp_router = APIRouter()` — line 163
- `mcp_endpoint()` — lines 1109–1545 (~437 lines)
- `_get_tool_schema()` — lines 1548–1722 (~175 lines)
- `GITHUB_OPERATION_INPUT_SCHEMA` — lines 26–68
- `GithubOperationArgs` validator — lines 71–137
- `TOOL_DESCRIPTIONS` — lines 178–286

Protocol version pinned to `2024-11-05`. 4 tools registered. Custom plumbing wrapped around each `tools/call`: API-key auth (via FastAPI middleware), per-tier rate limiting (`rate_limiter.check_limits` / `check_and_increment`), tenant_id / user_id / integration_name propagation, async Celery analytics logging (`log_request_call.delay`), GitHub-token scrubbing for the `github_operation` tool, per-tool progress logging (`generate_data`), and rate-limit response headers.

`mcp` SDK is not in `requirements.txt` today.

## Target architecture

### A. File layout

New package `src/api/mcp/`:

```
src/api/mcp/
├── __init__.py             # Re-exports streamable_http_app + the FastMCP instance
├── server.py               # FastMCP() instance, tool registration loop
├── schemas.py              # Pydantic input models + GithubOperationArgs + GITHUB_OPERATION_INPUT_SCHEMA
├── descriptions.py         # TOOL_DESCRIPTIONS dict, moved verbatim
├── dispatch.py             # _dispatch() and _dispatch_github() — cross-cutting wrapper
└── headers_middleware.py   # MCPRateLimitHeadersMiddleware (ASGI middleware on parent FastAPI app)
```

`src/main.py` changes (one line replaced):

```python
# remove:
from src.api.routers import router, mcp_router
app.include_router(mcp_router)

# add:
from src.api.routers import router
from src.api.mcp import streamable_http_app
from src.api.mcp.headers_middleware import MCPRateLimitHeadersMiddleware
app.mount("/mcp", streamable_http_app)
app.add_middleware(MCPRateLimitHeadersMiddleware)
```

The existing middleware stack in `src/main.py` (CORS → JWTAuth → APIKey → DashboardAuth, last-added-first effective ordering) is **unchanged**. `APIKeyAuthMiddleware` continues to run before the request reaches the mounted FastMCP app, so `request.state.tenant_id` / `api_key_id` / `tier` / `user_id` / `integration_name` are populated by the time the dispatch helper reads them.

### B. Tool registration & schemas

`src/api/mcp/schemas.py` defines:

```python
class GenerateDataInput(BaseModel):
    rows: int = Field(..., ge=1, le=10000)
    format: Literal["json", "csv"] = "json"
    fields: list[str] | None = None
    prompt: str | None = None
    domain: Literal["ecommerce", "saas", "iot_devices"] | None = None
    realism_level: Literal["basic", "medium", "high"] = "basic"
    enable_semantic_generation: bool = True

class RefinePromptInput(BaseModel):
    prompt: str = Field(..., min_length=1)
    domain: Literal["general", "image", "code", "rag", "llm"] = "general"
    skill_level: Literal["beginner", "intermediate", "expert"] = "intermediate"
    file_context: str | None = None
    conversation_history: list[dict[str, str]] | None = None
    attached_files: list[str] | None = None
    project_files: dict[str, str] | None = None

class GenerateCheatsheetInput(BaseModel):
    language: Literal["python", "javascript", "typescript", "go", "rust",
                      "java", "ruby", "php", "csharp"] | None = None
    skill_level: Literal["beginner", "intermediate", "expert"] = "beginner"
    code_context: str | None = None
    intent: str | None = None

# Ported verbatim from src/api/routers/__init__.py:
_GH_OP_NAMES = sorted(OPERATION_SCHEMAS.keys())
_GH_OP_LIST_STR = ", ".join(_GH_OP_NAMES)
GITHUB_OPERATION_INPUT_SCHEMA = { ... }   # the existing oneOf dict
class GithubOperationArgs(BaseModel): ... # the existing @model_validator
```

`src/api/mcp/server.py` registers tools:

```python
from mcp.server.fastmcp import FastMCP, Context

mcp = FastMCP(
    name="DevForge",
    version="1.0.0",
    instructions="DevForge tools: data generation, GitHub automation, prompt refinement, cheatsheets.",
)

@mcp.tool(description=TOOL_DESCRIPTIONS["generate_data"])
async def generate_data(args: GenerateDataInput, ctx: Context) -> dict:
    return await _dispatch("generate_data", args.model_dump(exclude_none=True), ctx)

@mcp.tool(description=TOOL_DESCRIPTIONS["refine_prompt"])
async def refine_prompt(args: RefinePromptInput, ctx: Context) -> dict:
    return await _dispatch("refine_prompt", args.model_dump(exclude_none=True), ctx)

@mcp.tool(description=TOOL_DESCRIPTIONS["generate_cheatsheet"])
async def generate_cheatsheet(args: GenerateCheatsheetInput, ctx: Context) -> dict:
    return await _dispatch("generate_cheatsheet", args.model_dump(exclude_none=True), ctx)

@mcp.tool(
    name="github_operation",
    description=TOOL_DESCRIPTIONS["github_operation"],
    input_schema=GITHUB_OPERATION_INPUT_SCHEMA,
)
async def github_operation_tool(arguments: dict, ctx: Context) -> dict:
    validated = GithubOperationArgs(**arguments)
    return await _dispatch_github(validated, ctx)

streamable_http_app = mcp.streamable_http_app()
```

`TOOL_DESCRIPTIONS` is preserved verbatim — these are agent-instructive prompts and any drift would degrade tool-calling quality.

**One trade-off:** FastMCP-generated JSON schemas use `anyOf: [{type: T}, {type: "null"}]` for `Optional` Pydantic fields, where today's hand-written schemas use bare `"type": T`. All target clients (Claude Desktop, Claude Code, Cursor, MCP Inspector) accept both; verified during implementation via MCP Inspector.

### C. Cross-cutting concerns in the dispatch helper

`src/api/mcp/dispatch.py` carries the per-call work that today lives inside `mcp_endpoint`:

```python
async def _dispatch(tool_name: str, args: dict, ctx: Context) -> dict:
    request: Request = ctx.request_context.request
    state = request.state

    tenant_id        = getattr(state, "tenant_id", "unknown")
    user_id          = getattr(state, "user_id", None)
    integration_name = getattr(state, "integration_name", "unknown")
    api_key_id       = getattr(state, "api_key_id", None)
    tier             = getattr(state, "tier", "free")

    # 1. Rate-limit pre-check
    if api_key_id:
        allowed, info = await rate_limiter.check_limits(
            api_key_id, tier,
            hourly_override=getattr(state, "hourly_limit_override", None),
            monthly_override=getattr(state, "monthly_limit_override", None),
        )
        if not allowed:
            state.rate_limit_info = info
            raise McpError(ErrorData(
                code=-32000, message="Rate limit exceeded",
                data={"error": "rate_limit_exceeded", "limit_info": info, ...},
            ))

    # 2. generate_data progress callback (translates to MCP progress notifications)
    progress_cb = _build_progress_callback(ctx) if tool_name == "generate_data" else None

    # 3. Dispatch
    start = time.time()
    agent_func = SUPPORTED_TOOLS[tool_name]   # imported from src.api.routers
    kwargs = {"progress_callback": progress_cb} if progress_cb else {}
    result = await agent_func(
        args, tenant_id=tenant_id, integration_name=integration_name,
        user_id=user_id, **kwargs,
    )
    duration_ms = int((time.time() - start) * 1000)
    success = result.get("success", True) and not result.get("error")

    # 4. Rate-limit increment + analytics — fire-and-forget
    if success and api_key_id:
        try:
            await rate_limiter.check_and_increment(api_key_id, tier, _tokens_used(result), ...)
        except Exception as e:
            logging.warning(f"Rate limit increment failed: {e}")

    try:
        log_request_call.delay(
            user_id=user_id, tenant_id=tenant_id, integration_name=integration_name,
            tool_name=tool_name, input_summary=truncate_input(args),
            success=success, duration_ms=duration_ms,
        )
    except Exception as e:
        logging.warning(f"Analytics log queue failed: {e}")

    # 5. Stash rate-limit usage for the headers middleware
    if api_key_id:
        try:
            state.rate_limit_info = await rate_limiter.get_usage(api_key_id, tier)
        except Exception:
            pass

    # 6. generate_data summary prepend (preserve current behavior)
    if tool_name == "generate_data" and success:
        result = _prepend_generate_data_summary(result)

    if result.get("error"):
        raise McpError(ErrorData(code=-32603, message=result["error"]))

    return result
```

`_dispatch_github` is the same shape but routes structured-vs-NL paths, strips `github_token` from `context` before any logging, and normalizes the `repo` → `repo_name` shorthand for the structured path. Identical to today's logic in `mcp_endpoint`, just relocated.

**Progress notifications upgrade:** today's `generate_data` progress callback emits Python `logging.info` records that clients never see. With FastMCP, `Context.report_progress(progress, total)` sends real MCP `notifications/progress` over the active session. Modern clients render a progress bar for the ~15–30 s `generate_data` cold-cache path. Free win; no client-side change required to benefit.

### D. Streamable HTTP transport & mount

```python
# src/api/mcp/server.py
streamable_http_app = mcp.streamable_http_app()

# src/main.py
from src.api.mcp import streamable_http_app
from src.api.mcp.headers_middleware import MCPRateLimitHeadersMiddleware

app.mount("/mcp", streamable_http_app)
app.add_middleware(MCPRateLimitHeadersMiddleware)
```

Behavior:

- `app.mount("/mcp", ...)` strips the prefix; the FastMCP app sees path `/`. Streamable HTTP only needs one endpoint.
- `MCPRateLimitHeadersMiddleware` is registered last on the parent app, so it runs latest on request / earliest on response — it wraps the FastMCP mount and injects `X-RateLimit-*` headers when `request.state.rate_limit_info` was populated by `_dispatch`. No-op for non-`/mcp` paths.
- Session state: Streamable HTTP issues `Mcp-Session-Id` per `initialize`. FastMCP manages it; no app-level work.
- Protocol version: FastMCP advertises the SDK's current default (2025-06-18 or newer at install time). When a legacy client sends an older version in `initialize`, the SDK negotiates down — backward compatible.
- Auth: `x-api-key` continues to be validated by `APIKeyAuthMiddleware` before requests reach FastMCP. MCP's own OAuth/bearer scheme is not used.

**Gunicorn/Uvicorn timeout verification:** Streamable HTTP can hold a connection open if a response upgrades to SSE for streaming progress. Verify the existing `gunicorn` `--timeout` allows ~60 s in `Dockerfile` and `docker-compose.yml` for `generate_data` cold-cache. If it doesn't, raise to 90 s. Called out as a verification step in the implementation plan.

### E. Deletions and what stays

**Moved to `src/api/mcp/` (verbatim, no semantic changes):**

| Lines in `__init__.py` | Symbol | New home |
|------------------------|--------|----------|
| 21–22 | `_GH_OP_NAMES`, `_GH_OP_LIST_STR` | `src/api/mcp/schemas.py` |
| 26–68 | `GITHUB_OPERATION_INPUT_SCHEMA` | `src/api/mcp/schemas.py` |
| 71–137 | `GithubOperationArgs` (with `@model_validator`) | `src/api/mcp/schemas.py` |
| 178–286 | `TOOL_DESCRIPTIONS` | `src/api/mcp/descriptions.py` |

**Deleted outright from `__init__.py`:**

| Lines | Symbol | Why safe |
|-------|--------|----------|
| 163 | `mcp_router = APIRouter()` | Replaced by FastMCP mount |
| 1109–1545 | `mcp_endpoint()` (~437 lines) | Replaced by FastMCP + dispatch helper |
| 1548–1722 | `_get_tool_schema()` (~175 lines) | Schemas now in `src/api/mcp/schemas.py` and FastMCP-generated from Pydantic models |

**Stays in `__init__.py` (untouched by this migration):**

- `router = APIRouter()` — the REST `/api` router
- `SUPPORTED_TOOLS` dict — still used by `/gateway`; also imported by `src/api/mcp/dispatch.py` (`from src.api.routers import SUPPORTED_TOOLS` — no duplication)
- `gateway_endpoint()` and the entire REST `/gateway` flow (~270 lines)
- All `/rag/*` admin/analytics/observability endpoints
- `/jobs/{job_id}` and `/rag/ingest-async` / `/rag/task/{task_id}`
- `/manifests/devforge.json` endpoint and `_generate_default_manifest()`

**Import cleanup in `__init__.py`:**

- Remove `from src.agents.github.schemas import OPERATION_SCHEMAS` (no longer used here)
- Remove `from pydantic import BaseModel, ValidationError, model_validator` (no longer used here)
- Keep all other imports — they support `/gateway` and RAG endpoints

**Net change to `__init__.py`:** ~1,722 → ~810 lines.

### F. Testing

**Existing MCP test impact:**

| File | MCP refs today | Action |
|------|----------------|--------|
| `tests/test_github_integration.py` | 37 | Keep raw HTTP JSON-RPC calls (minimizes test churn); adjust only response-shape assertions where the SDK's framing differs from today's hand-rolled output |
| `tests/conftest.py` | 1 | Update the `mcp_router` import to the new mount; any fixture that builds JSON-RPC payloads stays as-is |
| All other test files | 0 | Untouched |

The `mcp.client` SDK is used only by the new `tests/test_mcp_sdk.py` (covers SDK-specific behaviors that raw HTTP can't easily exercise, like progress notifications).

**New `tests/test_mcp_sdk.py`** covers:

1. **Protocol handshake:** `initialize` returns `protocolVersion` from the SDK default, `serverInfo.name == "DevForge"`, version `1.0.0`. `tools/list` returns exactly 4 tools by the existing names. Each tool's `description` equals `TOOL_DESCRIPTIONS[name]` verbatim.

2. **Schema parity smoke:** for each tool, `inputSchema["required"]` matches today's list; `properties` keys are a superset. Allow known `anyOf: [type, null]` differences for optional Pydantic fields.

3. **Cross-cutting flow:**
   - Missing `x-api-key` → 401 (parent middleware enforcement, not FastMCP)
   - Over rate-limit → JSON-RPC error code `-32000`, `data.error == "rate_limit_exceeded"`, `X-RateLimit-Limit-Hourly` header present
   - Successful call → `log_request_call.delay(...)` invoked exactly once with the right kwargs (mocked Celery task)
   - `github_operation` with `context.github_token` → token absent from captured log records AND `github_token=` kwarg reaches `github_agent_invoke`
   - `github_operation` structured path with `repo` (not `repo_name`) → normalized to `repo_name` before reaching the agent

4. **GithubOperationArgs validator parity** (port from current behavior):
   - Neither `query` nor `operation` → error "Must specify either 'query' or 'operation'"
   - Unknown `operation` → error includes the full operation list
   - `operation=list_repos` + `query="x"` → error "operation 'list_repos' does not accept a 'query' parameter"
   - `operation=search_code` + `query="x"` → succeeds (search_code's per-op schema accepts `query`)
   - Missing required per-op field → error includes the field name

5. **Progress notifications:** call `generate_data`, assert at least one `notifications/progress` is emitted over the session (uses `mcp.client.streamable_http.streamablehttp_client`).

6. **`generate_data` summary prepend:** result text starts with "Data generation complete." for success.

**Manual smoke (documented, not automated):**

```bash
npx @modelcontextprotocol/inspector
# Connect: http://localhost:8001/mcp with header x-api-key: <dev-key>
# Click each tool, run with sample input, verify response + progress bar for generate_data
```

This is the canonical "is the migration done" gate; listed as the final verification step in the implementation plan.

**What we explicitly do not test in this migration:**

- Per-tool behavior (`test_datagen.py`, `test_github_integration.py` non-MCP cases, etc.) — agents untouched.
- REST `/gateway` — out of scope per decision 3.

## External contract (what clients see)

- Same URL: `POST /mcp`
- Same auth: `x-api-key` header
- Same 4 tool names and parameter shapes
- Same `tools/list` descriptions (`TOOL_DESCRIPTIONS` preserved verbatim)
- Same `X-RateLimit-*` response headers
- Same JSON-RPC error semantics for the existing error cases (validator errors, rate-limit, internal errors)
- New: protocol version 2025-06-18 (negotiated down for older clients)
- New: real MCP progress notifications during `generate_data`

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Schema drift (Pydantic optional vs hand-written) breaks a strict client | Schema parity test (F.2); manual MCP Inspector check before merging |
| `Context.request_context.request` is `None` for non-HTTP transports | We're HTTP-only; guarded `getattr(...)` defaults preserve safety if the field is missing |
| Gunicorn timeout cuts off long Streamable HTTP responses | Verification step in implementation plan; raise to 90 s if today's value is below 60 |
| `GithubOperationArgs` validator behavior subtly changes when moved | Port the validator and its tests verbatim; section F.4 spells out the exact cases |
| Analytics task missed on the new path | Test F.3 asserts `log_request_call.delay` is invoked exactly once per call |
| Rate-limit headers absent from a response | `MCPRateLimitHeadersMiddleware` is exercised in test F.3; verify both block (429-equivalent) and success paths |

## Dependencies

Add to `requirements.txt`:

```
mcp>=1.2.0   # exact version pinned during implementation against the latest stable release
```

No other dependency changes. `fastapi`, `starlette`, `uvicorn`, `gunicorn` already present.

## Out of scope (explicit)

- Refactor of `/api/gateway` REST endpoint (per Q3)
- OAuth/bearer-token MCP auth
- MCP resources/prompts/sampling capabilities (`FastMCP` exposes only `tools` today)
- Tooling additions or removals
- Reorganization of the remaining bloat in `src/api/routers/__init__.py`

## Next step

Implementation plan via the `writing-plans` skill.
