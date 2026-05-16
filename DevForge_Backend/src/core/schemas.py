"""Pydantic models for request/response validation.

Supports both REST API and MCP Protocol formats for maximum compatibility.
"""

import json
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


# --------------------------------------------------------------------------- #
# GATEWAY REQUEST - Supports both 'name' and 'apiName' for compatibility
# --------------------------------------------------------------------------- #
class GatewayRequest(BaseModel):
    """
    Gateway request model supporting multiple client formats:
    
    1. Lobe Chat format: {"name": "tool_name", "arguments": {...}}
    2. MCP Inspector format: {"apiName": "tool_name", "arguments": {...}}
    3. String arguments: {"name": "tool_name", "arguments": "{\"key\": \"value\"}"}
    
    The model automatically:
    - Accepts both 'name' and 'apiName'
    - Parses JSON string arguments to dict
    - Validates required fields
    """
    
    # Accept either field name (Lobe Chat uses 'name', MCP Inspector uses 'apiName')
    name: Optional[str] = Field(None, description="Tool name (snake_case, Lobe Chat format)")
    apiName: Optional[str] = Field(None, description="Tool name (camelCase, MCP format)")
    
    # Arguments can be string or dict
    arguments: Union[str, Dict[str, Any]] = Field(
        ..., 
        description="Tool arguments as JSON string or dict"
    )
    
    # Optional MCP metadata
    id: Optional[str] = Field(None, description="Request ID for tracking")
    identifier: Optional[str] = Field(None, description="Plugin identifier")
    type: Optional[Literal["default"]] = Field(None, description="Request type")

    @field_validator("arguments", mode="before")
    @classmethod
    def parse_arguments(cls, v: Any) -> Dict[str, Any]:
        """
        Auto-parse arguments from JSON string to dict if needed.
        
        Args:
            v: Raw arguments value (string or dict)
            
        Returns:
            Parsed dict of arguments
            
        Raises:
            ValueError: If JSON string is invalid
        """
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in 'arguments': {exc}")
        
        if isinstance(v, dict):
            return v
        
        raise ValueError(f"'arguments' must be str or dict, got {type(v).__name__}")

    @model_validator(mode="after")
    def check_tool_name(self) -> "GatewayRequest":
        """
        Ensure at least one of 'name' or 'apiName' is provided.
        
        Returns:
            Self if validation passes
            
        Raises:
            ValueError: If neither field is provided
        """
        if not self.name and not self.apiName:
            raise ValueError("Either 'name' or 'apiName' must be provided")
        return self

    def get_tool_name(self) -> str:
        """
        Get tool name from either 'name' or 'apiName' field.
        Prioritizes 'name' if both are provided (for Lobe Chat compatibility).
        
        Returns:
            Tool name string
        """
        return self.name or self.apiName or ""

    model_config = {
        "populate_by_name": True,  # Allow both field names in input
        "json_schema_extra": {
            "examples": [
                {
                    "name": "generate_data",
                    "arguments": {"rows": 10, "format": "json"}
                },
                {
                    "apiName": "generate_data",
                    "arguments": "{\"rows\": 10, \"format\": \"json\"}"
                }
            ]
        }
    }


# --------------------------------------------------------------------------- #
# GATEWAY RESPONSE - Standardized format for all tools
# --------------------------------------------------------------------------- #
class GatewayResponse(BaseModel):
    """
    Standardized response format for gateway endpoint.
    
    All tools return this format for consistency.
    """
    
    success: bool = Field(..., description="Whether operation succeeded")
    data: Optional[Any] = Field(None, description="Tool execution result (can be any type)")
    message: str = Field(..., description="Human-readable status message")
    tool: Optional[str] = Field(None, description="Tool name that was executed")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")
    error: Optional[str] = Field(None, description="Error message if operation failed")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "data": {"result": "example output"},
                    "message": "Operation completed successfully",
                    "tool": "generate_data",
                    "execution_time": 1.23
                },
                {
                    "success": False,
                    "data": None,
                    "message": "Operation failed: Invalid input",
                    "error": "Invalid input",
                    "tool": "generate_data",
                    "execution_time": 0.05
                }
            ]
        }
    }


