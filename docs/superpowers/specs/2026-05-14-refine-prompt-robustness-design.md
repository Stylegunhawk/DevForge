# refine_prompt v0.10 — Robustness Design

**Date:** 2026-05-14
**Author:** Sid (with Claude)
**Status:** Approved for implementation planning
**Target tool:** `refine_prompt` (DevForge backend, `src/agents/prompt_refiner/`)
**Caller surface:** MCP `tools/call` (`POST /mcp`) and REST gateway (`POST /api/gateway`)

---

## 1. Goal

Close the three robustness gaps surfaced by adversarial testing of v0.9, without
breaking any existing caller integration and without changing how the tool is
exposed at the MCP protocol level.

The three gaps:

1. **Polyglot blindness.** `DependencyAnalyzer.PACKAGE_MAP` only knows Python
   (requirements.txt) and JavaScript (package.json). Go / Rust / Java / Kotlin /
   Ruby / PHP / C# projects produce zero evidence — tool defaults to a Python
   answer regardless of the user's actual stack.
2. **Service / framework conflation.** Conversation evidence treats AWS,
   PostgreSQL, Redis and similar names as peers of FastAPI / React in
   `chosen_stack.frameworks`. Calling agents have no way to distinguish a web
   framework from a backing service.
3. **Hallucination on vague prompts.** A single-word prompt like `"refactor"`
   produces a confident multi-page production specification with no grounding.
   The tool currently has no way to signal "this output is low-confidence —
   please re-call with more context."

## 2. Caller model

The primary caller is an LLM acting as an MCP client (Claude in an IDE, GPT-4
behind an agent framework, a custom orchestrator). The tool is invoked
programmatically, not by a human typing in a UI. This shapes every design
decision:

- **Never block on solvable problems.** Returning a hard error wastes a turn.
  Prefer returning a refined prompt plus structured quality signals.
- **Emit machine-parseable hints, not human prose.** A field named
  `suggested_inputs: ["project_files", "attached_files"]` is more useful to an
  agent than an English sentence saying "consider adding files".
- **Schema-time hints prevent runtime gaps.** The `inputSchema` description for
  each parameter is the agent's first opportunity to learn when to include the
  field. Improving descriptions reduces the number of calls that need
  follow-up enrichment.

## 3. Constraints

- **No new dependencies.** All new parsers use Python stdlib (`tomllib`,
  `xml.etree.ElementTree`, `json`, `re`). `tomllib` is built-in from Python
  3.11; the project pins 3.12.
- **No MCP protocol changes.** No new JSON-RPC methods, no change to the
  `content[]` shape on `tools/call` responses, no per-tool version field.
- **No cross-tool changes.** All router edits are scoped to the
  `refine_prompt` branches of `TOOL_DESCRIPTIONS` and `_get_tool_schema()`.
  `generate_data`, `github_operation`, `generate_cheatsheet` are untouched.
- **Backward compatibility.** Every key currently present in
  `data.chosen_stack` continues to be present and to mean the same thing.
  Existing callers that read `chosen_stack.frameworks` keep working without
  any change.
- **Free-LLM latency budget.** The underlying LLM call still dominates total
  time (typical 5–16s for `code` domain). No changes that increase LLM round
  trips. Caching and streaming are deferred to v0.11.

## 4. Out of scope (deferred)

| Item | Reason | Target |
|------|--------|--------|
| Refined-prompt caching by `(prompt, domain, evidence-hash)` | Adds Redis dependency; latency optimization is its own design | v0.11 |
| Streaming refined-prompt content over MCP | Hand-rolled MCP endpoint does not implement notifications; cross-tool risk | v0.11 |
| Splitting `tools/call` `content[]` into multiple typed items | Touches `mcp_endpoint` (line 1264 of `routers/__init__.py`) — affects all four tools | v0.11 |
| Per-tool `_tool_version` in response | Over-engineered for current scale; `serverInfo.version` bump suffices | — |
| Pluggable parser plugin interface | Registry pattern in v0.10 is enough; plugin interface adds maintenance cost without near-term payoff | v0.12 |
| Multi-language strict template | Current logic picks one primary language; full polyglot specs from one call is a separate UX problem | — |

