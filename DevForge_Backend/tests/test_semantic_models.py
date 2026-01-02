"""Tests for semantic_models.py

Tests Pydantic models for semantic field information and value catalogs.
"""

import pytest
from pydantic import ValidationError
from src.tools.datagen.semantic_models import (
    FieldSemanticInfo,
    ValueCatalog,
    SemanticPlan,
)


class TestFieldSemanticInfo:
    """Tests for FieldSemanticInfo model."""

    def test_valid_field_semantic_info(self):
        """Test creating valid field semantic info."""
        info = FieldSemanticInfo(
            entity_name="flowers",
            field_name="name",
            db_type="string",
            semantic_type="flower_name",
            generator_strategy="value_catalog"
        )
        
        assert info.entity_name == "flowers"
        assert info.field_name == "name"
        assert info.semantic_type == "flower_name"
        assert info.generator_strategy == "value_catalog"

    def test_field_info_with_constraints(self):
        """Test field info with constraints."""
        info = FieldSemanticInfo(
            entity_name="products",
            field_name="price",
            db_type="float",
            semantic_type="price_amount",
            generator_strategy="numeric_distribution",
            constraints={"min": 0, "max": 1000, "mean": 50}
        )
        
        assert info.constraints["min"] == 0
        assert info.constraints["max"] == 1000

    def test_field_info_with_notes(self):
        """Test field info with notes."""
        info = FieldSemanticInfo(
            entity_name="users",
            field_name="email",
            db_type="string",
            semantic_type="email_address",
            generator_strategy="faker",
            notes="Use Faker email provider"
        )
        
        assert info.notes == "Use Faker email provider"

    def test_invalid_generator_strategy(self):
        """Test invalid generator strategy raises error."""
        with pytest.raises(ValidationError):
            FieldSemanticInfo(
                entity_name="test",
                field_name="test",
                db_type="string",
                semantic_type="test",
                generator_strategy="invalid_strategy"
            )

    def test_all_generator_strategies(self):
        """Test all valid generator strategies."""
        strategies = [
            "faker",
            "numeric_distribution",
            "datetime_range",
            "uuid",
            "mongo_object_id",
            "value_catalog",
            "generic_text"
        ]
        
        for strategy in strategies:
            info = FieldSemanticInfo(
                entity_name="test",
                field_name="test",
                db_type="string",
                semantic_type="test",
                generator_strategy=strategy
            )
            assert info.generator_strategy == strategy


class TestValueCatalog:
    """Tests for ValueCatalog model."""

    def test_valid_catalog(self):
        """Test creating valid value catalog."""
        catalog = ValueCatalog(
            key="flowers.name",
            semantic_type="flower_name",
            values=["Rose", "Tulip", "Orchid"]
        )
        
        assert catalog.key == "flowers.name"
        assert catalog.semantic_type == "flower_name"
        assert len(catalog.values) == 3
        assert "Rose" in catalog.values

    def test_catalog_with_builtin_source(self):
        """Test catalog with builtin source."""
        catalog = ValueCatalog(
            key="countries.name",
            semantic_type="country_name",
            values=["USA", "UK", "Canada"],
            source="builtin"
        )
        
        assert catalog.source == "builtin"

    def test_catalog_default_source_is_llm(self):
        """Test default source is LLM."""
        catalog = ValueCatalog(
            key="test.test",
            semantic_type="test",
            values=["val1", "val2"]
        )
        
        assert catalog.source == "llm"

    def test_catalog_with_max_sample_size(self):
        """Test catalog with max sample size."""
        catalog = ValueCatalog(
            key="test.test",
            semantic_type="test",
            values=["a", "b", "c"],
            max_sample_size=100
        )
        
        assert catalog.max_sample_size == 100

    def test_empty_values_raises_error(self):
        """Test empty values list raises validation error."""
        with pytest.raises(ValidationError):
            ValueCatalog(
                key="test.test",
                semantic_type="test",
                values=[]  # Empty not allowed
            )


