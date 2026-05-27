# MCP SDK Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-rolled JSON-RPC `/mcp` endpoint (`src/api/routers/__init__.py:1109-1545`) with an implementation built on the official MCP Python SDK (`mcp` package, FastMCP API), preserving the external contract (URL, header, tool names, schemas, rate-limit headers, analytics) and adding free MCP progress notifications.

**Architecture:** A new self-contained package `src/api/mcp/` (six small files, each one responsibility) is mounted at `/mcp` via `app.mount(...)` in `src/main.py`. The existing FastAPI middleware stack (`APIKeyAuthMiddleware` populating `request.state.tenant_id` etc.) runs before requests reach FastMCP. A dispatch helper carries the cross-cutting plumbing (rate limit, analytics, token scrub). The REST `/api/gateway` and all RAG admin endpoints are untouched.

**Tech Stack:** `mcp>=1.2.0` (FastMCP + Streamable HTTP), FastAPI 0.120, Pydantic 2.12, Starlette 0.49, pytest, `mcp.client.streamable_http` (test only).

**Source spec:** `docs/superpowers/specs/2026-05-27-mcp-sdk-migration-design.md`

**Branch:** `mcp_sdk_migration` (already created off `rag_resolve`).

**Commit policy:** This repo's owner reviews all changes manually. After each task, run `git add .` to stage — **never** `git commit` or `git push`. Owner commits/pushes after review.

---

## File Plan

**New files (in `src/api/mcp/`):**

| File | Responsibility |
|------|----------------|
| `__init__.py` | Re-export `streamable_http_app` and the `mcp` FastMCP instance |
| `descriptions.py` | `TOOL_DESCRIPTIONS` dict — ported verbatim from `src/api/routers/__init__.py:178-286` |
| `schemas.py` | Pydantic input models (`GenerateDataInput`, `RefinePromptInput`, `GenerateCheatsheetInput`), plus `GithubOperationArgs` validator and `GITHUB_OPERATION_INPUT_SCHEMA` ported verbatim |
| `headers_middleware.py` | ASGI `MCPRateLimitHeadersMiddleware` that injects `X-RateLimit-*` on `/mcp/*` responses |
| `dispatch.py` | `_dispatch()`, `_dispatch_github()`, helper functions for the cross-cutting flow (rate limit, analytics, token scrub, progress callback, `generate_data` summary prepend) |
| `server.py` | `FastMCP` instance, four `@mcp.tool` registrations, `streamable_http_app` export |

**New test file:**

| File | Responsibility |
|------|----------------|
| `tests/test_mcp_sdk.py` | Protocol handshake, schema parity, dispatch cross-cutting flow, `GithubOperationArgs` parity, progress notifications, `generate_data` summary prepend |

**Modified files:**

| File | Change |
|------|--------|
| `requirements.txt` | Add `mcp>=1.2.0` |
| `src/main.py` | Replace `app.include_router(mcp_router)` with `app.mount("/mcp", streamable_http_app)` + add `MCPRateLimitHeadersMiddleware` |
| `src/api/routers/__init__.py` | Delete `mcp_router`, `mcp_endpoint`, `_get_tool_schema`, and remove ported symbols + their imports |
| `tests/conftest.py` | Update docstring example that mentions `/mcp` (no functional change) |
| `tests/test_github_integration.py` | Adjust only any assertions that depended on hand-rolled response shape; keep raw HTTP JSON-RPC calls |

---

## Task 1: Add the `mcp` SDK dependency

**Files:**
- Modify: `requirements.txt` — add one line

- [ ] **Step 1.1: Add the pin to `requirements.txt`**

Open `requirements.txt`. Find a good alphabetical slot near other `mcp`-prefixed packages (there are none — pick a slot near other Anthropic/LLM packages or simply append). Add the line:

```
mcp>=1.2.0
```

- [ ] **Step 1.2: Install in the active venv**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
source venv/bin/activate
pip install -r requirements.txt
```

Expected: `mcp` (and its transitive deps `pydantic`, `anyio`, `httpx`, `sse-starlette`) installed without conflicts. If pip resolves a newer major version, pin the exact installed version in `requirements.txt` (`mcp==X.Y.Z`).

- [ ] **Step 1.3: Smoke-import the SDK pieces we'll use**

Run:

```bash
python -c "from mcp.server.fastmcp import FastMCP, Context; from mcp.shared.exceptions import McpError; from mcp.types import ErrorData; print('mcp OK')"
```

Expected: prints `mcp OK`. If `ImportError`, the SDK package layout changed — check `pip show mcp` for the version and grep `site-packages/mcp/` for the new module path.

- [ ] **Step 1.4: Stage**

```bash
git add requirements.txt
```

> User will commit manually after reviewing all changes for this PR.

---

## Task 2: Create `descriptions.py` (port `TOOL_DESCRIPTIONS` verbatim)

This is the safest first move — pure data, no logic.

**Files:**
- Create: `src/api/mcp/__init__.py` (empty for now — package marker)
- Create: `src/api/mcp/descriptions.py`
- Test: not required (constant data; covered by Task 6's `tools/list` test)

- [ ] **Step 2.1: Create the package directory and empty `__init__.py`**

```bash
mkdir -p src/api/mcp
touch src/api/mcp/__init__.py
```

- [ ] **Step 2.2: Create `src/api/mcp/descriptions.py`**

Copy the entire `TOOL_DESCRIPTIONS` dict from `src/api/routers/__init__.py:178-286` verbatim into a new file. Header:

```python
"""Agent-instructive tool descriptions surfaced via MCP `tools/list`.

These long strings teach calling agents the iterative call pattern,
cache-latency expectations, and per-parameter usage. They must be preserved
verbatim — drift here regresses tool-calling quality for downstream agents.

Source of truth was previously src/api/routers/__init__.py:178-286.
"""

TOOL_DESCRIPTIONS: dict[str, str] = {
    "generate_data": (
        # ... entire string, exactly as in routers/__init__.py ...
    ),
    "github_operation": (
        # ... entire string, exactly as in routers/__init__.py ...
    ),
    "refine_prompt": (
        # ... entire string, exactly as in routers/__init__.py ...
    ),
    "generate_cheatsheet": (
        # ... entire string, exactly as in routers/__init__.py ...
    ),
}
```

**Verification:** the new file must produce byte-identical strings to the originals.

- [ ] **Step 2.3: Verify byte-identical strings**

```bash
python - <<'PY'
from src.api.mcp.descriptions import TOOL_DESCRIPTIONS as new
from src.api.routers import TOOL_DESCRIPTIONS as old
assert new.keys() == old.keys(), f"keys differ: {new.keys() ^ old.keys()}"
for k in old:
    assert new[k] == old[k], f"drift in {k}"
print("TOOL_DESCRIPTIONS: byte-identical OK")
PY
```

Expected: `TOOL_DESCRIPTIONS: byte-identical OK`. If it fails, fix the copy — the agent-instructive text must not drift.

- [ ] **Step 2.4: Stage**

```bash
git add src/api/mcp/__init__.py src/api/mcp/descriptions.py
```

---

## Task 3: Create `schemas.py` (Pydantic models + ported `GithubOperationArgs`)

**Files:**
- Create: `src/api/mcp/schemas.py`
- Test: `tests/test_mcp_sdk.py` (start the file with the validator parity tests)

- [ ] **Step 3.1: Write failing tests for the Pydantic input models**

Create `tests/test_mcp_sdk.py` with:

```python
"""Tests for the new src/api/mcp/* package — input models, validator parity,
dispatch flow, FastMCP handshake, progress notifications."""

import pytest
from pydantic import ValidationError

from src.api.mcp.schemas import (
    GenerateDataInput,
    RefinePromptInput,
    GenerateCheatsheetInput,
    GithubOperationArgs,
    GITHUB_OPERATION_INPUT_SCHEMA,
)


