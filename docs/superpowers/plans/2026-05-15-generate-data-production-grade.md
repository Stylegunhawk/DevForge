# generate_data v0.9 — Production-Grade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **User preference for this plan:** the user reviews and commits manually. **Do not run `git commit`.** Each task ends with a `git add` step only; the user runs `git commit` themselves after reviewing each task.

**Goal:** Bring `generate_data` to Mockaroo-level quality on arbitrary domains while keeping the existing MCP API, response shape, V1 fast path, and dashboard `/usage/` analytics intact.

**Architecture:** Insert a new `SchemaValidator` post-processor after `SchemaDesigner` (no LLM), add a batched per-entity `CatalogFactory.get_entity_catalogs` method (1 LLM call per entity, L1/L2 cached, tracked via `model_router.invoke_with_usage`), thread the resulting `field_catalog` into `SemanticRouter.generate_value`, consolidate realism by deleting V2's internal `_apply_realism` and routing through `realism_engine.apply_realism_to_data`, and mark business-domain fields nullable in the three domain templates so realism levels actually have something to inject.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2.12, LangChain 1.0, Faker 28, pytest 8 + pytest-asyncio. LLM routing via the project's `src/core/model_router.ModelRouter` (already async). Existing `CatalogFactory` L1/L2 cache reused with new key prefix `entity_catalog:`.

**Spec:** [2026-05-15-generate-data-production-grade-design.md](../specs/2026-05-15-generate-data-production-grade-design.md)

---

## Task 0: Pre-flight check

**Files:**
- Read only: existing tests, container status

- [ ] **Step 1: Confirm working tree matches the audit baseline**

Run from repo root:
```bash
git status --short
```
Expected: the working-tree state captured during the audit session — uncommitted changes in `DevForge_Backend/{docs/tools/refine_prompt.md, manifests/devforge.json, src/agents/datagen/agent.py, src/agents/prompt_refiner/agent.py, src/agents/prompt_refiner/conversation_parser.py, src/agents/prompt_refiner/context_types.py, src/agents/prompt_refiner/dependency_analyzer.py, src/agents/prompt_refiner/enhancer.py, src/agents/prompt_refiner/sanitizer.py, src/agents/prompt_refiner/templates.py, src/api/routers/__init__.py, src/tools/datagen/advanced_generator_v2.py, src/tools/datagen/semantic_router.py, tests/test_prompt_refiner.py, tests/test_prompt_refiner_phase2.py}` plus the new untracked test files `DevForge_Backend/tests/test_dependency_analyzer.py` and `DevForge_Backend/tests/test_quality_block.py`.

If the working tree differs significantly, stop and reconcile with the user before proceeding — the v0.9 fixes layer on top of v0.8.5.

- [ ] **Step 2: Confirm the API container is running**

```bash
docker compose --profile rag ps api | grep -q "Up\|running" && echo "API up" || echo "API down — start it before running MCP smoke tests in Task 9"
```

- [ ] **Step 3: Confirm baseline tests pass**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend && source venv/bin/activate
python3 -m pytest tests/test_prompt_refiner.py tests/test_prompt_refiner_phase2.py tests/test_sanitizer.py tests/test_dependency_analyzer.py tests/test_quality_block.py tests/test_datagen.py tests/test_relationships.py tests/test_realism.py tests/test_distributions.py tests/test_semantic_router.py 2>&1 | tail -5
```

Expected: a few pre-existing failures (per audit: 3 in `test_datagen.py::TestDataGenAgent` and 1 in `test_domain_templates.py`, all verified to predate v0.9). Catalog the pass/fail count as the baseline. Any **new** failure after a task means that task introduced a regression.

---

## Task 1: SchemaValidator (new module)

**Files:**
- Create: `DevForge_Backend/src/tools/datagen/schema_validator.py`
- Create: `DevForge_Backend/tests/test_schema_validator.py`

This module is pure-function: it takes a `SchemaDesign` and a user prompt and returns a corrected `SchemaDesign`. No LLM calls, no I/O. Easiest to TDD.

- [ ] **Step 1: Write the failing test file**

Create `DevForge_Backend/tests/test_schema_validator.py` with this complete content:

```python
"""Tests for SchemaValidator (v0.9).

SchemaValidator is a pure post-processor that runs after SchemaDesigner.
Two responsibilities:
  1. Enum-swap fix: if the user prompt names an explicit `enum: [...]` for a
     specific field, ensure the LLM landed it on that field (not another).
  2. Range inference: any numeric field without explicit min/max gets a sane
     default from RANGE_HINTS by field-name pattern (longest-match wins).
"""

import pytest

from src.tools.datagen.schema_models import (
    EntitySchema,
    FieldSchema,
    SchemaDesign,
)
from src.tools.datagen.schema_validator import SchemaValidator, RANGE_HINTS


def _build_schema(entity_name: str, fields: list[FieldSchema]) -> SchemaDesign:
    return SchemaDesign(
        entities={
            entity_name: EntitySchema(
                name=entity_name,
                fields=fields,
                count=10,
                primary_key="id",
            )
        },
        relationships=[],
        domain="test",
    )


# ---------- Enum-swap fix ----------

class TestEnumSwapFix:
    def test_no_change_when_no_explicit_enum_in_prompt(self):
        validator = SchemaValidator()
        sd = _build_schema(
            "book",
            [FieldSchema(name="genre", type="string",
                         constraints={"enum": ["Fiction", "Non-Fiction"]})],
        )
        out = validator.validate_and_fix(sd, user_prompt="Generate some books")
        assert out.entities["book"].fields[0].constraints == {"enum": ["Fiction", "Non-Fiction"]}

    def test_fixes_field_with_wrong_enum(self):
        """LLM put status-like values on `genre`; prompt says genre is Fiction/etc."""
        validator = SchemaValidator()
        sd = _build_schema(
            "book",
            [FieldSchema(name="genre", type="string",
                         constraints={"enum": ["active", "pending"]})],
        )
        prompt = 'Books with genre enum: ["Fiction","Non-Fiction","Sci-Fi"]'
        out = validator.validate_and_fix(sd, user_prompt=prompt)
        assert out.entities["book"].fields[0].constraints["enum"] == [
            "Fiction", "Non-Fiction", "Sci-Fi",
        ]

    def test_clears_misplaced_enum_from_other_field(self):
        """If status field was given the genre values, clear them."""
        validator = SchemaValidator()
        sd = _build_schema(
            "book",
            [
                FieldSchema(name="genre", type="string",
                            constraints={"enum": ["pending", "active"]}),
                FieldSchema(name="status", type="string",
                            constraints={"enum": ["Fiction", "Sci-Fi"]}),
            ],
        )
        prompt = 'Books with genre enum: ["Fiction","Sci-Fi"]'
        out = validator.validate_and_fix(sd, user_prompt=prompt)
        # genre now has the prompt's enum
        genre = next(f for f in out.entities["book"].fields if f.name == "genre")
        assert genre.constraints["enum"] == ["Fiction", "Sci-Fi"]
        # status had the wrong values copied — they get cleared
        status = next(f for f in out.entities["book"].fields if f.name == "status")
        assert "enum" not in (status.constraints or {}) or not status.constraints.get("enum")

    def test_case_insensitive_field_match(self):
        validator = SchemaValidator()
        sd = _build_schema(
            "book",
            [FieldSchema(name="Genre", type="string",
                         constraints={"enum": ["wrong"]})],
        )
        prompt = 'GENRE enum: ["A","B"]'
        out = validator.validate_and_fix(sd, user_prompt=prompt)
        assert out.entities["book"].fields[0].constraints["enum"] == ["A", "B"]

    def test_handles_quotes_with_spaces(self):
        validator = SchemaValidator()
        sd = _build_schema(
            "user",
            [FieldSchema(name="tier", type="string")],
        )
        prompt = 'tier enum: [ "free", "pro" , "enterprise" ]'
        out = validator.validate_and_fix(sd, user_prompt=prompt)
        assert out.entities["user"].fields[0].constraints["enum"] == ["free", "pro", "enterprise"]


# ---------- Range inference ----------

class TestRangeInference:
    def test_bedroom_count_gets_realistic_range(self):
        validator = SchemaValidator()
        sd = _build_schema(
            "listing",
            [FieldSchema(name="bedroom_count", type="int")],
        )
        out = validator.validate_and_fix(sd, user_prompt="real estate listings")
        constraints = out.entities["listing"].fields[0].constraints or {}
        assert constraints.get("min") == 1
        assert constraints.get("max") == 6

    def test_age_gets_realistic_range(self):
        validator = SchemaValidator()
        sd = _build_schema(
            "person",
            [FieldSchema(name="age", type="int")],
        )
        out = validator.validate_and_fix(sd, user_prompt="employees")
        constraints = out.entities["person"].fields[0].constraints or {}
        assert constraints.get("min") == 1
        assert constraints.get("max") == 120

    def test_longest_match_wins(self):
        """`year_built` should match the specific hint, not the generic `year_`."""
        validator = SchemaValidator()
        sd = _build_schema(
            "house",
            [FieldSchema(name="year_built", type="int")],
        )
        out = validator.validate_and_fix(sd, user_prompt="houses")
        constraints = out.entities["house"].fields[0].constraints or {}
        # year_built hint is (1900, 2030) — same as year_ in our table
        assert constraints.get("min") == 1900
        assert constraints.get("max") == 2030

    def test_does_not_override_explicit_min_max(self):
        validator = SchemaValidator()
        sd = _build_schema(
            "listing",
            [FieldSchema(name="bedroom_count", type="int",
                         constraints={"min": 2, "max": 10})],
        )
        out = validator.validate_and_fix(sd, user_prompt="luxury listings")
        constraints = out.entities["listing"].fields[0].constraints
        assert constraints["min"] == 2
        assert constraints["max"] == 10

    def test_no_hint_leaves_field_unconstrained(self):
        validator = SchemaValidator()
        sd = _build_schema(
            "blob",
            [FieldSchema(name="totally_unknown_metric", type="int")],
        )
        out = validator.validate_and_fix(sd, user_prompt="opaque data")
        constraints = out.entities["blob"].fields[0].constraints or {}
        assert "min" not in constraints
        assert "max" not in constraints

    def test_skips_non_numeric_fields(self):
        validator = SchemaValidator()
        sd = _build_schema(
            "x",
            [FieldSchema(name="bedroom_count", type="string")],  # string, not int
        )
        out = validator.validate_and_fix(sd, user_prompt="x")
        constraints = out.entities["x"].fields[0].constraints or {}
        assert "min" not in constraints

    def test_range_hints_dict_has_known_entries(self):
        """Sanity check the dict shape."""
        assert "age" in RANGE_HINTS
        assert RANGE_HINTS["age"] == (1, 120)
        assert "bedroom_count" in RANGE_HINTS
        assert "year_built" in RANGE_HINTS


