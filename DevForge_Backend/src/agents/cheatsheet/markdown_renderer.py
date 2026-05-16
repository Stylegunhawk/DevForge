"""Layer 3: deterministic markdown render. No LLM (v0.11)."""

from typing import List, Optional

from src.agents.cheatsheet.pack_models import Entry, Pack
from src.agents.cheatsheet.personalizer import PersonalizationOutput


def _lookup_entry(packs: List[Pack], entry_id: str) -> Optional[Entry]:
    for pack in packs:
        for entry in pack.entries:
            if entry.id == entry_id:
                return entry
    return None


def render_markdown(
    requested_language: str,
    requested_skill: str,
    packs: List[Pack],
    personalization: PersonalizationOutput,
) -> str:
    lines: list[str] = [
        f"# {requested_language.title()} Cheat Sheet - {requested_skill.title()}"
    ]

    if personalization.intro:
        lines.append("")
        lines.append(f"_{personalization.intro}_")

    section_no = 0
    for ranked in personalization.ranked:
        entry = _lookup_entry(packs, ranked.id)
        if entry is None:
            continue
        section_no += 1
        lines.append("")
        lines.append(f"## {section_no}. {entry.title}")
        if ranked.relevance_note:
            lines.append("")
            lines.append(f"> {ranked.relevance_note}")
        lines.append("")
        lines.append(entry.explanation)

        for ex in entry.examples:
            lines.append("")
            lines.append(f"### {ex.title}")
            lines.append("")
            lines.append(f"```{ex.language}")
            lines.append(ex.code.rstrip())
            lines.append("```")

        if entry.pitfalls:
            lines.append("")
            lines.append("### Common Pitfalls")
            for p in entry.pitfalls:
                lines.append(f"- {p}")

    return "\n".join(lines) + "\n"