class TestGenerateDataInput:
    def test_minimal_valid(self):
        m = GenerateDataInput(rows=10)
        assert m.rows == 10
        assert m.format == "json"
        assert m.realism_level == "basic"

    def test_rows_below_min_rejected(self):
        with pytest.raises(ValidationError):
            GenerateDataInput(rows=0)

    def test_rows_above_max_rejected(self):
        with pytest.raises(ValidationError):
            GenerateDataInput(rows=10001)

    def test_format_enum_enforced(self):
        with pytest.raises(ValidationError):
            GenerateDataInput(rows=10, format="xml")

    def test_realism_enum_enforced(self):
        with pytest.raises(ValidationError):
            GenerateDataInput(rows=10, realism_level="extreme")


class TestRefinePromptInput:
    def test_minimal_valid(self):
        m = RefinePromptInput(prompt="x")
        assert m.domain == "general"
        assert m.skill_level == "intermediate"

    def test_empty_prompt_rejected(self):
        with pytest.raises(ValidationError):
            RefinePromptInput(prompt="")

    def test_domain_enum_enforced(self):
        with pytest.raises(ValidationError):
            RefinePromptInput(prompt="x", domain="invalid")


class TestGenerateCheatsheetInput:
    def test_all_optional(self):
        m = GenerateCheatsheetInput()
        assert m.skill_level == "beginner"
        assert m.language is None

    def test_language_enum_enforced(self):
        with pytest.raises(ValidationError):
            GenerateCheatsheetInput(language="cobol")