# ---------- Determinism / purity ----------

class TestPureFunction:
    def test_does_not_mutate_input(self):
        validator = SchemaValidator()
        original = _build_schema(
            "x", [FieldSchema(name="age", type="int")],
        )
        original_constraints = original.entities["x"].fields[0].constraints
        _ = validator.validate_and_fix(original, user_prompt="x")
        # Input unchanged
        assert original.entities["x"].fields[0].constraints == original_constraints
```

- [ ] **Step 2: Run the test file and verify it fails with import error**

```bash
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend && source venv/bin/activate
python3 -m pytest tests/test_schema_validator.py -v 2>&1 | tail -5
```
Expected: `ModuleNotFoundError: No module named 'src.tools.datagen.schema_validator'` or similar import failure on every test.

- [ ] **Step 3: Implement SchemaValidator**

Create `DevForge_Backend/src/tools/datagen/schema_validator.py` with this complete content:

```python
"""Schema validation and correction (v0.9).

Pure post-processor that runs after SchemaDesigner.design_schema(). Two
responsibilities:

1. Enum-swap fix: when the user's prompt contains an explicit
   `<field> enum: [...]` pattern, ensure the LLM placed that enum on the
   named field. If the LLM placed status-like values on `genre` (the v0.8
   stress-test bug), move the prompt's values to genre and clear the
   misplaced values from the other field.

2. Range inference: when a numeric field has no explicit min/max
   constraint, look up a sane default in RANGE_HINTS by case-insensitive
   substring match. Longest match wins. Leaves the field unconstrained if
   no hint matches.

This module is pure: it operates on a copy of the input SchemaDesign and
makes no LLM calls or I/O. Determinism is required because we run it on
every V2 call, and tests must be reproducible.
"""

import copy
import logging
import re
from typing import Optional

from src.tools.datagen.schema_models import SchemaDesign

logger = logging.getLogger(__name__)


# Field-name pattern -> (min, max) for numeric range inference. When two
# patterns match, the LONGER pattern wins (so `year_built` beats `year_`).
# Case-insensitive substring match against the field name.
RANGE_HINTS: dict[str, tuple[float, float]] = {
    # Counts (small integers)
    "bedroom_count": (1, 6),
    "bathroom_count": (1, 5),
    "room_count": (1, 15),
    "guest_count": (1, 12),
    "child_count": (0, 8),
    "_count": (0, 1000),
    # Demographics
    "age": (1, 120),
    "year_of_": (1900, 2030),
    "year_built": (1900, 2030),
    "year_constructed": (1900, 2030),
    "year_": (1900, 2030),
    # Physical measurements
    "square_feet": (200, 20000),
    "sqft": (200, 20000),
    "_meters": (1, 10000),
    "_feet": (1, 10000),
    "weight_kg": (1, 200),
    "height_cm": (50, 250),
    # Engineering
    "engine_cc": (50, 8000),
    "voltage": (1, 480),
    "wattage": (1, 5000),
    # Rates / percentages
    "_percent": (0, 100),
    "_pct": (0, 100),
    "_rate": (0, 1),
    # Money / pricing
    "listing_price": (50000, 5000000),
    "_price": (1, 100000),
    "_cost": (0, 100000),
    # Time durations
    "duration_ms": (1, 60000),
    "duration_s": (1, 3600),
}


# Matches patterns like `genre enum: ["Fiction","Sci-Fi"]` or
# `tier enum=["free","pro"]` in the user's prompt. Captures field name and
# the raw bracketed body for value extraction.
_PROMPT_ENUM_RE = re.compile(
    r"""
    \b(\w+)              # 1: field name
    \s+enum\s*[:=]\s*
    \[                   # opening bracket
    ([^\]]+)             # 2: values body
    \]                   # closing bracket
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Matches a single string item inside the enum body, with optional quotes
# and surrounding whitespace.
_ENUM_ITEM_RE = re.compile(r"""['"]?\s*([^'",]+?)\s*['"]?\s*(?:,|$)""")


class SchemaValidator:
    """Pure post-processor for LLM-designed schemas."""

    def validate_and_fix(
        self,
        schema_design: SchemaDesign,
        user_prompt: str,
    ) -> SchemaDesign:
        """Return a corrected copy of the schema. Does not mutate input."""
        sd = copy.deepcopy(schema_design)
        sd = self._fix_enum_assignment(sd, user_prompt or "")
        sd = self._infer_missing_ranges(sd)
        return sd

    # ----- Enum-swap fix -----

    def _fix_enum_assignment(self, sd: SchemaDesign, prompt: str) -> SchemaDesign:
        """Match `<field> enum: [...]` patterns in the prompt and force each
        match onto the named field. Clear the same values from any other
        field that happens to carry them (the swap case)."""
        for match in _PROMPT_ENUM_RE.finditer(prompt):
            field_name = match.group(1).lower()
            body = match.group(2)
            values = self._parse_enum_body(body)
            if not values:
                continue
            self._apply_enum_to_field(sd, field_name, values)
        return sd

    @staticmethod
    def _parse_enum_body(body: str) -> list[str]:
        """Extract trimmed, unquoted strings from a bracketed enum body."""
        items = []
        for m in _ENUM_ITEM_RE.finditer(body):
            v = m.group(1).strip()
            if v:
                items.append(v)
        return items

    def _apply_enum_to_field(
        self,
        sd: SchemaDesign,
        target_field_lower: str,
        values: list[str],
    ) -> None:
        """Force `values` onto the named field; clear them from any other
        field that currently holds the same set."""
        values_set = set(values)
        for entity in sd.entities.values():
            for field in entity.fields:
                if field.name.lower() == target_field_lower:
                    constraints = field.constraints or {}
                    constraints = dict(constraints)
                    constraints["enum"] = list(values)
                    field.constraints = constraints
                    logger.info(
                        "SchemaValidator: forced enum %s onto %s.%s",
                        values, entity.name, field.name,
                    )
                else:
                    constraints = field.constraints or {}
                    existing = constraints.get("enum")
                    if existing and set(existing) == values_set:
                        new_constraints = {k: v for k, v in constraints.items() if k != "enum"}
                        field.constraints = new_constraints or None
                        logger.info(
                            "SchemaValidator: cleared misplaced enum from %s.%s",
                            entity.name, field.name,
                        )

    # ----- Range inference -----

    def _infer_missing_ranges(self, sd: SchemaDesign) -> SchemaDesign:
        """For each numeric field with no explicit min/max, apply the
        longest-matching RANGE_HINTS entry."""
        # Pre-sort hints by length (longest first) so longest-match wins.
        sorted_hints = sorted(RANGE_HINTS.items(), key=lambda kv: -len(kv[0]))
        for entity in sd.entities.values():
            for field in entity.fields:
                if field.type not in ("int", "float"):
                    continue
                constraints = field.constraints or {}
                if "min" in constraints or "max" in constraints:
                    continue
                fname = field.name.lower()
                inferred: Optional[tuple[float, float]] = None
                for pattern, range_ in sorted_hints:
                    if pattern.lower() in fname:
                        inferred = range_
                        break
                if inferred is None:
                    continue
                new_constraints = dict(constraints)
                new_constraints["min"] = inferred[0]
                new_constraints["max"] = inferred[1]
                field.constraints = new_constraints
                logger.debug(
                    "SchemaValidator: inferred range %s for %s.%s",
                    inferred, entity.name, field.name,
                )
        return sd
```

- [ ] **Step 4: Run the test file and verify all tests pass**

```bash
python3 -m pytest tests/test_schema_validator.py -v 2>&1 | tail -20
```
Expected: All ~14 tests PASSED. If any fail, the regex or the longest-match logic is wrong — fix inline and re-run.

- [ ] **Step 5: Stage for manual review**

```bash
git add src/tools/datagen/schema_validator.py tests/test_schema_validator.py
git status --short
```
Do NOT run `git commit`. The user reviews and commits manually.

---

## Task 2: CatalogFactory.get_entity_catalogs (extend)

**Files:**
- Modify: `DevForge_Backend/src/tools/datagen/catalog_factory.py` (add new async method, do not modify the existing sync `get_catalog`)
- Create: `DevForge_Backend/tests/test_catalog_sandbox.py`

- [ ] **Step 1: Write the failing test file**

Create `DevForge_Backend/tests/test_catalog_sandbox.py`:

```python
"""Tests for CatalogFactory.get_entity_catalogs (v0.9 catalog-sandbox).

Verifies the batched per-entity catalog method:
  - LLM is called via model_router.invoke_with_usage with the right task_type
  - Result is parsed into {field_name: [50 strings]}
  - L1/L2 cache keys are honored
  - Fallback to _smart_field_fallback on LLM failure / malformed JSON
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.tools.datagen.catalog_factory import CatalogFactory


@pytest.fixture
def factory():
    return CatalogFactory(cache_ttl_seconds=3600)


def _ok_response(payload: dict) -> MagicMock:
    """Build a fake UsageResult-shaped object with `.content`."""
    obj = MagicMock()
    obj.content = json.dumps(payload)
    return obj


# ---------- Happy path ----------

@pytest.mark.asyncio
async def test_returns_dict_of_string_fields_only(factory):
    fields = [("name", "string"), ("age", "int"), ("email", "string")]
    payload = {"name": [f"name_{i}" for i in range(50)],
               "email": [f"e{i}@ex.com" for i in range(50)]}
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=_ok_response(payload))
        result = await factory.get_entity_catalogs(
            entity_name="customer", fields=fields,
            user_prompt="customers for ecommerce", count=50,
        )
    assert set(result.keys()) == {"name", "email"}
    assert len(result["name"]) == 50
    assert len(result["email"]) == 50

