"""API routers for MCP endpoints (gateway and manifest).

Handles tool discovery via manifest and tool execution via gateway.
"""

import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

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
async def gateway(request: Request) -> GatewayResponse:
    start_time = time.time()

    # Read raw body
    body = await request.json()

    # Convert MCP/Lobe format to GatewayRequest format
    if "apiName" in body:
        body = {
            "name": body["apiName"],
            "arguments": body.get("arguments", {})
        }

    # Convert string arguments to dict if needed
    if isinstance(body.get("arguments"), str):
        try:
            body["arguments"] = json.loads(body["arguments"])
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format in 'arguments'")

    # Validate with schema after normalization
    request = GatewayRequest(**body)

    # --- existing validation and execution logic continues ---

    logging.info(f"Gateway request received: {request.name}")

    if request.name not in SUPPORTED_TOOLS:
        raise HTTPException(status_code=400, detail=f"Unsupported tool: {request.name}")

    agent_func = SUPPORTED_TOOLS[request.name]

    agent_result = await agent_func(request.arguments)
    execution_time = time.time() - start_time

    return GatewayResponse(
        success=agent_result.get("success", False),
        tool=request.name,
        format=agent_result.get("format"),
        data=agent_result.get("data"),
        error=None,
        execution_time=round(execution_time, 4),
    )
