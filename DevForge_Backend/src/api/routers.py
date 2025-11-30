"""API routers for MCP endpoints (gateway and manifest).

Handles tool discovery via manifest and tool execution via gateway.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.schemas import GatewayRequest, GatewayResponse
from src.core.utils import track_performance

# Import agents
from src.agents.datagen.agent import datagen_agent
from src.agents.rag.agent import rag_agent_invoke
from src.agents.github.agent import github_agent_invoke
from src.agents.reranker import rerank_docs_invoke
from src.agents.prompt_refiner.agent import refine_prompt_invoke
from src.agents.cheatsheet.agent import generate_cheatsheet_invoke

router = APIRouter()
mcp_router = APIRouter()

# Map tool names to agent invoke functions
SUPPORTED_TOOLS = {
    "generate_data": datagen_agent,
    "retrieve_docs": rag_agent_invoke,
    "github_operation": github_agent_invoke,
    "rerank_docs": rerank_docs_invoke,
    "refine_prompt": refine_prompt_invoke,
    "generate_cheatsheet": generate_cheatsheet_invoke,
}


@router.get("/manifests/devforge.json")
async def get_manifest():
    """
    Generates manifest dynamically with current gateway URL from settings.
    This allows the manifest to reflect the correct port and host.

    Returns:
        JSONResponse with manifest containing tools array
    """
    # Load base manifest structure
    manifest_path = Path(__file__).parent.parent.parent / "manifests" / "devforge.json"

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except FileNotFoundError:
        logging.warning("Static manifest not found, generating dynamically")
        manifest = _generate_default_manifest()
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in manifest file: {e}")
        manifest = _generate_default_manifest()

    # Update gateway URL dynamically
    manifest["gateway"] = settings.gateway_url

    logging.info(
        "Manifest requested",
        extra={"gateway_url": manifest["gateway"], "tools_count": len(manifest.get("tools", []))},
    )

    return JSONResponse(
        content=manifest,
        headers={"Content-Type": "application/json"},
    )


def _generate_default_manifest() -> dict:
    """Generate default manifest structure if static file is missing."""
    return {
        "name": "devforge",
        "version": "0.1.0",
        "description": "DevForge AI-powered developer tools",
        "schema_version": "v1",
        "gateway": settings.gateway_url,
        "tools": [
            {
                "name": "generate_data",
                "description": "Generate realistic mock CSV/JSON data using Faker and Pandas. Supports custom fields and formats.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rows": {
                            "type": "integer",
                            "description": "Number of rows to generate",
                            "default": 100,
                            "minimum": 1,
                            "maximum": 10000,
                        },
                        "format": {
                            "type": "string",
                            "description": "Output format",
                            "enum": ["csv", "json"],
                            "default": "json",
                        },
                        "fields": {
                            "type": "array",
                            "description": "Custom fields to generate (e.g., ['name', 'email', 'phone']). If omitted, generates common fields.",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["rows"],
                },
            }
        ],
    }


@router.post("/gateway")
@track_performance
async def gateway(gateway_req: GatewayRequest) -> GatewayResponse:
    start_time = time.time()

    # `arguments` is **already a dict** thanks to the validator above
    args = gateway_req.arguments
    tool_name = gateway_req.name          # snake_case alias

    logging.info(f"Gateway invoked → {tool_name}", extra={"arguments": args})

    if tool_name not in SUPPORTED_TOOLS:
        raise HTTPException(status_code=400, detail=f"Unsupported tool: {tool_name}")

    agent_func = SUPPORTED_TOOLS[tool_name]

    # ------------------------------------------------------------------- #
    # Special handling for github_operation (still expects a single string)
    # ------------------------------------------------------------------- #
    if tool_name == "github_operation":
        query = args.get("query")
        if not query:
            raise HTTPException(status_code=400, detail="github_operation requires 'query'")
        result = await agent_func(query)
    else:
        result = await agent_func(args)          # ← dict, no extra parsing

    exec_time = time.time() - start_time

    return GatewayResponse(
        success=result.get("success", False),
        tool=tool_name,
        format=result.get("format"),
        data=result.get("data"),
        error=result.get("error"),
        execution_time=round(exec_time, 4),
    )

@mcp_router.post("/mcp")
async def mcp_endpoint(request: Request):
    try:
        payload = await request.json()
    except:
        return {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}

    if payload.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}}

    method = payload.get("method")
    req_id = payload.get("id")

    # 1. initialize
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "1.0.0",
                "serverInfo": {"name": "DevForge", "version": "1.0"},
                "capabilities": {"tools": {}}
            }
        }

    # 2. tools/list
    if method == "tools/list":
        tools = []
        for name, func in SUPPORTED_TOOLS.items():
            tools.append({
                "name": name,
                "description": func.__doc__.strip() if func.__doc__ else "No description",
                "inputSchema": {
                    "type": "object",
                    "properties": {"rows": {"type": "integer"}},
                    "required": ["rows"] if name == "generate_data" else []
                }
            })
        return {"jsonrpc": "2.0", "id": req_id, "result": tools}

    # 3. tools/call → reuse your gateway!
    if method == "tools/call":
        params = payload.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})

        if name not in SUPPORTED_TOOLS:
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32602, "message": "Tool not found"}}

        # **Pydantic auto-parses string → dict**
        gateway_req = GatewayRequest(apiName=name, arguments=args)
        resp = await gateway(gateway_req)          # same route logic

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": resp.json()}]}
        }