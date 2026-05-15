"""Tests for realism consolidation in V2 generator (v0.9).

Verifies:
  - V2's internal _apply_realism is removed
  - Realism is applied exactly once per call
  - realism_engine.apply_realism_to_data is the single entry point
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
    """The V2 module must reference realism_engine.apply_realism_to_data."""
    import src.tools.datagen.advanced_generator_v2 as v2
    source = inspect.getsource(v2)
    assert "apply_realism_to_data" in source, (
        "advanced_generator_v2.py does not reference apply_realism_to_data — "
        "realism consolidation incomplete"
    )


def test_apply_realism_call_site_count_in_generate():
    """Realism should be applied exactly once per generate() call. The v0.8.5
    bug was a double-application (one inside try, one outside). After
    consolidation there must be exactly ONE invocation of
    apply_realism_to_data inside the `generate()` body.

    Counts only actual call patterns ``apply_realism_to_data(`` — comment
    mentions and the import line are excluded so docstrings can refer to
    the function freely.
    """
    src = inspect.getsource(AdvancedGeneratorV2.generate)
    # Count call patterns only (function-name followed by open paren).
    # Excludes the `from ... import apply_realism_to_data` line.
    call_count = src.count("apply_realism_to_data(")
    assert call_count == 1, (
        f"Expected exactly 1 call to apply_realism_to_data(); found {call_count}"
    )
