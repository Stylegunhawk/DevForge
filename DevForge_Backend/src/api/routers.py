"""API routers for MCP endpoints (gateway and manifest).

Handles tool discovery via manifest and tool execution via gateway.
"""

import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.schemas import GatewayRequest, GatewayResponse
from src.core.utils import track_performance

# Import agents
from src.agents.datagen.agent import datagen_agent

router = APIRouter()

# Track supported tools
SUPPORTED_TOOLS = {
    "generate_data": datagen_agent,
}


@router.get("/manifests/devforge.json")
async def get_manifest() -> JSONResponse:
    """Serve DevForge plugin manifest for Lobe Chat discovery.

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
async def gateway(request: GatewayRequest) -> GatewayResponse:
    """Gateway endpoint for tool execution.

    Dispatches tool calls to appropriate agents based on tool name.
    Phase 1 supports: generate_data

    Args:
        request: GatewayRequest with name and arguments

    Returns:
        GatewayResponse with execution results

    Raises:
        HTTPException: 400 for unsupported tools, 500 for execution errors
    """
    start_time = time.time()

    logging.info(
        f"Gateway request received: {request.name}",
        extra={"tool_name": request.name, "arguments_keys": list(request.arguments.keys()) if isinstance(request.arguments, dict) else []},
    )

    # Validate tool name
    if request.name not in SUPPORTED_TOOLS:
        error_msg = f"Unsupported tool: {request.name}. Supported tools: {list(SUPPORTED_TOOLS.keys())}"
        logging.warning(error_msg, extra={"requested_tool": request.name, "supported_tools": list(SUPPORTED_TOOLS.keys())})
        raise HTTPException(status_code=400, detail=error_msg)

    # Get agent function
    agent_func = SUPPORTED_TOOLS[request.name]

    try:
        # Validate arguments are dict (should be parsed by schema validator)
        if not isinstance(request.arguments, dict):
            raise ValueError("Arguments must be a dictionary after parsing")

        # Invoke agent
        logging.debug(f"Invoking agent {request.name} with arguments", extra={"arguments": request.arguments})
        agent_result = await agent_func(request.arguments)

        execution_time = time.time() - start_time

        # Build response
        response = GatewayResponse(
            success=agent_result.get("success", False),
            tool=request.name,
            format=agent_result.get("format"),
            data=agent_result.get("data"),
            error=None,
            execution_time=round(execution_time, 4),
        )

        # Log response size
        data_size = len(str(response.data)) if response.data else 0
        logging.info(
            f"Gateway request completed: {request.name}",
            extra={
                "tool": request.name,
                "success": response.success,
                "execution_time": response.execution_time,
                "data_size": data_size,
                "format": response.format,
            },
        )

        return response

    except ValueError as e:
        # Validation errors from agent/schema
        execution_time = time.time() - start_time
        error_msg = str(e)
        logging.error(
            f"Gateway validation error for {request.name}: {error_msg}",
            extra={"tool": request.name, "error": error_msg, "execution_time": execution_time},
        )
        raise HTTPException(status_code=400, detail=error_msg)

    except Exception as e:
        # Unexpected errors
        execution_time = time.time() - start_time
        error_msg = f"Internal error executing {request.name}: {str(e)}"
        logging.error(
            f"Gateway execution error for {request.name}",
            extra={"tool": request.name, "error": str(e), "execution_time": execution_time},
            exc_info=True,
        )
        # Don't expose internal details to client
        raise HTTPException(status_code=500, detail="Internal server error")

