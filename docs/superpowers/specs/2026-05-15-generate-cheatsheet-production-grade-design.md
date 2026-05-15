# generate_cheatsheet v0.11 — Production-Grade Design (Curated Packs + LLM Personalization)

**Date:** 2026-05-15
**Status:** Approved for implementation
**Supersedes:** generate_cheatsheet v0.8.0 (Python-only string templates)
**Companion specs:** [v0.10 refine_prompt](2026-05-14-refine-prompt-robustness-design.md), [v0.9 generate_data](2026-05-15-generate-data-production-grade-design.md)

---

## Goal

Replace the Python-only string-template cheatsheet pipeline with an **activity-driven, AI-personalized, deterministically-grounded** system. The current tool returns Python content under a relabelled header for any non-Python request; v0.11 returns real, syntax-validated content for 9 ecosystems, ranked by the user's actual code and intent, with zero LLM hallucination of code.

---

## Architecture (three layers)

```
Layer 1 — Ground Truth (deterministic, git-versioned)
   data/cheatsheet_packs/
     languages/{python,javascript,typescript,go,rust,java,ruby,php,csharp}/
       {beginner,intermediate,expert}.yaml
     libraries/{pandas,numpy,matplotlib,scikit-learn,fastapi,flask,django,
                pydantic,asyncio,aiohttp,sqlalchemy,requests,httpx,pytest}/
       {beginner,intermediate,expert}.yaml

Layer 2 — Personalization (single LLM call per request, bounded prompt)
   inputs:  resolved packs, code_context summary, intent, complexity
   outputs: ranked entry ids (max 7), per-entry relevance notes, intro paragraph
   retries: 2 on JSON parse failure; deterministic fallback on final failure

Layer 3 — Render (pure-function markdown assembly, no LLM)
   inputs:  ranked entries + Layer 1 examples/pitfalls + Layer 2 intro/notes
   outputs: markdown string with code fences tagged from entry.examples[].language
```

**Key invariants:**

1. **Code never invented by LLM.** All code examples come verbatim from YAML in Layer 1. LLM only ranks and writes prose `relevance_note` strings.
2. **No silent fallback.** Unsupported `language` returns 400 with the supported list. No more Python content under a Rust header.
3. **Code fence honesty.** The ` ```<lang>` tag echoes `entry.examples[].language`, not the request input.
4. **Determinism on repeat.** Identical inputs → identical pre-filter → same candidate set. LLM ordering may vary within that bounded set; falls back to deterministic order on LLM failure.
5. **Provenance.** Response includes `packs_used` with version + `last_reviewed` so callers can cite the source.

---

## Scope (v1)

- **9 ecosystems:** python, javascript, typescript, go, rust, java, ruby, php, csharp (matches refine_prompt v0.10).
- **14 libraries:** pandas, numpy, matplotlib, scikit-learn, fastapi, flask, django, pydantic, asyncio, aiohttp, sqlalchemy, requests, httpx, pytest (existing `LIBRARY_SIGNATURES`).
- **3 skill levels** per pack: beginner, intermediate, expert.
- **Total packs:** 9 × 3 + 14 × 3 = **69 YAML files**, each with 3–12 entries.

---

## Pack schema

```yaml
# data/cheatsheet_packs/languages/python/intermediate.yaml
pack:
  language: python                # tree-sitter grammar name
  skill_level: intermediate       # beginner | intermediate | expert
  version: 1                      # bump on material change
  last_reviewed: 2026-05-15
  reviewer: <git author>
  # library-only fields:
  # library: pandas
  # library_version_floor: "2.0"

entries:
  - id: py.intermediate.list_comprehensions
    title: "List Comprehensions"
    explanation: "Transform a sequence into another sequence in one expression."
    tags: [syntax, performance]
    when_to_use: "Mapping/filtering a list when readability isn't sacrificed."
    examples:
      - title: "Filter + transform"
        language: python
        code: |
          squares = [x*x for x in nums if x > 0]
    pitfalls:
      - "Nested comprehensions become unreadable quickly — prefer explicit loops past two levels."
      - "List comprehensions build the full list in memory; for large iterables use generators."
  # ... 2–11 more entries
