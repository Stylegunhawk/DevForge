"""Tests for cheatsheet pack loader (v0.11)."""

from pathlib import Path

import pytest

from src.agents.cheatsheet.pack_loader import (
    PackLoader,
    PackNotFoundError,
    SUPPORTED_LANGUAGES,
)


@pytest.fixture
def loader():
    # The repo root is two levels up from this test file (tests/ -> repo_root)
    root = Path(__file__).resolve().parent.parent / "data" / "cheatsheet_packs"
    return PackLoader(root=root)


def test_supported_languages_contains_9():
    assert set(SUPPORTED_LANGUAGES) == {
        "python", "javascript", "typescript", "go", "rust",
        "java", "ruby", "php", "csharp",
    }


def test_load_seed_python_beginner_pack(loader):
    pack = loader.load_language_pack("python", "beginner")
    assert pack.pack.language == "python"
    assert pack.pack.skill_level == "beginner"
    assert len(pack.entries) >= 3
    assert any(e.id == "py.beginner.variables" for e in pack.entries)


def test_load_missing_skill_pack_raises(loader):
    # python/intermediate.yaml doesn't exist in the seed
    with pytest.raises(PackNotFoundError):
        loader.load_language_pack("python", "intermediate")


def test_load_unsupported_language_raises(loader):
    with pytest.raises(PackNotFoundError):
        loader.load_language_pack("cobol", "beginner")


def test_l2_cache_returns_same_object(loader):
    p1 = loader.load_language_pack("python", "beginner")
    p2 = loader.load_language_pack("python", "beginner")
    assert p1 is p2


def test_load_library_pack_missing_returns_none(loader):
    # No library packs exist yet in the seed
    assert loader.load_library_pack("pandas", "beginner") is None
