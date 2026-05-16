"""Tests for cheatsheet personalizer (v0.11)."""

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.cheatsheet.pack_models import Entry, Example, Pack, PackMeta
from src.agents.cheatsheet.personalizer import Personalizer


def _entry(eid: str, tags=None):
    return Entry(
        id=eid,
        title=f"Title for {eid}",
        explanation="Explanation.",
        tags=tags or [],
        when_to_use="When useful.",
        examples=[Example(title="t", language="python", code="x = 1")],
        pitfalls=["Pitfall."],
    )


def _pack(language="python", skill="beginner", entry_ids=None):
    meta = PackMeta(
        language=language, skill_level=skill, version=1,
        last_reviewed=date(2026, 5, 15), reviewer="test",
    )
    entries = [_entry(eid) for eid in (entry_ids or ["e1", "e2", "e3"])]
    return Pack(pack=meta, entries=entries)


@pytest.fixture
def personalizer():
    return Personalizer()


def _mk_response(content: str):
    resp = MagicMock()
    resp.content = content
    return resp


@pytest.mark.asyncio
async def test_happy_path_returns_ranked_entries(personalizer):
    pack = _pack(entry_ids=["a", "b", "c", "d"])
    payload = json.dumps({
        "intro": "Test intro.",
        "ranked": [
            {"id": "a", "relevance_note": "Note A"},
            {"id": "b", "relevance_note": "Note B"},
        ],
    })
    with patch("src.agents.cheatsheet.personalizer.model_router") as mr:
        mr.invoke_with_usage = AsyncMock(return_value=_mk_response(payload))
        result = await personalizer.personalize(
            packs=[pack], code_context_blocks=[], detected_libraries=[],
            complexity_score=0, complexity_suggested_level="beginner",
            requested_language="python", requested_skill="beginner",
            intent="", tenant_id="t", integration_name="i", user_id="u",
        )
    assert result.quality == "curated"
    assert len(result.ranked) == 2
    assert result.ranked[0].id == "a"
    assert result.intro == "Test intro."


@pytest.mark.asyncio
async def test_retry_on_bad_json(personalizer):
    pack = _pack(entry_ids=["a", "b", "c"])
    bad = _mk_response("NOT JSON")
    good = _mk_response(json.dumps({
        "intro": "Recovered.",
        "ranked": [{"id": "a", "relevance_note": "n"}],
    }))
    with patch("src.agents.cheatsheet.personalizer.model_router") as mr:
        mr.invoke_with_usage = AsyncMock(side_effect=[bad, good])
        result = await personalizer.personalize(
            packs=[pack], code_context_blocks=[], detected_libraries=[],
            complexity_score=0, complexity_suggested_level="beginner",
            requested_language="python", requested_skill="beginner",
            intent="", tenant_id="t", integration_name="i", user_id="u",
        )
    assert result.quality == "curated"
    assert result.intro == "Recovered."


@pytest.mark.asyncio
async def test_fallback_on_all_failures(personalizer):
    pack = _pack(entry_ids=["a", "b", "c"])
    with patch("src.agents.cheatsheet.personalizer.model_router") as mr:
        mr.invoke_with_usage = AsyncMock(return_value=_mk_response("NOT JSON"))
        result = await personalizer.personalize(
            packs=[pack], code_context_blocks=[], detected_libraries=[],
            complexity_score=0, complexity_suggested_level="beginner",
            requested_language="python", requested_skill="beginner",
            intent="", tenant_id="t", integration_name="i", user_id="u",
        )
    assert result.quality == "curated_unpersonalized"
    assert result.intro == ""
    assert [r.id for r in result.ranked] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_hallucinated_ids_are_dropped(personalizer):
    pack = _pack(entry_ids=["a", "b", "c"])
    payload = json.dumps({
        "intro": "intro",
        "ranked": [
            {"id": "a", "relevance_note": "real"},
            {"id": "made-up-id", "relevance_note": "hallucinated"},
            {"id": "b", "relevance_note": "real"},
        ],
    })
    with patch("src.agents.cheatsheet.personalizer.model_router") as mr:
        mr.invoke_with_usage = AsyncMock(return_value=_mk_response(payload))
        result = await personalizer.personalize(
            packs=[pack], code_context_blocks=[], detected_libraries=[],
            complexity_score=0, complexity_suggested_level="beginner",
            requested_language="python", requested_skill="beginner",
            intent="", tenant_id="t", integration_name="i", user_id="u",
        )
    assert [r.id for r in result.ranked] == ["a", "b"]


def test_pre_filter_drops_async_tag_when_no_async_in_code(personalizer):
    pack = _pack(entry_ids=["sync_entry", "filler1", "filler2"])
    pack.entries.append(_entry("async_entry", tags=["async"]))
    candidates = personalizer._build_candidates(
        packs=[pack], code_context_blocks=["x = 1\nprint(x)"],
        detected_libraries=[], intent="",
    )
    candidate_ids = {c["id"] for c in candidates}
    assert "sync_entry" in candidate_ids
    assert "async_entry" not in candidate_ids


def test_pre_filter_keeps_async_tag_when_async_in_code(personalizer):
    pack = _pack(entry_ids=["sync_entry", "filler1", "filler2"])
    pack.entries.append(_entry("async_entry", tags=["async"]))
    candidates = personalizer._build_candidates(
        packs=[pack], code_context_blocks=["async def foo():\n    await bar()"],
        detected_libraries=[], intent="",
    )
    candidate_ids = {c["id"] for c in candidates}
    assert "async_entry" in candidate_ids