```

**Pydantic models** (`src/agents/cheatsheet/pack_models.py`):

```python
class Example(BaseModel):
    title: str
    language: str
    code: str

class Entry(BaseModel):
    id: str
    title: str
    explanation: str
    tags: list[str] = []
    when_to_use: str = ""
    examples: list[Example] = Field(min_length=1)
    pitfalls: list[str] = Field(min_length=1)

class PackMeta(BaseModel):
    language: str
    skill_level: Literal["beginner", "intermediate", "expert"]
    version: int = 1
    library: Optional[str] = None
    library_version_floor: Optional[str] = None
    last_reviewed: date
    reviewer: str

class Pack(BaseModel):
    pack: PackMeta
    entries: list[Entry] = Field(min_length=3, max_length=12)
```

**Schema invariants enforced by CI:**

- Every `examples[].code` parses cleanly under its `language` grammar via tree-sitter.
- Every entry has `id`, `title`, `explanation`, ≥1 `example`, ≥1 `pitfall`.
- `id` is globally unique across all packs.
- Library packs always have `pack.language == "python"` (current 14 libs are Python-only); `pack.library` is set.

---

## Request / response API

### Request

```python
class CheatsheetRequest(BaseModel):
    language: Optional[str] = None
    skill_level: Literal["beginner", "intermediate", "expert"] = "beginner"
    code_context: Optional[str] = Field(default=None, max_length=20000)
    intent: Optional[str] = Field(default=None, max_length=400)  # NEW v0.11

    @model_validator(mode="after")
    def validate_at_least_one(self):
        if not (self.language or self.code_context or self.intent):
            raise ValueError("Must provide at least one of: language, code_context, or intent.")
        return self
```

### Success response

```json
{
  "success": true,
  "data": {
    "language": "python",
    "skill_level": "intermediate",
    "complexity_score": 28,
    "complexity_suggested_level": "intermediate",
    "detected_libraries": ["pandas"],
    "packs_used": [
      {"kind": "language", "id": "python/intermediate", "version": 1, "last_reviewed": "2026-05-15"},
      {"kind": "library", "id": "pandas/intermediate", "version": 1, "last_reviewed": "2026-05-15"}
    ],
    "ranked_entries": [
      {"id": "pd.intermediate.groupby_agg", "title": "GroupBy + Aggregate",
       "relevance_note": "Matches your df.groupby call.",
       "source_pack": "libraries/pandas/intermediate"}
    ],
    "intro": "Because you're aggregating sales data with pandas, this sheet leads with GroupBy patterns.",
    "quality": "curated",
    "markdown": "# Python Cheat Sheet - Intermediate\n\n_intro paragraph_\n\n## 1. GroupBy + Aggregate\n..."
  },
  "format": "markdown"
}
```

### Error responses

| Trigger | Code | Message |
|---------|------|---------|
| Unknown `language` | 400 / `-32602` | `"Language 'cobol' is not supported. Supported: python, javascript, typescript, go, rust, java, ruby, php, csharp."` |
| No `language` AND no `code_context` AND no `intent` | 400 / `-32602` | `"Must provide at least one of: language, code_context, or intent."` |
| Auto-detect fails, no `language`, no `intent` | 400 / `-32602` | `"Could not detect language from code_context. Pass an explicit 'language' or 'intent'."` |
| Pack file missing for supported language (config drift) | 500 / `-32603` | `"Internal: pack data missing for {lang}/{skill}."` |
| LLM JSON parse fails after retries | **200 success** with `quality: "curated_unpersonalized"` | Deterministic fallback ordering, `intro=""`, no relevance notes |

---

## Personalization layer (single LLM call)

**Inputs sent to LLM:**

```python
{
  "user_intent": "<intent string or ''>",
  "code_context_summary": {
    "languages_seen": ["python"],
    "detected_libraries": ["pandas"],
    "complexity_score": 28,
    "complexity_suggested_level": "intermediate",
    "key_snippets": ["df.groupby('region').sum()", "..."]   # max 3, 200 chars each
  },
  "requested": {"language": "python", "skill_level": "intermediate"},
  "candidate_entries": [
    {"id": "py.intermediate.list_comprehensions", "title": "...",
     "when_to_use": "...", "tags": ["syntax"]},
    # ... max 20 candidates after deterministic pre-filter
  ]
}
```

**System prompt directive (abbreviated):**

> You are a cheat-sheet curator. You are NOT a code writer.
> Pick at most 7 entries by `id`. For each, write ≤25 words of relevance note.
> Write a 1–2 sentence intro framing the sheet around the user's activity.
> You must NOT invent new entries, rewrite code examples, or modify titles.
> Output strict JSON: `{intro: str, ranked: [{id: str, relevance_note: str}]}`.

**Pre-filter (deterministic, before LLM):**

1. Tag exclusion: drop entries tagged `async` if code shows no `async def` / `await ` / `asyncio.`.
2. Library gating: include library-pack entries only if the library was detected OR intent string mentions the library name.
3. Hard cap: if >20 candidates, keep top 20 by score = `(library_pack ? 3 : 1) + tag_overlap_with_intent`.

**Output validation:**

```python
class RankedEntry(BaseModel):
    id: str
    relevance_note: str = Field(max_length=200)

