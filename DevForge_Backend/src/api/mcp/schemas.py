"""Input schemas for the FastMCP-backed /mcp endpoint.

- Pydantic models for the 3 simple tools (generate_data, refine_prompt,
  generate_cheatsheet). FastMCP auto-generates the JSON schema from these.
- GITHUB_OPERATION_INPUT_SCHEMA + GithubOperationArgs are ported verbatim
  from src/api/routers/__init__.py because the oneOf union doesn't translate
  cleanly to a single Pydantic model.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator

from src.agents.github.schemas import OPERATION_SCHEMAS


# --------------------------------------------------------------------------- #
# Simple-tool input models — FastMCP auto-generates JSON schema from these
# --------------------------------------------------------------------------- #


class GenerateDataInput(BaseModel):
    rows: int = Field(..., ge=1, le=10000, description="Number of rows (1-10000)")
    format: Literal["json", "csv"] = "json"
    fields: Optional[list[str]] = None
    prompt: Optional[str] = Field(
        None,
        description=(
            "REQUIRED for custom/domain-specific data generation. Pass the user's "
            "exact description here. Without this field, only generic Faker data is "
            "generated (V1). With this field, LLM-powered semantic generation (V2)."
        ),
    )
    domain: Optional[Literal["ecommerce", "saas", "iot_devices"]] = None
    realism_level: Literal["basic", "medium", "high"] = "basic"
    enable_semantic_generation: bool = True


class RefinePromptInput(BaseModel):
    prompt: str = Field(..., min_length=1, description="User's original prompt — pass verbatim, do not pre-summarize.")
    domain: Literal["general", "image", "code", "rag", "llm"] = "general"
    skill_level: Literal["beginner", "intermediate", "expert"] = "intermediate"
    file_context: Optional[str] = None
    conversation_history: Optional[list[dict[str, str]]] = None
    attached_files: Optional[list[str]] = None
    project_files: Optional[dict[str, str]] = None


class GenerateCheatsheetInput(BaseModel):
    language: Optional[
        Literal[
            "python", "javascript", "typescript", "go", "rust",
            "java", "ruby", "php", "csharp",
        ]
    ] = None
    skill_level: Literal["beginner", "intermediate", "expert"] = "beginner"
    code_context: Optional[str] = None
    intent: Optional[str] = None


# --------------------------------------------------------------------------- #
# github_operation — ported verbatim from routers/__init__.py:21-137
# --------------------------------------------------------------------------- #

_GH_OP_NAMES = sorted(OPERATION_SCHEMAS.keys())
_GH_OP_LIST_STR = ", ".join(_GH_OP_NAMES)


GITHUB_OPERATION_INPUT_SCHEMA: dict = {
    "type": "object",
    "oneOf": [
        {
            "title": "Natural-language",
            "description": "Free-form English query — the LLM extracts intent and parameters.",
            "required": ["query"],
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language description of the GitHub action to perform.",
                },
                "context": {
                    "type": "object",
                    "description": "Optional context (github_token, diff, error_log, files, risk_confirmed, risk_reason, session_id).",
                    "additionalProperties": True,
                },
            },
            "additionalProperties": False,
        },
        {
            "title": "Structured",
            "description": (
                "Typed operation + parameters — skips the LLM intent step (~1-2s faster per call). "
                "Per-operation parameter validation runs at the gateway."
            ),
            "required": ["operation"],
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": _GH_OP_NAMES,
                    "description": "GitHub operation to execute. Per-op parameters are validated at runtime.",
                },
                "context": {
                    "type": "object",
                    "description": "github_token (required), risk_confirmed/risk_reason (for HIGH/CRITICAL ops), diff, error_log, etc.",
                    "additionalProperties": True,
                },
            },
            "additionalProperties": True,
        },
    ],
}


class GithubOperationArgs(BaseModel):
    """MCP-only validator for github_operation arguments.

    Ported verbatim from src/api/routers/__init__.py:71-137. Do not modify
    behavior; semantics tests in tests/test_mcp_sdk.py pin the contract.
    """

    query: Optional[str] = None
    operation: Optional[str] = None
    context: Optional[dict] = None
    model_config = {"extra": "allow"}

    @model_validator(mode="after")
    def _validate_exactly_one_and_op_schema(self) -> "GithubOperationArgs":
        has_query = bool(self.query)
        has_op = bool(self.operation)

        if not has_op:
            if not has_query:
                raise ValueError("Must specify either 'query' or 'operation' in arguments")
            return self

        if self.operation not in OPERATION_SCHEMAS:
            raise ValueError(
                f"Unknown operation '{self.operation}'. Valid operations: [{_GH_OP_LIST_STR}]"
            )
        op_model_cls = OPERATION_SCHEMAS[self.operation]
        op_field_names = set(op_model_cls.model_fields.keys())

        if has_query and "query" not in op_field_names:
            raise ValueError(
                f"Cannot specify both 'query' and 'operation' — operation "
                f"'{self.operation}' does not accept a 'query' parameter"
            )

        excluded = {"operation", "context"}
        if "query" not in op_field_names:
            excluded.add("query")
        op_params = self.model_dump(exclude=excluded)
        op_params = {k: v for k, v in op_params.items() if v is not None}
        if "repo" in op_params and "repo_name" not in op_params:
            op_params["repo_name"] = op_params.pop("repo")
        try:
            op_model_cls(**op_params)
        except ValidationError as e:
            field_msgs = []
            for err in e.errors():
                field = ".".join(str(p) for p in err["loc"])
                msg = err["msg"]
                field_msgs.append(f"'{field}': {msg}")
            combined = "; ".join(field_msgs)
            raise ValueError(f"Operation '{self.operation}' validation errors: {combined}") from e
        return self
