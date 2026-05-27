"""FastMCP server instance + tool registrations + Streamable HTTP app export.

Key design decisions:
- Flat function parameters for the 3 simple tools so FastMCP auto-generates
  the correct JSON schema (fields at top level, not nested under an 'args' key).
- github_operation uses _PassThroughArgs + direct Tool construction because its
  oneOf schema cannot be represented as flat typed parameters.
- streamable_http_path='/' so the route lives at '/' inside the Starlette sub-app;
  when mounted at '/mcp' in FastAPI the effective path becomes '/mcp'.
- json_response=True makes tests tractable (plain JSON, not SSE stream).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.tools.base import Tool
from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase, FuncMetadata
from pydantic import ConfigDict

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
    instructions="DevForge tools: data generation, GitHub automation, prompt refinement, cheatsheets.",
    stateless_http=True,
    streamable_http_path="/",
    json_response=True,
)
mcp._mcp_server.version = "1.0.0"


# --------------------------------------------------------------------------- #
# Simple tools — flat parameters so FastMCP auto-generates correct schema
# --------------------------------------------------------------------------- #


@mcp.tool(name="generate_data", description=TOOL_DESCRIPTIONS["generate_data"])
async def generate_data(
    rows: int,
    format: Literal["json", "csv"] = "json",
    fields: Optional[list[str]] = None,
    prompt: Optional[str] = None,
    domain: Optional[Literal["ecommerce", "saas", "iot_devices"]] = None,
    realism_level: Literal["basic", "medium", "high"] = "basic",
    enable_semantic_generation: bool = True,
    ctx: Context = None,
) -> dict:
    args = GenerateDataInput(
        rows=rows, format=format, fields=fields, prompt=prompt,
        domain=domain, realism_level=realism_level,
        enable_semantic_generation=enable_semantic_generation,
    )
    return await _dispatch("generate_data", args.model_dump(exclude_none=True), ctx)


@mcp.tool(name="refine_prompt", description=TOOL_DESCRIPTIONS["refine_prompt"])
async def refine_prompt(
    prompt: str,
    domain: Literal["general", "image", "code", "rag", "llm"] = "general",
    skill_level: Literal["beginner", "intermediate", "expert"] = "intermediate",
    file_context: Optional[str] = None,
    conversation_history: Optional[list[dict]] = None,
    attached_files: Optional[list[str]] = None,
    project_files: Optional[dict[str, str]] = None,
    ctx: Context = None,
) -> dict:
    args = RefinePromptInput(
        prompt=prompt, domain=domain, skill_level=skill_level,
        file_context=file_context, conversation_history=conversation_history,
        attached_files=attached_files, project_files=project_files,
    )
    return await _dispatch("refine_prompt", args.model_dump(exclude_none=True), ctx)


@mcp.tool(name="generate_cheatsheet", description=TOOL_DESCRIPTIONS["generate_cheatsheet"])
async def generate_cheatsheet(
    language: Optional[
        Literal["python", "javascript", "typescript", "go", "rust", "java", "ruby", "php", "csharp"]
    ] = None,
    skill_level: Literal["beginner", "intermediate", "expert"] = "beginner",
    code_context: Optional[str] = None,
    intent: Optional[str] = None,
    ctx: Context = None,
) -> dict:
    args = GenerateCheatsheetInput(
        language=language, skill_level=skill_level,
        code_context=code_context, intent=intent,
    )
    return await _dispatch("generate_cheatsheet", args.model_dump(exclude_none=True), ctx)


# --------------------------------------------------------------------------- #
# github_operation — oneOf schema requires _PassThroughArgs + direct Tool
# --------------------------------------------------------------------------- #


class _PassThroughArgs(ArgModelBase):
    """Accepts any flat kwargs and returns them all for dispatch."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    def model_dump_one_level(self) -> dict[str, Any]:
        return dict(self.__pydantic_extra__ or {})


async def _github_operation_fn(ctx: Context, **kwargs: Any) -> dict:
    validated = GithubOperationArgs(**kwargs)
    return await _dispatch_github(validated, ctx)


mcp._tool_manager._tools["github_operation"] = Tool(
    fn=_github_operation_fn,
    name="github_operation",
    description=TOOL_DESCRIPTIONS["github_operation"],
    parameters=GITHUB_OPERATION_INPUT_SCHEMA,
    fn_metadata=FuncMetadata(arg_model=_PassThroughArgs),
    is_async=True,
    context_kwarg="ctx",
)


# Streamable HTTP ASGI app — mount at /mcp in src/main.py via app.mount().
streamable_http_app = mcp.streamable_http_app()
