"""Cheatsheet agent v0.11 — Curated Packs + LLM Personalization.

Three-layer pipeline:
  1. Pack loader (deterministic ground truth from data/cheatsheet_packs/)
  2. Personalizer (single LLM call: ranks + writes relevance notes)
  3. Markdown renderer (pure-function assembly)
"""

import logging
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from src.agents.cheatsheet.complexity_scorer import calculate_complexity
from src.agents.cheatsheet.context_parser import parse_code_context
from src.agents.cheatsheet.language_detector import detect_language
from src.agents.cheatsheet.library_detector import detect_libraries
from src.agents.cheatsheet.markdown_renderer import render_markdown
from src.agents.cheatsheet.pack_loader import (
    PackLoader,
    PackNotFoundError,
    SUPPORTED_LANGUAGES,
)
from src.agents.cheatsheet.personalizer import Personalizer
from src.agents.cheatsheet.request_model import CheatsheetRequest

logger = logging.getLogger(__name__)

_PACK_ROOT = Path(__file__).resolve().parents[3] / "data" / "cheatsheet_packs"
_loader = PackLoader(root=_PACK_ROOT)
_personalizer = Personalizer()


def _failure(message: str) -> dict:
    return {"success": False, "data": {"message": message}, "format": "markdown"}


async def generate_cheatsheet_invoke(
    args: dict,
    tenant_id: str = "unknown",
    integration_name: str = "unknown",
    user_id: Optional[str] = None,
) -> dict:
    """MCP gateway entry point for the cheatsheet tool."""
    # 1. Validate request
    try:
        req = CheatsheetRequest(**args)
    except ValidationError as e:
        first = e.errors()[0]
        return _failure(first.get("msg", "Invalid request."))

    # 2. Parse code context + run deterministic analysis
    parsed = parse_code_context(req.code_context or "")
    blocks = parsed.get("blocks", [])
    detected_libraries = detect_libraries(blocks) if blocks else []
    complexity = (
        calculate_complexity(blocks)
        if blocks
        else {"score": 0, "suggested_level": "beginner", "features": {}}
    )

    # 3. Resolve language (explicit wins, else auto-detect from code)
    language = req.language
    if not language and blocks:
        language = detect_language(blocks[0])
    if not language:
        return _failure(
            "Could not detect language from code_context. "
            "Pass an explicit 'language' or 'intent'."
        )
    if language not in SUPPORTED_LANGUAGES:
        return _failure(
            f"Language {language!r} is not supported. "
            f"Supported: {', '.join(SUPPORTED_LANGUAGES)}."
        )

    # 4. Load packs
    try:
        lang_pack = _loader.load_language_pack(language, req.skill_level)
    except PackNotFoundError as e:
        logger.error(f"Pack data missing: {e}")
        return _failure(
            f"Internal: pack data missing for {language}/{req.skill_level}."
        )

    packs = [lang_pack]
    packs_used = [{
        "kind": "language",
        "id": f"{language}/{req.skill_level}",
        "version": lang_pack.pack.version,
        "last_reviewed": lang_pack.pack.last_reviewed.isoformat(),
    }]
    for lib in detected_libraries:
        lib_pack = _loader.load_library_pack(lib, req.skill_level)
        if lib_pack is not None:
            packs.append(lib_pack)
            packs_used.append({
                "kind": "library",
                "id": f"{lib}/{req.skill_level}",
                "version": lib_pack.pack.version,
                "last_reviewed": lib_pack.pack.last_reviewed.isoformat(),
            })

    # 5. Personalize (single LLM call — analytics flow via model_router.task_type)
    personalization = await _personalizer.personalize(
        packs=packs,
        code_context_blocks=blocks,
        detected_libraries=detected_libraries,
        complexity_score=complexity["score"],
        complexity_suggested_level=complexity["suggested_level"],
        requested_language=language,
        requested_skill=req.skill_level,
        intent=req.intent or "",
        tenant_id=tenant_id,
        integration_name=integration_name,
        user_id=user_id,
    )

    # 6. Render markdown
    markdown = render_markdown(language, req.skill_level, packs, personalization)

    # 7. Build response (additive new fields, keeps legacy keys)
    ranked_entries = []
    for ranked in personalization.ranked:
        entry = None
        source_pack = None
        for pack in packs:
            for e in pack.entries:
                if e.id == ranked.id:
                    entry = e
                    source_pack = (
                        f"libraries/{pack.pack.library}/{pack.pack.skill_level}"
                        if pack.pack.library
                        else f"languages/{pack.pack.language}/{pack.pack.skill_level}"
                    )
                    break
            if entry:
                break
        if entry is None:
            continue
        ranked_entries.append({
            "id": ranked.id,
            "title": entry.title,
            "relevance_note": ranked.relevance_note,
            "source_pack": source_pack,
        })

    return {
        "success": True,
        "data": {
            "language": language,
            "skill_level": req.skill_level,
            "complexity_score": complexity["score"],
            "complexity_suggested_level": complexity["suggested_level"],
            "detected_libraries": detected_libraries,
            "packs_used": packs_used,
            "ranked_entries": ranked_entries,
            "intro": personalization.intro,
            "quality": personalization.quality,
            "markdown": markdown,
        },
        "format": "markdown",
    }
