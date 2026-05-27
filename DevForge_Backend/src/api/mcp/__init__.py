"""DevForge MCP server — FastMCP-based replacement for the hand-rolled /mcp endpoint."""

from src.api.mcp.server import mcp, streamable_http_app

__all__ = ["mcp", "streamable_http_app"]
