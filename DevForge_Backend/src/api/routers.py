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
async def gateway(gateway_req: GatewayRequest):
    """
    Gateway endpoint for MCP tool execution.
    
    Returns standardized response format:
    {
        "success": true,
        "data": <actual_result>,
        "message": "Operation completed successfully"
    }
    """
    start_time = time.time()

    # `arguments` is **already a dict** thanks to the validator above
    args = gateway_req.arguments
    tool_name = gateway_req.get_tool_name()  # Supports both 'name' and 'apiName'


    logging.info(
        f"Gateway received request for tool: {tool_name}",
        extra={"tool": tool_name, "arguments": args},
    )

    # Validate tool name
    if tool_name not in SUPPORTED_TOOLS:
        error_msg = f"Unsupported tool: {tool_name}"
        logging.error(error_msg, extra={"tool": tool_name, "available_tools": list(SUPPORTED_TOOLS.keys())})
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "data": None,
                "message": error_msg,
            },
        )

    agent_func = SUPPORTED_TOOLS[tool_name]

    try:
        # ------------------------------------------------------------------- #
        # Special handling for github_operation (still expects a single string)
        # ------------------------------------------------------------------- #
        if tool_name == "github_operation":
            query = args.get("query")
            if not query:
                error_msg = "github_operation requires 'query' parameter"
                logging.error(error_msg, extra={"tool": tool_name, "args": args})
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "data": None,
                        "message": error_msg,
                    },
                )
            logging.info(f"Calling {tool_name} with query: {query[:100]}...")
            result = await agent_func(query)
        else:
            logging.info(f"Calling {tool_name} with args: {args}")
            result = await agent_func(args)          # ← dict, no extra parsing

        exec_time = time.time() - start_time

        # Extract data from result - handle different result structures
        result_data = result.get("data")
        if result_data is None:
            # If no 'data' key, use the entire result (minus metadata)
            result_data = {k: v for k, v in result.items() if k not in ["success", "tool", "format", "error", "execution_time"]}
            if not result_data:
                result_data = result  # Fallback to full result

        # Check if operation was successful
        success = result.get("success", True)  # Default to True if not specified
        error = result.get("error")

        if error:
            success = False
            message = f"{tool_name} execution failed: {error}"
            logging.error(message, extra={"tool": tool_name, "error": error, "execution_time": exec_time})
        else:
            message = f"{tool_name} executed successfully"

        logging.info(
            f"Tool {tool_name} executed successfully",
            extra={"tool": tool_name, "success": success, "execution_time": exec_time},
        )

        # Return standardized response format
        return JSONResponse(
            content={
                "success": success,
                "data": result_data,
                "message": message,
            },
        )

    except Exception as e:
        exec_time = time.time() - start_time
        error_msg = f"{tool_name} execution error: {str(e)}"
        logging.error(
            error_msg,
            extra={"tool": tool_name, "error": str(e), "execution_time": exec_time},
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "data": None,
                "message": error_msg,
            },
        )

# Replace the mcp_endpoint function in src/api/routers.py

@mcp_router.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    MCP Protocol endpoint (JSON-RPC 2.0).
    
    Handles:
    - initialize: Server capabilities handshake
    - tools/list: List available tools
    - tools/call: Execute a tool
    """
    try:
        body = await request.body()
        
        # Handle empty body
        if not body:
            logging.warning("MCP endpoint received empty body")
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": "Parse error: Empty request body"
                    }
                }
            )
        
        # Parse JSON
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            logging.error(f"MCP endpoint JSON decode error: {e}")
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
            )
        
        # Validate JSON-RPC version
        if payload.get("jsonrpc") != "2.0":
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request: jsonrpc must be '2.0'"
                    }
                }
            )
        
        method = payload.get("method")
        req_id = payload.get("id")
        params = payload.get("params", {})
        
        logging.info(f"MCP method: {method}, id: {req_id}")
        
        # Handle initialize
        if method == "initialize":
            logging.info("MCP initialize request received")
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {
                            "name": "DevForge",
                            "version": "0.7.0"
                        },
                        "capabilities": {
                            "tools": {}
                        }
                    }
                }
            )
        
        # Handle tools/list
        if method == "tools/list":
            logging.info("MCP tools/list request received")
            tools = []
            for name, func in SUPPORTED_TOOLS.items():
                # Build input schema based on tool
                input_schema = _get_tool_schema(name)
                
                tools.append({
                    "name": name,
                    "description": func.__doc__.strip() if func.__doc__ else f"{name} tool",
                    "inputSchema": input_schema
                })
            
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": tools}
                }
            )
        
        # Handle tools/call
        if method == "tools/call":
            logging.info(f"MCP tools/call request: {params}")
            
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if not tool_name:
                return JSONResponse(
                    status_code=400,
                    content={
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602,
                            "message": "Invalid params: 'name' is required"
                        }
                    }
                )
            
            if tool_name not in SUPPORTED_TOOLS:
                return JSONResponse(
                    status_code=400,
                    content={
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602,
                            "message": f"Tool not found: {tool_name}"
                        }
                    }
                )
            
            # Call the tool via gateway
            try:
                gateway_req = GatewayRequest(apiName=tool_name, arguments=arguments)
                gateway_response = await gateway(gateway_req)
                
                # Extract response body
                response_body = json.loads(gateway_response.body.decode())
                
                # Return MCP-formatted response
                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(response_body)
                                }
                            ]
                        }
                    }
                )
            
            except Exception as e:
                logging.error(f"MCP tools/call error: {e}", exc_info=True)
                return JSONResponse(
                    status_code=500,
                    content={
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32603,
                            "message": f"Internal error: {str(e)}"
                        }
                    }
                )
        
        # Unknown method
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
        )
    
    except Exception as e:
        logging.error(f"MCP endpoint error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
        )


def _get_tool_schema(tool_name: str) -> dict:
    """Generate JSON schema for tool parameters."""
    schemas = {
        "generate_data": {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "integer",
                    "description": "Number of rows to generate",
                    "minimum": 1,
                    "maximum": 10000
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "csv"],
                    "description": "Output format"
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Custom fields to generate"
                }
            },
            "required": ["rows"]
        },
        "retrieve_docs": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paths to documents"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results",
                    "default": 5
                }
            },
            "required": ["query"]
        },
        "github_operation": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language GitHub operation"
                }
            },
            "required": ["query"]
        },
        "rerank_docs": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query for reranking"
                },
                "documents": {
                    "type": "array",
                    "description": "Documents to rerank"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results"
                }
            },
            "required": ["query", "documents"]
        },
        "refine_prompt": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Prompt to refine"
                },
                "domain": {
                    "type": "string",
                    "enum": ["general", "image", "code", "rag", "llm"],
                    "description": "Domain"
                },
                "skill_level": {
                    "type": "string",
                    "enum": ["beginner", "intermediate", "expert"],
                    "description": "Skill level"
                }
            },
            "required": ["prompt"]
        },
        "generate_cheatsheet": {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "description": "Programming language"
                },
                "skill_level": {
                    "type": "string",
                    "enum": ["beginner", "intermediate", "expert"],
                    "description": "Skill level"
                },
                "code_context": {
                    "type": "string",
                    "description": "Code context"
                }
            },
            "required": ["language"]
        }
    }
    
    return schemas.get(tool_name, {
        "type": "object",
        "properties": {},
        "required": []
    })
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