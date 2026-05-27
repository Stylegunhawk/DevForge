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
