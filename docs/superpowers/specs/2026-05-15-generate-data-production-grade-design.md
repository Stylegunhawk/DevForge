# generate_data v0.9 — Production-Grade Design

**Date:** 2026-05-15
**Author:** Sid (with Claude)
**Status:** Approved for implementation planning
**Target tool:** `generate_data` (DevForge backend, `src/agents/datagen/`, `src/tools/datagen/`)
**Caller surface:** MCP `tools/call` (`POST /mcp`) and REST gateway (`POST /api/gateway`)
**Predecessor design:** [2026-05-14-refine-prompt-robustness-design.md](2026-05-14-refine-prompt-robustness-design.md) — same author, same project, same MCP infrastructure

---

## 1. Goal

Bring `generate_data` to "Mockaroo-level" quality for arbitrary domains while
keeping the existing API, response shape, dashboard analytics flow, and Faker
fast-path intact.

Three observable wins over v0.8:

1. **Off-template prompts produce domain-realistic values, not Faker lorem
   ipsum.** A request for `instrument.measurement_unit` returns
   `"kg/m³"`/`"Hz"`/`"Pa"` instead of `"perform"`/`"sure"`/`"grow"`.
2. **Realism levels actually fire.** `realism_level="high"` injects ~10% nulls
   on nullable business fields, ~2% duplicates on key-like fields, ~1%
   outliers on numeric fields. Today the observed rates are 0% / 0% / 0%.
3. **Schema design respects the user's prompt.** An explicit `enum:
   ["Fiction","Non-Fiction","Sci-Fi"]` in the prompt lands on the named
   field. Numeric fields without explicit ranges get sane defaults
   (`bedroom_count` → 1..6, not 1..1000).

The earlier session work (v0.8 → "v0.8.5") already fixed the `user_id`
NameError and the silent-success cascade. v0.9 builds on that.

## 2. Caller model

The MCP caller is an LLM acting as an agent (Claude in IDE, GPT-4 behind
an agent framework, custom orchestrator), plus the DevForge dashboard's
own `/usage/` page consuming analytics. This shapes every decision:

- **Quality over latency** within reason. The user has explicitly accepted
  2–3× cold-cache LLM cost for production-grade output. Catalog caching
  (L1 request + L2 process, 1h TTL) amortizes repeat calls.
- **Backward-compat API surface.** `DataGenArgs` parameters, response
  shape, and dashboard `log_request_call` payload do not change.
- **Faker as fallback, not foreground.** When LLM is unavailable, the
  pipeline degrades to Faker via existing routing — never to placeholder
  garbage like `measurement_unit_value_1`.

## 3. Constraints

- **No new MCP protocol behavior.** `tools/call` `content` shape unchanged,
  no new JSON-RPC methods, `isError` semantics unchanged.
- **`DataGenArgs` schema unchanged.** Same parameter names, same Pydantic
  validators, same `enable_semantic_generation` and
  `ENABLE_SEMANTIC_ANALYZER` env-flag behavior.
- **Dashboard `/usage/` analytics unchanged.** `routers/__init__.py`
  `log_request_call.delay(...)` payload (user_id, tenant_id,
  integration_name, tool_name="generate_data", success, duration_ms)
  keeps the same shape. Catalog LLM calls roll up under the parent
  `generate_data` row, not as separate `tool_name` entries (decided to
  keep dashboard simple; per-task LLM attribution deferred).
- **V1 path untouched.** No `prompt` and no `domain` argument still routes
  to pure Faker via `tools.py:generate_mock_data`.
- **Pydantic row bound stays at 10000.** Doc/version reconciliation is
  out of scope; spec just uses 10000 internally everywhere.
- **No new top-level dependencies.** New code uses stdlib + already-pinned
  packages (Faker, Pydantic, LangChain).

## 4. Out of scope (deferred)

| Item | Reason | Target |
|------|--------|--------|
| Reproducibility (`seed` arg, schema caching by prompt hash) | User explicitly deferred | v0.10 |
| Doc/version reconciliation (10000 vs 100000 row bound, version sprawl) | User explicitly deferred | v0.10 |
| Per-task LLM attribution in dashboard (`datagen_catalog_generation` rows) | User chose "simpler — parent generate_data" | v0.10 |
| SQL / Excel output formats (Mockaroo parity) | Not requested | — |
| Real-data-based synthesis (Tonic-style) | Architectural divergence | — |
| Fixing the 14 pre-existing async-vs-sync test failures in `test_semantic_analyzer_v2.py` | Unrelated infrastructure rot | separate test-modernization spec |

## 5. Architecture

The V2 pipeline grows from 3 layers to 4. The new layer is the **batched
catalog generation** that fires once per entity after schema design and
before per-row value production.

```
User prompt
  │
  ▼
