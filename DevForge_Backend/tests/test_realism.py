"""Tests for realism engine.

Tests cover:
- Null injection rates for different levels
- Duplicate injection on key fields
- Outlier injection on numeric fields
- Realism level configurations
- Edge cases
"""

import pytest
from src.tools.datagen.realism_engine import (
    RealismEngine,
    apply_realism_to_data,
    REALISM_CONFIGS,
)
from src.tools.datagen.schema_models import (
    EntitySchema,
    FieldSchema,
    SchemaDesign,
)


class TestRealismEngine:
    """Tests for RealismEngine class."""

    def test_basic_level_no_changes(self):
        """Test basic level makes no changes."""
        engine = RealismEngine("basic")
        
        data = [
            {"id": 1, "email": "test@example.com", "age": 25},
            {"id": 2, "email": "user@example.com", "age": 30},
        ]
        
        result = engine.apply_realism(
            data,
            entity_name="users",
            nullable_fields={"email"},
            key_fields={"email"},
            numeric_fields={"age"}
        )
        
        # No changes should be made
        assert result[0]["email"] == "test@example.com"
        assert result[1]["email"] == "user@example.com"
        assert result[0]["age"] == 25
        assert result[1]["age"] == 30

    def test_medium_level_null_injection(self):
        """Test medium level injects nulls."""
        engine = RealismEngine("medium")
        
        # Generate larger dataset for statistical testing
        data = [
            {"id": i, "email": f"user{i}@example.com", "optional": f"value{i}"}
            for i in range(1000)
        ]
        
        result = engine.apply_realism(
            data,
            entity_name="users",
            nullable_fields={"optional"},
            key_fields=set(),
            numeric_fields=set()
        )
        
        # Count nulls in optional field
        null_count = sum(1 for rec in result if rec["optional"] is None)
        
        # Should be around 5% (50 out of 1000)
        assert 30 < null_count < 70, f"Expected ~50 nulls, got {null_count}"

    def test_high_level_null_injection(self):
        """Test high level injects more nulls."""
        engine = RealismEngine("high")
        
        data = [
            {"id": i, "name": f"User {i}", "bio": f"Bio {i}"}
            for i in range(1000)
        ]
        
        result = engine.apply_realism(
            data,
            entity_name="users",
            nullable_fields={"bio"},
            key_fields=set(),
            numeric_fields=set()
        )
        
        # Count nulls
        null_count = sum(1 for rec in result if rec["bio"] is None)
        
        # Should be around 10% (100 out of 1000)
        assert 70 < null_count < 130, f"Expected ~100 nulls, got {null_count}"

    def test_high_level_duplicate_injection(self):
        """Test high level injects duplicates in key fields."""
        engine = RealismEngine("high")
        
        data = [
            {"id": i, "email": f"unique{i}@example.com"}
            for i in range(1000)
        ]
        
        result = engine.apply_realism(
            data,
            entity_name="users",
            nullable_fields=set(),
            key_fields={"email"},
            numeric_fields=set()
        )
        
        # Count unique emails
        unique_emails = len(set(rec["email"] for rec in result))
        
        # Should have some duplicates (roughly 2% duplicate rate means ~20 duplicates)
        # So unique count should be less than 1000
        assert unique_emails < 1000, f"Expected some duplicates, got {unique_emails} unique out of 1000"
        assert unique_emails > 950, f"Too many duplicates: {unique_emails} unique out of 1000"

    def test_high_level_outlier_injection(self):
        """Test high level injects outliers in numeric fields."""
        engine = RealismEngine("high")
        
        data = [
            {"id": i, "price": 100.0, "quantity": 5}
            for i in range(1000)
        ]
        
        result = engine.apply_realism(
            data,
            entity_name="products",
            nullable_fields=set(),
            key_fields=set(),
            numeric_fields={"price", "quantity"}
        )
        
        # Count outliers (values != 100 for price or != 5 for quantity)
        outlier_count = sum(
            1 for rec in result
            if rec["price"] != 100.0 or rec["quantity"] != 5
        )
        
        # Should be around 1% per field, so ~2% total (20 out of 1000)
        assert 5 < outlier_count < 40, f"Expected ~20 outliers, got {outlier_count}"
        
        # Check that outliers are 10x or 0.1x
        for rec in result:
            if rec["price"] != 100.0:
                assert rec["price"] in [1000.0, 10.0], f"Unexpected outlier: {rec['price']}"
            if rec["quantity"] != 5:
                assert rec["quantity"] in [50, 0.5], f"Unexpected outlier: {rec['quantity']}"

    def test_invalid_realism_level(self):
        """Test invalid realism level raises error."""
        with pytest.raises(ValueError, match="Invalid realism_level"):
            RealismEngine("extreme")

    def test_empty_data(self):
        """Test engine handles empty data."""
        engine = RealismEngine("high")
        
        result = engine.apply_realism(
            [],
            entity_name="users",
            nullable_fields={"email"},
            key_fields={"email"},
            numeric_fields={"age"}
        )
        
        assert result == []

    def test_null_injection_only_nullable_fields(self):
        """Test nulls are only injected in nullable fields."""
        engine = RealismEngine("high")
        
        data = [
            {"id": i, "required": f"value{i}", "optional": f"optional{i}"}
            for i in range(100)
        ]
        
        result = engine.apply_realism(
            data,
            entity_name="records",
            nullable_fields={"optional"},  # Only optional is nullable
            key_fields=set(),
            numeric_fields=set()
        )
        
        # Required field should never be null
        assert all(rec["required"] is not None for rec in result)
        
        # Optional field might be null
        null_count = sum(1 for rec in result if rec["optional"] is None)
        assert null_count > 0  # Should have some nulls


