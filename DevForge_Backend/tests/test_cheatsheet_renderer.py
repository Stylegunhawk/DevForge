"""Tests for cheatsheet markdown renderer (v0.11)."""

from datetime import date

from src.agents.cheatsheet.markdown_renderer import render_markdown
from src.agents.cheatsheet.pack_models import Entry, Example, Pack, PackMeta
from src.agents.cheatsheet.personalizer import PersonalizationOutput, RankedEntry


def _make_pack():
    meta = PackMeta(
        language="python", skill_level="intermediate", version=1,
        last_reviewed=date(2026, 5, 15), reviewer="test",
    )
    entries = [
        Entry(
            id="py.x", title="X Title", explanation="X explanation.",
            tags=[], when_to_use="",
            examples=[Example(title="X ex", language="python", code="x = 1")],
            pitfalls=["X pitfall"],
        ),
        Entry(
            id="py.y", title="Y Title", explanation="Y explanation.",
            tags=[], when_to_use="",
            examples=[Example(title="Y ex", language="rust", code="fn main() {}")],
            pitfalls=["Y pitfall"],
        ),
        Entry(
            id="py.z", title="Z Title", explanation="Z explanation.",
            tags=[], when_to_use="",
            examples=[Example(title="Z ex", language="python", code="z = 3")],
            pitfalls=["Z pitfall"],
        ),
    ]
    return Pack(pack=meta, entries=entries)


def test_header_uses_requested_language_and_skill():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="Some intro.",
        ranked=[RankedEntry(id="py.x", relevance_note="note")],
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert md.startswith("# Python Cheat Sheet - Intermediate")


def test_intro_is_included_when_present():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="Custom intro paragraph.",
        ranked=[RankedEntry(id="py.x", relevance_note="")],
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert "Custom intro paragraph." in md


def test_intro_omitted_when_empty():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="", ranked=[RankedEntry(id="py.x", relevance_note="")],
        quality="curated_unpersonalized",
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert "\n\n_\n\n" not in md


def test_fence_tag_tracks_entry_language_not_request():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="",
        ranked=[RankedEntry(id="py.y", relevance_note="")],
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert "```rust" in md
    assert "```python" not in md


def test_ranking_order_is_respected():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="",
        ranked=[
            RankedEntry(id="py.y", relevance_note=""),
            RankedEntry(id="py.x", relevance_note=""),
        ],
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert md.find("Y Title") < md.find("X Title")


def test_unknown_ranked_id_is_skipped():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="",
        ranked=[
            RankedEntry(id="py.x", relevance_note=""),
            RankedEntry(id="does.not.exist", relevance_note=""),
        ],
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert "X Title" in md
    assert "does.not.exist" not in md


def test_relevance_note_appears_inline():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="",
        ranked=[RankedEntry(id="py.x", relevance_note="Matches your code.")],
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert "Matches your code." in md


def test_pitfalls_section_rendered():
    pack = _make_pack()
    output = PersonalizationOutput(
        intro="", ranked=[RankedEntry(id="py.x", relevance_note="")],
    )
    md = render_markdown("python", "intermediate", [pack], output)
    assert "X pitfall" in md
    assert "Common Pitfalls" in md