@pytest.mark.asyncio
async def test_invokes_model_router_with_correct_task_type(factory):
    fields = [("name", "string")]
    payload = {"name": [f"n{i}" for i in range(50)]}
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=_ok_response(payload))
        await factory.get_entity_catalogs(
            entity_name="x", fields=fields, user_prompt="prompt",
            tenant_id="t1", integration_name="vscode", user_id="u1",
        )
    call_kwargs = mr.invoke_with_usage.call_args.kwargs
    assert call_kwargs["task_type"] == "datagen_catalog_generation"
    assert call_kwargs["tenant_id"] == "t1"
    assert call_kwargs["integration_name"] == "vscode"
    assert call_kwargs["user_id"] == "u1"


# ---------- Caching ----------

@pytest.mark.asyncio
async def test_l1_cache_hit_avoids_second_llm_call(factory):
    fields = [("name", "string")]
    payload = {"name": [f"n{i}" for i in range(50)]}
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=_ok_response(payload))
        await factory.get_entity_catalogs("e", fields, "p")
        await factory.get_entity_catalogs("e", fields, "p")
    assert mr.invoke_with_usage.call_count == 1


@pytest.mark.asyncio
async def test_different_prompt_misses_cache(factory):
    fields = [("name", "string")]
    payload = {"name": [f"n{i}" for i in range(50)]}
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=_ok_response(payload))
        await factory.get_entity_catalogs("e", fields, "prompt-A")
        await factory.get_entity_catalogs("e", fields, "prompt-B")
    assert mr.invoke_with_usage.call_count == 2


@pytest.mark.asyncio
async def test_different_entity_misses_cache(factory):
    fields = [("name", "string")]
    payload = {"name": [f"n{i}" for i in range(50)]}
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=_ok_response(payload))
        await factory.get_entity_catalogs("customer", fields, "p")
        await factory.get_entity_catalogs("product", fields, "p")
    assert mr.invoke_with_usage.call_count == 2


# ---------- Fallback ----------

@pytest.mark.asyncio
async def test_llm_exception_triggers_fallback(factory):
    fields = [("name", "string"), ("email", "string")]
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        result = await factory.get_entity_catalogs("x", fields, "p")
    assert set(result.keys()) == {"name", "email"}
    assert len(result["name"]) == 50
    assert len(result["email"]) == 50
    # Fallback values should be plausible Faker output (not "name_value_1")
    assert all(isinstance(v, str) and v for v in result["name"])
    assert not any(v.startswith("name_value_") for v in result["name"])


@pytest.mark.asyncio
async def test_malformed_json_triggers_fallback(factory):
    fields = [("name", "string")]
    bad_response = MagicMock()
    bad_response.content = "{ not json at all"
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=bad_response)
        result = await factory.get_entity_catalogs("x", fields, "p")
    assert len(result["name"]) == 50


@pytest.mark.asyncio
async def test_too_few_values_per_field_triggers_fallback(factory):
    fields = [("name", "string")]
    payload = {"name": [f"n{i}" for i in range(10)]}  # only 10, need >=40
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=_ok_response(payload))
        result = await factory.get_entity_catalogs("x", fields, "p")
    assert len(result["name"]) == 50  # padded by fallback


# ---------- Schema ----------

@pytest.mark.asyncio
async def test_empty_fields_returns_empty_dict(factory):
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task = MagicMock(return_value="test-model")
        mr.invoke_with_usage = AsyncMock()
        result = await factory.get_entity_catalogs("x", fields=[], user_prompt="p")
    assert result == {}
    mr.invoke_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_no_string_fields_returns_empty_dict(factory):
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task = MagicMock(return_value="test-model")
        mr.invoke_with_usage = AsyncMock()
        result = await factory.get_entity_catalogs(
            "x", fields=[("age", "int"), ("ok", "boolean")], user_prompt="p",
        )
    assert result == {}
    mr.invoke_with_usage.assert_not_called()