```

- [ ] **Step 3.2: Run the tests to verify they fail**

```bash
pytest tests/test_mcp_sdk.py -v
```

Expected: all fail with `ModuleNotFoundError: No module named 'src.api.mcp.schemas'`.

- [ ] **Step 3.3: Create `src/api/mcp/schemas.py` with the three Pydantic models**

```python
"""Input schemas for the FastMCP-backed /mcp endpoint.

- Pydantic models for the 3 simple tools (generate_data, refine_prompt,
  generate_cheatsheet). FastMCP auto-generates the JSON schema from these.
- GITHUB_OPERATION_INPUT_SCHEMA + GithubOperationArgs are ported verbatim
  from src/api/routers/__init__.py because the oneOf union doesn't translate
  cleanly to a single Pydantic model.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator

from src.agents.github.schemas import OPERATION_SCHEMAS


# --------------------------------------------------------------------------- #
# Simple-tool input models — FastMCP auto-generates JSON schema from these
# --------------------------------------------------------------------------- #


class GenerateDataInput(BaseModel):
    rows: int = Field(..., ge=1, le=10000, description="Number of rows (1-10000)")
    format: Literal["json", "csv"] = "json"
    fields: Optional[list[str]] = None
    prompt: Optional[str] = Field(
        None,
        description=(
            "REQUIRED for custom/domain-specific data generation. Pass the user's "
            "exact description here. Without this field, only generic Faker data is "
            "generated (V1). With this field, LLM-powered semantic generation (V2)."
        ),
    )
    domain: Optional[Literal["ecommerce", "saas", "iot_devices"]] = None
    realism_level: Literal["basic", "medium", "high"] = "basic"
    enable_semantic_generation: bool = True


class RefinePromptInput(BaseModel):
    prompt: str = Field(..., min_length=1, description="User's original prompt — pass verbatim, do not pre-summarize.")
    domain: Literal["general", "image", "code", "rag", "llm"] = "general"
    skill_level: Literal["beginner", "intermediate", "expert"] = "intermediate"
    file_context: Optional[str] = None
    conversation_history: Optional[list[dict[str, str]]] = None
    attached_files: Optional[list[str]] = None
    project_files: Optional[dict[str, str]] = None


class GenerateCheatsheetInput(BaseModel):
    language: Optional[
        Literal[
            "python", "javascript", "typescript", "go", "rust",
            "java", "ruby", "php", "csharp",
        ]
    ] = None
    skill_level: Literal["beginner", "intermediate", "expert"] = "beginner"
    code_context: Optional[str] = None
    intent: Optional[str] = None


# --------------------------------------------------------------------------- #
# github_operation — ported verbatim from routers/__init__.py:21-137
# --------------------------------------------------------------------------- #

_GH_OP_NAMES = sorted(OPERATION_SCHEMAS.keys())
_GH_OP_LIST_STR = ", ".join(_GH_OP_NAMES)


GITHUB_OPERATION_INPUT_SCHEMA: dict = {
    "type": "object",
    "oneOf": [
        {
            "title": "Natural-language",
            "description": "Free-form English query — the LLM extracts intent and parameters.",
            "required": ["query"],
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language description of the GitHub action to perform.",
                },
                "context": {
                    "type": "object",
                    "description": "Optional context (github_token, diff, error_log, files, risk_confirmed, risk_reason, session_id).",
                    "additionalProperties": True,
                },
            },
            "additionalProperties": False,
        },
        {
            "title": "Structured",
            "description": (
                "Typed operation + parameters — skips the LLM intent step (~1-2s faster per call). "
                "Per-operation parameter validation runs at the gateway."
            ),
            "required": ["operation"],
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": _GH_OP_NAMES,
                    "description": "GitHub operation to execute. Per-op parameters are validated at runtime.",
                },
                "context": {
                    "type": "object",
                    "description": "github_token (required), risk_confirmed/risk_reason (for HIGH/CRITICAL ops), diff, error_log, etc.",
                    "additionalProperties": True,
                },
            },
            "additionalProperties": True,
        },
    ],
}


class GithubOperationArgs(BaseModel):
    """MCP-only validator for github_operation arguments.

    Ported verbatim from src/api/routers/__init__.py:71-137. Do not modify
    behavior; semantics tests in tests/test_mcp_sdk.py pin the contract.
    """

    query: Optional[str] = None
    operation: Optional[str] = None
    context: Optional[dict] = None
    model_config = {"extra": "allow"}

    @model_validator(mode="after")
    def _validate_exactly_one_and_op_schema(self) -> "GithubOperationArgs":
        has_query = bool(self.query)
        has_op = bool(self.operation)

        if not has_op:
            if not has_query:
                raise ValueError("Must specify either 'query' or 'operation' in arguments")
            return self

        if self.operation not in OPERATION_SCHEMAS:
            raise ValueError(
                f"Unknown operation '{self.operation}'. Valid operations: [{_GH_OP_LIST_STR}]"
            )
        op_model_cls = OPERATION_SCHEMAS[self.operation]
        op_field_names = set(op_model_cls.model_fields.keys())

        if has_query and "query" not in op_field_names:
            raise ValueError(
                f"Cannot specify both 'query' and 'operation' — operation "
                f"'{self.operation}' does not accept a 'query' parameter"
            )

        excluded = {"operation", "context"}
        if "query" not in op_field_names:
            excluded.add("query")
        op_params = self.model_dump(exclude=excluded)
        op_params = {k: v for k, v in op_params.items() if v is not None}
        if "repo" in op_params and "repo_name" not in op_params:
            op_params["repo_name"] = op_params.pop("repo")
        try:
            op_model_cls(**op_params)
        except ValidationError as e:
            field_msgs = []
            for err in e.errors():
                field = ".".join(str(p) for p in err["loc"])
                msg = err["msg"]
                field_msgs.append(f"'{field}': {msg}")
            combined = "; ".join(field_msgs)
            raise ValueError(f"Operation '{self.operation}' validation errors: {combined}") from e
        return self
```

- [ ] **Step 3.4: Run the tests to verify they pass**

```bash
pytest tests/test_mcp_sdk.py -v
```

Expected: all 11 tests pass.

- [ ] **Step 3.5: Add the `GithubOperationArgs` parity tests**

Append to `tests/test_mcp_sdk.py`:

```python
class TestGithubOperationArgs:
    def test_neither_query_nor_operation_rejected(self):
        with pytest.raises(ValidationError) as exc:
            GithubOperationArgs()
        assert "Must specify either 'query' or 'operation'" in str(exc.value)

    def test_natural_language_path_ok(self):
        m = GithubOperationArgs(query="list my repos")
        assert m.query == "list my repos"
        assert m.operation is None

    def test_unknown_operation_rejected(self):
        with pytest.raises(ValidationError) as exc:
            GithubOperationArgs(operation="time_travel")
        assert "Unknown operation 'time_travel'" in str(exc.value)
        assert "Valid operations:" in str(exc.value)

    def test_query_with_non_query_op_rejected(self):
        # list_repos doesn't accept a `query` field
        with pytest.raises(ValidationError) as exc:
            GithubOperationArgs(operation="list_repos", query="anything")
        assert "does not accept a 'query' parameter" in str(exc.value)

    def test_query_with_search_code_ok(self):
        # search_code's schema accepts `query`
        m = GithubOperationArgs(
            operation="search_code",
            query="def foo",
            repo_name="owner/repo",
        )
        assert m.operation == "search_code"
        assert m.query == "def foo"

    def test_missing_required_per_op_field_reports_field_name(self):
        # create_issue requires title (and repo_name)
        with pytest.raises(ValidationError) as exc:
            GithubOperationArgs(operation="create_issue", repo_name="owner/repo")
        assert "Operation 'create_issue' validation errors" in str(exc.value)
        assert "title" in str(exc.value)


class TestGithubOperationSchema:
    def test_schema_has_oneOf_with_two_branches(self):
        assert "oneOf" in GITHUB_OPERATION_INPUT_SCHEMA
        assert len(GITHUB_OPERATION_INPUT_SCHEMA["oneOf"]) == 2

    def test_schema_lists_all_known_operations(self):
        struct_branch = GITHUB_OPERATION_INPUT_SCHEMA["oneOf"][1]
        op_enum = struct_branch["properties"]["operation"]["enum"]
        from src.agents.github.schemas import OPERATION_SCHEMAS
        assert set(op_enum) == set(OPERATION_SCHEMAS.keys())
```

- [ ] **Step 3.6: Run the new parity tests**

```bash
pytest tests/test_mcp_sdk.py -v
```

Expected: all tests pass (originals + 8 new).

- [ ] **Step 3.7: Stage**

```bash
git add src/api/mcp/schemas.py tests/test_mcp_sdk.py
```

---

## Task 4: Create `headers_middleware.py`

**Files:**
- Create: `src/api/mcp/headers_middleware.py`
- Test: append to `tests/test_mcp_sdk.py`

- [ ] **Step 4.1: Write the failing middleware test**

Append to `tests/test_mcp_sdk.py`:

```python
import asyncio

from src.api.mcp.headers_middleware import MCPRateLimitHeadersMiddleware


def _build_scope(path: str, state: dict) -> dict:
    """Minimal HTTP ASGI scope with a `state` carrier dict."""
    return {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [],
        "state": state,
    }


async def _run(app, scope):
    """Invoke an ASGI app and capture every send() message."""
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    await app(scope, receive, send)
    return sent


class _StubApp:
    """ASGI app that always returns 200 with empty body and no headers."""
    async def __call__(self, scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})


class TestMCPRateLimitHeadersMiddleware:
    def test_injects_headers_on_mcp_path_when_info_present(self):
        info = {
            "hourly_limit": 100, "hourly_used": 5, "hourly_reset_at": "2026-05-27T13:00:00Z",
            "monthly_limit": 10000, "monthly_used": 42, "monthly_reset_at": "2026-06-01T00:00:00Z",
        }
        scope = _build_scope("/mcp", {"rate_limit_info": info})
        sent = asyncio.run(_run(MCPRateLimitHeadersMiddleware(_StubApp()), scope))
        start = next(m for m in sent if m["type"] == "http.response.start")
        header_dict = {k.decode(): v.decode() for k, v in start["headers"]}
        assert header_dict["X-RateLimit-Limit-Hourly"] == "100"
        assert header_dict["X-RateLimit-Used-Hourly"] == "5"
        assert header_dict["X-RateLimit-Reset-Hourly"] == "2026-05-27T13:00:00Z"
        assert header_dict["X-RateLimit-Limit-Monthly"] == "10000"
        assert header_dict["X-RateLimit-Used-Monthly"] == "42"

    def test_skips_when_no_info_in_state(self):
        scope = _build_scope("/mcp", {})
        sent = asyncio.run(_run(MCPRateLimitHeadersMiddleware(_StubApp()), scope))
        start = next(m for m in sent if m["type"] == "http.response.start")
        assert start["headers"] == []

    def test_passes_through_non_mcp_paths(self):
        scope = _build_scope("/api/gateway", {"rate_limit_info": {"hourly_limit": 1, "hourly_used": 0, "hourly_reset_at": "x", "monthly_limit": 1, "monthly_used": 0, "monthly_reset_at": "y"}})
        sent = asyncio.run(_run(MCPRateLimitHeadersMiddleware(_StubApp()), scope))
        start = next(m for m in sent if m["type"] == "http.response.start")
        assert start["headers"] == []  # middleware must not touch non-/mcp paths

    def test_unlimited_tier_renders_as_string(self):
        info = {
            "hourly_limit": None, "hourly_used": 5, "hourly_reset_at": "x",
            "monthly_limit": None, "monthly_used": 42, "monthly_reset_at": "y",
        }
        scope = _build_scope("/mcp", {"rate_limit_info": info})
        sent = asyncio.run(_run(MCPRateLimitHeadersMiddleware(_StubApp()), scope))
        start = next(m for m in sent if m["type"] == "http.response.start")
        header_dict = {k.decode(): v.decode() for k, v in start["headers"]}
        assert header_dict["X-RateLimit-Limit-Hourly"] == "unlimited"
        assert header_dict["X-RateLimit-Limit-Monthly"] == "unlimited"
```

- [ ] **Step 4.2: Run the tests to confirm they fail**

```bash
pytest tests/test_mcp_sdk.py::TestMCPRateLimitHeadersMiddleware -v
```

Expected: all fail with `ModuleNotFoundError: No module named 'src.api.mcp.headers_middleware'`.

- [ ] **Step 4.3: Create `src/api/mcp/headers_middleware.py`**

```python
"""ASGI middleware that injects X-RateLimit-* response headers for /mcp.

The dispatch helper in src/api/mcp/dispatch.py stashes the rate-limit usage
dict in `request.state.rate_limit_info` after each tool call. This middleware
reads it on the response side and adds the same X-RateLimit-* headers the
hand-rolled mcp_endpoint used to emit. No-op for non-/mcp paths.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, MutableMapping


_HEADER_KEYS = (
    ("X-RateLimit-Limit-Hourly",   "hourly_limit"),
    ("X-RateLimit-Used-Hourly",    "hourly_used"),
    ("X-RateLimit-Reset-Hourly",   "hourly_reset_at"),
    ("X-RateLimit-Limit-Monthly",  "monthly_limit"),
    ("X-RateLimit-Used-Monthly",   "monthly_used"),
    ("X-RateLimit-Reset-Monthly",  "monthly_reset_at"),
)


