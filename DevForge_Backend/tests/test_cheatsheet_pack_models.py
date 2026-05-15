"""Tests for cheatsheet pack Pydantic models (v0.11)."""

from datetime import date

import pytest
from pydantic import ValidationError

from src.agents.cheatsheet.pack_models import Entry, Example, Pack, PackMeta


def _valid_example():
    return {"title": "Basic", "language": "python", "code": "x = 1"}


def _valid_entry():
    return {
        "id": "py.beginner.variables",
        "title": "Variables",
        "explanation": "Dynamic typing.",
        "examples": [_valid_example()],
        "pitfalls": ["Mind tabs vs spaces."],
    }


def _valid_meta(library=None):
    base = {
        "language": "python",
        "skill_level": "beginner",
        "version": 1,
        "last_reviewed": date(2026, 5, 15),
        "reviewer": "sid",
    }
    if library:
        base["library"] = library
    return base


def test_example_round_trip():
    ex = Example(**_valid_example())
    assert ex.language == "python"


def test_entry_requires_at_least_one_example_and_pitfall():
    entry = Entry(**_valid_entry())
    assert len(entry.examples) == 1
    assert len(entry.pitfalls) == 1


def test_entry_rejects_zero_examples():
    bad = _valid_entry()
    bad["examples"] = []
    with pytest.raises(ValidationError):
        Entry(**bad)


def test_entry_rejects_zero_pitfalls():
    bad = _valid_entry()
    bad["pitfalls"] = []
    with pytest.raises(ValidationError):
        Entry(**bad)


def test_pack_requires_3_to_12_entries():
    base = {"pack": _valid_meta(), "entries": [_valid_entry()] * 3}
    Pack(**base)
    base["entries"] = [_valid_entry()] * 12
    Pack(**base)
    base["entries"] = [_valid_entry()] * 2
    with pytest.raises(ValidationError):
        Pack(**base)
    base["entries"] = [_valid_entry()] * 13
    with pytest.raises(ValidationError):
        Pack(**base)


def test_pack_skill_level_enum():
    bad = {
        "pack": {**_valid_meta(), "skill_level": "novice"},
        "entries": [_valid_entry()] * 3,
    }
    with pytest.raises(ValidationError):
        Pack(**bad)


def test_library_pack_carries_library_field():
    meta = _valid_meta(library="pandas")
    meta["library_version_floor"] = "2.0"
    pack = Pack(pack=meta, entries=[_valid_entry()] * 3)
    assert pack.pack.library == "pandas"
    assert pack.pack.library_version_floor == "2.0"