## 5. Schema changes

All changes are **additive**. Every existing key in the response is preserved.

### 5.1 `data.chosen_stack`

```jsonc
{
  "data": {
    "chosen_stack": {
      // NEW: typed lists, each sorted alphabetically, each may be empty
      "languages": ["python"],
      "frameworks": ["FastAPI"],         // KEPT — see 5.1.1
      "libraries":  ["SQLAlchemy"],
      "services":   ["Redis"],
      "databases":  ["PostgreSQL"],

      // KEPT — unchanged shape
      "language":   "python",
      "source":     "dependency_analysis",
      "confidence": 0.85,
      "evidence":   [...]
    }
  }
}
```

#### 5.1.1 Denormalization rule for `frameworks`

`frameworks` is retained but is now a denormalized view:

```
frameworks == sorted({ e.match for e in evidence if e.category == "framework" })
```

A caller still doing `chosen_stack.frameworks` sees the same web-framework
list it always saw — just without services like AWS/Redis polluting it.
Services move to `chosen_stack.services`, databases to
`chosen_stack.databases`.

### 5.2 `data.chosen_stack.evidence[*].category`

Each `Evidence` item gains one new field:

```jsonc
{
  "source": "dependency_analysis",
  "match": "FastAPI",
  "weight": 0.9,
  "file": "requirements.txt",
  "line": 1,
  "excerpt": "fastapi==0.110.0",
  "confidence_hint": "strong",
  "category": "framework"          // NEW: one of language|framework|library|service|database
}
```

### 5.3 `data.quality` (new sibling block)

```jsonc
{
  "data": {
    "quality": {
      "prompt_grounding": "low",                       // low | medium | high
      "missing_signals":  ["language", "framework"],   // subset of: language, framework, database, specificity
      "suggested_inputs": ["project_files",            // subset of: project_files, attached_files, conversation_history, file_context
                           "attached_files"]
    }
  }
}
```

The block is deterministic — no LLM call, no random component. Same inputs
produce the same `quality`.

### 5.4 What does NOT change

- The top-level envelope: `{success, tool, data, execution_time, error}`
- `data.refined_prompt`, `data.context_summary`, `data.sanitization_log`,
  `data.domain` — unchanged
- The shape of `Evidence` items beyond the added `category` field
- The `inputSchema` parameter set (no new parameters, only better descriptions)
- The MCP `content[]` array shape (still single `text` item)
- `isError` semantics

## 6. Component changes

### 6.1 `src/agents/prompt_refiner/context_types.py`

`ChosenStack` gains four new fields, all defaulting to empty list:

```python
@dataclass
class ChosenStack:
    language: str = "unknown"
    frameworks: List[str] = field(default_factory=list)
    database: str = "unknown"
    source: str = "none"
    confidence: float = 0.0
    evidence: List[Evidence] = field(default_factory=list)

    # NEW
    languages: List[str] = field(default_factory=list)
    libraries: List[str] = field(default_factory=list)
    services:  List[str] = field(default_factory=list)
    databases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language":   self.language,
            "frameworks": self.frameworks,
            "database":   self.database,
            "source":     self.source,
            "confidence": round(self.confidence, 2),
            "languages":  self.languages,    # NEW
            "libraries":  self.libraries,    # NEW
            "services":   self.services,     # NEW
            "databases":  self.databases,    # NEW
            "evidence":   [...]              # unchanged shape, each item gains `category`
        }
```

`Evidence` gains a `category` field (default `"framework"` for backward
compatibility with hand-constructed Evidence instances in tests):

```python
@dataclass
class Evidence:
    source: str
    match: str
    weight: float
    file: Optional[str] = None
    line: Optional[int] = None
    excerpt: Optional[str] = None
    confidence_hint: Optional[str] = None
    category: str = "framework"   # NEW: language|framework|library|service|database
```

### 6.2 `src/agents/prompt_refiner/dependency_analyzer.py`

#### 6.2.1 PACKAGE_MAP gains `category`