# --------------------------------------------------------------------------- #
# TOOL-SPECIFIC ARGUMENT MODELS
# --------------------------------------------------------------------------- #

class DataGenArgs(BaseModel):
    """Arguments for generate_data tool."""
    
    # Original v1 parameters (required for backward compatibility)
    rows: int = Field(..., ge=1, le=10000, description="Number of rows to generate")
    format: Literal["csv", "json"] = Field("json", description="Output format")
    fields: Optional[List[str]] = Field(None, description="Custom fields to generate")
    
    # New v2 parameters (Phase 8 - all optional for backward compat)
    prompt: Optional[str] = Field(
        None,
        description="Natural language description for LLM-powered schema design"
    )
    domain: Optional[Literal["ecommerce", "saas", "iot_devices"]] = Field(
        None,
        description="Pre-defined domain template (ecommerce, saas, or iot_devices)"
    )
    realism_level: Literal["basic", "medium", "high"] = Field(
        "basic",
        description="Data quality realism level (null/duplicate/outlier injection)"
    )
    enable_semantic_generation: bool = Field(
        True,
        description="Enable Phase 1 semantic analysis for V2 mode (default: True)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                # V1 example (backward compatible)
                {"rows": 100, "format": "json", "fields": ["name", "email", "phone"]},
                # V2 example with domain
                {"rows": 500, "format": "json", "domain": "ecommerce", "realism_level": "medium"},
                # V2 example with prompt
                {"rows": 200, "format": "csv", "prompt": "Generate user subscription data", "realism_level": "high"}
            ]
        }
    }


class GitHubArgs(BaseModel):
    """Arguments for github_operation tool."""
    
    query: str = Field(..., description="Natural language GitHub operation request")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "list my repositories"},
                {"query": "create an issue titled 'Bug fix' in repo 'myproject'"}
            ]
        }
    }


class RerankArgs(BaseModel):
    """Arguments for rerank_docs tool."""
    
    query: str = Field(..., description="Query for reranking")
    documents: List[Dict[str, Any]] = Field(..., description="Documents to rerank")
    top_k: Optional[int] = Field(None, ge=1, description="Number of results to return")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "machine learning",
                    "documents": [
                        {"content": "ML is a subset of AI", "metadata": {}},
                        {"content": "Python is great for data science", "metadata": {}}
                    ],
                    "top_k": 5
                }
            ]
        }
    }


class PromptRefineArgs(BaseModel):
    """Arguments for refine_prompt tool."""
    
    prompt: str = Field(..., description="Original prompt to refine")
    domain: Literal["general", "image", "code", "rag", "llm"] = Field(
        "general", 
        description="Domain for optimization"
    )
    skill_level: Literal["beginner", "intermediate", "expert"] = Field(
        "intermediate",
        description="Target skill level"
    )
    file_context: Optional[str] = Field(None, description="File content for context")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "prompt": "Create a REST API",
                    "domain": "code",
                    "skill_level": "intermediate"
                }
            ]
        }
    }


# --------------------------------------------------------------------------- #
# MCP PROTOCOL MODELS (for official MCP Inspector compatibility)
# --------------------------------------------------------------------------- #

class MCPRequest(BaseModel):
    """
    JSON-RPC 2.0 request format for MCP Protocol.
    Used by official MCP Inspector.
    """
    
    jsonrpc: Literal["2.0"] = "2.0"
    method: str = Field(..., description="Method name (e.g., 'tools/call', 'tools/list')")
    params: Optional[Dict[str, Any]] = Field(None, description="Method parameters")
    id: Optional[Union[str, int]] = Field(None, description="Request ID")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "generate_data",
                        "arguments": {"rows": 10}
                    },
                    "id": 1
                }
            ]
        }
    }


class MCPResponse(BaseModel):
    """
    JSON-RPC 2.0 response format for MCP Protocol.
    """
    
    jsonrpc: Literal["2.0"] = "2.0"
    result: Optional[Any] = Field(None, description="Method result")
    error: Optional[Dict[str, Any]] = Field(None, description="Error object if method failed")
    id: Optional[Union[str, int]] = Field(None, description="Request ID")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "jsonrpc": "2.0",
                    "result": {"content": [{"type": "text", "text": "Success"}]},
                    "id": 1
                }
            ]
        }
    }