class PersonalizationOutput(BaseModel):
    intro: str = Field(max_length=400)
    ranked: list[RankedEntry] = Field(min_length=1, max_length=7)
```

- Validate every `id` exists in the candidate set; drop unknown ids silently (no hallucinated entries leak through).
- On parse failure → 1 retry with corrective prompt → final fallback returns pre-filter-ordered entries, `intro=""`, marked `quality: "curated_unpersonalized"`.

**Model routing:** uses `model_router.invoke_with_usage(task_type="cheatsheet_personalization", ...)` — dashboard `/usage/` page gets per-task attribution like v0.9 datagen.

**Latency budget:**

| Step | Time |
|------|------|
| Pack load (L2 cached) | <10 ms |
| Pre-filter | <5 ms |
| LLM call (free Ollama `gpt-oss:20b-cloud`) | 5–15 s warm, 20–30 s cold |
| Render markdown | <20 ms |
| **Total** | **~6–16 s warm, ~25–35 s cold** |

---

## Caching

| Layer | Key | TTL | Purpose |
|-------|-----|-----|---------|
| L1 pack | `(language, skill_level)` + detected libs | request scope | Avoid double-reads within one request |
| L2 pack | `(file_path, mtime)` → `Pack` | process lifetime | Hot reload on file change without restart |
| **No LLM cache in v1** | — | — | Personalization output is request-unique; LLM cache deferred to v0.12 if dashboard shows high duplicate-input rate |

---

## File changes

### New files

| File | Purpose |
|------|---------|
| `data/cheatsheet_packs/**/*.yaml` | ~69 ground-truth packs |
| `src/agents/cheatsheet/pack_models.py` | Pydantic models for Pack/Entry/Example |
| `src/agents/cheatsheet/pack_loader.py` | YAML load + L1/L2 cache + supported-language registry |
| `src/agents/cheatsheet/personalizer.py` | Single LLM call, JSON parse, retry, deterministic fallback |
| `src/agents/cheatsheet/markdown_renderer.py` | Pure-function render |
| `src/agents/cheatsheet/language_detector.py` | Tree-sitter-based detection, returns `Optional[str]` |
| `src/agents/cheatsheet/request_model.py` | `CheatsheetRequest` Pydantic model |
| `scripts/bootstrap_cheatsheet_packs.py` | One-shot LLM bootstrap to seed all packs |
| `scripts/validate_cheatsheet_packs.py` | CI gate: tree-sitter + Pydantic |
| `tests/test_cheatsheet_packs.py` | Pack schema + coverage tests |
| `tests/test_cheatsheet_personalizer.py` | LLM-mocked personalization tests |
| `tests/test_cheatsheet_renderer.py` | Render tests |

### Files to keep

| File | Action |
|------|--------|
| `src/agents/cheatsheet/agent.py` | **Rewrite** as orchestrator |
| `src/agents/cheatsheet/context_parser.py` | **Keep as-is** |
| `src/agents/cheatsheet/library_detector.py` | **Keep**, cross-validate keys against pack dirs |
| `src/agents/cheatsheet/complexity_scorer.py` | **Keep**, expose `suggested_level` in response |

### Files to delete

| File | Why |
|------|-----|
| `src/agents/cheatsheet/enhanced_templates.py` | 18 KB Python-only string templates, replaced by YAML packs |
| `src/agents/cheatsheet/section_selector.py` | Replaced by `pack_loader.py` + LLM ranking |
| `src/agents/cheatsheet/quick_reference.py` | Quick-ref rows become entries with `tags: [quick-ref]` inside packs |
| `src/tools/cheatsheet/tools.py` | `detect_language_from_code` replaced by tree-sitter detector |
| `src/tools/cheatsheet/` (whole dir) | Empty after deletion |

### Other changes

- `src/api/routers/__init__.py`: rewrite `TOOL_DESCRIPTIONS["generate_cheatsheet"]` in agent-instructive style; update `_get_tool_schema` to include `intent`.
- `manifests/devforge.json`: bump version 0.10.0 → 0.11.0, sync description.
- `src/agents/cheatsheet/agent.py` async wrapper: wire `log_request_call.delay(...)` analytics.
- `docs/tools/generate_cheatsheet.md`: rewrite to reflect v0.11.
- `docs/tools/generate_cheatsheet_flowchart.md`: new PlantUML for 3-layer pipeline (or create if missing).
- `DevForge_Backend/CLAUDE.md`: bump `generate_cheatsheet` row in "Current tool versions" table.

---

## Bootstrap workflow

`scripts/bootstrap_cheatsheet_packs.py`:

```bash
# Bootstrap all 69 packs (one-shot, ~30 min)
python scripts/bootstrap_cheatsheet_packs.py --all