Every entry in `PACKAGE_MAP` gains a `category` key. Existing entries
keep their `name` and `weight`. New categorization:

| Package | category |
|---------|----------|
| fastapi, flask, django, react, vue, next, express | framework |
| sqlalchemy, pandas, pytest | library |
| typescript | language |

(Services and databases are not present in the current `PACKAGE_MAP` — they
come from conversation evidence and from the new parsers below.)

#### 6.2.2 Parser registry

A new internal `PARSERS` dict mapping filename pattern → parser function:

```python
PARSERS: Dict[str, Callable[[str, str], List[Evidence]]] = {
    "requirements.txt": _parse_requirements,    # existing
    "package.json":     _parse_package_json,    # existing
    "go.mod":           _parse_go_mod,          # NEW
    "Cargo.toml":       _parse_cargo_toml,      # NEW
    "pom.xml":          _parse_pom_xml,         # NEW
    "build.gradle":     _parse_gradle,          # NEW (also matches build.gradle.kts)
    "Gemfile":          _parse_gemfile,         # NEW
    "composer.json":    _parse_composer_json,   # NEW
}
```

C# `*.csproj` files match by suffix (`endswith(".csproj")`), handled in the
dispatch loop, not the dict.

`analyze(files)` is refactored to look up the parser by filename suffix
match. Unknown filenames are silently ignored (current behavior).

#### 6.2.3 New parsers — implementation notes

Each parser is ~30 LOC, defensive against malformed input, and returns
`List[Evidence]` with `category` set per the PACKAGE_MAP entry.

- **`_parse_go_mod`** — regex match for lines like
  `\s+(github\.com/\S+|golang\.org/x/\S+)\s+v\d+`. Lookup each module path
  in PACKAGE_MAP (which gains entries for gin, echo, fiber, cobra, gorm).
- **`_parse_cargo_toml`** — use `tomllib.loads()`. Extract keys under
  `[dependencies]` and `[dev-dependencies]`. New entries: actix-web, axum,
  rocket, tokio, clap, serde, diesel.
- **`_parse_pom_xml`** — `xml.etree.ElementTree.fromstring()`. Iterate
  `dependency/artifactId` elements. New entries: spring-boot, spring-core,
  hibernate-core, junit-jupiter.
- **`_parse_gradle`** — regex over lines like
  `(implementation|api|testImplementation)\s+['"](\S+):(\S+):(\S+)['"]`.
  Same package map as pom.xml. Single function handles both `.gradle` and
  `.gradle.kts`.
- **`_parse_gemfile`** — regex over `gem\s+['"](\S+)['"]`. New entries:
  rails, sinatra, rspec, sidekiq.
- **`_parse_composer_json`** — `json.loads()`. Iterate keys under
  `require` and `require-dev`. New entries: laravel/framework,
  symfony/symfony, phpunit/phpunit.
- **`_parse_csproj`** — `xml.etree.ElementTree.fromstring()`. Iterate
  `PackageReference[@Include]`. New entries: Microsoft.AspNetCore.App,
  Microsoft.EntityFrameworkCore, xunit, NUnit.

All parsers populate `Evidence.category` from the matched PACKAGE_MAP entry.
Unknown packages within a recognized file are skipped (not surfaced as
unknown frameworks).

#### 6.2.4 PACKAGE_MAP additions

Top frameworks/libraries per ecosystem (categorized). Approximate counts:

| Ecosystem | Frameworks | Libraries | Languages |
|-----------|-----------|-----------|-----------|
| Go | gin, echo, fiber, cobra | gorm | go (implied) |
| Rust | actix-web, axum, rocket | tokio, clap, serde, diesel | rust |
| Java | spring-boot, spring-core | hibernate-core, junit | java |
| Kotlin | ktor | (shares spring/junit) | kotlin |
| Ruby | rails, sinatra | rspec, sidekiq | ruby |
| PHP | laravel, symfony | phpunit | php |
| C# | aspnetcore | entityframework, xunit, nunit | csharp |

Roughly 30 new PACKAGE_MAP entries total.

### 6.3 `src/agents/prompt_refiner/enhancer.py`

