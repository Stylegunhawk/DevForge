"""Pydantic models for request/response validation.

Uses Pydantic v2 syntax with field_validator and modern type hints.
"""

import json
from typing import Any

from pydantic import BaseModel, field_validator


class GatewayRequest(BaseModel):
    """Request format from Lobe Chat tool calls.

    Lobe Chat's LLM returns tool calls as {name: "...", arguments: "{}"}
    where arguments is a JSON string.
    """

    name: str
    arguments: str | dict  # JSON string or dict (LLM output)

    @field_validator("arguments", mode="before")
    @classmethod
    def parse_arguments(cls, v: Any) -> dict:
        """Convert JSON string to dict if needed."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON in arguments: {v}")
        if isinstance(v, dict):
            return v
        raise ValueError(f"Arguments must be str or dict, got {type(v)}")


class GatewayResponse(BaseModel):
    """Standard gateway response format."""

    success: bool
    tool: str
    format: str | None = None
    data: Any
    error: str | None = None
    execution_time: float | None = None


class DataGenArgs(BaseModel):
    """Arguments for DataGen tool."""

    rows: int
    format: str = "json"  # "csv" or "json"
    fields: list[str] | None = None

    @field_validator("rows")
    @classmethod
    def validate_rows(cls, v: int) -> int:
        """Ensure rows is between 1 and 10000."""
        if v < 1:
            raise ValueError("rows must be at least 1")
        if v > 10000:
            raise ValueError("rows cannot exceed 10000")
        return v

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Ensure format is csv or json."""
        if v.lower() not in ("csv", "json"):
            raise ValueError("format must be 'csv' or 'json'")
        return v.lower()

