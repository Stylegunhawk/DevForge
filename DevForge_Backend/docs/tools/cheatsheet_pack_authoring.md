# Cheatsheet Pack Authoring Guide

**For:** Engineers and writers who want to add a new language/library cheat sheet or deepen an existing one.
**Last updated:** 2026-05-15
**Related:** [generate_cheatsheet.md](generate_cheatsheet.md), [generate_cheatsheet_frontend_integration.md](generate_cheatsheet_frontend_integration.md)

This guide is the playbook for working with `data/cheatsheet_packs/`. It covers (1) the LLM bootstrap workflow for getting a first-draft pack on disk in 30 s, and (2) the hand-deepening pattern that promotes a pack to production quality — the same pattern used to take `python/{beginner,intermediate,expert}` from bootstrap to v2 on 2026-05-15.

---

## 1. Mental model — three layers, one truth

```
┌─────────────────────────────────┐
│  data/cheatsheet_packs/*.yaml   │  ← YOU EDIT HERE (ground truth)
│  Hand-reviewed in PR, in git    │
└─────────────────────────────────┘
              ▲
              │ loads pack at request time
              │
┌─────────────────────────────────┐
│  src/agents/cheatsheet/         │  ← Runtime — never edited by you
│   personalizer.py (1 LLM call,  │     unless changing behavior
│   ranks ids + writes notes)     │
│   markdown_renderer.py          │
└─────────────────────────────────┘
              │
              ▼
   markdown returned to user
```

**The LLM at request time never invents code or new entry IDs.** It picks 3–7 entries from your YAML and writes one-sentence relevance notes. So **the quality of the user's cheatsheet is the quality of your YAML.**

---

## 2. Pack file layout

```
data/cheatsheet_packs/
├── languages/
│   ├── python/
│   │   ├── beginner.yaml
│   │   ├── intermediate.yaml
│   │   └── expert.yaml
│   ├── javascript/...
│   └── ... (9 supported languages)
└── libraries/
    ├── pandas/
    │   ├── beginner.yaml
    │   ├── intermediate.yaml
    │   └── expert.yaml
    ├── fastapi/...
    └── ... (14 libraries)
```

**Rule:** language packs go under `languages/<lang>/<skill>.yaml`. Library packs go under `libraries/<lib>/<skill>.yaml`. The 9 supported languages are listed in `src/agents/cheatsheet/pack_loader.py:SUPPORTED_LANGUAGES`. The 14 libraries are detected by regex in `src/agents/cheatsheet/library_detector.py:LIBRARY_SIGNATURES`.

To add a *new* library detector, add a regex to `LIBRARY_SIGNATURES` first, then drop YAML packs under `libraries/<new-lib>/`. To add a *new* language, edit `SUPPORTED_LANGUAGES` and `language_detector.py:LANGUAGE_SIGNATURES`.

---

## 3. Schema reference

Defined in `src/agents/cheatsheet/pack_models.py`. Pydantic v2 with `extra="forbid"` — typos and unexpected fields will be rejected at load time.

### `PackMeta` (the `pack:` block)