#### 6.3.1 Category-aware `_build_chosen_stack`

After existing evidence aggregation, route each framework name into the
right list based on `Evidence.category`:

```python
languages = sorted({e.match for e in all_evidence if e.category == "language"})
frameworks = sorted({e.match for e in all_evidence if e.category == "framework"})
libraries  = sorted({e.match for e in all_evidence if e.category == "library"})
services   = sorted({e.match for e in all_evidence if e.category == "service"})
databases  = sorted({e.match for e in all_evidence if e.category == "database"})
```

Existing `frameworks` field becomes this filtered set — services no longer
appear in it.

#### 6.3.2 Conversation evidence categorization

`_extract_conversation_evidence` currently creates Evidence with no
category. Update so AWS, GCP, Docker, Kubernetes → `service`; PostgreSQL,
MySQL, MongoDB, Redis, SQLite → `database`; everything else in the existing
`TECH_KEYWORDS` map keeps `framework`.

Concretely: add a `CONVERSATION_CATEGORY_MAP` in `conversation_parser.py`
keyed by the same tech name, returning the category. The enhancer reads it
when constructing Evidence items.

#### 6.3.3 Quality block

New pure function `_compute_quality(prompt, code_context, chosen_stack) -> dict`:

```python
def _compute_quality(prompt: str, code_context, chosen_stack) -> dict:
    tokens = len(prompt.split())

    # Grounding tier
    if tokens >= 8 and chosen_stack.confidence >= 0.7:
        grounding = "high"
    elif tokens >= 5 or chosen_stack.confidence >= 0.4:
        grounding = "medium"
    else:
        grounding = "low"

    # Missing signals
    missing = []
    if not chosen_stack.languages:  missing.append("language")
    if not chosen_stack.frameworks: missing.append("framework")
    if not chosen_stack.databases:  missing.append("database")
    if tokens < 5:                  missing.append("specificity")

    # Suggested inputs
    suggested = []
    if "framework" in missing or "language" in missing:
        suggested.append("project_files")
    if not code_context or not code_context.code_structure.imports:
        suggested.append("attached_files")
    if grounding == "low":
        suggested.append("conversation_history")

    return {
        "prompt_grounding": grounding,
        "missing_signals":  missing,
        "suggested_inputs": sorted(set(suggested)),
    }
```

Called once at the end of `enhance()`. Result is merged into the return
dict under key `quality`.

### 6.4 `src/agents/prompt_refiner/templates.py`

Add a new template `CODE_TEMPLATE_LOW_GROUNDING`:

```python
CODE_TEMPLATE_LOW_GROUNDING = """You are a senior software architect.

ORIGINAL REQUEST: {prompt}

CONTEXT: The user did not provide enough information to determine their tech
stack. Do NOT commit to an arbitrary stack. Instead, your refined prompt must:

1. Identify the 2-3 most important missing pieces of context (e.g., target
   language, web framework, deployment environment, database).
2. Phrase those as clarifying questions to the user.
3. Provide a short, generic outline of next steps that does not assume a stack.

Output ONLY the refined prompt (which should consist primarily of those
clarifying questions).
"""
```

Template selection in `enhance()`:

```python
template_key = domain
if domain == "code":
    if chosen_stack.confidence >= 0.6:
        template_key = "code_context"          # strict
    elif quality["prompt_grounding"] == "low":
        template_key = "code_low_grounding"    # NEW
    # else: falls through to standard "code" template
```

### 6.5 `src/agents/prompt_refiner/agent.py`

In `refine()`, after `enhancement_result` is obtained, copy `quality` into
the result dict. In `refine_prompt_invoke()`, propagate it into the
returned `data` block. Empty-prompt validation (added in this session)
stays unchanged — empty prompts remain a hard `success: false` failure with
a clear error message; that is the right MCP behavior for a client bug.

### 6.6 `src/api/routers/__init__.py`

Two surgical edits — both scoped to the `refine_prompt` entries only.

#### 6.6.1 `TOOL_DESCRIPTIONS["refine_prompt"]`

Replace lines 86-90 with a description that teaches the iterative pattern:

