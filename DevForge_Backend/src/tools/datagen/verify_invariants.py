
import asyncio
import logging
import sys
import os
import json
import re

# Add src to path
sys.path.append(os.getcwd())

from unittest.mock import MagicMock

# Mock dependencies to avoid import errors
sys.modules["src.core.model_router"] = MagicMock()
sys.modules["src.tools.datagen.semantic_analyzer_v2"] = MagicMock()
sys.modules["src.tools.datagen.catalog_factory"] = MagicMock()
sys.modules["langchain_ollama"] = MagicMock() # Just in case

from src.tools.datagen.semantic_router import SemanticRouter
from src.tools.datagen.advanced_generator_v2 import AdvancedGeneratorV2
from src.tools.datagen.schema_models import SchemaDesign, EntitySchema, FieldSchema
from src.tools.datagen.relationship_engine import RelationshipEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFIER")

async def test_invariants():
    logger.info("Starting Invariant Verification...")
    
    # 1. Test SemanticRouter Constraint Precedence
    logger.info("[Test] Invariant 1: Constraint-First Generation")
    router = SemanticRouter()
    
    # Enum overrides min/max
    val = router.generate_value("numeric_id", constraints={"enum": [999], "min": 1, "max": 10})
    assert val == 999, f"Enum failed to override min/max: {val}"
    
    # Pattern overrides defaults
    val = router.generate_value("string", constraints={"pattern": "ABC-\d{3}"})
    assert re.match(r"ABC-\d{3}", val), f"Pattern failed: {val}"
    
    # Min/Max overrides semantic defaults (Date)
    val = router.generate_value("date", constraints={"min": "2050-01-01", "max": "2050-12-31"})
    assert "2050" in val, f"Date min/max failed: {val}"
    
    logger.info("Invariant 1 Passed.")
    
    # 2. Test Constraint Normalization is implicit in usage above, but we rely on code review mostly.
    
    # 3. Test No Null Injection in RelationshipEngine
    logger.info("[Test] Invariant 4: Single Source of Null Injection")
    # Create simple schema
    schema = SchemaDesign(
        domain="test",
        entities={
            "User": EntitySchema(
                name="User",
                fields=[FieldSchema(name="name", type="string", nullable=True)],
                count=100
            )
        }
    )
    # Mock field generator to return a string
    class MockGen:
        def get_generator(self, e, f): return lambda: "test"
        
    engine = RelationshipEngine(schema, MockGen())
    data = engine.generate_all_entities()
    
    # Check for nulls
    nulls = [r for r in data["User"] if r["name"] is None]
    assert len(nulls) == 0, f"RelationshipEngine injected {len(nulls)} nulls! forbidden."
    logger.info("Invariant 4 Passed.")
    
    # 4. Test AdvancedGeneratorV2 Validation & Failures
    logger.info("[Test] Invariant 3 & 8: No Post-Hoc Fixing & Deterministic Success")
    
    generator = AdvancedGeneratorV2(enable_semantic=False)
    
    # Schema with impossible constraint (min > max for number) to force fallback/fail or just check validation logic
    # Actually, let's try to pass a value that violates constraint
    
    # We can't easily force SemanticRouter to fail since we fixed it to retry/respect constraints!
    # So we manually inject invalid data to test VALIDATOR.
    
    schema_dict = {
        "User": {
            "fields": {
                "age": {"type": "integer", "constraints": {"min": 18, "max": 99}},
                "name": {"type": "string", "nullable": False}
            }
        }
    }
    
    # Mock generation by subclassing or hijacking? 
    # Let's just run normal generation. Since we fixed Router, it SHOULD succeed.
    res = await generator.generate(schema_dict, row_count=10)
    assert len(res["constraint_violations"]) == 0, "Should have 0 violations with fixed router"
    assert res["data"]["User"], "Should return data on success"
    
    # Now verify INVALID data handling by calling _validate_constraints directly with bad data
    bad_data = {"User": [{"age": 10, "name": None}]} # 10 < 18, name is None but not nullable
    violations = generator._validate_constraints(bad_data, schema_dict, {})
    
    assert len(violations) == 2, f"Expected 2 violations, got {len(violations)}"
    v_types = {v["constraint"] for v in violations}
    assert "min" in v_types, "Failed to detect min violation"
    assert "nullable" in v_types, "Failed to detect nullable violation"
    
    logger.info("Invariant 3 & 8 Passed.")
    
    # 5. Test Metadata Truthfulness
    logger.info("[Test] Invariant 7: Metadata Truthfulness")
    # Use the result from successful generation
    meta = generator._build_metadata({}, res["data"], schema_dict, [])
    # Check field analysis
    # Need to simulate semantic info to get field analysis populated
    # But basic generator (enable_semantic=False) might skip some of that ?
    # Let's mock semantic info
    from src.tools.datagen.semantic_types import SemanticFieldInfo
    
    sem_info = {"User": [SemanticFieldInfo(
        entity_name="User",
        field_name="age",
        raw_type="integer", 
        semantic_type="age", 
        data_type="integer",
        confidence=1.0, 
        source="lexical", 
        constraints={"min": 18}
    )]}
    
    meta = generator._build_metadata(sem_info, res["data"], schema_dict, [])
    
    field_analysis = meta["field_analysis"]["User"]["age"]
    assert field_analysis["constraints_respected"] is True, "Should be True when 0 violations"
    
    # Test with violations
    meta_fail = generator._build_metadata(sem_info, bad_data, schema_dict, violations)
    field_analysis_fail = meta_fail["field_analysis"]["User"]["age"]
    assert field_analysis_fail["constraints_respected"] is False, "Should be False when violations exist"
    
    logger.info("Invariant 7 Passed.")

    logger.info("ALL INVARIANTS VERIFIED.")

if __name__ == "__main__":
    asyncio.run(test_invariants())