| Field | Type | Required | Notes |
|---|---|---|---|
| `language` | string | yes | One of the 9 supported languages, lowercase |
| `skill_level` | `beginner` \| `intermediate` \| `expert` | yes | Literal enum |
| `version` | int | no (default 1) | Bump when you make breaking changes; surfaced to clients as `packs_used[].version` |
| `library` | string \| null | **null for language packs** | Set ONLY for packs under `libraries/`. **This is the bug we hit on 2026-05-15** — see [the rust/expert footgun](#7-known-footguns) |
| `library_version_floor` | string \| null | null unless library | Informational only; not auto-checked against installed library |
| `last_reviewed` | YYYY-MM-DD | yes | Surfaced in response provenance |
| `reviewer` | string | yes | Your name/handle |

### `Pack`

| Field | Type | Constraints |
|---|---|---|
| `pack` | `PackMeta` | yes |
| `entries` | list of `Entry` | **min_length=3, max_length=12** |

### `Entry`

| Field | Type | Constraints |
|---|---|---|
| `id` | string | unique within file. Convention: `<lang|lib>.<skill>.<topic>` (e.g. `py.expert.metaclasses`) |
| `title` | string | The header that renders in the markdown |
| `explanation` | string | 1–3 sentences. The LLM uses this for ranking context. |
| `tags` | list of strings | **The personalizer scores entries by tag overlap with user intent — richer tags = better matching.** Aim 5–9 tags per entry, lowercase, hyphenated. |
| `when_to_use` | string | 1 sentence. Reinforces relevance signal — repeat intent keywords here. |
| `examples` | list of `Example` | **min_length=1**. We recommend **2–3 examples per entry** for production quality. |
| `pitfalls` | list of strings | **min_length=1**. We recommend **4–5 pitfalls** — these are gold for users. |

### `Example`

| Field | Type | Constraints |
|---|---|---|
| `title` | string | Short label rendered above the code block |
| `language` | string | **MUST be lowercase** — `python` not `Python`, `javascript` not `JavaScript`. The tree-sitter validator (`scripts/validate_cheatsheet_packs.py`) maps lowercase only |
| `code` | string | **MUST tree-sitter parse cleanly** under the named grammar. Validate with the validator script before committing. |

---

## 4. Two workflows

### Workflow A — LLM bootstrap (first draft, 30 s)

```bash
docker exec -w /app -e PYTHONPATH=/app devforge-api \
  python scripts/bootstrap_cheatsheet_packs.py \
  --language go --skill intermediate
```

Flags:
- `--all` — bootstrap every missing pack (9 × 3 + 14 × 3 = 69 total)
- `--language <name>` — single language; combine with `--skill` to narrow
- `--library <name>` — single library; combine with `--skill`
- `--skill <beginner|intermediate|expert>` — narrow skill, requires `--language` or `--library`
- `--overwrite` — replace existing files (default: skip if present, preserving hand-edits)

**The bootstrap script:**
- Calls `gpt-oss:20b-cloud` once per pack with a strict YAML-only prompt
- Validates output through `Pack(**raw)` Pydantic before write — bad output is retried up to 3 times
- Appends per-pack outcome to `scripts/bootstrap_report.md`
- Idempotent — re-running is safe; won't touch existing files unless `--overwrite`

**Quality expectation:** bootstrap output is a **first draft**:
- 5–8 entries per pack
- 1 example per entry
- 2–3 tags per entry (sparse)
- 2 pitfalls per entry
- ~50% chance of cosmetic issues (capitalized `language: Python`, duplicate ids across packs, occasional `library: <name>` leaking onto a language pack)

It's enough to demo the feature for any new language. For production polish, deepen by hand — see Workflow B.

### Workflow B — Hand-deepening (production quality, ~1 hr per skill level)

This is the pattern used to take `python/*.yaml` to v2.

**Target shape:**
- 10–12 entries (max enforced by schema)
- 2–3 examples per entry (show different idioms / use cases)
- 4–5 pitfalls per entry
- 5–9 tags per entry (the more, the better the personalizer ranks for off-keyword intents)

**Topic-selection rubric:**
1. Cover the **language fundamentals** at beginner (variables, types, control flow, functions, collections, I/O, errors, imports, basic comprehensions if applicable)
2. Cover **intermediate idioms** at intermediate (decorators, OOP, dunder methods, context managers, iterators/generators, type hints, dataclasses, advanced exceptions, stdlib essentials, testing)
3. Cover **expert topics** at expert (metaclasses/macros, descriptors/equivalents, async, concurrency model, advanced typing, performance/profiling, memory model, pattern matching, advanced decorators, packaging, C interop)

**Step-by-step:**

```bash
# 1. Start from bootstrap output (or empty file)
cat data/cheatsheet_packs/languages/<lang>/<skill>.yaml

# 2. Edit. Aim for 10-12 entries with rich tags and 2-3 examples each.
$EDITOR data/cheatsheet_packs/languages/<lang>/<skill>.yaml

# 3. Validate Pydantic + tree-sitter
docker exec -w /app -e PYTHONPATH=/app devforge-api \
  python scripts/validate_cheatsheet_packs.py data/cheatsheet_packs/

# 4. Live-test through the gateway (hot reload via L2 mtime cache — no restart needed)
curl -sS -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: $DEVFORGE_API_KEY" \
  -d '{"name":"generate_cheatsheet","arguments":{
    "language":"<lang>",
    "skill_level":"<skill>",
    "intent":"<topic that should match one of your new entries>"
  }}' | jq '{quality, num_entries: (.data.ranked_entries|length), entries: [.data.ranked_entries[]|.id]}'

# 5. Iterate until tags + when_to_use match the intent phrasings users will type
```

---

## 5. Quality bar — anatomy of a v2 entry

This is `py.intermediate.dataclasses` from the deepened Python pack — use as a template.

```yaml
- id: py.intermediate.dataclasses                       # ← namespaced: <lang>.<skill>.<topic>
  title: "Dataclasses"                                  # ← user-facing header
  explanation: "Auto-generated __init__, __repr__,      # ← 1-3 sentences. Used for LLM ranking context.
    __eq__ from class field declarations. Less
    boilerplate than plain classes for data-holding
    types. Use `frozen=True` for immutability,
    `slots=True` for memory."
  tags: [dataclass, dataclasses, frozen, slots, repr,   # ← 5-9 lowercase hyphenated tags.
    intermediate]                                       #   The personalizer scores tag-overlap with intent.
  when_to_use: "Plain data containers — request/        # ← Repeat intent keywords here.
    response models, value objects, DTOs. Skip if
    you need complex __init__ logic."
  examples:
    - title: "Basic dataclass"                          # ← 2-3 examples per entry, each
      language: python                                  #   showing a different idiom.
      code: |
        from dataclasses import dataclass

        @dataclass
        class User:
            name: str
            age: int
            email: str = ""

        u = User("Alice", 25)
    - title: "Frozen + slots + default factory"
      language: python
      code: |
        from dataclasses import dataclass, field

        @dataclass(frozen=True, slots=True)
        class Point:
            x: float
            y: float
            metadata: dict = field(default_factory=dict)
    - title: "Custom __post_init__"
      language: python
      code: |
        from dataclasses import dataclass

        @dataclass
        class Range:
            low: int
            high: int

            def __post_init__(self):
                if self.low > self.high:
                    raise ValueError(f"low {self.low} > high {self.high}")
  pitfalls:                                             # ← 4-5 substantive pitfalls.
    - "Mutable defaults — `tags: list = []` won't       #   These are the highest-value content per token.
      work, you need `field(default_factory=list)`."
    - "`frozen=True` makes assignment raise
      FrozenInstanceError. Need mutation? Use a
      regular class or copy.replace()."
    - "`slots=True` saves memory but breaks dynamic
      attribute assignment and multiple inheritance."
    - "Dataclass `__eq__` compares all fields by
      default. Use `field(compare=False)` to exclude
      a field from equality."
```

---

## 6. Validation tooling

### `scripts/validate_cheatsheet_packs.py`

Run this **before every commit** that touches `data/cheatsheet_packs/`.

```bash
docker exec -w /app -e PYTHONPATH=/app devforge-api \
  python scripts/validate_cheatsheet_packs.py data/cheatsheet_packs/
```

It enforces:
1. **YAML parses** + matches the `Pack` Pydantic schema (typos, wrong types, missing required fields)
2. **Every example's `code` parses cleanly** via tree-sitter for the declared language
3. **Entry `id` is globally unique** across all packs

Known false-positives to ignore for now:
- *`no tree-sitter grammar mapped for language 'Python'`* — bootstrap LLM occasionally emits capitalized language tags. Fix by lowercasing the `language:` field on the affected examples.
- *`duplicate entry id ...`* — bootstrap LLM reuses common ids like `error-handling` across packs. Strictly speaking this is global-validator over-strictness; in practice the runtime only loads one language pack + a few library packs per request, so cross-language collisions don't matter. To stay strict, use the namespacing convention (`<lang>.<skill>.<topic>`).

### Local Python-only validator (the one we used for the v2 deepening)

```bash
docker exec -w /app -e PYTHONPATH=/app devforge-api python -c "
from pathlib import Path
import yaml
from src.agents.cheatsheet.pack_models import Pack
from tree_sitter_languages import get_parser

parser = get_parser('python')
def has_err(node):
    if node.has_error or node.is_missing: return True
    return any(has_err(c) for c in node.children)

errs, ok = [], 0
for path in sorted(Path('data/cheatsheet_packs/languages/python').glob('*.yaml')):
    pack = Pack(**yaml.safe_load(path.read_text()))
    for entry in pack.entries:
        for ex in entry.examples:
            tree = parser.parse(ex.code.encode('utf-8'))
            if has_err(tree.root_node):
                errs.append(f'{path.name}::{entry.id}::{ex.title}')
            else:
                ok += 1
print(f'OK examples: {ok}, errors: {len(errs)}')
for e in errs: print(f'  - {e}')
"
```

Use this scoped variant when iterating on one language — much faster than scanning all 69 packs.

### Live-test through the gateway

The L2 pack cache is keyed by file mtime, so saved edits are picked up on the **next request** without restart. Iteration loop:

```bash
# Edit YAML → save → fire test request → inspect result → repeat
curl -sS -X POST http://localhost:8001/api/gateway \
  -H "x-api-key: $DEVFORGE_API_KEY" -H "Content-Type: application/json" \
  -d '{"name":"generate_cheatsheet","arguments":{"language":"<lang>","skill_level":"<skill>","intent":"<test phrasing>"}}' \
  | jq '{quality, entries: [.data.ranked_entries[]|.id]}'
```

If your new entry doesn't appear in `entries[]` for an obvious intent match, the tags need work. Add more synonyms to `tags`.

---

## 7. Known footguns

### 7a. The `library: serde` footgun (the rust/expert bug)

**Bug:** the LLM bootstrap once emitted `library: serde` on `languages/rust/expert.yaml` (a *language* pack). The personalizer pre-filter did this:

```python
is_library_pack = pack.pack.library is not None   # ← TRUE because of the bad field
if is_library_pack:
    lib = pack.pack.library or ""                  # ← "serde"
    if lib not in detected_libraries and lib.lower() not in intent_lower:
        continue                                   # ← ALL entries dropped
```

→ 0 candidates → `quality: curated_unpersonalized` with empty markdown.

**Fix when authoring:** on every `languages/<lang>/<skill>.yaml`, explicitly write:

```yaml
pack:
  language: rust
  skill_level: expert
  version: 2
  library: null                # ← REQUIRED on language packs
  library_version_floor: null  # ← REQUIRED on language packs
  last_reviewed: 2026-05-15
  reviewer: you
```

Future-proofing recommendation: tighten `PackMeta` in `pack_models.py` to reject `library != None` when the pack file path is under `languages/`. ~5-line change.

### 7b. YAML integer-as-tag

```yaml
tags: [pattern-matching, match, case, 310, advanced]   # ← WRONG
                                       # ^^^ YAML reads as int 310, Pydantic rejects
```

Quote any tag that looks like a number:

```yaml
tags: [pattern-matching, match, case, "py310", advanced]   # ← right
```

Same for tags like `true`, `false`, `yes`, `no`, `null` — quote them or they get parsed as bool/null.

### 7c. Tree-sitter parse failures

Common causes when hand-writing code:
- **Unclosed string** — `code: "print(\"hi)"` — the closing `"` is missing inside, makes the YAML still valid but tree-sitter fails
- **Indentation** — mixing tabs and spaces inside the code block. Always use spaces (4) consistently
- **f-string with unmatched braces** — `f"{x + 1"`
- **Trailing colon missing** — `def foo()` instead of `def foo():`

Always use YAML block scalar `code: |` and indent the code 2 spaces beyond the `code:` key.

### 7d. Capitalized language tag

```yaml
examples:
  - title: "demo"
    language: Python     # ← BAD — validator can't find grammar
```

```yaml
examples:
  - title: "demo"
    language: python     # ← right (lowercase)
```

The validator maps lowercase only. Bootstrap output sometimes ships with `Python` — sed-fix or hand-fix before commit.

### 7e. Duplicate ids across packs

Bootstrap output often reuses simple ids (`error-handling`, `async-await`) across packs. The validator flags these as duplicates. **Use the namespaced convention** to avoid:

```yaml
- id: py.expert.async_await           # ← good
- id: py.expert.metaclasses           # ← good
- id: rust.expert.lifetimes_borrowing # ← good
```

Pattern: `<short-lang|lib>.<skill>.<snake_case_topic>` — never collides because the prefix is unique per pack.

### 7f. Bootstrap data drift

The bootstrap LLM occasionally produces low-quality output:
- One-example entries with trivial code
- 2-tag entries that won't match anything but the exact title
- Hand-wavy pitfalls ("don't make mistakes")

**Don't ship bootstrap output unmodified to production.** Use it as scaffolding, then deepen.

---

## 8. Personalizer interaction — what makes an entry rank

The personalizer pre-filter (`personalizer.py:_build_candidates`) scores each entry like this:

```python
score = (3 if is_library_pack else 1) + tag_overlap
```

Where `tag_overlap` is the number of entry tags whose lowercase string appears in the user's lowercase intent.

So:
- **Library packs auto-rank higher** (+3 floor) when the library is detected from code or named in intent
- **Each matched tag adds +1**. An entry with 8 tags has 8× the surface area for matching as an entry with 1 tag.
- The top **20 entries** survive pre-filter and go to the LLM. The LLM picks up to 7.

**Optimization for authors:**
- Add synonyms and adjacent terms to tags. If your entry is about *generators*, also tag `lazy`, `streaming`, `yield`, `iter`.
- Repeat keywords in `when_to_use` (also free-text matched by the personalizer's LLM prompt)
- Use **intent phrasings users actually type**. `"debugging async deadlock"` should hit something tagged `async, deadlock, debug`.

---

## 9. Versioning

When you bump pack content significantly:

```yaml
pack:
  language: python
  skill_level: expert
  version: 2          # ← bumped from 1
  ...
```

The response includes `packs_used[].version` so clients can know what pack they got. Bump on:
- Adding/removing/renaming entries
- Major rewrite of explanations or pitfalls
- Restructuring tags in a way that affects ranking

Don't bump for typo fixes or single-line changes.

---

## 10. End-to-end walk-through — adding a new pack

Suppose you want to add `libraries/redis/intermediate.yaml`.

```bash
# Step 0: add detector if redis is not already in LIBRARY_SIGNATURES
grep redis src/agents/cheatsheet/library_detector.py
# If not present, add a regex like r'\bimport\s+redis\b|\bredis\.Redis\(' first.

# Step 1: bootstrap to get a first draft
docker exec -w /app -e PYTHONPATH=/app devforge-api \
  python scripts/bootstrap_cheatsheet_packs.py \
  --library redis --skill intermediate

# Step 2: inspect the draft
cat data/cheatsheet_packs/libraries/redis/intermediate.yaml

# Step 3: deepen (target 10-12 entries, 2-3 examples each, 5-9 tags each)
$EDITOR data/cheatsheet_packs/libraries/redis/intermediate.yaml

# Step 4: validate
docker exec -w /app -e PYTHONPATH=/app devforge-api \
  python scripts/validate_cheatsheet_packs.py data/cheatsheet_packs/

# Step 5: live test (with a redis-shaped code_context to trigger lib detection)
curl -sS -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" -H "x-api-key: $DEVFORGE_API_KEY" \
  -d '{"name":"generate_cheatsheet","arguments":{
    "language":"python","skill_level":"intermediate",
    "code_context":"import redis\nr = redis.Redis()\nr.set(\"key\", \"value\")",
    "intent":"using redis pub/sub for events"
  }}' \
  | jq '{detected: .data.detected_libraries, packs_used: .data.packs_used, entries: [.data.ranked_entries[]|.id]}'

# Step 6: commit when satisfied
git add data/cheatsheet_packs/libraries/redis/intermediate.yaml \
        src/agents/cheatsheet/library_detector.py
git commit -m "feat(cheatsheet): add redis intermediate pack"
```

---

## 11. Reference: existing v2 example to copy from

The deepened Python triplet is the canonical reference:

- `data/cheatsheet_packs/languages/python/beginner.yaml` — 10 entries, 30 examples
- `data/cheatsheet_packs/languages/python/intermediate.yaml` — 12 entries, 36 examples
- `data/cheatsheet_packs/languages/python/expert.yaml` — 11 entries, 33 examples

99 tree-sitter-validated examples, 5-9 tags per entry, 4-5 pitfalls per entry. Use these as the template when deepening another language to v2 quality.

---

## 12. Checklist before committing a pack change

- [ ] `library: null` and `library_version_floor: null` set explicitly on language packs
- [ ] All `examples[].language` values are lowercase (`python`, not `Python`)
- [ ] All numeric-looking tags are quoted (`"py310"`, `"3"`)
- [ ] All entry ids namespaced (`<short-lang|lib>.<skill>.<topic>`)
- [ ] `scripts/validate_cheatsheet_packs.py` passes (or only reports known cross-pack id collisions)
- [ ] Live test via gateway returns `quality: "curated"` with your new entry id appearing for an obvious intent
- [ ] `last_reviewed` updated to today
- [ ] `version` bumped if entries added/removed/renamed
- [ ] No commit of the API key — `$DEVFORGE_API_KEY` env var, not literal