```python
"refine_prompt": (
    "Refines a user prompt into a detailed, production-ready specification, "
    "with optional tech-stack grounding from project files, conversation "
    "history, or attached code. "

    "ITERATIVE USE (recommended for agents): Call once with the user's raw "
    "prompt. The response's `quality.prompt_grounding` field returns 'low', "
    "'medium', or 'high'. If 'low' or 'medium', re-call with the inputs "
    "named in `quality.suggested_inputs` (e.g. project_files, "
    "attached_files, conversation_history). Each enrichment cycle improves "
    "the refined prompt's grounding. "

    "OUTPUT: data.refined_prompt is the refined prompt text. "
    "data.chosen_stack splits detected tech into languages, frameworks, "
    "libraries, services, and databases — use these typed lists, not the "
    "legacy denormalized `frameworks` field. "
    "data.sanitization_log lists redacted secrets and blocked prompt "
    "injection attempts (metadata only — actual secrets are never logged). "

    "DOMAINS: code, image, rag, llm, general (default)."
),
```

#### 6.6.2 `_get_tool_schema()["refine_prompt"]`

Update each parameter's `description` to be agent-instructive. The
parameter set is unchanged; only descriptions change. Examples:

```python
"prompt": {
    "type": "string",
    "description": (
        "The user's original prompt to refine. Required, non-empty. "
        "Pass the raw prompt verbatim — do not pre-summarize."
    ),
},
"project_files": {
    "type": "object",
    "description": (
        "Dependency manifest files keyed by filename. Strongly recommended "
        "for the 'code' domain — without these the response's "
        "quality.prompt_grounding will be 'low' and the refined prompt "
        "will ask clarifying questions instead of producing a specification. "
        "Supported filenames: requirements.txt, package.json, go.mod, "
        "Cargo.toml, pom.xml, build.gradle, build.gradle.kts, Gemfile, "
        "composer.json, *.csproj. Pass the file content as a string value."
    ),
    "additionalProperties": {"type": "string"},
},
"attached_files": {
    "type": "array",
    "items": {"type": "string"},
    "description": (
        "Source code file contents (as strings, one per array element). "
        "Used to detect imported frameworks and existing class/function "
        "names that the refined prompt should integrate with. Pair with "
        "project_files when both are available."
    ),
},
"conversation_history": {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "role": {"type": "string"},
            "content": {"type": "string"},
        },
    },
    "description": (
        "Recent chat messages providing context. Weak evidence by default "
        "(weight 0.4) — useful when project_files and attached_files are "
        "unavailable. Last 5 messages are considered."
    ),
},
"domain": {
    "type": "string",
    "enum": ["general", "image", "code", "rag", "llm"],
    "description": (
        "Refinement domain. 'code' triggers tech-stack detection and "
        "evidence-based templates. 'image' produces Midjourney/SD-style "
        "prompts. 'rag' produces vector-search-friendly queries. 'llm' "
        "and 'general' produce general-purpose refined prompts. Default: "
        "general."
    ),
},
"skill_level": {
    "type": "string",
    "enum": ["beginner", "intermediate", "expert"],
    "description": (
        "Adjusts depth and assumed prior knowledge in the refined prompt. "
        "Default: intermediate."
    ),
},
"file_context": {
    "type": "string",
    "description": (
        "Free-form text context. Prefer attached_files (array of code) "
        "and project_files (manifests) for stronger evidence. Sanitized "
        "before use."
    ),
},
```

#### 6.6.3 `serverInfo.version`

Bump line 988 from `"0.8.0"` to `"0.9.0"`. This is the only multi-tool
change in the router, and it is a one-line metadata edit — no behavioral
impact. MCP clients running `initialize` can detect the bump.

### 6.7 `manifests/devforge.json` (legacy sync)

Update the `refine_prompt` entry's description to match
`TOOL_DESCRIPTIONS["refine_prompt"]` from §6.6.1. Update the input schema
descriptions to match §6.6.2. Bump the manifest's version field if present.

This file is consumed by LobeHub-style plugin discovery, not by the MCP
endpoint. Keeping it in sync is convention; the in-code dict is authoritative.

