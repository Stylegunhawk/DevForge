"""Pydantic gate for /generate_tests requests."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

Language = Literal["python", "javascript", "typescript"]
Framework = Literal["pytest", "jest", "vitest"]
Coverage = Literal["happy_path", "edge_cases", "all"]


class GenerateTestsRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=16000, description="Source under test (pass verbatim).")
    language: Language
    framework: Optional[Framework] = None
    module_path: Optional[str] = Field(default=None, max_length=300)
    coverage: Coverage = "all"
    use_repo_context: bool = False
    instructions: Optional[str] = Field(default=None, max_length=1000)