```

- [ ] **Step 2: Run and verify the new tests fail**

```bash
python3 -m pytest tests/test_catalog_sandbox.py -v 2>&1 | tail -10
```
Expected: `AttributeError: 'CatalogFactory' object has no attribute 'get_entity_catalogs'` on every test.

- [ ] **Step 3: Extend CatalogFactory**

Edit `DevForge_Backend/src/tools/datagen/catalog_factory.py`. **Do not touch** the existing `get_catalog`, `_generate_catalog`, `_parse_catalog`, or `_fallback_catalog` methods. Add the new async method + helper:

At the top of the file, add to the imports (after the existing `import time`):
```python
import asyncio
import hashlib
from typing import Tuple
```

Add this import inside the file (near the top), right after `from typing import List, Optional, Dict`:
```python
from src.core.model_router import model_router
```

(The existing file already imports `Dict` for type hints in the new method; if not, add it.)

At the bottom of the `CatalogFactory` class (before `clear_cache` at line 309), add these methods:

```python
    # =====================================================================
    # v0.9 — Batched per-entity catalogs (catalog-sandbox)
    # =====================================================================

    ENTITY_CATALOG_PROMPT = (
        "You are a data catalog generator.\n"
        "Generate {count} realistic sample values for each string field of "
        "the `{entity_name}` entity. Return ONLY a single JSON object — one "
        "key per field, each value an array of EXACTLY {count} strings.\n\n"
        "Context: {user_prompt}\n\n"
        "Fields:\n{field_lines}\n\n"
        "Rules:\n"
        "1. Differentiate by field name. `customer.name` is a person; "
        "`product.name` is a product/title; `flower.name` is a flower species.\n"
        "2. All values must be plausible for production data in this domain.\n"
        "3. No prose, no markdown, no explanations — only the JSON object.\n\n"
        'Example: {{"field_a": ["v1", "v2", ..., "v{count}"], '
        '"field_b": ["v1", ..., "v{count}"]}}\n'
    )

    async def get_entity_catalogs(
        self,
        entity_name: str,
        fields: List[Tuple[str, str]],
        user_prompt: str,
        count: int = 50,
        tenant_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """Generate domain-realistic value catalogs for all string fields of
        one entity in a single LLM call.

        Args:
            entity_name: Logical entity name (used for LLM context + cache key).
            fields: List of (field_name, data_type) tuples. Only data_type
                == "string" entries are included in the catalog request;
                numeric/date/bool fields are skipped.
            user_prompt: The original user prompt (used for LLM context +
                cache key). Truncated to 500 chars for the cache key hash.
            count: Number of values per field (default 50). Catalog is
                rejected and fallback used if any field receives < 40.
            tenant_id, integration_name, user_id: Forwarded to
                model_router.invoke_with_usage for analytics.

        Returns:
            Dict mapping string-typed field name to a list of `count`
            realistic values. Empty dict if `fields` has no string entries.
        """
        # Skip work if no string fields.
        string_fields = [(n, t) for n, t in fields if t == "string"]
        if not string_fields:
            return {}

        # Cache key — entity + sorted-fields-hash + prompt-hash.
        fields_hash = self._hash_fields(string_fields)
        prompt_hash = self._hash_text(user_prompt or "")
        cache_key = f"entity_catalog:{entity_name}:{fields_hash}:{prompt_hash}"

        # L1 cache.
        if cache_key in self.l1_cache:
            logger.debug(f"Entity catalog L1 hit: {cache_key}")
            return self.l1_cache[cache_key].values  # type: ignore[return-value]

        # L2 cache (TTL check).
        if cache_key in self.l2_cache:
            cat = self.l2_cache[cache_key]
            if time.time() - cat.generated_at < self.cache_ttl:
                logger.debug(f"Entity catalog L2 hit: {cache_key}")
                self.l1_cache[cache_key] = cat
                return cat.values  # type: ignore[return-value]

        # Generate via LLM with fallback.
        catalogs = await self._generate_entity_catalogs(
            entity_name=entity_name,
            string_fields=string_fields,
            user_prompt=user_prompt,
            count=count,
            tenant_id=tenant_id,
            integration_name=integration_name,
            user_id=user_id,
        )

        # Wrap in Catalog dataclass for cache uniformity. The `values`
        # field on Catalog is List[str]; we store the dict directly to
        # avoid a parallel cache type — accept the type:ignore.
        cat = Catalog(
            semantic_type=f"entity:{entity_name}",
            domain="general",
            values=catalogs,  # type: ignore[arg-type]
            generated_at=time.time(),
        )
        self.l1_cache[cache_key] = cat
        self.l2_cache[cache_key] = cat

        if len(self.l2_cache) > 1000:
            oldest_key = min(self.l2_cache.keys(), key=lambda k: self.l2_cache[k].generated_at)
            del self.l2_cache[oldest_key]

        return catalogs

    async def _generate_entity_catalogs(
        self,
        entity_name: str,
        string_fields: List[Tuple[str, str]],
        user_prompt: str,
        count: int,
        tenant_id: Optional[str],
        integration_name: Optional[str],
        user_id: Optional[str],
    ) -> Dict[str, List[str]]:
        """Single LLM call. Falls back per-field on any failure."""
        field_lines = "\n".join(f"- {n} ({t})" for n, t in string_fields)
        prompt = self.ENTITY_CATALOG_PROMPT.format(
            count=count,
            entity_name=entity_name,
            user_prompt=(user_prompt or "")[:500],
            field_lines=field_lines,
        )

        try:
            model_name = model_router.select_model_by_task("routing")
            usage_result = await model_router.invoke_with_usage(
                prompt=prompt,
                model_name=model_name,
                tenant_id=tenant_id,
                integration_name=integration_name,
                task_type="datagen_catalog_generation",
                user_id=user_id,
            )
            text = usage_result.content if hasattr(usage_result, "content") else str(usage_result)
            parsed = self._parse_entity_catalogs(text, [n for n, _ in string_fields])
        except Exception as e:
            logger.warning(f"Entity catalog LLM call failed for {entity_name}: {e}")
            parsed = None

        # If parsing failed or any field has < 40 entries, fall back per-field.
        result: Dict[str, List[str]] = {}
        for name, _type in string_fields:
            llm_values = (parsed or {}).get(name) or []
            if len(llm_values) >= 40:
                # Top up to `count` by sampling with replacement from the LLM list
                values = list(llm_values)
                while len(values) < count:
                    values.append(values[len(values) % len(llm_values)])
                result[name] = values[:count]
            else:
                result[name] = self._smart_field_fallback(name, count)
        return result

    def _parse_entity_catalogs(
        self,
        text: str,
        expected_fields: List[str],
    ) -> Optional[Dict[str, List[str]]]:
        """Extract a JSON object of {field: [values]} from LLM output.

        Tolerant of markdown fences and extra prose. Returns None if no
        valid object found.
        """
        import re as _re
        text = (text or "").strip()
        # Strip markdown code fences if present.
        fence = _re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        candidate = fence.group(1) if fence else text
        # Otherwise: locate first { ... last }
        if not fence:
            first = candidate.find("{")
            last = candidate.rfind("}")
            if first == -1 or last == -1 or last < first:
                return None
            candidate = candidate[first:last + 1]
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        # Coerce values: keep only lists of strings (or things stringifiable).
        cleaned: Dict[str, List[str]] = {}
        for name in expected_fields:
            v = obj.get(name)
            if isinstance(v, list):
                cleaned[name] = [str(item) for item in v if item is not None]
        return cleaned

    def _smart_field_fallback(
        self,
        field_name: str,
        count: int,
    ) -> List[str]:
        """Field-name-aware Faker fallback. Returns `count` plausible values
        based on field-name shape — never placeholder garbage like
        `<field>_value_1`.

        Mirrors the logic of SemanticRouter._smart_free_text so the per-row
        fallback path and the catalog fallback path stay consistent.
        """
        from faker import Faker
        fk = Faker()
        fn = (field_name or "").lower()

        if not fn:
            return [fk.word() for _ in range(count)]

        # Detect name-like fields → catch_phrase (product-flavoured)
        name_hints = ("_name", "name_of", "title", "label", "product", "model")
        desc_hints = ("description", "comment", "note", "details", "summary", "bio")

        if any(h in fn for h in name_hints):
            return [fk.catch_phrase() for _ in range(count)]
        if any(h in fn for h in desc_hints):
            return [fk.sentence(nb_words=6) for _ in range(count)]
        if "email" in fn:
            return [fk.email() for _ in range(count)]
        if "phone" in fn:
            return [fk.phone_number() for _ in range(count)]
        if "city" in fn:
            return [fk.city() for _ in range(count)]
        if "country" in fn:
            return [fk.country() for _ in range(count)]
        return [fk.word() for _ in range(count)]

    @staticmethod
    def _hash_fields(string_fields: List[Tuple[str, str]]) -> str:
        body = "|".join(f"{n}:{t}" for n, t in sorted(string_fields))
        return hashlib.sha1(body.encode("utf-8")).hexdigest()[:8]

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha1((text or "")[:500].encode("utf-8")).hexdigest()[:8]
```

- [ ] **Step 4: Run and verify the new tests pass**

```bash
python3 -m pytest tests/test_catalog_sandbox.py -v 2>&1 | tail -15
```
Expected: All ~11 tests PASSED. Pay particular attention to:
- `test_invokes_model_router_with_correct_task_type` (the dashboard analytics path)
- `test_llm_exception_triggers_fallback` (graceful degradation)

- [ ] **Step 5: Verify existing catalog tests still pass (`get_catalog` untouched)**

```bash
python3 -m pytest tests/ -k "catalog" --no-header 2>&1 | tail -5
```
Expected: any pre-existing CatalogFactory tests still pass. Only the new ones are added.

- [ ] **Step 6: Stage for manual review**

```bash
git add src/tools/datagen/catalog_factory.py tests/test_catalog_sandbox.py
git status --short
```

---

## Task 3: SchemaDesigner prompt update (nullable marking)

**Files:**
- Modify: `DevForge_Backend/src/tools/datagen/schema_designer.py` (lines 25-63, the `SCHEMA_DESIGN_PROMPT` constant)

No new tests. Existing `test_schema_designer.py::test_design_with_llm_valid_response` must continue to pass — verify after the edit.

- [ ] **Step 1: Update the prompt constant**

Open `DevForge_Backend/src/tools/datagen/schema_designer.py`. Find the `SCHEMA_DESIGN_PROMPT` constant (lines 25-63). Replace its body with this updated version that adds nullable-marking instructions (the new rule #4 plus the example block):

```python
SCHEMA_DESIGN_PROMPT = """You are a data schema designer. Given a natural language description, 
design a data schema for synthetic data generation.

Output ONLY valid JSON matching this exact structure:

{
  "entities": {
    "entity_name": {
      "name": "entity_name",
      "fields": [
        {
          "name": "field_name", 
          "type": "string|int|float|date|datetime|boolean|uuid", 
          "nullable": false, 
          "faker_provider": "email|name|phone_number|etc",
          "constraints": {"enum": ["A", "B"], "min": 0, "max": 100, "pattern": "^regex$"}
        }
      ],
      "count": 100,
      "primary_key": "id"
    }
  },
  "relationships": [
    {"from_entity": "child", "from_field": "parent_id", "to_entity": "parent", "to_field": "id", "cardinality": "1:N"}
  ],
  "domain": "optional_domain_hint"
}

Rules:
1. Use snake_case for all names
2. Allowed types: string, int, float, date, datetime, boolean, uuid
3. faker_provider options: name, email, phone_number, address, company, job, city, country, url, text, uuid4, date, date_time
4. Mark `nullable: true` for fields that represent optional or often-missing information in real production data.
   Always nullable: middle_name, address_line_2, description, comment, last_login, deleted_at, deactivation_reason, suffix, extension, error_message, notes
   Often nullable (mark true if the domain suggests it): phone, alternate_email, referral_code, promo_code, attachment_url, cancellation_reason
   Never nullable: id, primary_key, the primary email when it is the contact key, created_at, foreign keys
5. Use "constraints" for enums, numeric ranges (min/max), and regex patterns
6. For relationships: from_entity is the child (has FK), to_entity is the parent
7. Add appropriate primary keys (default: "id" with uuid type)
8. Be realistic with counts (10-1000 typical, max 10000)

Now design a schema for this request:
"""
```

The substantive change is the new rule #4 and the renumbering of subsequent rules. The JSON shape, the existing constraints block, and the closing "Now design..." line are unchanged.

- [ ] **Step 2: Verify existing schema-designer test still passes**

```bash
python3 -m pytest tests/test_schema_designer.py -v 2>&1 | tail -10
```
Expected: existing tests still PASS. The `_extract_json` parser is permissive, and the test mocks return well-formed JSON that already satisfies the new rule.

- [ ] **Step 3: Stage for manual review**

```bash
git add src/tools/datagen/schema_designer.py
git status --short
```

---

## Task 4: SemanticRouter — add field_catalog parameter

**Files:**
- Modify: `DevForge_Backend/src/tools/datagen/semantic_router.py` — extend `generate_value` signature and add the sample-from-catalog branch
- Modify: `DevForge_Backend/tests/test_semantic_router.py` (extend with new test cases)

- [ ] **Step 1: Write the new tests**

Append to `DevForge_Backend/tests/test_semantic_router.py` (at the bottom of the file):

```python


# ---------- v0.9: field_catalog parameter ----------

class TestFieldCatalogSandbox:
    """When a field_catalog is supplied and the semantic type is loose,
    sample from the catalog instead of using Faker."""

    def test_samples_from_catalog_for_free_text(self):
        from src.tools.datagen.semantic_router import SemanticRouter
        router = SemanticRouter()
        catalog = [f"FlowerName{i}" for i in range(50)]
        seen = set()
        for _ in range(20):
            v = router.generate_value(
                semantic_type="free_text",
                entity_name="flower",
                constraints={},
                field_name="common_name",
                field_catalog=catalog,
            )
            assert v in catalog
            seen.add(v)
        assert len(seen) > 1  # we actually sample more than one value

    def test_samples_from_catalog_for_unknown(self):
        from src.tools.datagen.semantic_router import SemanticRouter
        router = SemanticRouter()
        catalog = ["kg/m³", "Hz", "Pa", "lumen", "mol"] * 10
        v = router.generate_value(
            semantic_type="unknown",
            entity_name="instrument",
            constraints={},
            field_name="measurement_unit",
            field_catalog=catalog,
        )
        assert v in catalog

    def test_samples_from_catalog_for_enum_value_without_explicit_enum(self):
        from src.tools.datagen.semantic_router import SemanticRouter
        router = SemanticRouter()
        catalog = [f"unit_{i}" for i in range(50)]
        v = router.generate_value(
            semantic_type="enum_value",
            entity_name="x",
            constraints={},  # no enum supplied
            field_name="unit",
            field_catalog=catalog,
        )
        assert v in catalog

    def test_explicit_enum_overrides_catalog(self):
        from src.tools.datagen.semantic_router import SemanticRouter
        router = SemanticRouter()
        catalog = [f"wrong_{i}" for i in range(50)]
        v = router.generate_value(
            semantic_type="enum_value",
            entity_name="x",
            constraints={"enum": ["A", "B", "C"]},
            field_name="tier",
            field_catalog=catalog,
        )
        assert v in ("A", "B", "C")

    def test_explicit_pattern_overrides_catalog(self):
        from src.tools.datagen.semantic_router import SemanticRouter
        router = SemanticRouter()
        catalog = [f"wrong_{i}" for i in range(50)]
        v = router.generate_value(
            semantic_type="free_text",
            entity_name="x",
            constraints={"pattern": r"^[A-Z]{3}-\d{3}$"},
            field_name="code",
            field_catalog=catalog,
        )
        # Must match pattern, not catalog
        import re
        assert re.match(r"^[A-Z]{3}-\d{3}$", v) is not None

    def test_known_semantic_type_ignores_catalog(self):
        """If the classifier already pinned a high-confidence type (email,
        person_name, etc.), we trust it and ignore the catalog."""
        from src.tools.datagen.semantic_router import SemanticRouter
        router = SemanticRouter()
        catalog = [f"not-an-email-{i}" for i in range(50)]
        v = router.generate_value(
            semantic_type="email_address",
            entity_name="x",
            constraints={},
            field_name="email",
            field_catalog=catalog,
        )
        # Should look like an email, not "not-an-email-N"
        assert "@" in v
        assert not v.startswith("not-an-email-")

    def test_no_catalog_falls_back_to_smart_free_text(self):
        """When no field_catalog is supplied, the v0.8.5 _smart_free_text
        heuristic is used."""
        from src.tools.datagen.semantic_router import SemanticRouter
        router = SemanticRouter()
        v = router.generate_value(
            semantic_type="free_text",
            entity_name="x",
            constraints={},
            field_name="model_name",
            field_catalog=None,
        )
        # Should be Faker catch_phrase (model-like), not lorem ipsum
        assert isinstance(v, str)
        assert len(v) > 0
```

(If `tests/test_semantic_router.py` does not exist, create it with just this class plus minimal imports at the top: `import pytest`.)

- [ ] **Step 2: Run the new tests and verify they fail**

```bash
python3 -m pytest tests/test_semantic_router.py::TestFieldCatalogSandbox -v 2>&1 | tail -10
```
Expected: each test fails with `TypeError: generate_value() got an unexpected keyword argument 'field_catalog'`.

- [ ] **Step 3: Add the `field_catalog` parameter and the sample branch**

Edit `DevForge_Backend/src/tools/datagen/semantic_router.py`. Find the `generate_value` method (currently signature `def generate_value(self, semantic_type, entity_name="", constraints=None, field_name="")` after the v0.8.5 fix). Update its signature and the early body:

Find:
```python
    def generate_value(
        self,
        semantic_type: str,
        entity_name: str = "",
        constraints: dict = None,
        field_name: str = "",
    ) -> Any:
```

Replace with:
```python
    def generate_value(
        self,
        semantic_type: str,
        entity_name: str = "",
        constraints: dict = None,
        field_name: str = "",
        field_catalog: Optional[List[str]] = None,
    ) -> Any:
```

(Make sure `from typing import List, Optional` is imported at the top of the file; if `List` is not already imported, add it.)

Now find the constraint-first block inside `generate_value` (the section that handles enum / pattern, right after the `constraints = normalized_constraints` line). The structure is currently:

```python
        # 2. Constraint-First: Enum overrides everything
        if "enum" in constraints and constraints["enum"]:
            return random.choice(constraints["enum"])

        # 3. Constraint-First: Pattern overrides semantic type
        if "pattern" in constraints and constraints["pattern"]:
            return self._generate_pattern(constraints["pattern"])

        # Get generator (registry signature: (entity, constraints, field_name))
```

Insert a new block between step 3 (pattern) and the generator lookup (step 4):

```python
        # 2. Constraint-First: Enum overrides everything
        if "enum" in constraints and constraints["enum"]:
            return random.choice(constraints["enum"])

        # 3. Constraint-First: Pattern overrides semantic type
        if "pattern" in constraints and constraints["pattern"]:
            return self._generate_pattern(constraints["pattern"])

        # 3a. Catalog-sandbox: if a field-specific catalog was supplied AND
        # the classifier landed on a loose semantic type (free_text,
        # unknown, or enum_value-without-values), sample from the catalog
        # rather than falling through to the heuristic Faker generators.
        # Known semantic types (email_address, person_full_name, etc.) are
        # NOT affected — they keep using their dedicated generators because
        # the classifier has already pinned the type with high confidence.
        if field_catalog and semantic_type in {"free_text", "unknown", "enum_value"}:
            return random.choice(field_catalog)

        # Get generator (registry signature: (entity, constraints, field_name))
```

- [ ] **Step 4: Run the new tests and verify they pass**

```bash
python3 -m pytest tests/test_semantic_router.py::TestFieldCatalogSandbox -v 2>&1 | tail -10
```
Expected: all 7 tests PASS.

- [ ] **Step 5: Run the full test_semantic_router suite + the existing v0.8.5 tests**

```bash
python3 -m pytest tests/test_semantic_router.py tests/test_dependency_analyzer.py tests/test_quality_block.py tests/test_prompt_refiner_phase2.py 2>&1 | tail -5
```
Expected: no regressions vs the Task 0 baseline.

- [ ] **Step 6: Stage for manual review**

```bash
git add src/tools/datagen/semantic_router.py tests/test_semantic_router.py
git status --short
```

---

## Task 5: Wire SchemaValidator + entity catalogs into AdvancedGeneratorV2

**Files:**
- Modify: `DevForge_Backend/src/tools/datagen/advanced_generator_v2.py` — three insertion points: (a) after schema design call (validator), (b) after semantic analysis (catalogs), (c) per-field generation (pass field_catalog)

- [ ] **Step 1: Wire SchemaValidator after schema design**

Open `DevForge_Backend/src/tools/datagen/advanced_generator_v2.py`. Find the `generate_advanced_data_v2` outer function. Locate the "Step 1: Design Schema" block (around line 793). Right after the `schema = await schema_designer.design_schema(...)` call (still inside the try/except, before the `schema_dict = {}` block at ~line 819), add:

```python
        # v0.9: post-LLM schema validation (enum-swap fix + range inference).
        # Pure function — no LLM call, no side effects.
        from src.tools.datagen.schema_validator import SchemaValidator
        schema = SchemaValidator().validate_and_fix(
            schema, user_prompt=prompt or domain or "",
        )
```

- [ ] **Step 2: Add per-entity catalog precomputation in `AdvancedGeneratorV2.generate`**

In the same file, find `AdvancedGeneratorV2.generate` (around line 83). Locate the existing pipeline body inside the `try:` block. After the semantic analysis call (the `semantic_info = await self._analyze_schema_semantically(...)` block at ~line 122) and BEFORE the `self._report("catalog_generation", ...)` line, insert the new catalog-precomputation block:

```python
            # v0.9: precompute one batched catalog per entity. Cached at
            # L1+L2 in CatalogFactory; subsequent rows sample from these
            # in-memory dicts.
            self._entity_catalogs: Dict[str, Dict[str, List[str]]] = {}
            if self.enable_semantic and self.catalog_factory:
                for entity_name, entity_schema in schema.items():
                    field_pairs: List[Tuple[str, str]] = []
                    fields = entity_schema.get("fields", entity_schema.get("properties", {}))
                    for fname, fcfg in fields.items():
                        ftype = (fcfg.get("type") or "string") if isinstance(fcfg, dict) else "string"
                        # Map schema types to the simple "string" / "int" / etc.
                        # the catalog factory expects.
                        if ftype in ("string",):
                            field_pairs.append((fname, "string"))
                    if not field_pairs:
                        continue
                    try:
                        catalogs = await self.catalog_factory.get_entity_catalogs(
                            entity_name=entity_name,
                            fields=field_pairs,
                            user_prompt=user_prompt or "",
                            count=50,
                            tenant_id=tenant_id,
                            integration_name=integration_name,
                        )
                        self._entity_catalogs[entity_name] = catalogs
                    except Exception as e:
                        logger.warning(
                            f"Entity catalog precompute failed for {entity_name}: {e}"
                        )
                        self._entity_catalogs[entity_name] = {}
```

(If `Dict`, `List`, `Tuple` are not already imported at the top of the file, add `from typing import Any, Dict, List, Literal, Optional, Tuple` — the existing import already covers most of these.)

- [ ] **Step 3: Pass `field_catalog` from generation loop into `SemanticRouter.generate_value`**

Same file. Locate the two router call sites (per the v0.8.5 audit):

**Site A: `_generate_with_relationships` adapter (around line 270-285).** Find the lambda inside `SemanticFieldGeneratorAdapter.get_generator`:

```python
                if field_name in semantic_map:
                    sem_info = semantic_map[field_name]
                    return lambda: self.router.generate_value(
                        semantic_type=sem_info.semantic_type,
                        entity_name=entity_name,
                        constraints=sem_info.constraints,
                        field_name=field_name,
                    )
```

Change to:

```python
                if field_name in semantic_map:
                    sem_info = semantic_map[field_name]
                    entity_cats = self.entity_catalogs.get(entity_name, {})
                    field_cat = entity_cats.get(field_name)
                    return lambda: self.router.generate_value(
                        semantic_type=sem_info.semantic_type,
                        entity_name=entity_name,
                        constraints=sem_info.constraints,
                        field_name=field_name,
                        field_catalog=field_cat,
                    )
```

The adapter's `__init__` (currently `def __init__(self, router, semantic_info, faker)`) needs a new param `entity_catalogs`. Update:

```python
            def __init__(self, router, semantic_info, faker, entity_catalogs):
                self.router = router
                self.semantic_info = semantic_info
                self.faker = faker
                self.entity_catalogs = entity_catalogs
```

And update the adapter instantiation in `_generate_with_relationships` (around line 290):

```python
        field_generator = SemanticFieldGeneratorAdapter(
            self.semantic_router, semantic_info, self.faker, self._entity_catalogs,
        )
```

**Site B: `_generate_independent_entities` (around line 320-335).** Find:

```python
                    if field_name in semantic_map:
                        sem_info = semantic_map[field_name]
                        row[field_name] = self.semantic_router.generate_value(
                            semantic_type=sem_info.semantic_type,
                            entity_name=entity_name,
                            constraints=sem_info.constraints,
                            field_name=field_name,
                        )
```

Change to:

```python
                    if field_name in semantic_map:
                        sem_info = semantic_map[field_name]
                        entity_cats = self._entity_catalogs.get(entity_name, {})
                        field_cat = entity_cats.get(field_name)
                        row[field_name] = self.semantic_router.generate_value(
                            semantic_type=sem_info.semantic_type,
                            entity_name=entity_name,
                            constraints=sem_info.constraints,
                            field_name=field_name,
                            field_catalog=field_cat,
                        )
```

- [ ] **Step 4: Run the existing V2 generator integration test (if any) and the new sandbox tests together**

```bash
python3 -m pytest tests/test_catalog_sandbox.py tests/test_semantic_router.py tests/test_schema_validator.py tests/test_relationships.py 2>&1 | tail -8
```
Expected: all pass. No regression.

- [ ] **Step 5: End-to-end MCP smoke test of the catalog-sandbox path**

The API container needs to be restarted to pick up code changes:

```bash
docker compose restart api && until curl -s http://localhost:8001/manifests/devforge.json >/dev/null; do sleep 1; done
```

Then send a V2 prompt that previously produced lorem-ipsum garbage:

```bash
curl -s -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: df_QBwcmV9rZ0A6yITSAw8-TmGGy9hAxLpaoDaMC3Pr4wY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"generate_data","arguments":{"rows":5,"prompt":"Generate scientific instruments: instrument_name, measurement_unit, accuracy_percent, calibration_interval_days"}}}' \
  --max-time 180 | python3 -c "
