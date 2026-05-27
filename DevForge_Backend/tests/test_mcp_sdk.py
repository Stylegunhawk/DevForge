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
        assert start["headers"] == []

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


from unittest.mock import AsyncMock, MagicMock, patch

from mcp.shared.exceptions import McpError

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
        assert request.state.rate_limit_info == info
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


class TestTokensUsed:
    def test_top_level(self):
        assert _tokens_used({"tokens_used": 5}) == 5

    def test_nested_in_data(self):
        assert _tokens_used({"data": {"tokens_used": 7}}) == 7

    def test_default(self):
        assert _tokens_used({"success": True}) == 1


# --------------------------------------------------------------------------- #
# T6: server.py — in-process registration tests (no HTTP / no lifespan needed)
# --------------------------------------------------------------------------- #


class TestFastMCPRegistration:
    """Verify the FastMCP instance in server.py has the right name, version, and tools."""

    def test_server_name(self):
        from src.api.mcp.server import mcp
        assert mcp._mcp_server.name == "DevForge"

    def test_server_version(self):
        from src.api.mcp.server import mcp
        assert mcp._mcp_server.version == "1.0.0"

    def test_four_tools_registered(self):
        from src.api.mcp.server import mcp
        names = set(mcp._tool_manager._tools.keys())
        assert names == {"generate_data", "github_operation", "refine_prompt", "generate_cheatsheet"}

    def test_descriptions_match(self):
        from src.api.mcp.server import mcp
        from src.api.mcp.descriptions import TOOL_DESCRIPTIONS
        for name, tool in mcp._tool_manager._tools.items():
            assert tool.description == TOOL_DESCRIPTIONS[name], f"description drift: {name}"

    def test_streamable_http_app_is_starlette(self):
        from starlette.applications import Starlette
        from src.api.mcp import streamable_http_app
        assert isinstance(streamable_http_app, Starlette)


class TestToolSchemas:
    """Verify JSON schemas match the legacy hand-rolled contract."""

    def _tools(self):
        from src.api.mcp.server import mcp
        return {name: t for name, t in mcp._tool_manager._tools.items()}

    def test_generate_data_required(self):
        assert self._tools()["generate_data"].parameters["required"] == ["rows"]

    def test_refine_prompt_required(self):
        assert self._tools()["refine_prompt"].parameters["required"] == ["prompt"]

    def test_generate_cheatsheet_no_required(self):
        assert self._tools()["generate_cheatsheet"].parameters.get("required", []) == []

    def test_github_operation_oneOf_two_branches(self):
        schema = self._tools()["github_operation"].parameters
        assert "oneOf" in schema
        assert len(schema["oneOf"]) == 2

    def test_github_operation_lists_all_operations(self):
        from src.agents.github.schemas import OPERATION_SCHEMAS
        schema = self._tools()["github_operation"].parameters
        struct_branch = schema["oneOf"][1]
        op_enum = struct_branch["properties"]["operation"]["enum"]
        assert set(op_enum) == set(OPERATION_SCHEMAS.keys())


# --------------------------------------------------------------------------- #
# T7: main.py wiring — verify mount and middleware without HTTP round-trip
# --------------------------------------------------------------------------- #


class TestMainWiring:
    def test_mcp_mount_exists(self):
        from src.main import app
        from starlette.routing import Mount
        mcp_mounts = [r for r in app.routes if isinstance(r, Mount) and r.path == "/mcp"]
        assert len(mcp_mounts) == 1, "Expected exactly one /mcp mount in app.routes"

    def test_rate_limit_middleware_present(self):
        from src.main import app
        from src.api.mcp.headers_middleware import MCPRateLimitHeadersMiddleware
        middleware_classes = [m.cls for m in app.user_middleware if hasattr(m, "cls")]
        assert MCPRateLimitHeadersMiddleware in middleware_classes

    def test_mcp_router_removed(self):
        from src.main import app
        from starlette.routing import Route
        mcp_post_routes = [
            r for r in app.routes
            if isinstance(r, Route) and r.path == "/mcp"
        ]
        assert len(mcp_post_routes) == 0, "Old hand-rolled /mcp APIRouter route should be gone"