# Regenerate one combination
python scripts/bootstrap_cheatsheet_packs.py --library polars --skill expert

# Force overwrite existing files
python scripts/bootstrap_cheatsheet_packs.py --all --overwrite
```

**Per-target flow:**

1. Build prompt with target + skill_level + JSON schema of `Pack`.
2. Call `model_router.invoke_with_usage(task_type="cheatsheet_bootstrap")`.
3. Parse YAML → `Pack` Pydantic. Retry 2× on parse failure.
4. Run tree-sitter on every example. On any failure: feed back to LLM with `"your example for entry X failed: <err>. Rewrite ONLY that example."` Retry 2×.
5. Write YAML. Append result to `scripts/bootstrap_report.md` (timestamp, retries, validation outcome).

**Idempotence:** skip existing files unless `--overwrite`. Temperature=0 + deterministic system prompt header.

**NOT in CI** — offline ops script run by humans, output reviewed via PR.

---

## CI / build-time gates

Add to test target:

```bash
python scripts/validate_cheatsheet_packs.py data/cheatsheet_packs/  # tree-sitter + Pydantic
pytest tests/ -v
```

Broken syntax in any pack fails the build.

---

## Testing strategy (5 layers)

| Layer | What it asserts | Test file | CI? |
|-------|-----------------|-----------|-----|
| Pack schema | Every YAML parses, has required fields, ids globally unique | `tests/test_cheatsheet_packs.py` | yes |
| Pack syntax | Every example parses under its declared grammar (0 errors) | `scripts/validate_cheatsheet_packs.py` via pytest fixture | yes |
| Pack coverage | 9 langs × 3 = 27 language packs; 14 libs × 3 = 42 library packs all present | `tests/test_cheatsheet_packs.py::test_coverage_matrix` | yes |
| Personalizer | Happy path, retry-on-bad-JSON, hallucinated-id drop, deterministic fallback | `tests/test_cheatsheet_personalizer.py` | yes |
| Renderer | Fence tag matches `entry.examples[].language`, ranked order respected, intro appears once | `tests/test_cheatsheet_renderer.py` | yes |
| End-to-end | Real LLM call returns valid markdown, `quality: "curated"` | `tests/test_cheatsheet.py::test_e2e_with_real_llm` | nightly only (opt-in) |

Target counts:
- Schema: ~6 tests
- Syntax gate: 1 parametrized test (~345 syntax assertions across all packs)
- Coverage: 3 tests
- Personalizer: ~10 tests
- Renderer: ~8 tests
- E2E: 2 tests (skipped unless `RUN_LLM_TESTS=1`)
- **Grand total: ~30 deterministic + 2 LLM-gated** (current state: 14 tests across 3 files)

---

## Backward compatibility

- Old request shape (`language` + `skill_level` + `code_context`) still works — `intent` is optional.
- Old response fields retained: `success`, `language`, `skill_level`, `markdown`, `data.detected_libraries`, `data.complexity_score`.
- New fields are additive: `data.complexity_suggested_level`, `data.packs_used`, `data.ranked_entries`, `data.intro`, `data.quality`.
- **One breaking change:** `data.sections: [{title}]` is removed — replaced by `data.ranked_entries[].title`. Grep frontend/dashboard for `data.sections` before merge.

---

## Failure modes & observability

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Pack file deleted in prod | Loader logs `ERROR: missing pack file X`, returns 500 | Re-deploy; alert via existing logging |
| LLM endpoint down | Personalizer catches exception → deterministic fallback | User gets useful sheet; dashboard shows `cheatsheet_personalization` failures spike |
| LLM returns bad JSON 3× | Same fallback path | Same |
| Tree-sitter gate detects regression in CI | PR red-bar | Reviewer fixes, re-runs |
| Bootstrap produces subtle pitfall error | Human PR review | Reviewer rewrites; nightly e2e catches obvious regressions |

Dashboard `/usage/` gets a new row `task_type=cheatsheet_personalization` automatically via `model_router.invoke_with_usage`.

---

## MCP tool description (agent-instructive, matches v0.9/v0.10)

```text
Generates an activity-aware programming cheat sheet from curated, human-reviewed
knowledge packs (one LLM call for personalization).