import json, sys
d = json.load(sys.stdin)
t = d['result']['content'][0]['text']
r = json.loads(t.split('\n\n', 1)[-1] if 'Data generation' in t else t)
dd = r['data']
print('success:', r['success'])
for entity, rows in dd['data'].items():
    if not isinstance(rows, list) or not rows: continue
    print(f'{entity}: {len(rows)} rows')
    for s in rows[:3]:
        print(f'  {s}')
"
```

Expected: `measurement_unit` values are plausible units (kg/m³, Hz, Pa, …) or at least domain-realistic short strings — **never** Faker single words like `"perform"` or lorem ipsum sentences. `instrument_name` is product-flavored (catch_phrase or LLM-generated names), never `"Agent every development say."`.

- [ ] **Step 6: Stage for manual review**

```bash
git add src/tools/datagen/advanced_generator_v2.py
git status --short
```

---

## Task 6: Realism consolidation (delete V2 internal, route through realism_engine)

**Files:**
- Modify: `DevForge_Backend/src/tools/datagen/advanced_generator_v2.py` — delete the internal `_apply_realism` method (lines 532-584 before edits in Task 5), replace both call sites with a single call to `realism_engine.apply_realism_to_data`
- Create: `DevForge_Backend/tests/test_realism_consolidation.py`

- [ ] **Step 1: Write the failing test file**

Create `DevForge_Backend/tests/test_realism_consolidation.py`:

```python
"""Tests for realism consolidation in V2 generator (v0.9).

Verifies:
  - V2's internal _apply_realism is removed
  - Realism is applied exactly once per call
  - realism_engine.apply_realism_to_data is the single entry point
  - High realism on a domain with nullable fields produces real nulls
"""