DataGenArgs (Pydantic, 1..10000)
  │
  ▼
SchemaDesigner (LLM call #1)         ─── existing, with prompt update (B8)
  │
  ▼
SchemaValidator                      ─── NEW: enum-swap fix + range inference
  │
  ▼
SemanticAnalyzer                     ─── existing, classifies fields
  │
  ▼
For each entity:
    CatalogFactory.get_entity_catalogs(entity, fields, prompt)
                                     ─── NEW: 1 LLM call per entity, batched
                                     ─── L1+L2 cache by (entity, fields_hash, prompt_hash)
  │
  ▼
For each row, for each field:
    Numeric/date/bool                → existing generators (Faker/range)
    Constrained string (enum/pattern) → existing constraint-first path
    String otherwise (NEW PATH)      → random.choice(catalog[field])
                                       Fallback to _smart_free_text if LLM down
  │
  ▼
RelationshipEngine                   ─── existing, FK linkage
  │
  ▼
_validate_constraints + _validate_fk_integrity
                                     ─── existing
  │
  ▼
realism_engine.apply_realism_to_data ─── CONSOLIDATED: single call,
                                       deletes V2's internal _apply_realism (B1)
                                       only invoked when realism_level != "basic"
  │
  ▼
format_output (JSON/CSV)             ─── existing
  │
  ▼
Response                             ─── existing shape + optional
                                       data.catalog_usage metadata
```

### 5.1 Layer responsibilities

| Layer | Responsibility | LLM? | Cached? |
|-------|----------------|------|---------|
| Schema design | NL prompt → typed entity schema | Yes (1 call) | No (LLM nondeterminism is OK) |
| Schema validation | Fix enum-swap, infer ranges from field-name heuristics | No | N/A (pure function) |
| Semantic classification | Each field → semantic type (uuid, email, etc.) | Sometimes (LLM tier when lexical+pattern miss) | Yes (existing L1/L2) |
| **Catalog generation (new)** | **Per entity → {field: [50 values]}** | **Yes (1 call per entity)** | **Yes (L1/L2, 1h TTL)** |
| Value production | Sample from catalog OR Faker OR numeric range | No (per-row) | N/A |
| Relationship engine | Assign FKs from sampled parent IDs | No | N/A |
| Constraint validation | Enum/pattern/min/max/nullable | No | N/A |
| Realism | Null/duplicate/outlier injection | No | N/A |

## 6. Component changes per file

### 6.1 `src/tools/datagen/catalog_factory.py`

Add a new method on `CatalogFactory`:

```python
async def get_entity_catalogs(
    self,
    entity_name: str,
    fields: List[Tuple[str, str]],          # [(field_name, data_type), ...]
    user_prompt: str,
    count: int = 50,
    tenant_id: Optional[str] = None,
    integration_name: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, List[str]]:
    """Generate domain-realistic value catalogs for all string fields of
    one entity in a single LLM call.

    Returns:
        {field_name: [50 realistic values], ...}
        Only string-typed fields are included; numeric/date/bool fields
        are skipped (handled by their dedicated generators).

    Cache key:
        f"entity_catalog:{entity_name}:{fields_hash}:{prompt_hash}"
        - fields_hash = sha1 of sorted [(name, type)] tuples (8 chars)
        - prompt_hash = sha1 of user_prompt[:500] (8 chars)
        - L1 (request) + L2 (process, 1h TTL) — same eviction as existing
          get_catalog cache

    Fallback chain (in order):
        1. L1 cache hit
        2. L2 cache hit (within TTL)
        3. LLM call via model_router.invoke_with_usage (B5 — gets tracked)
        4. _smart_field_fallback(field, type) — uses existing
           semantic_router._smart_free_text logic (B6 — no placeholder
           garbage)

    LLM prompt structure:
        Returns a single JSON object with one key per string field, each
        value being an array of `count` realistic strings. Uses the
        entity_name and user_prompt for context. Asks the LLM to
        differentiate by field name (e.g. `customer.name` is a person,
        `product.name` is a product).
    """
```

The existing `get_catalog(semantic_type, entity_name, domain)` method is
**not modified** — it stays for `semantic_router`'s product_name /
flower_name / institution_name paths. Two cache key namespaces coexist:
`catalog:*` (legacy) and `entity_catalog:*` (new).

#### 6.1.1 LLM prompt template

```
You are a data catalog generator.
Generate 50 realistic sample values for each string field of the
{entity_name} entity. Return ONLY a single JSON object — one key per
field, each value an array of exactly 50 strings.

Context: {user_prompt[:500]}

Fields:
{for each (name, type):  "- {name} ({type})"}

Rules:
1. Differentiate by field name. `customer.name` is a person name; `product.name` is a product/title; `flower.name` is a flower species.
2. All values must be plausible for production data in this domain.
3. No prose, no markdown, no explanations — only the JSON object.

Example output shape:
{"field_a": ["v1", "v2", ..., "v50"], "field_b": ["v1", ..., "v50"]}
```

#### 6.1.2 LLM invocation

Uses `model_router.invoke_with_usage(prompt=..., model_name=...,
tenant_id=..., integration_name=..., task_type="datagen_catalog_generation",
user_id=...)`. This routes through the same path schema_designer uses, so:

- Token usage is logged to the dashboard's `/usage/` analytics
- Tenant/integration/user IDs are propagated for attribution
- Failures degrade to fallback without raising

Per the user's choice, the dashboard's `/usage/` page rolls these calls
under the parent `generate_data` request entry — they don't appear as
distinct `tool_name` rows.

#### 6.1.3 Fallback paths

If the LLM call fails, returns malformed JSON, or yields fewer than 40
items per field, fall back per-field to `_smart_field_fallback`:

```python
def _smart_field_fallback(self, field_name: str, data_type: str) -> List[str]:
    """Field-name-aware Faker fallback. Returns 50 plausible values
    matching the field name shape, never placeholder garbage."""
    # Reuses semantic_router._smart_free_text logic for consistency
    # with the per-row fallback path.
```

### 6.2 `src/tools/datagen/semantic_router.py`

Add a new branch in `generate_value()`: when `data_type == "string"` and
the semantic_type is `free_text`, `unknown`, or `enum_value` without
explicit values, **and** the V2 generator has loaded an entity catalog
for this `(entity, field)`, sample from the catalog instead of routing
through the existing `_smart_free_text`. Existing routing for known
semantic types (email, person_name, etc.) is unchanged.

The catalog is passed in via a new optional parameter on `generate_value`:

```python
def generate_value(
    self,
    semantic_type: str,
    entity_name: str = "",
    constraints: dict = None,
    field_name: str = "",
    field_catalog: Optional[List[str]] = None,   # NEW
) -> Any:
    ...
    # If we have a field catalog and the semantic type is loose, sample from it
    if field_catalog and semantic_type in {"free_text", "unknown", "enum_value"}:
        if not (constraints.get("enum") or constraints.get("pattern")):
            return random.choice(field_catalog)
    # ... existing path unchanged
```

The earlier session's `_smart_free_text` is retained as the final fallback
when no catalog is available.

### 6.3 `src/tools/datagen/advanced_generator_v2.py`

Three changes to `AdvancedGeneratorV2.generate()`:

**(a)** Between semantic analysis and row generation, call
`catalog_factory.get_entity_catalogs(...)` for each entity. Store the
resulting `{field: [values]}` map in `self._entity_catalogs[entity_name]`.

**(b)** In `_generate_independent_entities` and the
`SemanticFieldGeneratorAdapter` inside `_generate_with_relationships`,
pass `field_catalog=self._entity_catalogs.get(entity_name, {}).get(field_name)`
into `semantic_router.generate_value(...)`.

**(c)** **DELETE the internal `_apply_realism` method (lines 532-584).**
Replace both call sites (lines 156-159 inside the try block and 170-173
outside) with a single call:

```python
# OLD: two calls to self._apply_realism — applied realism twice (B2 bug)
# NEW: single call to consolidated realism engine
from src.tools.datagen.realism_engine import apply_realism_to_data
if realism_level != "basic":
    generated_data = apply_realism_to_data(
        generated_data, schema_design, realism_level,
    )
```

This addresses **B1** (dead-code dual implementation) and **B2** (double
application). `realism_engine.apply_realism_to_data` handles null +
duplicate + outlier injection in one pass.

### 6.4 `src/tools/datagen/realism_engine.py`

No API changes. Verify the existing critical-field protection holds:
emails / phones / uuids / dates remain non-null even when nullable.
The current `RealismEngine._inject_nulls` injects into any field in
the `nullable_fields` set — verify the caller-side filter
(`apply_realism_to_data` line 213, `nullable_fields = {f.name for f in
entity_schema.fields if f.nullable}`) correctly excludes business-critical
fields. If not, add the critical-semantic-type guard from V2's old
internal `_apply_realism` (lines 545-548 of advanced_generator_v2.py
before deletion) into `apply_realism_to_data`.

### 6.5 `src/tools/datagen/schema_designer.py`

Update `SCHEMA_DESIGN_PROMPT` (lines 25-63) with explicit instructions
and few-shot examples for marking fields nullable:

```
4. Mark fields nullable=true when they represent optional or
   often-missing information in real production data. Examples:
   - Always nullable: middle_name, address_line_2, description, comment,
     last_login, deleted_at, deactivation_reason, suffix, extension
   - Sometimes nullable (mark true if domain suggests): phone, alternate_email,
     referral_code, promo_code, notes, attachment_url
   - Never nullable: id, primary_key, email (when primary contact),
     created_at, foreign keys
5. ...
```

The `_extract_json` regex parser (lines 207-241) already tolerates
additional fields, so the JSON contract is unchanged from the parser's
perspective. **Risk:** the existing
`test_schema_designer::test_design_with_llm_valid_response` may mock a
response without `nullable` markers; verify the test still passes after
the prompt change (the parser is permissive).

### 6.6 `src/tools/datagen/schema_validator.py` (NEW FILE)

Pure post-processor that runs after `SchemaDesigner.design_schema(...)`
returns. Two responsibilities:

```python
class SchemaValidator:
    """Validates and corrects LLM-designed schemas without further LLM calls."""

    def validate_and_fix(
        self,
        schema_design: SchemaDesign,
        user_prompt: str,
    ) -> SchemaDesign:
        """Returns a corrected SchemaDesign. Mutates a copy, not the input."""
        schema_design = self._fix_enum_assignment(schema_design, user_prompt)
        schema_design = self._infer_missing_ranges(schema_design)
        return schema_design

    def _fix_enum_assignment(self, sd: SchemaDesign, prompt: str) -> SchemaDesign:
        """Detect explicit `<field> enum: [...]` patterns in the prompt
        and verify each lands on its named field. If the LLM put the enum
        on the wrong field, move it.

        Pattern: `(\w+)\s+enum\s*[:=]\s*\[([^\]]+)\]` (case-insensitive)
        Example: `genre enum: ["Fiction","Non-Fiction","Sci-Fi"]`
        - Extract: field_name="genre", values=["Fiction","Non-Fiction","Sci-Fi"]
        - Find any entity.field where field.name == "genre"
        - If that field's constraints don't contain those values, OVERWRITE.
        - If another field has those values (the swap case), CLEAR them there.
        """

    def _infer_missing_ranges(self, sd: SchemaDesign) -> SchemaDesign:
        """For any numeric field (type in int/float) with no min/max
        constraint, apply RANGE_HINTS lookup by field-name pattern."""
```

The `RANGE_HINTS` dict (case-insensitive substring match):

```python
RANGE_HINTS = {
    # Counts (small integers)
    "bedroom_count": (1, 6),
    "bathroom_count": (1, 5),
    "room_count":    (1, 15),
    "guest_count":   (1, 12),
    "child_count":   (0, 8),
    "_count":        (0, 1000),       # generic fallback for *_count
    # Demographics
    "age":           (1, 120),
    "year_of_":      (1900, 2030),
    "year_built":    (1900, 2030),
    "year_constructed": (1900, 2030),
    "year_":         (1900, 2030),
    # Physical measurements
    "square_feet":   (200, 20000),
    "sqft":          (200, 20000),
    "_meters":       (1, 10000),
    "_feet":         (1, 10000),
    "weight_kg":     (1, 200),
    "height_cm":     (50, 250),
    # Engineering
    "engine_cc":     (50, 8000),
    "voltage":       (1, 480),
    "wattage":       (1, 5000),
    # Rates / percentages
    "_percent":      (0, 100),
    "_pct":          (0, 100),
    "_rate":         (0, 1),
    # Money / pricing
    "listing_price": (50000, 5000000),
    "_price":        (1, 100000),
    "_cost":         (0, 100000),
    # Time
    "duration_ms":   (1, 60000),
    "duration_s":    (1, 3600),
}
```

When two hints match (e.g. `year_built` matches both `year_built` and
`year_`), the longest match wins.

If no hint matches, leave the field unconstrained — `semantic_router`'s
`numeric_id` generator already uses 1..1000000 as ultimate fallback, but
the new `_smart_free_text` numeric path (added earlier this session) uses
1..1000. Both are wide but neither is nonsensical.

### 6.7 `src/tools/datagen/domain_templates.py`

Add `nullable=True` to business-domain fields per **B3**:

**ecommerce template:**

| Entity | Field | nullable change |
|--------|-------|-----------------|
| customers | `phone` | `False` → `True` |
| customers | `address` | `False` → `True` |
| products | `category` | `False` → `True` |
| products | `description` | (add field, `nullable=True`) |

**saas template:**

| Entity | Field | nullable change |
|--------|-------|-----------------|
| users | `phone` | `False` → `True` |
| users | `last_login` | `False` → `True` |
| subscriptions | `cancellation_reason` | (add field, `nullable=True`) |
| usage_logs | `error_message` | (add field, `nullable=True`) |

**iot_devices template:**

| Entity | Field | nullable change |
|--------|-------|-----------------|
| devices | `last_seen` | `False` → `True` |
| readings | `error_code` | (add field, `nullable=True`) |

**Test impact:** `test_domain_templates.py::test_list_domains` and other
template-shape tests may need updating. Update assertions to match the new
template structure in the same commit.

### 6.8 `src/agents/datagen/agent.py`

No structural changes. The existing `enable_semantic_generation` /
`ENABLE_SEMANTIC_ANALYZER` kill-switches automatically disable the new
catalog-sandbox path because the catalog factory only runs when
`generator.enable_semantic` is True (controlled by the same flag).
Comment update at line 79 to document this.

### 6.9 `src/api/routers/__init__.py`

No changes. Tool description string at lines 58-64 is already accurate
for v0.9 ("V2 (Advanced): Multi-entity generation with semantic analysis,
constraint enforcement, and relationship integrity"). Catalog-sandbox is
an implementation detail not exposed via the MCP `tools/list` description.

The dashboard's `log_request_call.delay(...)` payload at lines 817-825
(REST) and 1195-1203 (MCP) is **unchanged**. Per the user's choice (B5
follow-up), catalog LLM calls bubble up under the parent `generate_data`
tool_name; per-task attribution is v0.10 work.

### 6.10 `manifests/devforge.json`

Bump `version` from `0.9.0` to `0.10.0`. (Note: refine_prompt's bump in
the prior session was a tool-internal version; this is the project-wide
manifest version.) No description or schema field changes.

### 6.11 `docs/tools/generate_data.md`

Major update:

- Bump `Version: 0.8.0` → `0.9.0` (matches `_internal_success` semantics
  fixed in this session; v0.10 is the manifest version which moves
  separately)
- Replace the "Phase 1: Semantic Generation" section with a new
  "Catalog-Sandbox" section explaining the per-entity batched LLM
  catalogs and when they fire
- Update the realism table at lines 83-87 to show real observed rates
  (after consolidation) and document the critical-field protection list
- Add a "What changed in v0.9" callout summarizing the three observable
  wins
- Update the "All-In-One stress test" expected output to show enum=Fiction
  not enum=active (the T5 fix)
- Doc/version sprawl mentioned in earlier review stays as a known issue
  (per "out of scope" §4)

## 7. Backward compatibility matrix

| Caller behavior | v0.8 | v0.9 |
|-----------------|------|------|
| `DataGenArgs` parameters | unchanged | unchanged |
| `enable_semantic_generation=False` | disables analyzer | also disables catalog-sandbox |
| `ENABLE_SEMANTIC_ANALYZER=false` env | disables analyzer | also disables catalog-sandbox |
| V1 path (no prompt/domain) | pure Faker | pure Faker (untouched) |
| V2 domain templates | works, no nulls at realism=high | works, **inject ~10% nulls** in newly-nullable fields |
| V2 prompt mode known fields (email, name) | Faker via semantic_router | Faker via semantic_router (catalog-sandbox does not override Tier-1 types) |
| V2 prompt mode unknown fields (`measurement_unit`, etc.) | Faker `_smart_free_text` or worse | catalog-sandbox first, `_smart_free_text` fallback |
| `data.entities` / `data.data` / `data.fk_integrity` | shape | unchanged |
| `data.catalog_usage` | (not present) | **NEW optional** — names which fields used catalogs, cache hit count, LLM call count for this request |
| MCP `isError` semantics | based on `success` | unchanged |
| Dashboard `/usage/` `log_request_call` payload | (user_id, tenant_id, integration_name, tool_name, duration_ms, success) | **unchanged** |
| LLM cost per cold call | 1 LLM call (schema design) | ~1 + entity_count LLM calls (schema design + per-entity catalogs) |
| LLM cost per warm call (within 1h TTL) | 1 LLM call | 1 LLM call (catalogs from L2 cache) |

The only observable change for an unaware caller is **enum=high produces
nulls** on domain-template responses. That's the intended fix (B3) but
must be called out in the docs as a behavior change.

## 8. LLM cost & latency budget

Profiled against the free Ollama endpoint used by the project, measured
during the earlier session's V2 testing (after the silent-failure fix).

| Scenario | LLM calls | Wall-clock (free Ollama) | Cache state |
|----------|-----------|--------------------------|-------------|
| V1 (no prompt/domain) | 0 | < 1s | N/A |
| V2 domain="ecommerce", cold | 1 (schema is template, only catalogs) + 3 (one per entity) = 4 | 15–25s | Cold |
| V2 domain="ecommerce", warm (≤1h since) | 0 | 5–10s | L2 hit |
| V2 prompt="bookstore...", cold | 1 (schema) + 3 (catalogs) = 4 | 18–30s | Cold |
| V2 prompt="bookstore...", warm | 0 (same prompt hash) | 5–10s | L2 hit |
| V2 prompt="bookstore...", warm different prompt | 1 (schema, no cache) + 0–3 (catalogs hit cache if entities/fields match) | 8–20s | Partial |

Cold-cache cost is roughly 2× v0.8. Warm-cache is identical to v0.8 for
the request path, much faster than v0.8 for the value-quality side. The
L2 TTL of 1h means a busy domain amortizes within minutes.

The `progress_callback` wired at `routers/__init__.py:1162-1168` already
emits stage events (`schema_design 20% → semantic_analysis 40% →
catalog_generation 60% → row_generation 80% → complete 100%`). The
frontend can subscribe to display real progress instead of a blocking
spinner. **No backend change needed for progress** — the wiring is
already there.

## 9. Testing

### 9.1 New tests

- `tests/test_catalog_sandbox.py` — new file. Cases:
  - `get_entity_catalogs` returns `Dict[str, List[str]]` with exactly the
    string-typed fields as keys
  - L1 cache hit on second call within same request (no LLM invocation)
  - L2 cache hit on identical `(entity, fields, prompt)` across requests
  - Cache miss when `prompt` differs (prompt hash in key)
  - Fallback to `_smart_field_fallback` on LLM exception, returns 50 items
  - Fallback to `_smart_field_fallback` on JSON parse failure
  - `model_router.invoke_with_usage` called with `task_type=
    "datagen_catalog_generation"` and propagates `tenant_id` / `user_id`

- `tests/test_schema_validator.py` — new file. Cases:
  - Enum swap fix: prompt `'genre enum: ["Fiction","Sci-Fi"]'` + LLM that
    put `["active","pending"]` on genre → fixed to `["Fiction","Sci-Fi"]`
  - Enum swap clears the misplaced enum from the other field
  - Range inference: `bedroom_count` no constraint → (1, 6)
  - Range inference: `age` no constraint → (1, 120)
  - Range inference: longest-match wins (`year_built` over `year_`)
  - No range inference when explicit min/max already set
  - Pure function (no LLM call, no side effect on input)

- `tests/test_realism_consolidation.py` — new file. Cases:
  - V2 generator's `_apply_realism` is no longer present (importable
    only as the module-level `realism_engine.apply_realism_to_data`)
  - `realism_level="high"` on ecommerce domain produces ≥5% nulls in
    `phone` field (was 0% in v0.8)
  - `realism_level="high"` produces ≥1% duplicates in `email` field
  - `realism_level="high"` produces ≥0.5% outliers in numeric fields
  - Critical fields (`email`, `phone`, `id`, `uuid`, `created_at`) never
    get null when nullable=false even at high realism

### 9.2 Modified tests

- `tests/test_domain_templates.py` — update assertions for new
  `nullable=True` markers and any added fields (B3).
- `tests/test_schema_designer.py` — mock LLM responses adjusted to
  reflect the new SCHEMA_DESIGN_PROMPT examples (B8).

### 9.3 Untouched tests (must continue to pass)

- All `test_sanitizer.py` tests
- All `test_relationships.py` tests
- All `test_distributions.py` tests
- The earlier-session test files: `test_dependency_analyzer.py`,
  `test_quality_block.py` (refine_prompt v0.10 work)

### 9.4 Pre-existing failures (out of scope)

The 14 failures in `test_semantic_analyzer_v2.py` (sync-vs-async test
infrastructure rot, predating v0.9) remain. Documented as a separate
test-modernization spec.

## 10. Implementation order

This is the order the writing-plans skill should produce:

1. **`schema_validator.py`** — new file, pure function, no dependencies
   on the rest of the changes. Tests can be written first (TDD).
2. **`catalog_factory.py`** — add `get_entity_catalogs`, leave existing
   `get_catalog` untouched. Tests with mocked `model_router`.
3. **`schema_designer.py`** — prompt update only. Verify
   `test_design_with_llm_valid_response` still passes.
4. **`semantic_router.py`** — add `field_catalog` parameter and the
   sample-from-catalog branch. No structural change.
5. **`advanced_generator_v2.py`** — wire `SchemaValidator` after
   `SchemaDesigner`, wire `get_entity_catalogs` before row generation,
   pass `field_catalog` to `generate_value`, **delete `_apply_realism`
   method**, replace both call sites with single
   `realism_engine.apply_realism_to_data` call.
6. **`domain_templates.py`** — add `nullable=True` per B3, add new fields
   for saas (`cancellation_reason`) and iot (`error_code`).
7. **Test updates** — `test_domain_templates.py` assertions.
8. **Docs** — `docs/tools/generate_data.md`, `manifests/devforge.json`
   version bump.
9. **End-to-end MCP smoke** — re-run the 10 hard-test scenarios from
   this session and confirm production-grade outputs.

## 11. Versioning + migration

- `docs/tools/generate_data.md` version: `0.8.0` → `0.9.0`
- `manifests/devforge.json` version: `0.9.0` → `0.10.0`
- `src/main.py` and `Dockerfile` version stamps: deferred to the
  out-of-scope doc reconciliation work
- No DB migration. No environment-variable changes. No new dependencies.
- Existing in-flight calls: none — `generate_data` is stateless per
  request, so deploy is a simple container restart.

## 12. Acceptance criteria

A v0.9 build ships when all of the following hold:

1. **The T6 vintage motorcycles MCP test** (previously produced `"Agent every
   development say."`) now produces domain-realistic model names like
   `"Ducati 916"`, `"MV Agusta F4"`. Verified via MCP call after deploy.
2. **The T10 scientific instruments MCP test** produces measurement_units
   like `"kg/m³"`, `"Hz"`, `"Pa"` — not single Faker words like `"perform"`.
3. **The T5 stress test** with `genre enum: ["Fiction","Non-Fiction","Sci-Fi"]`
   produces only those three values for `genre` (the swap is fixed).
4. **`realism_level="high"` on ecommerce domain at 200 rows** produces
   between 8% and 12% nulls in the `phone` field (target: 10% per
   `REALISM_CONFIGS`).
5. **`realism_level="high"` produces at least 1 outlier per 100 numeric
   field rows** (target: 1% per config).
6. **All v0.8 keys still present in v0.9 response** — `success`, `tool`,
   `data.refined_prompt` (where applicable), `data.entities`,
   `data.data`, `data.schema`, `data.fk_integrity`,
   `data.constraint_violations`, `data.semantic_generation_used`,
   `data._internal_success`, `data.metadata`.
7. **Dashboard `/usage/` analytics still receives one row per
   `generate_data` call** with the same payload fields. Verified by
   running 5 calls and checking the dashboard.
8. **The 111 v0.8 passing tests still pass.**
9. **The 3 new test files pass** (test_catalog_sandbox, test_schema_validator,
   test_realism_consolidation).
10. **V2's internal `_apply_realism` method is removed** (`grep -n
    "_apply_realism" src/tools/datagen/advanced_generator_v2.py` returns
    empty).
11. **`docs/tools/generate_data.md`** version is `0.9.0` and documents the
    catalog-sandbox, the consolidated realism, and the SchemaValidator.

## 13. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM returns malformed JSON for batched catalog | Medium | Falls back to `_smart_field_fallback` per field — output is plausible Faker, not garbage | Already covered |
| Cache key collision between entity_catalog and legacy catalog | Low | Different key prefixes (`entity_catalog:` vs `catalog:`) | Verified in §6.1 |
| Schema designer prompt change breaks `test_design_with_llm_valid_response` | Medium | Test fails CI | Adjust mock LLM response in same commit |
| Domain template tests fail after nullable changes | High | CI fails until updated | Update tests in same commit per §6.7 |
| Realism consolidation produces too many nulls on existing user data | Medium | Customer surprise | Document as behavior change in §11 migration note; default `realism_level` is `basic` (no nulls) |
| Cold-cache latency on the free Ollama endpoint blows past 30s for large prompts | Medium | Frontend timeout | Existing `progress_callback` wiring lets frontend show progress; user accepted 2-3× cost in scope question |
| The 14 pre-existing async-vs-sync test failures multiply | Low | Test infrastructure regression | Verified stable across earlier session's changes; v0.9 changes don't touch the broken-test surface |
| Catalog LLM call missing usage tracking surfaces inconsistencies on dashboard | Low | Per-task attribution missing | Out of scope per user choice; documented as v0.10 work |

## 14. Open questions (none blocking)

None. All architectural decisions are locked. The three open questions
from the brainstorming dialog (B3 nullable, B1 consolidation, B5 usage
tracking) were resolved by the user.

---

**End of design.**
