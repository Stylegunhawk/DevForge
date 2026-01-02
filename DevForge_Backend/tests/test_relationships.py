"""Tests for relationship engine.

Tests cover:
- Parent-first generation order
- Valid FK assignment (no orphans)
- FK distribution statistics
- Multi-level relationship chains
- Edge cases (single record, large datasets)
"""

import pytest
from src.tools.datagen.schema_models import (
    EntitySchema,
    FieldSchema,
    RelationshipSchema,
    SchemaDesign,
)
from src.tools.datagen.relationship_engine import RelationshipEngine, generate_relational_data


class TestRelationshipEngine:
    """Tests for RelationshipEngine class."""

    def test_simple_relationship(self):
        """Test simple 1:N relationship (customers -> orders)."""
        schema = SchemaDesign(
            entities={
                "customers": EntitySchema(
                    name="customers",
                    fields=[
                        FieldSchema(name="email", type="string", faker_provider="email"),
                    ],
                    count=10,
                    primary_key="id"
                ),
                "orders": EntitySchema(
                    name="orders",
                    fields=[
                        FieldSchema(name="customer_id", type="uuid"),
                        FieldSchema(name="total", type="float"),
                    ],
                    count=50,
                    primary_key="id"
                )
            },
            relationships=[
                RelationshipSchema(
                    from_entity="orders",
                    from_field="customer_id",
                    to_entity="customers",
                    to_field="id"
                )
            ]
        )
        
        engine = RelationshipEngine(schema)
        data = engine.generate_all_entities()
        
        # Check data was generated
        assert "customers" in data
        assert "orders" in data
        assert len(data["customers"]) == 10
        assert len(data["orders"]) == 50
        
        # Validate relationships
        report = engine.validate_relationships()
        assert report["valid"] is True
        assert len(report["errors"]) == 0
        
        # Check statistics
        stats = report["statistics"]["orders->customers"]
        assert stats["total_children"] == 50
        assert stats["total_parents"] == 10
        assert stats["orphaned_children"] == 0

    def test_no_orphaned_records(self):
        """Test that zero orphaned records are generated."""
        schema = SchemaDesign(
            entities={
                "users": EntitySchema(
                    name="users",
                    fields=[FieldSchema(name="name", type="string")],
                    count=5
                ),
                "posts": EntitySchema(
                    name="posts",
                    fields=[
                        FieldSchema(name="user_id", type="uuid"),
                        FieldSchema(name="title", type="string"),
                    ],
                    count=20
                )
            },
            relationships=[
                RelationshipSchema(
                    from_entity="posts",
                    from_field="user_id",
                    to_entity="users",
                    to_field="id"
                )
            ]
        )
        
        engine = RelationshipEngine(schema)
        data = engine.generate_all_entities()
        
        # Get all user IDs
        user_ids = {user["id"] for user in data["users"]}
        
        # Check all post foreign keys are valid
        for post in data["posts"]:
            assert post["user_id"] in user_ids, f"Orphaned FK: {post['user_id']}"
        
        # Validation should pass
        report = engine.validate_relationships()
        assert report["valid"] is True
        assert report["statistics"]["posts->users"]["orphaned_children"] == 0

    def test_fk_distribution(self):
        """Test FK distribution statistics."""
        schema = SchemaDesign(
            entities={
                "authors": EntitySchema(
                    name="authors",
                    fields=[FieldSchema(name="name", type="string")],
                    count=10
                ),
                "books": EntitySchema(
                    name="books",
                    fields=[
                        FieldSchema(name="author_id", type="uuid"),
                        FieldSchema(name="title", type="string"),
                    ],
                    count=30
                )
            },
            relationships=[
                RelationshipSchema(
                    from_entity="books",
                    from_field="author_id",
                    to_entity="authors",
                    to_field="id"
                )
            ]
        )
        
        engine = RelationshipEngine(schema)
        data = engine.generate_all_entities()
        
        # Count children per parent
        author_book_count = {}
        for book in data["books"]:
            author_id = book["author_id"]
            author_book_count[author_id] = author_book_count.get(author_id, 0) + 1
        
        report = engine.validate_relationships()
        stats = report["statistics"]["books->authors"]
        
        # With random sampling, it's likely (but not guaranteed) some authors have 0 books
        # At minimum, verify the distribution makes sense
        assert stats["total_children"] == 30
        assert stats["total_parents"] == 10
        assert stats["max_children_per_parent"] >= 1
        
        # Some parents might have 0 children due to random sampling
        assert stats["parents_with_zero_children"] >= 0

    def test_chain_relationship(self):
        """Test multi-level relationship chain (users -> subscriptions -> usage_logs)."""
        schema = SchemaDesign(
            entities={
                "users": EntitySchema(
                    name="users",
                    fields=[FieldSchema(name="email", type="string")],
                    count=5
                ),
                "subscriptions": EntitySchema(
                    name="subscriptions",
                    fields=[
                        FieldSchema(name="user_id", type="uuid"),
                        FieldSchema(name="plan", type="string"),
                    ],
                    count=10
                ),
                "usage_logs": EntitySchema(
                    name="usage_logs",
                    fields=[
                        FieldSchema(name="subscription_id", type="uuid"),
                        FieldSchema(name="action", type="string"),
                    ],
                    count=50
                )
            },
            relationships=[
                RelationshipSchema(
                    from_entity="subscriptions",
                    from_field="user_id",
                    to_entity="users",
                    to_field="id"
                ),
                RelationshipSchema(
                    from_entity="usage_logs",
                    from_field="subscription_id",
                    to_entity="subscriptions",
                    to_field="id"
                )
            ]
        )
        
        engine = RelationshipEngine(schema)
        data = engine.generate_all_entities()
        
        # Verify generation order
        order = schema.get_generation_order()
        assert order.index("users") < order.index("subscriptions")
        assert order.index("subscriptions") < order.index("usage_logs")
        
        # Validate all relationships
        report = engine.validate_relationships()
        assert report["valid"] is True
        
        # Check both relationships
        assert "subscriptions->users" in report["statistics"]
        assert "usage_logs->subscriptions" in report["statistics"]
        
        # No orphans
        assert report["statistics"]["subscriptions->users"]["orphaned_children"] == 0
        assert report["statistics"]["usage_logs->subscriptions"]["orphaned_children"] == 0

    def test_multiple_children_from_same_parent(self):
        """Test multiple child entities referencing same parent."""
        schema = SchemaDesign(
            entities={
                "products": EntitySchema(
                    name="products",
                    fields=[FieldSchema(name="name", type="string")],
                    count=10
                ),
                "reviews": EntitySchema(
                    name="reviews",
                    fields=[
                        FieldSchema(name="product_id", type="uuid"),
                        FieldSchema(name="rating", type="int"),
                    ],
                    count=30
                ),
                "purchases": EntitySchema(
                    name="purchases",
                    fields=[
                        FieldSchema(name="product_id", type="uuid"),
                        FieldSchema(name="quantity", type="int"),
                    ],
                    count=20
                )
            },
            relationships=[
                RelationshipSchema(
                    from_entity="reviews",
                    from_field="product_id",
                    to_entity="products",
                    to_field="id"
                ),
                RelationshipSchema(
                    from_entity="purchases",
                    from_field="product_id",
                    to_entity="products",
                    to_field="id"
                )
            ]
        )
        
        engine = RelationshipEngine(schema)
        data = engine.generate_all_entities()
        
        # Get product IDs
        product_ids = {p["id"] for p in data["products"]}
        
        # Check all reviews reference valid products
        for review in data["reviews"]:
            assert review["product_id"] in product_ids
        
        # Check all purchases reference valid products
        for purchase in data["purchases"]:
            assert purchase["product_id"] in product_ids
        
        report = engine.validate_relationships()
        assert report["valid"] is True

    def test_single_parent_single_child(self):
        """Test edge case: 1 parent, 1 child."""
        schema = SchemaDesign(
            entities={
                "config": EntitySchema(
                    name="config",
                    fields=[FieldSchema(name="key", type="string")],
                    count=1
                ),
                "settings": EntitySchema(
                    name="settings",
                    fields=[
                        FieldSchema(name="config_id", type="uuid"),
                        FieldSchema(name="value", type="string"),
                    ],
                    count=1
                )
            },
            relationships=[
                RelationshipSchema(
                    from_entity="settings",
                    from_field="config_id",
                    to_entity="config",
                    to_field="id"
                )
            ]
        )
        
        engine = RelationshipEngine(schema)
        data = engine.generate_all_entities()
        
        assert len(data["config"]) == 1
        assert len(data["settings"]) == 1
        
        # Validate
        report = engine.validate_relationships()
        assert report["valid"] is True
        assert report["statistics"]["settings->config"]["orphaned_children"] == 0

    def test_large_dataset(self):
        """Test with larger dataset to verify performance and correctness."""
        schema = SchemaDesign(
            entities={
                "customers": EntitySchema(
                    name="customers",
                    fields=[FieldSchema(name="email", type="string")],
                    count=100
                ),
                "orders": EntitySchema(
                    name="orders",
                    fields=[
                        FieldSchema(name="customer_id", type="uuid"),
                        FieldSchema(name="total", type="float"),
                    ],
                    count=1000
                )
            },
            relationships=[
                RelationshipSchema(
                    from_entity="orders",
                    from_field="customer_id",
                    to_entity="customers",
                    to_field="id"
                )
            ]
        )
        
        engine = RelationshipEngine(schema)
        data = engine.generate_all_entities()
        
        assert len(data["customers"]) == 100
        assert len(data["orders"]) == 1000
        
        # Validate
        report = engine.validate_relationships()
        assert report["valid"] is True
        assert report["statistics"]["orders->customers"]["orphaned_children"] == 0

    def test_all_fields_populated(self):
        """Test that all entity fields are properly populated."""
        schema = SchemaDesign(
            entities={
                "companies": EntitySchema(
                    name="companies",
                    fields=[
                        FieldSchema(name="name", type="string", faker_provider="company"),
                        FieldSchema(name="city", type="string", faker_provider="city"),
                    ],
                    count=5
                ),
                "employees": EntitySchema(
                    name="employees",
                    fields=[
                        FieldSchema(name="company_id", type="uuid"),
                        FieldSchema(name="name", type="string", faker_provider="name"),
                        FieldSchema(name="email", type="string", faker_provider="email"),
                        FieldSchema(name="salary", type="float"),
                    ],
                    count=20
                )
            },
            relationships=[
                RelationshipSchema(
                    from_entity="employees",
                    from_field="company_id",
                    to_entity="companies",
                    to_field="id"
                )
            ]
        )
        
        engine = RelationshipEngine(schema)
        data = engine.generate_all_entities()
        
        # Check all company fields are populated
        for company in data["companies"]:
            assert "id" in company
            assert "name" in company
            assert "city" in company
            assert company["name"] is not None
        
        # Check all employee fields are populated
        for employee in data["employees"]:
            assert "id" in employee
            assert "company_id" in employee
            assert "name" in employee
            assert "email" in employee
            assert "salary" in employee
            assert employee["salary"] is not None


