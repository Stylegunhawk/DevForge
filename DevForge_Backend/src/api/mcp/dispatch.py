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
            import asyncio
            asyncio.get_event_loop().create_task(ctx.report_progress(percent, 100))
            logger.info(f"DataGen Progress: {percent}% - {stage}: {message}")
        except RuntimeError as e:
            logger.warning(f"Progress callback failed (no running loop): {e}")
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
        "_state":           state,
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
