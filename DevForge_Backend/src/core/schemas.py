"""Pydantic models for request/response validation.

Pydantic v2 – field_validator, modern type hints, auto-parsing of JSON strings.
"""

import json
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, field_validator, ValidationError


# --------------------------------------------------------------------------- #
# 1. GATEWAY (LobeChat / MCP) – accepts `arguments` as **string OR dict**
# --------------------------------------------------------------------------- #
class GatewayRequest(BaseModel):
    """Incoming tool-call from LobeChat, MCP, or any client.

    LobeChat sends:
        {"apiName": "...", "arguments": "{\"rows\":10,...}"}
    Gemini/OpenAI function-calling sends:
        {"name": "...", "arguments": {"rows":10,...}}
    We accept **both**.
    """

    apiName: str                                   # LobeChat uses camelCase
    arguments: str | Dict[str, Any]                # JSON string **or** dict
    id: Optional[str] = None
    identifier: Optional[str] = None
    type: Optional[Literal["default"]] = None

    # ------------------------------------------------------------------- #
    # Auto-convert JSON string → dict (runs *before* any other validation)
    # ------------------------------------------------------------------- #
    @field_validator("arguments", mode="before")
    @classmethod
    def _normalize_arguments(cls, v: Any) -> Dict[str, Any]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in 'arguments': {exc}")
        if isinstance(v, dict):
            return v
        raise ValueError(f"'arguments' must be str or dict, got {type(v).__name__}")

    # ------------------------------------------------------------------- #
    # Normalise field name for internal code (we use snake_case `name`)
    # ------------------------------------------------------------------- #
    @property
    def name(self) -> str:
        """Convenient snake_case alias used everywhere else."""
        return self.apiName


# --------------------------------------------------------------------------- #
# 2. RESPONSE
# --------------------------------------------------------------------------- #
class GatewayResponse(BaseModel):
    success: bool
    tool: str
    format: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


# --------------------------------------------------------------------------- #
# 3. TOOL-SPECIFIC ARG MODELS (used inside agents)
# --------------------------------------------------------------------------- #
class DataGenArgs(BaseModel):
    rows: int
    format: Literal["csv", "json"] = "json"
    fields: Optional[List[str]] = None

    @field_validator("rows")
    @classmethod
    def _check_rows(cls, v: int) -> int:
        if not (1 <= v <= 10_000):
            raise ValueError("rows must be 1-10,000")
        return v


class RAGArgs(BaseModel):
    query: str
    file_paths: Optional[List[str]] = None
    top_k: int = 5
    embed_model: Optional[str] = None
    backend: Optional[str] = None
    score_threshold: Optional[float] = None

    @field_validator("top_k")
    @classmethod
    def _check_top_k(cls, v: int) -> int:
        if not (1 <= v <= 50):
            raise ValueError("top_k must be 1-50")
        return v

    @field_validator("score_threshold")
    @classmethod
    def _check_score(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("score_threshold must be 0.0-1.0")
        return v