### 6.8 `docs/tools/refine_prompt.md`

- Bump `Version: 0.10.0`
- Document the typed lists in `chosen_stack` and the denormalization rule
- Document the `quality` block with examples per grounding tier
- Document the new manifest filenames supported
- Add an "Agent integration pattern" section showing the iterative
  enrichment loop in pseudocode
- Keep the existing Performance / free-LLM section unchanged

## 7. Quality block — worked examples

| Input | tokens | confidence | languages | frameworks | databases | → grounding | missing_signals | suggested_inputs |
|-------|--------|-----------|-----------|-----------|-----------|------------|----------------|-----------------|
| `"refactor"` | 1 | 0.0 | [] | [] | [] | `low` | `[language, framework, database, specificity]` | `[project_files, attached_files, conversation_history]` |
| `"fix the login bug"` | 4 | 0.0 | [] | [] | [] | `low` | `[language, framework, database, specificity]` | `[project_files, attached_files, conversation_history]` |
| `"add OAuth2 with PKCE"` (no context) | 4 | 0.0 | [] | [] | [] | `low` | `[language, framework, database, specificity]` | `[project_files, attached_files, conversation_history]` |
| `"add OAuth2 with PKCE"` + requirements.txt(fastapi) | 4 | 0.9 | [] | [FastAPI] | [] | `medium` | `[language, database]` | `[project_files]` |
| `"add OAuth2 with PKCE for our FastAPI service"` + full project_files | 8 | 0.9 | [python] | [FastAPI] | [PostgreSQL] | `high` | `[]` | `[]` |

## 8. Anti-hallucination guard — interaction model

When the calling agent sends `"refactor"` with `domain: "code"`:

1. Tool sees `tokens=1`, `confidence=0.0`, `grounding="low"`.
2. Template selection picks `code_low_grounding` (not the strict `code_context`,
   not the generic `code`).
3. The LLM is instructed to produce clarifying questions, not a stack-bound
   specification.
4. Response includes `quality.suggested_inputs: [project_files,
   attached_files, conversation_history]`.
5. Calling agent reads `quality`, decides whether to surface questions to the
   human or to fetch the user's project files itself, then re-calls with
   enrichment.

This eliminates the v0.9 failure mode where `"refactor"` produced a confident
FastAPI refactoring plan with no basis.

## 9. Backward compatibility matrix

| Caller behavior | v0.9 | v0.10 |
|-----------------|------|-------|
| Reads `data.chosen_stack.frameworks` | List of all detected names | List of frameworks only (services moved) — **caller may see a shorter list when conversation mentions AWS/Redis/etc.** |
| Reads `data.chosen_stack.confidence` | Works | Works (unchanged formula) |
| Reads `data.refined_prompt` | Works | Works |
| Reads `data.sanitization_log` | Works | Works |
| Reads `data.chosen_stack.evidence[i].weight` | Works | Works |
| Reads `data.chosen_stack.evidence[i].category` | Not present | Present |
| Reads `data.quality` | Not present | Present |
| Reads `data.chosen_stack.{languages,libraries,services,databases}` | Not present | Present |

The only observable difference for an unaware caller is that
`chosen_stack.frameworks` no longer contains services like AWS/Redis/PostgreSQL.
That is the intended fix for Gap 2 — services were never frameworks. Callers
that need both can read `chosen_stack.services` in addition.

## 10. Testing

### 10.1 New unit tests

- `tests/test_dependency_analyzer.py` (new file) — one test per parser, each
  using a representative real-world manifest snippet. Asserts on Evidence
  count, match names, and category routing.
- `tests/test_quality_block.py` (new file) — boundary cases for the
  `_compute_quality` function:
  - empty signals → `low`, all four missing_signals, three suggested_inputs
  - tokens=5, confidence=0.0 → `medium`
  - tokens=8, confidence=0.7 → `high`, no missing_signals, no suggested
  - tokens=1, confidence=0.9 → `medium` (token gate fails, confidence rescues)