class TestRealismConfigs:
    """Tests for realism configuration constants."""

    def test_basic_config(self):
        """Test basic config has zero rates."""
        config = REALISM_CONFIGS["basic"]
        assert config["null_rate"] == 0.0
        assert config["duplicate_rate"] == 0.0
        assert config["outlier_rate"] == 0.0

    def test_medium_config(self):
        """Test medium config has only null rate."""
        config = REALISM_CONFIGS["medium"]
        assert config["null_rate"] == 0.05
        assert config["duplicate_rate"] == 0.0
        assert config["outlier_rate"] == 0.0

    def test_high_config(self):
        """Test high config has all rates."""
        config = REALISM_CONFIGS["high"]
        assert config["null_rate"] == 0.10
        assert config["duplicate_rate"] == 0.02
        assert config["outlier_rate"] == 0.01


class TestApplyRealismToData:
    """Tests for apply_realism_to_data convenience function."""

    def test_apply_realism_to_multi_entity(self):
        """Test applying realism to multi-entity data."""
        schema = SchemaDesign(
            entities={
                "users": EntitySchema(
                    name="users",
                    fields=[
                        FieldSchema(name="email", type="string"),
                        FieldSchema(name="bio", type="string", nullable=True),
                    ],
                    count=100
                ),
                "posts": EntitySchema(
                    name="posts",
                    fields=[
                        FieldSchema(name="user_id", type="uuid"),
                        FieldSchema(name="likes", type="int"),
                    ],
                    count=500
                )
            },
            relationships=[]
        )
        
        data = {
            "users": [
                {"id": f"user{i}", "email": f"user{i}@example.com", "bio": f"Bio {i}"}
                for i in range(100)
            ],
            "posts": [
                {"id": f"post{i}", "user_id": "user1", "likes": 10}
                for i in range(500)
            ]
        }
        
        result = apply_realism_to_data(data, schema, realism_level="medium")
        
        # Should have some nulls in bio
        null_bios = sum(1 for user in result["users"] if user["bio"] is None)
        assert null_bios > 0

    def test_apply_realism_basic_level(self):
        """Test applying basic realism makes no changes."""
        schema = SchemaDesign(
            entities={
                "records": EntitySchema(
                    name="records",
                    fields=[
                        FieldSchema(name="value", type="string", nullable=True),
                    ],
                    count=10
                )
            },
            relationships=[]
        )
        
        data = {
            "records": [{"id": i, "value": f"val{i}"} for i in range(10)]
        }
        
        result = apply_realism_to_data(data, schema, realism_level="basic")
        
        # No changes
        assert all(rec["value"] is not None for rec in result["records"])


class TestEdgeCases:
    """Tests for edge cases."""

    def test_outlier_injection_with_zero_values(self):
        """Test outlier injection skips zero values."""
        engine = RealismEngine("high")
        
        data = [
            {"id": i, "value": 0}
            for i in range(100)
        ]
        
        result = engine.apply_realism(
            data,
            entity_name="records",
            nullable_fields=set(),
            key_fields=set(),
            numeric_fields={"value"}
        )
        
        # All values should still be 0 (outliers skipped for zero)
        assert all(rec["value"] == 0 for rec in result)

    def test_outlier_injection_with_null_values(self):
        """Test outlier injection skips null values."""
        engine = RealismEngine("high")
        
        data = [
            {"id": i, "value": None}
            for i in range(100)
        ]
        
        result = engine.apply_realism(
            data,
            entity_name="records",
            nullable_fields=set(),
            key_fields=set(),
            numeric_fields={"value"}
        )
        
        # All values should still be None
        assert all(rec["value"] is None for rec in result)

    def test_duplicate_injection_with_no_values(self):
        """Test duplicate injection handles empty field values."""
        engine = RealismEngine("high")
        
        data = [
            {"id": i}  # No email field
            for i in range(10)
        ]
        
        result = engine.apply_realism(
            data,
            entity_name="users",
            nullable_fields=set(),
            key_fields={"email"},
            numeric_fields=set()
        )
        
        # Should not crash
        assert len(result) == 10

    def test_field_identification(self):
        """Test that key fields are identified correctly."""
        schema = SchemaDesign(
            entities={
                "users": EntitySchema(
                    name="users",
                    fields=[
                        FieldSchema(name="email", type="string"),
                        FieldSchema(name="phone_number", type="string"),
                        FieldSchema(name="username", type="string"),
                        FieldSchema(name="name", type="string"),
                    ],
                    count=10
                )
            },
            relationships=[]
        )
        
        data = {
            "users": [
                {
                    "email": f"user{i}@example.com",
                    "phone_number": f"555-000{i}",
                    "username": f"user{i}",
                    "name": f"User {i}"
                }
                for i in range(100)
            ]
        }
        
        result = apply_realism_to_data(data, schema, realism_level="high")
        
        # Key fields (email, phone_number, username) should have potential duplicates
        # Name field should not (not a key field)
        unique_names = len(set(u["name"] for u in result["users"]))
        assert unique_names == 100  # Name should not have duplicates