SUPPORTED LANGUAGES: python, javascript, typescript, go, rust, java, ruby, php,
csharp. Unsupported languages return a 400 error — DO NOT retry with a different
value, ask the user.

INPUTS you should provide:
  - language (one of the above, or omit to auto-detect from code_context)
  - skill_level (beginner|intermediate|expert; default beginner)
  - code_context (paste the user's actual code if available — enables library
    detection and activity-aware ranking)
  - intent (1-line description of what the user is trying to do, e.g.
    'debugging async deadlock' — strongly improves relevance when code is
    unavailable or short).

OUTPUTS: data.markdown (rendered sheet), data.ranked_entries (structured),
data.packs_used (provenance for citing), data.quality ('curated' = LLM-
personalized; 'curated_unpersonalized' = deterministic fallback fired because
LLM returned bad JSON — content is still trustworthy but not tailored).

LATENCY: 5–15s warm-cache, 20–30s cold-cache. Suggest a loading indicator.
```

---

## Out of scope for v1

- LLM response caching (Redis L3) — deferred to v0.12 pending dashboard usage data.
- Adding languages beyond the 9 ecosystems — additive PR per language.
- Per-version library variants (e.g., pandas 1.x vs 2.x) — current `library_version_floor` is informational only in v1.
- Auto-bootstrap on new library detection — manual PR workflow only.
- Per-tenant pack overrides / customization — single shared knowledge base in v1.

---

## Rollout phases

| Phase | Work | Days |
|-------|------|------|
| 0 | Spec + plan | 0 |
| 1 | Foundation: pack_models, pack_loader, language_detector, validate script | 1–2 |
| 2 | Bootstrap content + manual review of 69 packs | 3–4 |
| 3 | Personalizer + renderer + agent rewrite | 5–6 |
| 4 | Delete legacy + analytics + MCP description + docs | 7 |
| 5 | MCP verification (5 scenarios) + dashboard verification | 8 |

**~8 days end-to-end**, calendar-time dominated by Phase 2 (~6 hours of human spot-review).