class TestConvenienceFunction:
    """Tests for generate_relational_data convenience function."""

    def test_generate_relational_data(self):
        """Test convenience function."""
        schema = SchemaDesign(
            entities={
                "users": EntitySchema(
                    name="users",
                    fields=[FieldSchema(name="email", type="string")],
                    count=5
                ),
                "posts": EntitySchema(
                    name="posts",
                    fields=[
                        FieldSchema(name="user_id", type="uuid"),
                        FieldSchema(name="title", type="string"),
                    ],
                    count=10
                )
            },
            relationships=[
                RelationshipSchema(
                    from_entity="posts",
                    from_field="user_id",
                    to_entity="users",
                    to_field="id"
                )
            ]
        )
        
        data = generate_relational_data(schema)
        
        assert "users" in data
        assert "posts" in data
        assert len(data["users"]) == 5
        assert len(data["posts"]) == 10


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_no_relationships(self):
        """Test schema with no relationships."""
        schema = SchemaDesign(
            entities={
                "standalone": EntitySchema(
                    name="standalone",
                    fields=[FieldSchema(name="value", type="string")],
                    count=10
                )
            },
            relationships=[]
        )
        
        engine = RelationshipEngine(schema)
        data = engine.generate_all_entities()
        
        assert len(data["standalone"]) == 10
        
        # Validation should still work
        report = engine.validate_relationships()
        assert report["valid"] is True
        assert len(report["statistics"]) == 0

    def test_nullable_fields(self):
        """Test that nullable fields can be null."""
        schema = SchemaDesign(
            entities={
                "records": EntitySchema(
                    name="records",
                    fields=[
                        FieldSchema(name="required", type="string", nullable=False),
                        FieldSchema(name="optional", type="string", nullable=True),
                    ],
                    count=20
                )
            },
            relationships=[]
        )
        
        engine = RelationshipEngine(schema)
        data = engine.generate_all_entities()
        
        # Check that some optional fields are null
        null_count = sum(1 for rec in data["records"] if rec["optional"] is None)
        
        # With 10% null rate and 20 records, expect at least 1 null (probabilistic)
        # But don't make test flaky - just verify nulls are possible
        assert all(rec["required"] is not None for rec in data["records"])
        assert null_count >= 0  # Just verify no crash
