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


def _field(sd: SchemaDesign, entity_name: str, field_name: str) -> FieldSchema:
    """Lookup a field by name (EntitySchema auto-prepends a primary key
    field, so fields[0] is not necessarily the field we asked for)."""
    fields = sd.entities[entity_name].fields
    return next(f for f in fields if f.name == field_name.lower())


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
        assert _field(out, "book", "genre").constraints == {"enum": ["Fiction", "Non-Fiction"]}

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
        assert _field(out, "book", "genre").constraints["enum"] == [
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
        genre = _field(out, "book", "genre")
        assert genre.constraints["enum"] == ["Fiction", "Sci-Fi"]
        # status had the wrong values copied — they get cleared
        status = _field(out, "book", "status")
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
        assert _field(out, "book", "genre").constraints["enum"] == ["A", "B"]

    def test_handles_quotes_with_spaces(self):
        validator = SchemaValidator()
        sd = _build_schema(
            "user",
            [FieldSchema(name="tier", type="string")],
        )
        prompt = 'tier enum: [ "free", "pro" , "enterprise" ]'
        out = validator.validate_and_fix(sd, user_prompt=prompt)
        assert _field(out, "user", "tier").constraints["enum"] == ["free", "pro", "enterprise"]


# ---------- Range inference ----------

class TestRangeInference:
    def test_bedroom_count_gets_realistic_range(self):
        validator = SchemaValidator()
        sd = _build_schema(
            "listing",
            [FieldSchema(name="bedroom_count", type="int")],
        )
        out = validator.validate_and_fix(sd, user_prompt="real estate listings")
        constraints = _field(out, "listing", "bedroom_count").constraints or {}
        assert constraints.get("min") == 1
        assert constraints.get("max") == 6

    def test_age_gets_realistic_range(self):
        validator = SchemaValidator()
        sd = _build_schema(
            "person",
            [FieldSchema(name="age", type="int")],
        )
        out = validator.validate_and_fix(sd, user_prompt="employees")
        constraints = _field(out, "person", "age").constraints or {}
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
        constraints = _field(out, "house", "year_built").constraints or {}
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
        constraints = _field(out, "listing", "bedroom_count").constraints
        assert constraints["min"] == 2
        assert constraints["max"] == 10

    def test_no_hint_leaves_field_unconstrained(self):
        validator = SchemaValidator()
        sd = _build_schema(
            "blob",
            [FieldSchema(name="totally_unknown_metric", type="int")],
        )
        out = validator.validate_and_fix(sd, user_prompt="opaque data")
        constraints = _field(out, "blob", "totally_unknown_metric").constraints or {}
        assert "min" not in constraints
        assert "max" not in constraints

    def test_skips_non_numeric_fields(self):
        validator = SchemaValidator()
        sd = _build_schema(
            "x",
            [FieldSchema(name="bedroom_count", type="string")],  # string, not int
        )
        out = validator.validate_and_fix(sd, user_prompt="x")
        constraints = _field(out, "x", "bedroom_count").constraints or {}
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
        original_constraints = _field(original, "x", "age").constraints
        _ = validator.validate_and_fix(original, user_prompt="x")
        # Input unchanged
        assert _field(original, "x", "age").constraints == original_constraints
