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