def _build_headers(info: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for header, field in _HEADER_KEYS:
        val = info.get(field)
        if val is None and field.endswith("_limit"):
            out[header] = "unlimited"
        elif val is not None:
            out[header] = str(val)
    return out


class MCPRateLimitHeadersMiddleware:
    """Pure-ASGI middleware. Mount on the parent FastAPI app, not the FastMCP sub-app."""

    def __init__(self, app: Callable[..., Awaitable[Any]]):
        self.app = app

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                info = scope.get("state", {}).get("rate_limit_info")
                if info:
                    extra = _build_headers(info)
                    headers = list(message.get("headers", []))
                    for k, v in extra.items():
                        headers.append((k.encode("latin-1"), v.encode("latin-1")))
                    message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
```

> **Note on `scope["state"]`:** Starlette places `request.state.__dict__` into `scope["state"]` for downstream ASGI tools. When FastAPI middleware sets `request.state.foo = bar`, the dispatch helper inside the FastMCP sub-app can also access it via the same `scope["state"]` dict. This is why the middleware reads from `scope["state"]` rather than re-deriving from headers.

- [ ] **Step 4.4: Run the middleware tests to verify they pass**

```bash
pytest tests/test_mcp_sdk.py::TestMCPRateLimitHeadersMiddleware -v
```

Expected: all 4 tests pass.

- [ ] **Step 4.5: Stage**

```bash
git add src/api/mcp/headers_middleware.py tests/test_mcp_sdk.py
```

---

## Task 5: Create `dispatch.py` (the cross-cutting helper)

This is the biggest, riskiest task. Build it test-first.

**Files:**
- Create: `src/api/mcp/dispatch.py`
- Test: append to `tests/test_mcp_sdk.py`

- [ ] **Step 5.1: Write the failing tests for `_dispatch` happy path**

Append to `tests/test_mcp_sdk.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.mcp.dispatch import _dispatch, _dispatch_github, _tokens_used


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_ctx(state: dict | None = None):
    """Build a fake FastMCP Context with a `request_context.request.state` chain."""
    request = MagicMock()
    request.state = MagicMock()
    if state:
        for k, v in state.items():
            setattr(request.state, k, v)
    request.state.__dict__.setdefault("rate_limit_info", None)
    ctx = MagicMock()
    ctx.request_context.request = request
    ctx.report_progress = AsyncMock()
    return ctx, request


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestDispatchHappyPath:
    async def test_calls_agent_with_correct_kwargs(self):
        ctx, request = _make_ctx({
            "tenant_id": "t1",
            "user_id": "u1",
            "integration_name": "ide",
            "api_key_id": None,
            "tier": "free",
        })
        fake_agent = AsyncMock(return_value={"success": True, "data": {"ok": 1}})

        with patch.dict("src.api.routers.SUPPORTED_TOOLS", {"refine_prompt": fake_agent}):
            result = await _dispatch("refine_prompt", {"prompt": "hi"}, ctx)

        fake_agent.assert_awaited_once()
        call_kwargs = fake_agent.await_args.kwargs
        assert call_kwargs["tenant_id"] == "t1"
        assert call_kwargs["user_id"] == "u1"
        assert call_kwargs["integration_name"] == "ide"
        positional = fake_agent.await_args.args
        assert positional[0] == {"prompt": "hi"}
        assert result == {"success": True, "data": {"ok": 1}}

    async def test_analytics_log_queued_on_success(self):
        ctx, _ = _make_ctx({"tenant_id": "t1", "api_key_id": None, "tier": "free"})
        fake_agent = AsyncMock(return_value={"success": True})

        with patch.dict("src.api.routers.SUPPORTED_TOOLS", {"refine_prompt": fake_agent}), \
             patch("src.workers.tasks.analytics_tasks.log_request_call.delay") as fake_log:
            await _dispatch("refine_prompt", {"prompt": "hi"}, ctx)

        fake_log.assert_called_once()
        kwargs = fake_log.call_args.kwargs
        assert kwargs["tool_name"] == "refine_prompt"
        assert kwargs["success"] is True
        assert kwargs["tenant_id"] == "t1"
```

- [ ] **Step 5.2: Run tests to confirm they fail**

```bash
pytest tests/test_mcp_sdk.py::TestDispatchHappyPath -v
```

Expected: fail with `ModuleNotFoundError: No module named 'src.api.mcp.dispatch'`.

- [ ] **Step 5.3: Create `src/api/mcp/dispatch.py` with the minimal happy path**

```python
"""Cross-cutting dispatch wrapper for FastMCP tool calls.

Replicates the per-call flow that lives inside the hand-rolled mcp_endpoint
(rate-limit pre-check, agent dispatch, analytics log, rate-limit increment,
response-header stashing, generate_data summary prepend). The split between
_dispatch (3 simple tools) and _dispatch_github (special routing + token scrub)
mirrors the existing branch in routers/__init__.py:1311-1394.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from mcp.server.fastmcp import Context
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData

from src.api.routers import SUPPORTED_TOOLS  # untouched dispatch table
from src.api.mcp.schemas import GithubOperationArgs
from src.core.config import settings
from src.core.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _tokens_used(result: dict) -> int:
    """Extract token count from a tool result; falls back to 1."""
    if isinstance(result, dict):
        if "tokens_used" in result:
            return result["tokens_used"]
        data = result.get("data")
        if isinstance(data, dict) and "tokens_used" in data:
            return data["tokens_used"]
    return 1


def _build_progress_callback(ctx: Context) -> Callable[[str, int, str], None]:
    """generate_data accepts (stage, percent, message). FastMCP wants (progress, total)."""
    def cb(stage: str, percent: int, message: str) -> None:
        try:
            # report_progress is async; schedule but don't await — the agent
            # is not async-aware about progress reporting and shouldn't block.
            import asyncio
            asyncio.ensure_future(ctx.report_progress(percent, 100))
            logger.info(f"DataGen Progress: {percent}% - {stage}: {message}")
        except Exception as e:
            logger.warning(f"Progress callback failed: {e}")
    return cb


def _prepend_generate_data_summary(result: dict) -> dict:
    """Preserve the legacy 'DO NOT reproduce the data' instruction prepend."""
    rows = result.get("rows", "N/A")
    data_container = result.get("data", {})
    data_obj = data_container.get("data", {}) if isinstance(data_container, dict) else {}
    if isinstance(data_obj, dict) and data_obj:
        entities = list(data_obj.keys())
        entity_info = f"{len(entities)} entities: {', '.join(entities)}"
    else:
        entity_info = "the requested format"
    summary = (
        f"Data generation complete. {rows} rows generated across {entity_info}. "
        "Results are displayed in the interactive table in the UI. "
        "DO NOT reproduce the data. Just confirm to the user what was generated."
    )
    # Stash the summary in a known field; the FastMCP tool body returns the
    # full dict and FastMCP serializes it as a content block.
    result["_summary"] = summary
    return result


def _extract_state(ctx: Context) -> dict[str, Any]:
    request = ctx.request_context.request
    state = request.state
    return {
        "tenant_id":        getattr(state, "tenant_id", "unknown"),
        "user_id":          getattr(state, "user_id", None),
        "integration_name": getattr(state, "integration_name", "unknown"),
        "api_key_id":       getattr(state, "api_key_id", None),
        "tier":             getattr(state, "tier", "free"),
        "hourly_override":  getattr(state, "hourly_limit_override", None),
        "monthly_override": getattr(state, "monthly_limit_override", None),
        "_state":           state,  # for stashing rate_limit_info post-call
    }


async def _rate_limit_pre_check(ctx_meta: dict[str, Any]) -> None:
    api_key_id = ctx_meta["api_key_id"]
    if not api_key_id:
        return
    allowed, info = await rate_limiter.check_limits(
        api_key_id,
        ctx_meta["tier"],
        hourly_override=ctx_meta["hourly_override"],
        monthly_override=ctx_meta["monthly_override"],
    )
    if not allowed:
        ctx_meta["_state"].rate_limit_info = info
        data = {
            "error": "rate_limit_exceeded",
            "message": f"Rate limit exceeded for {ctx_meta['tier']} tier",
            "limit_info": info,
        }
        if settings.DASHBOARD_UPGRADE_URL:
            data["limit_info"]["upgrade_url"] = settings.DASHBOARD_UPGRADE_URL
        raise McpError(ErrorData(code=-32000, message="Rate limit exceeded", data=data))


async def _post_call_bookkeeping(
    ctx_meta: dict[str, Any],
    tool_name: str,
    args: dict,
    result: dict,
    duration_ms: int,
    success: bool,
) -> None:
    api_key_id = ctx_meta["api_key_id"]

    if success and api_key_id:
        try:
            await rate_limiter.check_and_increment(
                api_key_id,
                ctx_meta["tier"],
                _tokens_used(result),
                hourly_override=ctx_meta["hourly_override"],
                monthly_override=ctx_meta["monthly_override"],
            )
        except Exception as e:
            logger.warning(f"Rate limit increment failed: {e}")

    # Fire-and-forget analytics. Lazy-import to keep startup cheap.
    try:
        from src.workers.tasks.analytics_tasks import log_request_call
        from src.utils.sanitization import truncate_input
        log_request_call.delay(
            user_id=ctx_meta["user_id"],
            tenant_id=ctx_meta["tenant_id"],
            integration_name=ctx_meta["integration_name"],
            tool_name=tool_name,
            input_summary=truncate_input(args),
            success=success,
            duration_ms=duration_ms,
        )
    except Exception as e:
        logger.warning(f"Analytics log queue failed: {e}")

    if api_key_id:
        try:
            usage = await rate_limiter.get_usage(api_key_id, ctx_meta["tier"])
            ctx_meta["_state"].rate_limit_info = usage
        except Exception as e:
            logger.warning(f"Failed to fetch rate-limit usage for headers: {e}")


# --------------------------------------------------------------------------- #
# Public dispatch entry points
# --------------------------------------------------------------------------- #


async def _dispatch(tool_name: str, args: dict, ctx: Context) -> dict:
    """Standard tool dispatch (generate_data, refine_prompt, generate_cheatsheet)."""
    ctx_meta = _extract_state(ctx)
    await _rate_limit_pre_check(ctx_meta)

    progress_cb = _build_progress_callback(ctx) if tool_name == "generate_data" else None

    start = time.time()
    agent_func = SUPPORTED_TOOLS[tool_name]
    kwargs = {"progress_callback": progress_cb} if progress_cb else {}
    result = await agent_func(
        args,
        tenant_id=ctx_meta["tenant_id"],
        integration_name=ctx_meta["integration_name"],
        user_id=ctx_meta["user_id"],
        **kwargs,
    )
    duration_ms = int((time.time() - start) * 1000)
    success = result.get("success", True) and not result.get("error")

    await _post_call_bookkeeping(ctx_meta, tool_name, args, result, duration_ms, success)

    if tool_name == "generate_data" and success:
        result = _prepend_generate_data_summary(result)

    if result.get("error"):
        raise McpError(ErrorData(code=-32603, message=result["error"]))

    return result


async def _dispatch_github(validated: GithubOperationArgs, ctx: Context) -> dict:
    """Github tool dispatch (structured vs NL routing + github_token scrub)."""
    ctx_meta = _extract_state(ctx)
    await _rate_limit_pre_check(ctx_meta)

    context = dict(validated.context or {})
    # Pop token BEFORE any logging — never log raw tokens.
    github_token = context.pop("github_token", None)

    agent_func = SUPPORTED_TOOLS["github_operation"]

    start = time.time()
    if validated.operation:
        op_params = validated.model_dump(exclude={"operation", "context"})
        op_params = {k: v for k, v in op_params.items() if v is not None}
        if "repo" in op_params and "repo_name" not in op_params:
            op_params["repo_name"] = op_params.pop("repo")
        result = await agent_func(
            operation=validated.operation,
            parameters=op_params,
            context=context,
            github_token=github_token,
            tenant_id=ctx_meta["tenant_id"],
            integration_name=ctx_meta["integration_name"],
            user_id=ctx_meta["user_id"],
        )
    else:
        result = await agent_func(
            query=validated.query,
            context=context,
            github_token=github_token,
            tenant_id=ctx_meta["tenant_id"],
            integration_name=ctx_meta["integration_name"],
            user_id=ctx_meta["user_id"],
        )
    duration_ms = int((time.time() - start) * 1000)
    success = result.get("success", True) and not result.get("error")

    args_for_log: dict = {"operation": validated.operation, "query": validated.query}
    await _post_call_bookkeeping(ctx_meta, "github_operation", args_for_log, result, duration_ms, success)

    if result.get("error"):
        raise McpError(ErrorData(code=-32603, message=result["error"]))

    return result
```

- [ ] **Step 5.4: Run the happy-path tests**

```bash
pytest tests/test_mcp_sdk.py::TestDispatchHappyPath -v
```

Expected: both tests pass.

- [ ] **Step 5.5: Add rate-limit tests**

Append to `tests/test_mcp_sdk.py`:

```python
@pytest.mark.asyncio
class TestDispatchRateLimit:
    async def test_rate_limit_block_raises_mcp_error_with_data(self):
        ctx, request = _make_ctx({
            "tenant_id": "t1", "api_key_id": "key1", "tier": "free",
        })
        info = {"hourly_used": 100, "hourly_limit": 100,
                "monthly_used": 1, "monthly_limit": 10,
                "hourly_reset_at": "x", "monthly_reset_at": "y"}

        fake_agent = AsyncMock(return_value={"success": True})

        with patch.dict("src.api.routers.SUPPORTED_TOOLS", {"refine_prompt": fake_agent}), \
             patch("src.api.mcp.dispatch.rate_limiter") as rl:
            rl.check_limits = AsyncMock(return_value=(False, info))
            with pytest.raises(McpError) as exc:
                await _dispatch("refine_prompt", {"prompt": "x"}, ctx)

        assert exc.value.error.code == -32000
        assert exc.value.error.data["error"] == "rate_limit_exceeded"
        # state stash for headers middleware
        assert request.state.rate_limit_info == info
        # agent never called
        fake_agent.assert_not_awaited()

    async def test_increment_called_on_success(self):
        ctx, _ = _make_ctx({"tenant_id": "t1", "api_key_id": "key1", "tier": "free"})
        fake_agent = AsyncMock(return_value={"success": True, "tokens_used": 42})

        with patch.dict("src.api.routers.SUPPORTED_TOOLS", {"refine_prompt": fake_agent}), \
             patch("src.api.mcp.dispatch.rate_limiter") as rl:
            rl.check_limits = AsyncMock(return_value=(True, {}))
            rl.check_and_increment = AsyncMock()
            rl.get_usage = AsyncMock(return_value={
                "hourly_limit": 100, "hourly_used": 1, "hourly_reset_at": "x",
                "monthly_limit": 10, "monthly_used": 1, "monthly_reset_at": "y",
            })
            await _dispatch("refine_prompt", {"prompt": "x"}, ctx)

        rl.check_and_increment.assert_awaited_once()
        assert rl.check_and_increment.await_args.args[2] == 42  # tokens_used
```

- [ ] **Step 5.6: Run them**

```bash
pytest tests/test_mcp_sdk.py::TestDispatchRateLimit -v
```

Expected: pass.

- [ ] **Step 5.7: Add `_dispatch_github` token-scrub + structured-path tests**

Append to `tests/test_mcp_sdk.py`:

```python
@pytest.mark.asyncio
class TestDispatchGithub:
    async def test_token_stripped_from_context_before_agent(self):
        ctx, _ = _make_ctx({"tenant_id": "t1", "api_key_id": None, "tier": "free"})
        fake_agent = AsyncMock(return_value={"success": True})
        args = GithubOperationArgs(query="list repos", context={"github_token": "ghp_secret", "diff": "X"})

        with patch.dict("src.api.routers.SUPPORTED_TOOLS", {"github_operation": fake_agent}):
            await _dispatch_github(args, ctx)

        kwargs = fake_agent.await_args.kwargs
        assert kwargs["github_token"] == "ghp_secret"
        # context that reaches the agent must NOT contain github_token
        assert "github_token" not in kwargs["context"]
        assert kwargs["context"]["diff"] == "X"

    async def test_structured_path_normalizes_repo_to_repo_name(self):
        ctx, _ = _make_ctx({"tenant_id": "t1", "api_key_id": None, "tier": "free"})
        fake_agent = AsyncMock(return_value={"success": True})
        args = GithubOperationArgs(operation="list_branches", repo="owner/repo")

        with patch.dict("src.api.routers.SUPPORTED_TOOLS", {"github_operation": fake_agent}):
            await _dispatch_github(args, ctx)

        kwargs = fake_agent.await_args.kwargs
        assert kwargs["operation"] == "list_branches"
        assert kwargs["parameters"]["repo_name"] == "owner/repo"
        assert "repo" not in kwargs["parameters"]

    async def test_nl_path_passes_query(self):
        ctx, _ = _make_ctx({"tenant_id": "t1", "api_key_id": None, "tier": "free"})
        fake_agent = AsyncMock(return_value={"success": True})
        args = GithubOperationArgs(query="show me PRs")

        with patch.dict("src.api.routers.SUPPORTED_TOOLS", {"github_operation": fake_agent}):
            await _dispatch_github(args, ctx)

        kwargs = fake_agent.await_args.kwargs
        assert kwargs["query"] == "show me PRs"
        assert kwargs["github_token"] is None
```

- [ ] **Step 5.8: Run them**

```bash
pytest tests/test_mcp_sdk.py::TestDispatchGithub -v
```

Expected: pass.

- [ ] **Step 5.9: Add `_tokens_used` helper test**

Append:

```python
class TestTokensUsed:
    def test_top_level(self):
        assert _tokens_used({"tokens_used": 5}) == 5

    def test_nested_in_data(self):
        assert _tokens_used({"data": {"tokens_used": 7}}) == 7

    def test_default(self):
        assert _tokens_used({"success": True}) == 1
```

- [ ] **Step 5.10: Run it**

```bash
pytest tests/test_mcp_sdk.py::TestTokensUsed -v
```

Expected: 3 passes.

- [ ] **Step 5.11: Run the full file to ensure nothing regressed**

```bash
pytest tests/test_mcp_sdk.py -v
```

Expected: every test in the file passes.

- [ ] **Step 5.12: Stage**

```bash
git add src/api/mcp/dispatch.py tests/test_mcp_sdk.py
```

---

## Task 6: Create `server.py` and re-export from `__init__.py`

**Files:**
- Modify: `src/api/mcp/__init__.py`
- Create: `src/api/mcp/server.py`
- Test: append to `tests/test_mcp_sdk.py` (handshake + tools/list)

- [ ] **Step 6.1: Write the failing handshake test (TestClient-based)**

Append to `tests/test_mcp_sdk.py`:

```python
import json

from fastapi.testclient import TestClient


@pytest.fixture
def mcp_client(monkeypatch):
    """Build a TestClient with /mcp mounted but auth/rate-limit bypassed.

    APIKeyAuthMiddleware would otherwise reject our test requests. We disable
    it here via a feature flag (added in Task 7) OR by patching the middleware
    no-op. For Task 6, we instantiate FastAPI bare and mount FastMCP directly.
    """
    from fastapi import FastAPI
    from src.api.mcp import streamable_http_app

    app = FastAPI()
    app.mount("/mcp", streamable_http_app)
    return TestClient(app)


def _rpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}


class TestFastMCPHandshake:
    def test_initialize_returns_serverinfo(self, mcp_client):
        # Streamable HTTP requires explicit content-type negotiation.
        headers = {"Accept": "application/json, text/event-stream"}
        resp = mcp_client.post("/mcp/", json=_rpc("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.0.1"},
        }), headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"]["serverInfo"]["name"] == "DevForge"
        assert body["result"]["serverInfo"]["version"] == "1.0.0"

    def test_tools_list_returns_all_four(self, mcp_client):
        from src.api.mcp.descriptions import TOOL_DESCRIPTIONS

        headers = {"Accept": "application/json, text/event-stream"}
        # Most SDKs require initialize before tools/list. The TestClient is
        # stateless per-call; rely on FastMCP's sessionless mode for tests.
        resp = mcp_client.post("/mcp/", json=_rpc("tools/list"), headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        names = {t["name"] for t in body["result"]["tools"]}
        assert names == {"generate_data", "github_operation", "refine_prompt", "generate_cheatsheet"}
        for tool in body["result"]["tools"]:
            assert tool["description"] == TOOL_DESCRIPTIONS[tool["name"]]
```

> **Why these tests may need an initialize step first depending on SDK version:** FastMCP's Streamable HTTP transport defaults to *stateful* sessions but can be configured stateless via `mcp.streamable_http_app(stateless=True)`. We use stateless for tests so each call works without `Mcp-Session-Id` round-trips. See Task 6.3 — the server is configured `stateless=True`.

- [ ] **Step 6.2: Run them to confirm failure**

```bash
pytest tests/test_mcp_sdk.py::TestFastMCPHandshake -v
```

Expected: `ModuleNotFoundError` for `src.api.mcp.server` or `streamable_http_app`.

- [ ] **Step 6.3: Create `src/api/mcp/server.py`**

```python
"""FastMCP server instance + tool registrations + Streamable HTTP app export."""

from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from src.api.mcp.descriptions import TOOL_DESCRIPTIONS
from src.api.mcp.dispatch import _dispatch, _dispatch_github
from src.api.mcp.schemas import (
    GITHUB_OPERATION_INPUT_SCHEMA,
    GenerateCheatsheetInput,
    GenerateDataInput,
    GithubOperationArgs,
    RefinePromptInput,
)


mcp = FastMCP(
    name="DevForge",
    version="1.0.0",
    instructions="DevForge tools: data generation, GitHub automation, prompt refinement, cheatsheets.",
    stateless_http=True,
)


@mcp.tool(name="generate_data", description=TOOL_DESCRIPTIONS["generate_data"])
async def generate_data(args: GenerateDataInput, ctx: Context) -> dict:
    return await _dispatch("generate_data", args.model_dump(exclude_none=True), ctx)


@mcp.tool(name="refine_prompt", description=TOOL_DESCRIPTIONS["refine_prompt"])
async def refine_prompt(args: RefinePromptInput, ctx: Context) -> dict:
    return await _dispatch("refine_prompt", args.model_dump(exclude_none=True), ctx)


@mcp.tool(name="generate_cheatsheet", description=TOOL_DESCRIPTIONS["generate_cheatsheet"])
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


# Streamable HTTP ASGI app for mounting under FastAPI.
streamable_http_app = mcp.streamable_http_app()
```

> **`stateless_http=True`:** Removes the `Mcp-Session-Id` requirement. Easier for stateless API-key clients and matches today's hand-rolled behavior (no sessions). MCP Inspector and Claude clients still work — they fall back to per-request initialization.
>
> **The `input_schema` kwarg on the github tool:** if your installed `mcp` version names this kwarg differently (`inputSchema`, `schema`, etc.), check `help(mcp.tool)` or `inspect.signature(FastMCP.tool)`. The SDK API stabilized in 1.2.0+; adjust per the actual signature.

- [ ] **Step 6.4: Update `src/api/mcp/__init__.py` to re-export**

```python
"""DevForge MCP server — FastMCP-based replacement for the hand-rolled /mcp endpoint."""

from src.api.mcp.server import mcp, streamable_http_app

__all__ = ["mcp", "streamable_http_app"]
```

- [ ] **Step 6.5: Run the handshake tests**

```bash
pytest tests/test_mcp_sdk.py::TestFastMCPHandshake -v
```

Expected: both pass. If the test fails because `mcp.tool(input_schema=...)` isn't accepted, the SDK signature differs — `pip show mcp` to see the version and adjust the kwarg name. Document the chosen signature in `src/api/mcp/server.py` as a one-line comment.

- [ ] **Step 6.6: Add a schema-parity smoke test**

Append:

```python
class TestToolSchemas:
    def test_required_fields_match_legacy(self, mcp_client):
        headers = {"Accept": "application/json, text/event-stream"}
        resp = mcp_client.post("/mcp/", json=_rpc("tools/list"), headers=headers)
        tools = {t["name"]: t for t in resp.json()["result"]["tools"]}

        # generate_data — `rows` is the only required field
        assert tools["generate_data"]["inputSchema"]["required"] == ["rows"]

        # refine_prompt — `prompt` is required
        assert tools["refine_prompt"]["inputSchema"]["required"] == ["prompt"]

        # generate_cheatsheet — nothing required
        assert tools["generate_cheatsheet"]["inputSchema"].get("required", []) == []

        # github_operation — oneOf schema preserved
        assert "oneOf" in tools["github_operation"]["inputSchema"]
        assert len(tools["github_operation"]["inputSchema"]["oneOf"]) == 2
```

- [ ] **Step 6.7: Run it**

```bash
pytest tests/test_mcp_sdk.py::TestToolSchemas -v
```

Expected: pass. If Pydantic auto-generation puts extra fields in `required`, switch the affected Pydantic field to have an explicit default value (e.g., `format: Literal["json", "csv"] = "json"` already does this).

- [ ] **Step 6.8: Stage**

```bash
git add src/api/mcp/__init__.py src/api/mcp/server.py tests/test_mcp_sdk.py
```

---

## Task 7: Wire FastMCP into `src/main.py`

**Files:**
- Modify: `src/main.py`
- Test: append end-to-end tests to `tests/test_mcp_sdk.py`

- [ ] **Step 7.1: Read the current relevant lines in `src/main.py`**

Open `src/main.py:16` and `src/main.py:93`:

```python
# line 16:
from src.api.routers import router, mcp_router

# line 93:
app.include_router(mcp_router)  # MCP endpoints
```

- [ ] **Step 7.2: Replace those two lines**

Change line 16 to:

```python
from src.api.routers import router
```

Replace line 93 (`app.include_router(mcp_router)`) with:

```python
# MCP endpoint (FastMCP-backed Streamable HTTP, mounted as ASGI sub-app)
from src.api.mcp import streamable_http_app
from src.api.mcp.headers_middleware import MCPRateLimitHeadersMiddleware
app.mount("/mcp", streamable_http_app)
app.add_middleware(MCPRateLimitHeadersMiddleware)
```

> **Middleware order:** Starlette wraps `add_middleware` calls so the last-added runs first on the request. By adding `MCPRateLimitHeadersMiddleware` *after* the existing auth middlewares (CORS / JWTAuth / APIKeyAuth / DashboardAuth, all already added earlier in `main.py`), it wraps the FastMCP mount and runs latest on request / earliest on response — correct for header injection.
>
> **Why mount, not include_router:** FastMCP's `streamable_http_app()` returns a Starlette ASGI app, not a FastAPI `APIRouter`. `app.mount(...)` is the right tool.

- [ ] **Step 7.3: Smoke-start the server to confirm it boots**

```bash
uvicorn src.main:app --port 18001
```

Expected output includes `Application startup complete.` In a separate terminal:

```bash
curl -sS -X POST http://localhost:18001/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

Expected: `401 Unauthorized` (APIKeyAuthMiddleware is doing its job — no `x-api-key` header). That's correct; auth is still enforced before the mount.

Add the API key:

```bash
curl -sS -X POST http://localhost:18001/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "x-api-key: dev-test-key" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

Expected: a JSON-RPC response with `serverInfo.name == "DevForge"`. (If `x-api-key: dev-test-key` isn't a valid local dev key, use one from your local DB; see `docs/API.md`.)

Kill the dev server (`Ctrl-C`).

- [ ] **Step 7.4: Add a full-stack TestClient test**

Append to `tests/test_mcp_sdk.py`:

```python
class TestEndToEndViaMain:
    """Hit /mcp through the real FastAPI app from src/main.py.

    Bypasses auth by setting request.state directly via a custom middleware
    inserted between APIKeyAuth and FastMCP. Done as a fixture override so
    the test doesn't depend on a live DB.
    """

    @pytest.fixture
    def real_client(self, monkeypatch):
        # Bypass the API key middleware for tests by stubbing its dispatch.
        from src.core.api_key_middleware import APIKeyAuthMiddleware

        async def passthrough(self, request, call_next):
            request.state.tenant_id = "test-tenant"
            request.state.user_id = "test-user"
            request.state.integration_name = "pytest"
            request.state.api_key_id = None  # disables rate-limit branch
            request.state.tier = "free"
            return await call_next(request)

        monkeypatch.setattr(APIKeyAuthMiddleware, "dispatch", passthrough)

        from src.main import app
        return TestClient(app)

    def test_tools_list_via_main(self, real_client):
        headers = {"Accept": "application/json, text/event-stream"}
        resp = real_client.post(
            "/mcp/",
            headers={"x-api-key": "ignored-bypassed", **headers},
            json=_rpc("tools/list"),
        )
        assert resp.status_code == 200
        names = {t["name"] for t in resp.json()["result"]["tools"]}
        assert names == {"generate_data", "github_operation", "refine_prompt", "generate_cheatsheet"}
```

- [ ] **Step 7.5: Run the new test**

```bash
pytest tests/test_mcp_sdk.py::TestEndToEndViaMain -v
```

Expected: pass. If it fails because importing `src.main` triggers DB / Redis lookups, scope the test to skip on missing services — but the lifespan only logs at startup, so import should be safe.

- [ ] **Step 7.6: Stage**

```bash
git add src/main.py tests/test_mcp_sdk.py
```

---

## Task 8: Delete old MCP code from `src/api/routers/__init__.py`

**Files:**
- Modify: `src/api/routers/__init__.py`

This is a large delete. Use one focused edit per chunk so review is straightforward.

- [ ] **Step 8.1: Verify the new MCP path is fully wired before deleting the old one**

```bash
pytest tests/test_mcp_sdk.py -v
```

Expected: every test passes. **If any test fails, STOP** — do not delete anything until the new path is green.

- [ ] **Step 8.2: Delete `mcp_router = APIRouter()` (line 163)**

```python
# REMOVE:
mcp_router = APIRouter()
```

Leave the `router = APIRouter()` line on 162 untouched.

- [ ] **Step 8.3: Delete `mcp_endpoint` function (lines 1109–1545)**

Remove the entire `@mcp_router.post("/mcp")` block and the `async def mcp_endpoint(...)` body. That's ~437 lines starting at:

```python
@mcp_router.post("/mcp")
async def mcp_endpoint(request: Request):
```

and ending right before the `def _get_tool_schema(...)` definition at line 1548.

- [ ] **Step 8.4: Delete `_get_tool_schema` function (lines 1548–1722)**

Remove the entire `def _get_tool_schema(tool_name: str) -> dict:` function and its `schemas` dict body. The file should now end at the `_get_tool_schema` definition's previous line.

- [ ] **Step 8.5: Delete the ported symbols and their imports**

Remove:

- Lines 18: `from src.agents.github.schemas import OPERATION_SCHEMAS`
- Lines 20–22: the `_GH_OP_NAMES`, `_GH_OP_LIST_STR` block (and the comment above it)
- Lines 24–68: `GITHUB_OPERATION_INPUT_SCHEMA`
- Lines 70–137: `class GithubOperationArgs(BaseModel): ...`
- Lines 178–286: `TOOL_DESCRIPTIONS = {...}`

In the imports at the top, also remove:

```python
# REMOVE:
from pydantic import BaseModel, ValidationError, model_validator
```

…**only if no remaining code uses them.** Grep first:

```bash
grep -n "BaseModel\|ValidationError\|model_validator" src/api/routers/__init__.py
```

If `BaseModel` is still used (e.g., by another model in the file), leave it. Otherwise remove. Same logic for `ValidationError` and `model_validator`.

- [ ] **Step 8.6: Confirm the file still imports cleanly**

```bash
python -c "import src.api.routers; print('OK')"
```

Expected: `OK`. If `NameError` or `ImportError`, find the dangling reference and fix.

- [ ] **Step 8.7: Run the full test suite (or at least the directly affected files)**

```bash
pytest tests/test_mcp_sdk.py tests/test_github_integration.py tests/test_api.py -v
```

Expected: all `tests/test_mcp_sdk.py` tests pass. `test_github_integration.py` and `test_api.py` may have failures from response-shape drift — those are addressed in Task 9.

- [ ] **Step 8.8: Stage**

```bash
git add src/api/routers/__init__.py
```

---

## Task 9: Update existing MCP-touching tests

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_github_integration.py`

- [ ] **Step 9.1: Update the docstring in `tests/conftest.py`**

Open `tests/conftest.py:115-126`. Find the docstring fragment:

```python
        with patch_github_operation(mock):
            response = client.post("/mcp", json=...)
```

Replace `/mcp` with `/mcp/`. The Streamable HTTP mount expects the trailing slash (FastMCP serves at `/`).

- [ ] **Step 9.2: Run the suite to see what test_github_integration.py drift looks like**

```bash
pytest tests/test_github_integration.py -v
```

Take note of every failing test and the assertion that fails. Classify into:

- **(a) response-format drift** (e.g., `result.content[0].text` differs slightly from old `result.content[0].text`)
- **(b) status-code drift** (e.g., old returned 200 with error in body, new returns 200 with `result.isError=true`)
- **(c) error-message drift** (e.g., the wording of validator errors changed because Pydantic v2 wrapping)
- **(d) genuine semantic regression** — must investigate, do NOT just adjust the assertion

- [ ] **Step 9.3: For each (a)/(b)/(c) failure, adjust the test assertion**

Examples of acceptable drift adjustments:

- Old: `assert resp.json()["error"]["message"] == "Invalid params: 'name' is required"`
  New: `assert "name" in resp.json()["error"]["message"]` (still validates the field name surfaces)

- Old: `assert resp.json()["result"]["isError"] is False`
  New: same (FastMCP preserves `isError`)

- Old: `assert "github_token" not in caplog.text`
  New: same (token scrub still in dispatch.py)

- [ ] **Step 9.4: For any (d) failure, STOP and investigate**

Re-run with `-s` and check the actual responses. Compare against the dispatch helper. Fix the helper, not the test. The contract must be preserved.

- [ ] **Step 9.5: Re-run the suite**

```bash
pytest tests/ -v
```

Expected: full green. Investigate any new failures.

- [ ] **Step 9.6: Stage**

```bash
git add tests/conftest.py tests/test_github_integration.py
```

---

## Task 10: Verify Gunicorn / Docker timeout (no code change expected)

**Files:** none modified — verification only.

- [ ] **Step 10.1: Confirm `--timeout 120` in `Dockerfile`**

```bash
grep -n "timeout" Dockerfile
```

Expected:

```
102:    "--timeout", "120"]
```

If `--timeout` is below 60, raise it to 120 in `Dockerfile` and stage that change (`git add Dockerfile`).

- [ ] **Step 10.2: Confirm `docker-compose.yml` does not override the Gunicorn timeout**

```bash
grep -n "command\|gunicorn\|uvicorn.workers" docker-compose.yml
```

Expected: the `api` service uses Uvicorn directly for dev (`uvicorn src.main:app --reload`), inheriting Docker's container-level keepalive. Production runs `gunicorn` per `Dockerfile`. No overrides expected.

- [ ] **Step 10.3: Document the check in the implementation log**

Add a comment to the PR description (when the user opens it): "Gunicorn `--timeout 120` already exceeds the worst-case Streamable HTTP hold (`generate_data` cold-cache ~30s). No Docker change required."

---

## Task 11: Manual MCP Inspector smoke test

**Files:** none modified — verification only. This is the canonical "is the migration done" gate.

- [ ] **Step 11.1: Start the dev server**

```bash
source venv/bin/activate
uvicorn src.main:app --port 8001 --reload
```

- [ ] **Step 11.2: Launch MCP Inspector**

In a separate terminal:

```bash
npx @modelcontextprotocol/inspector
```

A browser tab opens.

- [ ] **Step 11.3: Connect to the local server**

In Inspector:
- Transport: **Streamable HTTP**
- URL: `http://localhost:8001/mcp/`
- Custom headers: `x-api-key: <your-local-dev-key>`

Click **Connect**.

Expected: `Connected` status, server info shows `DevForge 1.0.0`.

- [ ] **Step 11.4: Verify tools/list**

Click the **Tools** tab. Expected: 4 tools listed by name (`generate_data`, `github_operation`, `refine_prompt`, `generate_cheatsheet`) with the long agent-instructive descriptions intact.

- [ ] **Step 11.5: Call each tool once**

For each of the 4 tools, fill in minimal arguments and click **Run**:

- `generate_data`: `{"rows": 5}` — expected: success, response includes `data` and "Data generation complete." preamble. **Verify a progress indicator appears during the call** (the free upgrade — Section C of the spec).
- `refine_prompt`: `{"prompt": "build a calculator"}` — expected: success, `data.refined_prompt` non-empty.
- `generate_cheatsheet`: `{"language": "python"}` — expected: success, `data.markdown` non-empty.
- `github_operation`: `{"query": "list my repos", "context": {"github_token": "<your-PAT>"}}` — expected: success or a clear permission-related error if the PAT is wrong. **Verify the `x-api-key` and `github_token` do NOT appear in the server log** (`tail -f logs/* 2>/dev/null` or just watch the uvicorn terminal).

- [ ] **Step 11.6: Verify rate-limit headers on the response**

In the Inspector's "Response" panel, expand the HTTP headers. Expected: `X-RateLimit-Limit-Hourly`, `X-RateLimit-Used-Hourly`, etc. present.

- [ ] **Step 11.7: Document outcome**

If all four tools work and progress + headers behave correctly, the migration is done. Note this in your PR description.

If anything fails, capture the Inspector network-tab payload + the server log line. Fix in the relevant file and re-run from Step 11.5.

- [ ] **Step 11.8: Final stage check**

```bash
git status --short
```

Expected: only changes shown are the files explicitly staged in tasks 1–9. No accidental edits. The user reviews `git diff --staged` and commits manually.

---

## Self-review (against the spec)

**1. Spec coverage check:**

| Spec section | Tasks |
|--------------|-------|
| A. File layout | T2–T6 (create), T7 (wire), T8 (delete) |
| B. Tool registration & schemas | T3 (schemas), T6 (registrations) |
| C. Cross-cutting concerns | T5 (dispatch helper + tests) |
| D. Streamable HTTP transport | T6 (FastMCP instance), T7 (mount + middleware), T10 (timeout verification) |
| E. Deletions | T8 |
| F. Testing | T3/T4/T5/T6/T7 (unit + e2e), T9 (existing-test adjustments), T11 (manual Inspector) |
| External contract preservation | T11.4–T11.6 (verified end-to-end) |
| `mcp>=1.2.0` dependency | T1 |

No gaps.

**2. Placeholder scan:** every code block is concrete; every `...` is verbatim-port shorthand explicitly defined in T2.2's instructions. No "TBD", no "implement later".

**3. Type consistency:** function names match across tasks (`_dispatch`, `_dispatch_github`, `_tokens_used`, `_extract_state`, `_rate_limit_pre_check`, `_post_call_bookkeeping`, `_build_progress_callback`, `_prepend_generate_data_summary`, `_build_headers`, `streamable_http_app`, `mcp`). Module names match (`src.api.mcp.{descriptions,schemas,dispatch,headers_middleware,server}`).