class TestSemanticPlan:
    """Tests for SemanticPlan model."""

    def test_valid_semantic_plan(self):
        """Test creating valid semantic plan."""
        plan = SemanticPlan(
            entities={
                "flowers": [
                    FieldSemanticInfo(
                        entity_name="flowers",
                        field_name="name",
                        db_type="string",
                        semantic_type="flower_name",
                        generator_strategy="value_catalog"
                    )
                ]
            },
            value_catalogs={
                "flowers.name": ValueCatalog(
                    key="flowers.name",
                    semantic_type="flower_name",
                    values=["Rose", "Tulip"]
                )
            }
        )
        
        assert "flowers" in plan.entities
        assert len(plan.entities["flowers"]) == 1
        assert "flowers.name" in plan.value_catalogs

    def test_get_field_info_success(self):
        """Test get_field_info finds field."""
        plan = SemanticPlan(
            entities={
                "users": [
                    FieldSemanticInfo(
                        entity_name="users",
                        field_name="email",
                        db_type="string",
                        semantic_type="email_address",
                        generator_strategy="faker"
                    ),
                    FieldSemanticInfo(
                        entity_name="users",
                        field_name="name",
                        db_type="string",
                        semantic_type="person_name",
                        generator_strategy="faker"
                    )
                ]
            }
        )
        
        info = plan.get_field_info("users", "email")
        assert info is not None
        assert info.field_name == "email"
        assert info.semantic_type == "email_address"

    def test_get_field_info_not_found(self):
        """Test get_field_info returns None for non-existent field."""
        plan = SemanticPlan(
            entities={
                "users": [
                    FieldSemanticInfo(
                        entity_name="users",
                        field_name="email",
                        db_type="string",
                        semantic_type="email_address",
                        generator_strategy="faker"
                    )
                ]
            }
        )
        
        info = plan.get_field_info("users", "nonexistent")
        assert info is None
        
        info = plan.get_field_info("nonexistent_entity", "email")
        assert info is None

    def test_get_catalog_exact_match(self):
        """Test get_catalog with exact key match."""
        plan = SemanticPlan(
            entities={
                "flowers": [
                    FieldSemanticInfo(
                        entity_name="flowers",
                        field_name="name",
                        db_type="string",
                        semantic_type="flower_name",
                        generator_strategy="value_catalog"
                    )
                ]
            },
            value_catalogs={
                "flowers.name": ValueCatalog(
                    key="flowers.name",
                    semantic_type="flower_name",
                    values=["Rose", "Tulip"]
                )
            }
        )
        
        catalog = plan.get_catalog("flowers", "name")
        assert catalog is not None
        assert catalog.key == "flowers.name"
        assert "Rose" in catalog.values

    def test_get_catalog_by_semantic_type(self):
        """Test get_catalog falls back to semantic type match."""
        plan = SemanticPlan(
            entities={
                "flowers": [
                    FieldSemanticInfo(
                        entity_name="flowers",
                        field_name="common_name",
                        db_type="string",
                        semantic_type="flower_name",
                        generator_strategy="value_catalog"
                    )
                ]
            },
            value_catalogs={
                "flowers.name": ValueCatalog(
                    key="flowers.name",
                    semantic_type="flower_name",
                    values=["Rose", "Tulip"]
                )
            }
        )
        
        # Different field name but same semantic type
        catalog = plan.get_catalog("flowers", "common_name")
        assert catalog is not None
        assert catalog.semantic_type == "flower_name"

    def test_get_catalog_not_found(self):
        """Test get_catalog returns None when not found."""
        plan = SemanticPlan(
            entities={
                "flowers": [
                    FieldSemanticInfo(
                        entity_name="flowers",
                        field_name="name",
                        db_type="string",
                        semantic_type="flower_name",
                        generator_strategy="value_catalog"
                    )
                ]
            },
            value_catalogs={}
        )
        
        catalog = plan.get_catalog("flowers", "name")
        assert catalog is None

    def test_fields_needing_catalogs(self):
        """Test fields_needing_catalogs returns correct fields."""
        plan = SemanticPlan(
            entities={
                "flowers": [
                    FieldSemanticInfo(
                        entity_name="flowers",
                        field_name="name",
                        db_type="string",
                        semantic_type="flower_name",
                        generator_strategy="value_catalog"
                    ),
                    FieldSemanticInfo(
                        entity_name="flowers",
                        field_name="price",
                        db_type="float",
                        semantic_type="price_amount",
                        generator_strategy="numeric_distribution"
                    ),
                    FieldSemanticInfo(
                        entity_name="flowers",
                        field_name="family",
                        db_type="string",
                        semantic_type="botanical_family",
                        generator_strategy="value_catalog"
                    )
                ]
            }
        )
        
        catalog_fields = plan.fields_needing_catalogs()
        
        assert len(catalog_fields) == 2
        field_names = [f.field_name for f in catalog_fields]
        assert "name" in field_names
        assert "family" in field_names
        assert "price" not in field_names

    def test_empty_semantic_plan(self):
        """Test creating empty semantic plan."""
        plan = SemanticPlan(entities={})
        
        assert len(plan.entities) == 0
        assert len(plan.value_catalogs) == 0
        assert plan.fields_needing_catalogs() == []
