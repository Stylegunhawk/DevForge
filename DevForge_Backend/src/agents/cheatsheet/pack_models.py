"""Pydantic models for cheatsheet knowledge packs (v0.11)."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Example(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    language: str
    code: str


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    explanation: str
    tags: list[str] = []
    when_to_use: str = ""
    examples: list[Example] = Field(min_length=1)
    pitfalls: list[str] = Field(min_length=1)


class PackMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str
    skill_level: Literal["beginner", "intermediate", "expert"]
    version: int = 1
    library: Optional[str] = None
    library_version_floor: Optional[str] = None
    last_reviewed: date
    reviewer: str


class Pack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pack: PackMeta
    entries: list[Entry] = Field(min_length=3, max_length=12)