- `tests/test_prompt_refiner_phase2.py` — extend existing file with:
  - Category routing test: AWS via conversation lands in `services`, not
    `frameworks`
  - Polyglot test: Cargo.toml + go.mod produce evidence with correct
    categories and the right `language` selection
  - Low-grounding template test: `"refactor"` with `domain="code"` selects
    `code_low_grounding` template

### 10.2 Regression tests

- Re-run the 10 MCP calls from the v0.10 design session. All must succeed.
- Assert every existing key in the response is still present.
- Assert `chosen_stack.frameworks` only contains framework-category
  matches.
- Verify Postgres URL redaction still works.
- Verify injection blocking still works (full pattern set).
- Verify empty prompt still returns `success: false`.

### 10.3 Pre-existing test failures

The three MagicMock-related failures (`test_refine_general_prompt`,
`test_gateway_invoke_wrapper`,
`test_formatted_prompt_contains_evidence_block`) predate v0.10. Fix as part
of this release by mocking `model_router.invoke_with_usage` correctly —
they currently mock `select_model_by_task` and `get_chat_model` but not
`invoke_with_usage`, which is the actual method called from
`enhancer.py` (the `await model_router.invoke_with_usage(...)` call inside
`enhance()`). One-line fix per test — replace the MagicMock with an
AsyncMock that returns an object with a `content` attribute.

## 11. Versioning

- Internal tool version: `0.9.0 → 0.10.0`. Reflected in
  `docs/tools/refine_prompt.md` header.
- Server MCP version: `serverInfo.version: "0.8.0" → "0.9.0"` in
  `routers/__init__.py:988`. Reflects the bundle of changes shipping in
  this release.
- Manifest version field bumped in lockstep.
- No per-tool version field in the response payload.

## 12. Acceptance criteria

A v0.10 build is shippable when all of the following hold:

1. All seven new parsers produce Evidence with correct `category` from a
   sample manifest snippet.
2. AWS / PostgreSQL / Redis mentioned in `conversation_history` land in
   `chosen_stack.services` or `.databases`, not `.frameworks`.
3. `chosen_stack.frameworks` for the OAuth2 multi-context test from this
   session shows only `["FastAPI", "Next.js", "React"]` — not `["AWS",
   "FastAPI", "Next.js", "PostgreSQL", "React", "Redis", "SQLAlchemy",
   "TypeScript"]`.
4. `refine_prompt("refactor", domain="code")` returns
   `quality.prompt_grounding: "low"` and a refined prompt consisting of
   clarifying questions, not a stack-bound specification.
5. `refine_prompt("build a CLI", project_files={"go.mod": "..."})`
   produces a Go answer with `languages: ["go"]` and at least one
   framework from PACKAGE_MAP (cobra/gin/echo).
6. Every existing key in v0.9 response is still present and means the
   same thing.
7. Existing 35 prompt_refiner tests still pass.
8. The three pre-existing MagicMock failures now pass.
9. MCP `tools/list` returns the new `TOOL_DESCRIPTIONS` and updated
   `inputSchema` descriptions.
10. MCP `initialize` returns `serverInfo.version: "0.9.0"`.
11. `docs/tools/refine_prompt.md` documents every new field with at least
    one worked example.

## 13. Risks and mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Caller relies on AWS/Redis being in `frameworks` | Low | Documented in changelog; services available in new `services` list |
| New parser crashes on malformed manifest | Medium | All parsers wrap in try/except, return empty list on failure (matches current `_parse_package_json` behavior) |
| `tomllib` import fails on Python < 3.11 | Low | Project pins 3.12; CI verifies |
| Quality heuristic too eager / too lax | Medium | Thresholds (5/8 tokens, 0.4/0.7 confidence) are explicit constants — easy to tune in follow-up if production data shows skew |
| Low-grounding template produces unhelpful clarifying questions | Medium | Template is plain English; iteration cost is one edit. Worked-example boundary cases in test_quality_block ensure path is exercised |
| Manifest description drifts from in-code TOOL_DESCRIPTIONS | Low | Comment in `routers/__init__.py:56` already calls this out; release checklist includes a `diff` step |

---

**End of design.**