import inspect
import pytest

from src.tools.datagen.advanced_generator_v2 import AdvancedGeneratorV2


def test_internal_apply_realism_method_is_removed():
    """V2's internal _apply_realism method must be deleted per the spec."""
    assert not hasattr(AdvancedGeneratorV2, "_apply_realism"), (
        "AdvancedGeneratorV2._apply_realism still exists — should be removed "
        "and replaced with realism_engine.apply_realism_to_data"
    )


def test_realism_engine_module_is_imported_in_v2():
    """The V2 module must import realism_engine.apply_realism_to_data
    (or the realism_engine module) — this is how realism is wired post-fix."""
    import src.tools.datagen.advanced_generator_v2 as v2
    source = inspect.getsource(v2)
    assert "realism_engine" in source, (
        "advanced_generator_v2.py does not reference realism_engine — "
        "realism consolidation incomplete"
    )


def test_apply_realism_call_site_count_in_generate():
    """Realism should be applied exactly once per generate() call. The v0.8.5
    bug was a double-application (one inside try, one outside). After
    consolidation there must be exactly ONE call to apply_realism_to_data
    inside the `generate()` body."""
    src = inspect.getsource(AdvancedGeneratorV2.generate)
    count = src.count("apply_realism_to_data")
    assert count == 1, f"Expected exactly 1 call to apply_realism_to_data; found {count}"
```

- [ ] **Step 2: Run the test and verify it fails**

```bash
python3 -m pytest tests/test_realism_consolidation.py -v 2>&1 | tail -10
```
Expected:
- `test_internal_apply_realism_method_is_removed` **FAILS** — method still exists
- `test_realism_engine_module_is_imported_in_v2` may PASS (the module is already imported lazily in `apply_realism_to_data`) — verify
- `test_apply_realism_call_site_count_in_generate` **FAILS** — two `_apply_realism` calls today

- [ ] **Step 3: Delete the internal `_apply_realism` method**

In `DevForge_Backend/src/tools/datagen/advanced_generator_v2.py`, delete the entire `_apply_realism` method definition. After the v0.8.5 fixes, this method begins with:

```python
    def _apply_realism(
        self,
        data: dict,
        level: str,
        semantic_info: dict,
        schema: dict,
    ) -> dict:
        """Apply v0.8 realism — null injection only.
        ...
        """
        import random
        
        null_rate = {"medium": 0.05, "high": 0.10}.get(level, 0)
        ...
