"""Tests for field_value_generator.py

Tests semantic-aware field value generation with various strategies.
"""

import pytest
from src.tools.datagen.field_value_generator import FieldValueGenerator
from src.tools.datagen.semantic_models import (
    SemanticPlan,
    FieldSemanticInfo,
    ValueCatalog,
)


class TestFieldValueGenerator:
    """Tests for FieldValueGenerator class."""

    def test_get_generator_uuid(self):
        """Test UUID generator."""
        plan = SemanticPlan(
            entities={
                "users": [
                    FieldSemanticInfo(
                        entity_name="users",
                        field_name="id",
                        db_type="uuid",
                        semantic_type="identifier",
                        generator_strategy="uuid"
                    )
                ]
            }
        )
        
        generator = FieldValueGenerator(plan)
        gen_func = generator.get_generator("users", "id")
        
        # Generate value
        value = gen_func()
        
        # Should be UUID string
        assert isinstance(value, str)
        assert len(value) == 36  # UUID format
        assert value.count('-') == 4

    def test_get_generator_catalog(self):
        """Test catalog-based generator."""
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
                    values=["Rose", "Tulip", "Orchid", "Lily"]
                )
            }
        )
        
        generator = FieldValueGenerator(plan)
        gen_func = generator.get_generator("flowers", "name")
        
        # Generate values
        values = [gen_func() for _ in range(10)]
        
        # All values should be from catalog
        for value in values:
            assert value in ["Rose", "Tulip", "Orchid", "Lily"]

    def test_get_generator_catalog_fallback_to_faker(self):
        """Test catalog generator falls back to Faker when catalog missing."""
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
            value_catalogs={}  # No catalog
        )
        
        generator = FieldValueGenerator(plan)
        gen_func = generator.get_generator("flowers", "name")
        
        # Should not crash, should fallback to Faker
        value = gen_func()
        assert isinstance(value, str)
        assert len(value) > 0

    def test_get_generator_faker_email(self):
        """Test Faker generator for email."""
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
        
        generator = FieldValueGenerator(plan)
        gen_func = generator.get_generator("users", "email")
        
        # Generate email
        value = gen_func()
        
        # Should look like email
        assert "@" in value
        assert "." in value

    def test_get_generator_faker_phone(self):
        """Test Faker generator for phone."""
        plan = SemanticPlan(
            entities={
                "contacts": [
                    FieldSemanticInfo(
                        entity_name="contacts",
                        field_name="phone",
                        db_type="string",
                        semantic_type="phone_number",
                        generator_strategy="faker"
                    )
                ]
            }
        )
        
        generator = FieldValueGenerator(plan)
        gen_func = generator.get_generator("contacts", "phone")
        
        # Generate phone
        value = gen_func()
        
        # Should be string
        assert isinstance(value, str)
        assert len(value) > 0

    def test_get_generator_numeric_price(self):
        """Test numeric generator for prices (lognormal)."""
        plan = SemanticPlan(
            entities={
                "products": [
                    FieldSemanticInfo(
                        entity_name="products",
                        field_name="price",
                        db_type="float",
                        semantic_type="price_amount",
                        generator_strategy="numeric_distribution"
                    )
                ]
            }
        )
        
        generator = FieldValueGenerator(plan)
        gen_func = generator.get_generator("products", "price")
        
        # Generate prices
        prices = [gen_func() for _ in range(20)]
        
        # All should be positive floats
        for price in prices:
            assert isinstance(price, float)
            assert price > 0

    def test_get_generator_numeric_count(self):
        """Test numeric generator for counts (pareto)."""
        plan = SemanticPlan(
            entities={
                "orders": [
                    FieldSemanticInfo(
                        entity_name="orders",
                        field_name="item_count",
                        db_type="int",
                        semantic_type="count",
                        generator_strategy="numeric_distribution"
                    )
                ]
            }
        )
        
        generator = FieldValueGenerator(plan)
        gen_func = generator.get_generator("orders", "item_count")
        
        # Generate counts
        counts = [gen_func() for _ in range(20)]
        
        # All should be positive integers
        for count in counts:
            assert isinstance(count, int)
            assert count >= 0

    def test_get_generator_datetime(self):
        """Test datetime generator."""
        plan = SemanticPlan(
            entities={
                "events": [
                    FieldSemanticInfo(
                        entity_name="events",
                        field_name="created_at",
                        db_type="datetime",
                        semantic_type="timestamp",
                        generator_strategy="datetime_range"
                    )
                ]
            }
        )
        
        generator = FieldValueGenerator(plan)
        gen_func = generator.get_generator("events", "created_at")
        
        # Generate timestamp
        value = gen_func()
        
        # Should be ISO format string
        assert isinstance(value, str)
        assert "T" in value  # ISO format has T separator

    def test_get_generator_generic_fallback(self):
        """Test generic fallback for unknown field."""
        plan = SemanticPlan(entities={})
        
        generator = FieldValueGenerator(plan)
        gen_func = generator.get_generator("unknown", "unknown")
        
        # Should not crash
        value = gen_func()
        assert isinstance(value, str)

    def test_get_generator_generic_text(self):
        """Test generic text generator."""
        plan = SemanticPlan(
            entities={
                "notes": [
                    FieldSemanticInfo(
                        entity_name="notes",
                        field_name="content",
                        db_type="string",
                        semantic_type="generic_text",
                        generator_strategy="generic_text"
                    )
                ]
            }
        )
        
        generator = FieldValueGenerator(plan)
        gen_func = generator.get_generator("notes", "content")
        
        # Generate text
        value = gen_func()
        
        # Should be string
        assert isinstance(value, str)
        assert len(value) > 0

    def test_get_generator_boolean(self):
        """Test boolean generator."""
        plan = SemanticPlan(
            entities={
                "flags": [
                    FieldSemanticInfo(
                        entity_name="flags",
                        field_name="is_active",
                        db_type="boolean",
                        semantic_type="boolean_flag",
                        generator_strategy="generic_text"
                    )
                ]
            }
        )
        
        generator = FieldValueGenerator(plan)
        gen_func = generator.get_generator("flags", "is_active")
        
        # Generate booleans
        values = [gen_func() for _ in range(10)]
        
        # All should be boolean
        for value in values:
            assert isinstance(value, bool)

    def test_multiple_fields_same_entity(self):
        """Test generating multiple fields from same entity."""
        plan = SemanticPlan(
            entities={
                "users": [
                    FieldSemanticInfo(
                        entity_name="users",
                        field_name="id",
                        db_type="uuid",
                        semantic_type="identifier",
                        generator_strategy="uuid"
                    ),
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
        
        generator = FieldValueGenerator(plan)
        
        # Get generators for both fields
        id_gen = generator.get_generator("users", "id")
        email_gen = generator.get_generator("users", "email")
        
        # Generate values
        user_id = id_gen()
        email = email_gen()
        
        # Verify both work
        assert isinstance(user_id, str)
        assert len(user_id) == 36
        assert "@" in email
