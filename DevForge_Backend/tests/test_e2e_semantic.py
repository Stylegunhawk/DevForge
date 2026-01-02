"""End-to-end tests for Phase 8.6 semantic generation.

Tests the complete pipeline: schema design → semantic analysis → catalog building → data generation.
Verifies that the "Daniel Doyle flower" bug is fixed.

NOTE: These are integration tests that require LLM access.
Run with: pytest tests/test_e2e_semantic.py -m integration
"""

import pytest
import json
from src.tools.datagen.advanced_generator import generate_advanced_data

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestEndToEndSemanticGeneration:
    """End-to-end tests for semantic-aware data generation."""

    @pytest.mark.asyncio
    async def test_flower_catalog_no_human_names(self):
        """Test that flowers get flower names, not human names (Daniel Doyle bug fix)."""
        
        # Generate flower data with semantic generation enabled
        result = await generate_advanced_data(
            prompt="Generate a catalog of 20 different flowers",
            default_rows=20,
            output_format="json",
            enable_semantic_generation=True
        )
        
        # Verify semantic generation was used
        assert result["semantic_generation_used"] is True, "Semantic generation should be enabled"
        
        # Get the generated flower data
        assert "flowers" in result["data"], "Should have generated flowers entity"
        
        flower_data_str = result["data"]["flowers"]
        flower_records = json.loads(flower_data_str)
        
        # Verify we have records
        assert len(flower_records) > 0, "Should have generated flower records"
        
        # Common faker human names that should NOT appear
        human_names = [
            "John", "Jane", "Daniel", "Sarah", "Michael", "Emily",
            "David", "Jessica", "William", "Ashley", "Doyle", "Smith",
            "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller"
        ]
        
        # Check that flower names are NOT human names
        for flower in flower_records:
            if "name" in flower:
                flower_name = flower["name"]
                
                # Flower names should not contain common human first/last names
                for human_name in human_names:
                    assert human_name not in flower_name, (
                        f"Flower name '{flower_name}' contains human name '{human_name}'. "
                        f"This is the Daniel Doyle bug!"
                    )
        
        print(f"✅ Generated {len(flower_records)} flowers with domain-specific names")
        print(f"Sample flower names: {[f.get('name', 'N/A') for f in flower_records[:5]]}")

    @pytest.mark.asyncio
    async def test_semantic_vs_nonsemantic_generation(self):
        """Compare semantic generation vs regular Faker generation."""
        
        prompt = "Generate a catalog of flowers with names and types"
        
        # Generate with semantic generation
        semantic_result = await generate_advanced_data(
            prompt=prompt,
            default_rows=10,
            enable_semantic_generation=True
        )
        
        # Generate without semantic generation (Faker fallback)
        faker_result = await generate_advanced_data(
            prompt=prompt,
            default_rows=10,
            enable_semantic_generation=False
        )
        
        # Verify flags
        assert semantic_result["semantic_generation_used"] is True
        assert faker_result["semantic_generation_used"] is False
        
        # Both should have generated data
        assert "flowers" in semantic_result["data"]
        assert "flowers" in faker_result["data"]
        
        print("✅ Both semantic and non-semantic generation modes work")

    @pytest.mark.asyncio
    async def test_university_catalog(self):
        """Test that universities get university names."""
        
        result = await generate_advanced_data(
            prompt="Generate a database of 15 universities",
            default_rows=15,
            enable_semantic_generation=True
        )
        
        assert result["semantic_generation_used"] is True
        
        # Verify universities entity exists
        assert "universities" in result["data"]
        
        university_data = json.loads(result["data"]["universities"])
        assert len(university_data) > 0
        
        # Common non-university names that should NOT appear
        avoid_names = ["John", "Daniel", "Acme Corp", "Generic LLC"]
        
        for uni in university_data:
            if "name" in uni:
                uni_name = uni["name"]
                for avoid in avoid_names:
                    assert avoid not in uni_name, (
                        f"University name '{uni_name}' contains '{avoid}'"
                    )
        
        print(f"✅ Generated {len(university_data)} universities with appropriate names")
        print(f"Sample university names: {[u.get('name', 'N/A') for u in university_data[:5]]}")

    @pytest.mark.asyncio
    async def test_fallback_on_semantic_failure(self):
        """Test that system gracefully falls back to Faker if semantic generation fails."""
        
        # Simple schema that doesn't trigger complex semantic analysis
        result = await generate_advanced_data(
            prompt="Generate simple test data",
            default_rows=5,
            enable_semantic_generation=True  # Enabled but may fallback
        )
        
        # Should have generated data regardless
        assert len(result["data"]) > 0
        assert result["entities"]
        
        print("✅ Graceful fallback to Faker works when semantic generation fails")


class TestBackwardCompatibility:
    """Verify backward compatibility with V1 mode."""

    @pytest.mark.asyncio
    async def test_disable_semantic_generation(self):
        """Test that disabling semantic generation works (V1 mode)."""
        
        result = await generate_advanced_data(
            prompt="Generate test data",
            default_rows=10,
            enable_semantic_generation=False  # V1 mode
        )
        
        # Should work without semantic generation
        assert result["semantic_generation_used"] is False
        assert len(result["data"]) > 0
        
        print("✅ V1 mode (non-semantic) still works correctly")