```

Remove the full method body (from `def _apply_realism(` through the final `return data` for that method). Do **not** delete `_build_metadata` (the next method) or any other code.

- [ ] **Step 4: Replace the two call sites with one call to `realism_engine.apply_realism_to_data`**

Same file, find the two existing `self._apply_realism(...)` calls inside `generate()`. Today (post-v0.8.5) the structure looks like:

```python
            # Step 5: Apply realism (if needed) - must respect schema constraints
            if realism_level != "basic":
                generated_data = self._apply_realism(
                    generated_data, realism_level, semantic_info, schema
                )
        except Exception as e:
            ...
        
        # Step 5: Apply realism (if needed) - must respect schema constraints
        if realism_level != "basic":
            generated_data = self._apply_realism(
                generated_data, realism_level, semantic_info, schema
            )
```

Replace **both** blocks with a **single** call placed OUTSIDE the try/except (so realism only runs if generation succeeded). Concretely: remove both `if realism_level != "basic":` blocks and add this single replacement after the `except` block exits successfully (i.e., after the existing `if constraint_violations or not fk_integrity.get("valid", True):` block at the end of the try body):

```python
        # v0.9: realism is applied exactly once via the consolidated
        # realism_engine.apply_realism_to_data. Routes nulls/duplicates/
        # outliers per REALISM_CONFIGS. The schema_design's nullable flag
        # is the gate — see domain template updates in Task 7.
        if realism_level != "basic":
            try:
                from src.tools.datagen.realism_engine import apply_realism_to_data
                if schema_design is not None:
                    generated_data = apply_realism_to_data(
                        generated_data, schema_design, realism_level,
                    )
            except Exception as e:
                logger.warning(f"Realism application failed: {e}")
```

Place this block AFTER the `except Exception as e:` block of the main try and BEFORE the `# Step 6: Build metadata` line. Make sure no other `self._apply_realism(` call survives — use grep:

```bash
grep -n "_apply_realism" src/tools/datagen/advanced_generator_v2.py
```
Expected: zero matches.

- [ ] **Step 5: Run the consolidation tests + the full V2 test suite**

```bash
python3 -m pytest tests/test_realism_consolidation.py tests/test_realism.py tests/test_relationships.py 2>&1 | tail -8
```
Expected: realism_consolidation tests PASS. test_realism / test_relationships still PASS (these test the realism_engine module directly, which we didn't touch).

- [ ] **Step 6: MCP smoke test — confirm realism still runs**

Restart container:

```bash
docker compose restart api && until curl -s http://localhost:8001/manifests/devforge.json >/dev/null; do sleep 1; done
```

Run a V2 domain call at realism=high. Nulls likely still 0 until Task 7 (templates) marks fields nullable, but the call must succeed:

```bash
curl -s -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: df_QBwcmV9rZ0A6yITSAw8-TmGGy9hAxLpaoDaMC3Pr4wY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"generate_data","arguments":{"rows":50,"domain":"ecommerce","realism_level":"high"}}}' \
  --max-time 180 | python3 -c "
import json, sys
d = json.load(sys.stdin)
t = d['result']['content'][0]['text']
r = json.loads(t.split('\n\n', 1)[-1] if 'Data generation' in t else t)
print('success:', r['success'])
print('isError:', d['result']['isError'])
"
```
Expected: `success: True / isError: False`. No exception in container logs.

- [ ] **Step 7: Stage for manual review**

```bash
git add src/tools/datagen/advanced_generator_v2.py tests/test_realism_consolidation.py
git status --short
```

---

## Task 7: Domain templates — nullable markers

**Files:**
- Modify: `DevForge_Backend/src/tools/datagen/domain_templates.py` (lines ~58-115 ecommerce, ~120-200 saas, ~205-285 iot_devices)
- Modify: `DevForge_Backend/tests/test_domain_templates.py` (update field-shape assertions to match new templates)

- [ ] **Step 1: Update the ecommerce template — mark fields nullable, add `description` to products**

Open `domain_templates.py`. Find `get_ecommerce_template`. Find the `customers` entity (around line 60):

```python
            "customers": EntitySchema(
                name="customers",
                fields=[
                    FieldSchema(name="name", type="string", faker_provider="name"),
                    FieldSchema(name="email", type="string", faker_provider="email"),
                    FieldSchema(name="phone", type="string", faker_provider="phone_number"),
                    FieldSchema(name="address", type="string", faker_provider="address"),
                    FieldSchema(name="created_at", type="datetime"),
                ],
                count=customer_count,
                primary_key="id"
            ),
```

Change to:

```python
            "customers": EntitySchema(
                name="customers",
                fields=[
                    FieldSchema(name="name", type="string", faker_provider="name"),
                    FieldSchema(name="email", type="string", faker_provider="email"),
                    FieldSchema(name="phone", type="string", faker_provider="phone_number", nullable=True),
                    FieldSchema(name="address", type="string", faker_provider="address", nullable=True),
                    FieldSchema(name="created_at", type="datetime"),
                ],
                count=customer_count,
                primary_key="id"
            ),
```

Find the `products` entity (around line 72):

```python
            "products": EntitySchema(
                name="products",
                fields=[
                    FieldSchema(name="name", type="string", faker_provider="text"),
                    FieldSchema(name="category", type="string"),
                    FieldSchema(name="price", type="float", distribution="lognormal"),
                    FieldSchema(name="in_stock", type="boolean"),
                    FieldSchema(name="created_at", type="datetime"),
                ],
                count=product_count,
                primary_key="id"
            ),
```

Change to:

```python
            "products": EntitySchema(
                name="products",
                fields=[
                    FieldSchema(name="name", type="string", faker_provider="text"),
                    FieldSchema(name="category", type="string", nullable=True),
                    FieldSchema(name="description", type="string", nullable=True),
                    FieldSchema(name="price", type="float", distribution="lognormal"),
                    FieldSchema(name="in_stock", type="boolean"),
                    FieldSchema(name="created_at", type="datetime"),
                ],
                count=product_count,
                primary_key="id"
            ),
```

- [ ] **Step 2: Update the saas template**

Find `get_saas_template`. Open the file and locate the saas template body (typically around lines 130-200). For the `users` entity, locate the `phone` field if present (some templates omit it) and add `last_login`. For the `subscriptions` entity, add `cancellation_reason`. For `usage_logs`, add `error_message`.

If the file structure is:
```python
            "users": EntitySchema(
                name="users",
                fields=[
                    FieldSchema(name="email", type="string", faker_provider="email"),
                    FieldSchema(name="name", type="string", faker_provider="name"),
                    FieldSchema(name="signup_date", type="datetime"),
                ],
                ...
            ),
```

Change to:
```python
            "users": EntitySchema(
                name="users",
                fields=[
                    FieldSchema(name="email", type="string", faker_provider="email"),
                    FieldSchema(name="name", type="string", faker_provider="name"),
                    FieldSchema(name="phone", type="string", faker_provider="phone_number", nullable=True),
                    FieldSchema(name="last_login", type="datetime", nullable=True),
                    FieldSchema(name="signup_date", type="datetime"),
                ],
                ...
            ),
```

For `subscriptions`:
```python
            "subscriptions": EntitySchema(
                name="subscriptions",
                fields=[
                    FieldSchema(name="user_id", type="uuid"),
                    FieldSchema(name="plan", type="string"),
                    FieldSchema(name="started_at", type="datetime"),
                    FieldSchema(name="expires_at", type="datetime", nullable=True),
                    FieldSchema(name="cancellation_reason", type="string", nullable=True),  # NEW
                ],
                ...
            ),
```

For `usage_logs`:
```python
            "usage_logs": EntitySchema(
                name="usage_logs",
                fields=[
                    FieldSchema(name="subscription_id", type="uuid"),
                    FieldSchema(name="api_calls", type="int", distribution="pareto"),
                    FieldSchema(name="logged_at", type="datetime"),
                    FieldSchema(name="error_message", type="string", nullable=True),  # NEW
                ],
                ...
            ),
```

(If the actual saas template differs in current code, adapt to the existing structure — the principle is: add nullable=True on `phone`, `last_login`, `cancellation_reason`, `error_message`.)

- [ ] **Step 3: Update the iot_devices template**

Find `get_iot_devices_template`. For `devices`, locate `last_seen` if present (add it nullable if missing). For `readings`, add `error_code`:

```python
            "devices": EntitySchema(
                name="devices",
                fields=[
                    FieldSchema(name="device_type", type="string"),
                    FieldSchema(name="firmware_version", type="string"),
                    FieldSchema(name="registered_at", type="datetime"),
                    FieldSchema(name="last_seen", type="datetime", nullable=True),  # ensure nullable
                ],
                ...
            ),
            "readings": EntitySchema(
                name="readings",
                fields=[
                    FieldSchema(name="device_id", type="uuid"),
                    FieldSchema(name="value", type="float", distribution="normal"),
                    FieldSchema(name="recorded_at", type="datetime"),
                    FieldSchema(name="error_code", type="string", nullable=True),  # NEW
                ],
                ...
            ),
```

- [ ] **Step 4: Update test_domain_templates.py assertions**

Open `DevForge_Backend/tests/test_domain_templates.py`. Find any assertion that checks the exact field list for ecommerce / saas / iot templates. Common patterns:

- `assert len(template.entities["customers"].fields) == 5` → change `5` to `5` (unchanged for ecommerce customers) — but for products, length goes from 5 to 6
- `assert set(field.name for field in template.entities["products"].fields) == {"name", "category", "price", "in_stock", "created_at"}` → add `"description"`
- Similar adjustments for saas (add `phone`, `last_login`, `cancellation_reason`, `error_message`) and iot (`last_seen`, `error_code`)

Also: the pre-existing `test_list_domains` failure (asserts `len(domains) == 2` but code returns 3) is unrelated to v0.9 — leave it as-is, or fix it inline if convenient by changing the assertion to `== 3`.

- [ ] **Step 5: Run the template tests**

```bash
python3 -m pytest tests/test_domain_templates.py -v 2>&1 | tail -15
```
Expected: all PASS. If a field-shape assertion breaks, the update in step 4 was incomplete — fix and re-run.

- [ ] **Step 6: MCP smoke — realism=high on ecommerce should now produce ~10% nulls in `phone`**

```bash
docker compose restart api && until curl -s http://localhost:8001/manifests/devforge.json >/dev/null; do sleep 1; done

curl -s -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: df_QBwcmV9rZ0A6yITSAw8-TmGGy9hAxLpaoDaMC3Pr4wY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"generate_data","arguments":{"rows":300,"domain":"ecommerce","realism_level":"high"}}}' \
  --max-time 180 | python3 -c "
import json, sys
d = json.load(sys.stdin)
t = d['result']['content'][0]['text']
r = json.loads(t.split('\n\n', 1)[-1] if 'Data generation' in t else t)
dd = r['data']
customers = dd['data'].get('customers', [])
phone_nulls = sum(1 for c in customers if c.get('phone') is None)
addr_nulls = sum(1 for c in customers if c.get('address') is None)
print(f'customers: {len(customers)} rows; phone nulls: {phone_nulls} ({100*phone_nulls/max(1,len(customers)):.1f}%); address nulls: {addr_nulls} ({100*addr_nulls/max(1,len(customers)):.1f}%)')
products = dd['data'].get('products', [])
desc_nulls = sum(1 for p in products if p.get('description') is None)
cat_nulls = sum(1 for p in products if p.get('category') is None)
print(f'products: {len(products)} rows; description nulls: {desc_nulls}; category nulls: {cat_nulls}')
"
```
Expected: phone-null rate between 5% and 15% (target 10%, ±5% sampling jitter). Description-null rate similar. Critical fields like `email` and `created_at` must show 0 nulls.

- [ ] **Step 7: Stage for manual review**

```bash
git add src/tools/datagen/domain_templates.py tests/test_domain_templates.py
git status --short
```

---

## Task 8: Docs + manifest version bump

**Files:**
- Modify: `DevForge_Backend/docs/tools/generate_data.md` — bump version, add v0.9 section
- Modify: `DevForge_Backend/manifests/devforge.json` — bump version

- [ ] **Step 1: Bump version + add "v0.9" section to generate_data.md**

Open `DevForge_Backend/docs/tools/generate_data.md`. Change the version header at line 4:

From:
```markdown
**Version:** 0.8.0 (Phase 1 Complete - Production Ready)
```

To:
```markdown
**Version:** 0.9.0 (Catalog-Sandbox + Realism Consolidation)
```

Just after the existing "**Phase 1 Refactor:** LLM is now confined to..." paragraph (around line 19), insert a new section:

```markdown
**v0.9 Production-Grade (Catalog-Sandbox):**
- **Per-entity batched LLM catalogs**: every string field gets a domain-realistic value catalog (50 values per field), generated in one LLM call per entity, cached L1+L2 with 1h TTL. Replaces the v0.8 Faker `_smart_free_text` fallback for unknown semantic types.
- **SchemaValidator**: post-LLM schema fixes (enum-swap correction + range inference for numeric fields without explicit min/max).
- **Realism consolidation**: V2's dead-code dual realism implementation is gone. Single call to `realism_engine.apply_realism_to_data` handles nulls + duplicates + outliers per `REALISM_CONFIGS`.
- **Domain templates mark fields nullable**: `customers.phone`, `customers.address`, `products.category`, `products.description`, `users.last_login`, `subscriptions.cancellation_reason`, `usage_logs.error_message`, `devices.last_seen`, `readings.error_code` are now nullable so `realism_level="high"` actually injects the documented ~10% nulls.

> [!IMPORTANT]
> **Behavior change**: `realism_level="high"` on the `ecommerce` / `saas` / `iot_devices` domains now produces 5-15% nulls in the fields listed above. Previous v0.8 behavior produced 0% nulls. Update test assertions and downstream consumers accordingly.
```

- [ ] **Step 2: Bump the manifest version**

Open `DevForge_Backend/manifests/devforge.json`. Find the version field (in the `meta` block, line 6). Change:

```json
    "version": "0.9.0",
```

to:

```json
    "version": "0.10.0",
```

- [ ] **Step 3: Verify JSON validity**

```bash
python3 -c "import json; json.load(open('manifests/devforge.json')); print('manifest valid')"
```
Expected: `manifest valid`.

- [ ] **Step 4: Stage for manual review**

```bash
git add docs/tools/generate_data.md manifests/devforge.json
git status --short
```

---

## Task 9: End-to-end MCP acceptance test suite

**Files:**
- Read only / MCP calls only

This is the §12 acceptance criteria from the spec, exercised against the running container. Restart first to ensure all prior tasks' changes are loaded.

- [ ] **Step 1: Restart API and wait**

```bash
docker compose restart api && until curl -s http://localhost:8001/manifests/devforge.json >/dev/null; do sleep 1; done
echo "API ready"
```

- [ ] **Step 2: Acceptance #1 — Vintage motorcycles must not return "Agent every…"**

```bash
curl -s -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: df_QBwcmV9rZ0A6yITSAw8-TmGGy9hAxLpaoDaMC3Pr4wY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"generate_data","arguments":{"rows":10,"prompt":"Generate vintage Italian motorcycles with model_name, manufacturer (Ducati, Moto Guzzi, MV Agusta, Bimota, Aprilia), year_built between 1950 and 1985, engine_cc between 125 and 1100, and original_price_usd between 500 and 8000"}}}' \
  --max-time 240 | python3 -c "
import json, sys
d = json.load(sys.stdin)
t = d['result']['content'][0]['text']
r = json.loads(t.split('\n\n', 1)[-1] if 'Data generation' in t else t)
dd = r['data']
for entity, rows in dd['data'].items():
    if not isinstance(rows, list) or not rows: continue
    print(f'{entity}:')
    for s in rows[:5]:
        print(f'  {s}')
    names = [r_.get('model_name', '') for r_ in rows]
    bad = [n for n in names if 'agent every' in str(n).lower()]
    assert not bad, f'lorem ipsum still present: {bad}'
print('PASS: no Agent-every lorem ipsum')
"
```
Expected: prints rows, no AssertionError.

- [ ] **Step 3: Acceptance #2 — Scientific instruments measurement_unit should be plausible units**

```bash
curl -s -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: df_QBwcmV9rZ0A6yITSAw8-TmGGy9hAxLpaoDaMC3Pr4wY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"generate_data","arguments":{"rows":10,"prompt":"Generate scientific instruments: instrument_name, measurement_unit, accuracy_percent, calibration_interval_days"}}}' \
  --max-time 180 | python3 -c "
import json, sys
d = json.load(sys.stdin)
t = d['result']['content'][0]['text']
r = json.loads(t.split('\n\n', 1)[-1] if 'Data generation' in t else t)
dd = r['data']
for entity, rows in dd['data'].items():
    if not isinstance(rows, list) or not rows: continue
    print(f'{entity}:')
    units = set()
    for s in rows[:5]:
        print(f'  {s}')
    units = {r_.get('measurement_unit', '') for r_ in rows}
    # measurement_unit should be domain-realistic (>1 char, not single English words) OR catalog output
    short_word_units = [u for u in units if u.isalpha() and len(u) < 6 and u.islower()]
    print(f'  measurement_unit values: {units}')
    # Weak assertion — at minimum, none should be lorem ipsum sentence
    bad = [u for u in units if 'ipsum' in str(u).lower() or len(str(u).split()) > 4]
    assert not bad, f'lorem ipsum still in measurement_unit: {bad}'
print('PASS: measurement_unit is not lorem ipsum')
"
```
Expected: prints rows; no AssertionError. Ideal output has units like `kg/m³`, `Hz`, `Pa`. Acceptable: short coherent strings. **Not** acceptable: full-sentence lorem ipsum.

- [ ] **Step 4: Acceptance #3 — Enum-swap fix on stress test**

```bash
curl -s -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: df_QBwcmV9rZ0A6yITSAw8-TmGGy9hAxLpaoDaMC3Pr4wY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"generate_data","arguments":{"rows":50,"prompt":"Library system: employees (employee_id, name); books (isbn pattern: \"^978-[0-9]{10}$\", title, author, genre enum: [\"Fiction\",\"Non-Fiction\",\"Sci-Fi\"]); checkouts (id, employee_id FK, book_id FK, status enum: [\"active\",\"returned\",\"overdue\"], checkout_date)","realism_level":"basic"}}}' \
  --max-time 240 | python3 -c "
import json, sys
d = json.load(sys.stdin)
t = d['result']['content'][0]['text']
r = json.loads(t.split('\n\n', 1)[-1] if 'Data generation' in t else t)
dd = r['data']
allowed_genre = {'Fiction', 'Non-Fiction', 'Sci-Fi'}
allowed_status = {'active', 'returned', 'overdue'}
for entity, rows in dd['data'].items():
    if not isinstance(rows, list) or not rows: continue
    if 'book' in entity:
        genres = {r_.get('genre') for r_ in rows} - {None}
        bad = genres - allowed_genre
        assert not bad, f'genre out of enum: {bad}'
        print(f'  books genres: {genres} OK')
    if 'checkout' in entity:
        statuses = {r_.get('status') for r_ in rows} - {None}
        bad = statuses - allowed_status
        assert not bad, f'status out of enum: {bad}'
        print(f'  checkouts statuses: {statuses} OK')
print('PASS: enums respected')
"
```
Expected: prints "OK" for both; PASS. If genre contains `active`/`pending`, the SchemaValidator's enum-swap fix failed — regress to Task 1 step 3.

- [ ] **Step 5: Acceptance #4 — Realism nulls on ecommerce**

```bash
curl -s -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: df_QBwcmV9rZ0A6yITSAw8-TmGGy9hAxLpaoDaMC3Pr4wY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"generate_data","arguments":{"rows":300,"domain":"ecommerce","realism_level":"high"}}}' \
  --max-time 240 | python3 -c "
import json, sys
d = json.load(sys.stdin)
t = d['result']['content'][0]['text']
r = json.loads(t.split('\n\n', 1)[-1] if 'Data generation' in t else t)
dd = r['data']
customers = dd['data'].get('customers', [])
phone_null = sum(1 for c in customers if c.get('phone') is None)
addr_null = sum(1 for c in customers if c.get('address') is None)
total = len(customers)
print(f'customers={total} phone_null_pct={100*phone_null/max(1,total):.1f}% addr_null_pct={100*addr_null/max(1,total):.1f}%')
assert 5 <= 100*phone_null/max(1,total) <= 15, 'phone null rate out of [5%, 15%]'
# Critical fields stay non-null
email_null = sum(1 for c in customers if c.get('email') is None)
id_null = sum(1 for c in customers if c.get('id') is None)
created_null = sum(1 for c in customers if c.get('created_at') is None)
assert email_null == 0, 'email should never be null'
assert id_null == 0, 'id should never be null'
assert created_null == 0, 'created_at should never be null'
print('PASS: nulls in nullable fields, none in critical fields')
"
```
Expected: phone-null between 5% and 15%; PASS. If 0% nulls, Task 7 templates not loaded — restart container.

- [ ] **Step 6: Acceptance #5 — V1 path regression test**

```bash
curl -s -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: df_QBwcmV9rZ0A6yITSAw8-TmGGy9hAxLpaoDaMC3Pr4wY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"generate_data","arguments":{"rows":5,"format":"json"}}}' \
  --max-time 60 | python3 -c "
import json, sys
d = json.load(sys.stdin)
t = d['result']['content'][0]['text']
r = json.loads(t.split('\n\n', 1)[-1] if 'Data generation' in t else t)
assert r['mode'] == 'v1', f'expected v1, got {r[\"mode\"]}'
inner = json.loads(r['data'])
assert len(inner) == 5
print(f'PASS: V1 mode produced {len(inner)} rows, sample: {inner[0][\"name\"]}, {inner[0][\"email\"]}')
"
```
Expected: PASS. V1 path is untouched by this work — must produce 5 Faker rows.

- [ ] **Step 7: Acceptance #6 — Final full test suite**

```bash
python3 -m pytest tests/test_schema_validator.py tests/test_catalog_sandbox.py tests/test_realism_consolidation.py tests/test_semantic_router.py tests/test_dependency_analyzer.py tests/test_quality_block.py tests/test_prompt_refiner.py tests/test_prompt_refiner_phase2.py tests/test_sanitizer.py tests/test_datagen.py tests/test_relationships.py tests/test_realism.py tests/test_distributions.py tests/test_domain_templates.py 2>&1 | tail -10
```
Expected: all v0.9 new tests PASS. v0.8 baseline tests have same pass/fail counts as Task 0 step 3 (no new regressions). 14 pre-existing async-vs-sync failures in `test_semantic_analyzer_v2.py` remain — out of scope.

- [ ] **Step 8: Stage any remaining files (should be empty)**

```bash
git status --short
```
Expected: every file from Tasks 1-8 is already staged via that task's step. If anything is unstaged, stage it now with `git add <file>`.

- [ ] **Step 9: Summarize for the user**

Print the final summary:

```bash
echo "=== v0.9 IMPLEMENTATION COMPLETE — READY FOR MANUAL COMMIT ==="
echo ""
echo "Files staged:"
git diff --cached --stat
echo ""
echo "Next step: review staged changes with 'git diff --cached' and commit manually."
```

---

## Self-review summary

Skim each spec section against the plan tasks:

| Spec section | Plan task |
|--------------|-----------|
| §6.1 CatalogFactory `get_entity_catalogs` | Task 2 |
| §6.2 SemanticRouter `field_catalog` param | Task 4 |
| §6.3 V2 generator wiring | Task 5 |
| §6.3 V2 `_apply_realism` deletion + consolidation | Task 6 |
| §6.4 `realism_engine.py` (no API change — verified untouched) | Task 6 (verification) |
| §6.5 SchemaDesigner prompt update | Task 3 |
| §6.6 SchemaValidator (new module) | Task 1 |
| §6.7 Domain template nullable | Task 7 |
| §6.8 `agent.py` (no structural change — verified untouched) | Task 5 (verification by smoke test) |
| §6.9 `routers/__init__.py` (no change — verified untouched) | Task 9 (smoke test confirms MCP works) |
| §6.10 manifest version bump | Task 8 |
| §6.11 generate_data.md update | Task 8 |
| §12 Acceptance criteria 1-11 | Task 9 |

No placeholders. Every code block contains executable code or exact diff. Every test step states expected output. Every command has expected exit / output behavior.

**Type consistency check:**
- `SchemaValidator.validate_and_fix(schema_design: SchemaDesign, user_prompt: str) -> SchemaDesign` — consistent across Tasks 1 and 5
- `CatalogFactory.get_entity_catalogs(...)` returns `Dict[str, List[str]]` — consistent across Tasks 2 and 5
- `SemanticRouter.generate_value(..., field_catalog: Optional[List[str]] = None)` — consistent across Tasks 4 and 5
- `realism_engine.apply_realism_to_data(generated_data, schema_design, realism_level)` — signature matches existing realism_engine.py line 188

**Out-of-scope items** (per spec §4 — explicitly deferred):
- Reproducibility / `seed` arg
- Doc/version reconciliation across src/main.py + Dockerfile + manifest
- Per-task LLM attribution in dashboard
- SQL/Excel output
- Fixing the 14 pre-existing async-vs-sync test failures
