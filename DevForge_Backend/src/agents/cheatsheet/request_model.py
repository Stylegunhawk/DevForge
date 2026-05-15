"""Pydantic gate for /generate_cheatsheet requests (v0.11)."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class CheatsheetRequest(BaseModel):
    language: Optional[str] = None
    skill_level: Literal["beginner", "intermediate", "expert"] = "beginner"
    code_context: Optional[str] = Field(default=None, max_length=20000)
    intent: Optional[str] = Field(default=None, max_length=400)

    @model_validator(mode="after")
    def validate_at_least_one(self) -> "CheatsheetRequest":
        if not (self.language or self.code_context or self.intent):
            raise ValueError(
                "Must provide at least one of: language, code_context, or intent."
            )
        return self
