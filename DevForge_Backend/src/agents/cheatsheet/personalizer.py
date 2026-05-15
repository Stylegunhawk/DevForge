"""Single LLM call that ranks pack entries and writes relevance notes (v0.11).

Layer 2 of the three-layer architecture. NEVER invents code — the LLM only
ranks pre-written entry ids and produces short prose.
"""

import json
import logging
import re
from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError

from src.agents.cheatsheet.pack_models import Pack
from src.core.model_router import model_router

logger = logging.getLogger(__name__)


class RankedEntry(BaseModel):
    id: str
    relevance_note: str = Field(default="", max_length=200)


class PersonalizationOutput(BaseModel):
    intro: str = Field(default="", max_length=400)
    ranked: List[RankedEntry] = Field(min_length=1, max_length=7)
    quality: str = "curated"  # "curated" | "curated_unpersonalized"


SYSTEM_PROMPT = """You are a cheat-sheet curator. You are NOT a code writer.

Given a list of pre-written cheat-sheet entries, your job is to:
1. Pick at most 7 entries that best match the user's intent and code context.
2. For each picked entry, write ONE short sentence (<=25 words) explaining how it relates to what the user is doing right now. This is the `relevance_note`.
3. Write a 1-2 sentence intro paragraph that frames the cheat sheet around the user's activity.

You MUST NOT:
- Invent new entries or new ids
- Rewrite code examples or modify titles
- Output anything outside the JSON object

You MUST return entries by their `id` exactly as given in candidate_entries.

Output STRICT JSON only, matching this schema:
{
  "intro": "<1-2 sentences>",
  "ranked": [
    {"id": "<exact id from candidates>", "relevance_note": "<short>"},
    ...
  ]
}"""

_ASYNC_RE = re.compile(r"\b(async\s+def|await\s+|asyncio\.|\.create_task|\.gather)")


class Personalizer:
    """Layer 2: LLM personalization with retry + deterministic fallback."""

    MAX_CANDIDATES = 20

    def _build_candidates(
        self,
        packs: List[Pack],
        code_context_blocks: List[str],
        detected_libraries: List[str],
        intent: str,
    ) -> List[dict]:
        """Deterministic pre-filter. Returns candidate dicts in stable order."""
        code_blob = "\n".join(code_context_blocks)
        has_async = bool(_ASYNC_RE.search(code_blob))
        intent_lower = intent.lower()

        candidates: list[dict] = []
        for pack in packs:
            is_library_pack = pack.pack.library is not None
            for entry in pack.entries:
                if not has_async and "async" in entry.tags:
                    continue
                if is_library_pack:
                    lib = pack.pack.library or ""
                    if lib not in detected_libraries and lib.lower() not in intent_lower:
                        continue
                tag_overlap = sum(1 for t in entry.tags if t.lower() in intent_lower)
                score = (3 if is_library_pack else 1) + tag_overlap
                candidates.append({
                    "id": entry.id,
                    "title": entry.title,
                    "when_to_use": entry.when_to_use,
                    "tags": entry.tags,
                    "_score": score,
                })

        candidates.sort(key=lambda c: -c["_score"])
        candidates = candidates[: self.MAX_CANDIDATES]
        for c in candidates:
            c.pop("_score", None)
        return candidates

    def _summarize_code(self, blocks: List[str]) -> List[str]:
        snippets: list[str] = []
        for b in blocks:
            stripped = b.strip()
            if not stripped:
                continue
            snippets.append(stripped[:200])
            if len(snippets) >= 3:
                break
        return snippets

    def _parse_output(
        self, content: str, candidate_ids: set
    ) -> Optional[PersonalizationOutput]:
        if "```" in content:
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
                if content.startswith(("json\n", "yaml\n")):
                    content = content.split("\n", 1)[1]
        try:
            raw = json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Personalizer JSON parse failed: {e}")
            return None
        try:
            ranked_raw = raw.get("ranked", [])
            filtered = [r for r in ranked_raw if r.get("id") in candidate_ids]
            if not filtered:
                logger.warning("Personalizer returned 0 valid ids")
                return None
            raw["ranked"] = filtered
            return PersonalizationOutput(**raw)
        except ValidationError as e:
            logger.warning(f"Personalizer schema validation failed: {e}")
            return None

    def _fallback(self, candidates: List[dict]) -> PersonalizationOutput:
        ranked = [RankedEntry(id=c["id"], relevance_note="") for c in candidates[:7]]
        return PersonalizationOutput(
            intro="", ranked=ranked, quality="curated_unpersonalized"
        )

    async def personalize(
        self,
        packs: List[Pack],
        code_context_blocks: List[str],
        detected_libraries: List[str],
        complexity_score: int,
        complexity_suggested_level: str,
        requested_language: str,
        requested_skill: str,
        intent: str,
        tenant_id: str,
        integration_name: str,
        user_id: Optional[str],
    ) -> PersonalizationOutput:
        candidates = self._build_candidates(
            packs, code_context_blocks, detected_libraries, intent
        )
        if not candidates:
            return PersonalizationOutput(
                intro="",
                ranked=[RankedEntry(id="__none__")],
                quality="curated_unpersonalized",
            )

        candidate_ids = {c["id"] for c in candidates}
        payload = {
            "user_intent": intent,
            "code_context_summary": {
                "detected_libraries": detected_libraries,
                "complexity_score": complexity_score,
                "complexity_suggested_level": complexity_suggested_level,
                "key_snippets": self._summarize_code(code_context_blocks),
            },
            "requested": {
                "language": requested_language,
                "skill_level": requested_skill,
            },
            "candidate_entries": candidates,
        }

        model_name = model_router.select_model_by_task("routing")
        last_content = ""
        for attempt in range(2):
            try:
                user_msg = json.dumps(payload, ensure_ascii=False)
                if attempt > 0:
                    user_msg = (
                        f"Your previous output was invalid JSON: {last_content[:200]}. "
                        f"Return valid JSON only matching the schema.\n\n" + user_msg
                    )
                prompt = f"{SYSTEM_PROMPT}\n\n{user_msg}"
                response = await model_router.invoke_with_usage(
                    prompt=prompt,
                    model_name=model_name,
                    task_type="cheatsheet_personalization",
                    tenant_id=tenant_id,
                    integration_name=integration_name,
                    user_id=user_id,
                )
                content = (
                    response.content if hasattr(response, "content") else str(response)
                )
                last_content = content
                parsed = self._parse_output(content, candidate_ids)
                if parsed is not None:
                    return parsed
            except Exception as e:
                logger.warning(f"Personalizer attempt {attempt + 1} raised: {e}")
                continue

        logger.warning("Personalizer exhausted retries; using deterministic fallback")
        return self._fallback(candidates)
