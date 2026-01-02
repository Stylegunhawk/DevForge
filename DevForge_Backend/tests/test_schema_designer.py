"""Tests for schema models and schema designer.

Tests cover:
- Pydantic model validation
- Schema relationships and referential integrity
- Topological sort for generation order
- LLM schema design with mocked responses
- Fallback behavior
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.tools.datagen.schema_models import (
    EntitySchema,
    FieldSchema,
    RelationshipSchema,
    SchemaDesign,
    create_minimal_schema,
)
from src.tools.datagen.schema_designer import SchemaDesigner


class TestFieldSchema:
    """Tests for FieldSchema model."""

    def test_valid_field(self):
        """Test creating a valid field."""
        field = FieldSchema(name="email", type="string", faker_provider="email")
        assert field.name == "email"
        assert field.type == "string"
        assert field.nullable is False
        assert field.faker_provider == "email"

    def test_field_name_normalization(self):
        """Test field name is lowercased."""
        field = FieldSchema(name="Email", type="string")
        assert field.name == "email"

    def test_field_name_with_underscore(self):
        """Test field name with underscores is valid."""
        field = FieldSchema(name="created_at", type="datetime")
        assert field.name == "created_at"

    def test_invalid_field_name_special_chars(self):
        """Test field name with special characters fails."""
        with pytest.raises(ValueError, match="alphanumeric"):
            FieldSchema(name="email@field", type="string")

    def test_invalid_field_type(self):
        """Test invalid field type fails."""
        with pytest.raises(ValueError):
            FieldSchema(name="test", type="invalid_type")

    def test_all_valid_types(self):
        """Test all valid field types."""
        valid_types = ["string", "int", "float", "date", "datetime", "boolean", "uuid"]
        for field_type in valid_types:
            field = FieldSchema(name="test", type=field_type)
            assert field.type == field_type


class TestEntitySchema:
    """Tests for EntitySchema model."""

    def test_valid_entity(self):
        """Test creating a valid entity."""
        entity = EntitySchema(
            name="users",
            fields=[
                FieldSchema(name="email", type="string"),
                FieldSchema(name="age", type="int"),
            ],
            count=100
        )
        assert entity.name == "users"
        assert len(entity.fields) == 3  # 2 + auto-added id
        assert entity.count == 100
        assert entity.primary_key == "id"

    def test_entity_auto_adds_primary_key(self):
        """Test that primary key is auto-added if missing."""
        entity = EntitySchema(
            name="users",
            fields=[FieldSchema(name="email", type="string")],
        )
        field_names = [f.name for f in entity.fields]
        assert "id" in field_names
        # ID should be first
        assert entity.fields[0].name == "id"
        assert entity.fields[0].type == "uuid"

    def test_entity_with_custom_pk(self):
        """Test entity with custom primary key."""
        entity = EntitySchema(
            name="users",
            fields=[
                FieldSchema(name="user_id", type="uuid"),
                FieldSchema(name="email", type="string"),
            ],
            primary_key="user_id"
        )
        assert entity.primary_key == "user_id"
        # Should not add duplicate pk
        assert len([f for f in entity.fields if f.name == "user_id"]) == 1

    def test_entity_count_limits(self):
        """Test entity count constraints."""
        # Valid count
        entity = EntitySchema(
            name="users",
            fields=[FieldSchema(name="x", type="string")],
            count=10000
        )
        assert entity.count == 10000

        # Invalid: too high
        with pytest.raises(ValueError):
            EntitySchema(
                name="users",
                fields=[FieldSchema(name="x", type="string")],
                count=100001
            )

        # Invalid: zero
        with pytest.raises(ValueError):
            EntitySchema(
                name="users",
                fields=[FieldSchema(name="x", type="string")],
                count=0
            )


class TestRelationshipSchema:
    """Tests for RelationshipSchema model."""

    def test_valid_relationship(self):
        """Test creating a valid relationship."""
        rel = RelationshipSchema(
            from_entity="orders",
            from_field="customer_id",
            to_entity="customers",
            to_field="id",
            cardinality="1:N"
        )
        assert rel.from_entity == "orders"
        assert rel.to_entity == "customers"
        assert rel.cardinality == "1:N"

    def test_default_cardinality(self):
        """Test default cardinality is 1:N."""
        rel = RelationshipSchema(
            from_entity="orders",
            from_field="customer_id",
            to_entity="customers"
        )
        assert rel.cardinality == "1:N"
        assert rel.to_field == "id"


class TestSchemaDesign:
    """Tests for SchemaDesign model."""

    def test_valid_schema_no_relationships(self):
        """Test schema with no relationships."""
        schema = SchemaDesign(
            entities={
                "users": EntitySchema(
                    name="users",
                    fields=[FieldSchema(name="email", type="string")],
                    count=100
                )
            }
        )
        assert "users" in schema.entities
        assert len(schema.relationships) == 0

    def test_valid_schema_with_relationships(self):
        """Test schema with valid relationships."""
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
                    count=500
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
        assert len(schema.relationships) == 1

    def test_invalid_relationship_missing_entity(self):
        """Test relationship with missing entity fails."""
        with pytest.raises(ValueError, match="not found in entities"):
            SchemaDesign(
                entities={
                    "orders": EntitySchema(
                        name="orders",
                        fields=[FieldSchema(name="customer_id", type="uuid")],
                    )
                },
                relationships=[
                    RelationshipSchema(
                        from_entity="orders",
                        from_field="customer_id",
                        to_entity="customers",  # Does not exist!
                        to_field="id"
                    )
                ]
            )

    def test_generation_order_simple(self):
        """Test generation order with simple dependency."""
        schema = SchemaDesign(
            entities={
                "customers": EntitySchema(
                    name="customers",
                    fields=[FieldSchema(name="email", type="string")],
                ),
                "orders": EntitySchema(
                    name="orders",
                    fields=[FieldSchema(name="customer_id", type="uuid")],
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
        
        order = schema.get_generation_order()
        # customers must come before orders
        assert order.index("customers") < order.index("orders")

    def test_generation_order_chain(self):
        """Test generation order with chain dependency."""
        schema = SchemaDesign(
            entities={
                "users": EntitySchema(
                    name="users",
                    fields=[FieldSchema(name="email", type="string")],
                ),
                "subscriptions": EntitySchema(
                    name="subscriptions",
                    fields=[FieldSchema(name="user_id", type="uuid")],
                ),
                "usage_logs": EntitySchema(
                    name="usage_logs",
                    fields=[FieldSchema(name="subscription_id", type="uuid")],
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
        
        order = schema.get_generation_order()
        assert order.index("users") < order.index("subscriptions")
        assert order.index("subscriptions") < order.index("usage_logs")


class TestMinimalSchema:
    """Tests for create_minimal_schema function."""

    def test_minimal_schema_default_rows(self):
        """Test minimal schema with default rows."""
        schema = create_minimal_schema()
        assert "records" in schema.entities
        assert schema.entities["records"].count == 100

    def test_minimal_schema_custom_rows(self):
        """Test minimal schema with custom rows."""
        schema = create_minimal_schema(rows=500)
        assert schema.entities["records"].count == 500

    def test_minimal_schema_has_common_fields(self):
        """Test minimal schema has common fields."""
        schema = create_minimal_schema()
        field_names = [f.name for f in schema.entities["records"].fields]
        assert "name" in field_names
        assert "email" in field_names


class TestSchemaDesigner:
    """Tests for SchemaDesigner class."""

    def test_get_ecommerce_template(self):
        """Test getting ecommerce domain template."""
        designer = SchemaDesigner()
        template = designer.get_domain_template("ecommerce")
        
        assert template is not None
        assert "customers" in template.entities
        assert "products" in template.entities
        assert "orders" in template.entities

    def test_get_saas_template(self):
        """Test getting saas domain template."""
        designer = SchemaDesigner()
        template = designer.get_domain_template("saas")
        
        assert template is not None
        assert "users" in template.entities
        assert "subscriptions" in template.entities
        assert "usage_logs" in template.entities

    def test_get_unknown_template(self):
        """Test getting unknown domain returns None."""
        designer = SchemaDesigner()
        template = designer.get_domain_template("unknown_domain")
        assert template is None

    def test_infer_domain_ecommerce(self):
        """Test domain inference for ecommerce keywords."""
        designer = SchemaDesigner()
        
        assert designer._infer_domain("Generate data for an online store") == "ecommerce"
        assert designer._infer_domain("Create product catalog with orders") == "ecommerce"
        assert designer._infer_domain("E-commerce customer database") == "ecommerce"

    def test_infer_domain_saas(self):
        """Test domain inference for saas keywords."""
        designer = SchemaDesigner()
        
        assert designer._infer_domain("SaaS platform usage data") == "saas"
        assert designer._infer_domain("User subscriptions and billing") == "saas"
        assert designer._infer_domain("API usage dashboard data") == "saas"

    def test_infer_domain_unknown(self):
        """Test domain inference returns None for generic prompts."""
        designer = SchemaDesigner()
        
        assert designer._infer_domain("Generate random test data") is None
        assert designer._infer_domain("Mock data for testing") is None

    def test_design_schema_sync_with_domain(self):
        """Test synchronous schema design with domain."""
        designer = SchemaDesigner()
        schema = designer.design_schema_sync(
            prompt="any prompt",
            domain="ecommerce"
        )
        
        assert schema.domain == "ecommerce"
        assert "customers" in schema.entities

    def test_design_schema_sync_infer_domain(self):
        """Test synchronous schema design with domain inference."""
        designer = SchemaDesigner()
        schema = designer.design_schema_sync(
            prompt="Generate customer orders for an e-commerce platform"
        )
        
        assert "customers" in schema.entities or "records" in schema.entities

    def test_design_schema_sync_fallback(self):
        """Test synchronous schema design falls back to minimal."""
        designer = SchemaDesigner()
        schema = designer.design_schema_sync(
            prompt="Generate random stuff",
            default_rows=200
        )
        
        assert "records" in schema.entities
        assert schema.entities["records"].count == 200

    @pytest.mark.asyncio
    async def test_design_schema_with_domain(self):
        """Test async schema design uses domain template."""
        designer = SchemaDesigner()
        schema = await designer.design_schema(
            prompt="any prompt",
            domain="saas"
        )
        
        assert schema.domain == "saas"
        assert "users" in schema.entities

    @pytest.mark.asyncio
    async def test_design_schema_llm_fallback(self):
        """Test async schema design falls back on LLM failure."""
        designer = SchemaDesigner()
        
        # Mock model_router to raise exception
        with patch.object(designer, '_design_with_llm', return_value=None):
            schema = await designer.design_schema(
                prompt="Create user data for a SaaS app"
            )
        
        # Should infer domain and use template
        assert "users" in schema.entities or "records" in schema.entities

    def test_extract_json_from_code_block(self):
        """Test JSON extraction from markdown code block."""
        designer = SchemaDesigner()
        
        text = '''Here's the schema:
```json
{"entities": {"test": {"name": "test", "fields": [], "count": 10}}}
```
'''
        result = designer._extract_json(text)
        assert result is not None
        assert "entities" in result

    def test_extract_json_raw(self):
        """Test JSON extraction from raw text."""
        designer = SchemaDesigner()
        
        text = '{"entities": {"test": {"name": "test", "fields": [], "count": 10}}}'
        result = designer._extract_json(text)
        assert result is not None
        assert "entities" in result

    def test_extract_json_invalid(self):
        """Test JSON extraction returns None for invalid JSON."""
        designer = SchemaDesigner()
        
        text = "This is not valid JSON at all"
        result = designer._extract_json(text)
        assert result is None


class TestSchemaDesignerLLMIntegration:
    """Tests for LLM integration with mocked responses."""

    @pytest.mark.asyncio
    async def test_design_with_llm_valid_response(self):
        """Test LLM schema design with valid response."""
        designer = SchemaDesigner()
        
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "entities": {
                "users": {
                    "name": "users",
                    "fields": [
                        {"name": "email", "type": "string", "faker_provider": "email"}
                    ],
                    "count": 100,
                    "primary_key": "id"
                }
            },
            "relationships": []
        })
        
        mock_chat_model = AsyncMock()
        mock_chat_model.ainvoke.return_value = mock_response
        
        with patch('src.tools.datagen.schema_designer.model_router') as mock_router:
            mock_router.select_model_by_task.return_value = "test-model"
            mock_router.get_chat_model.return_value = mock_chat_model
            
            schema = await designer._design_with_llm("Create user data", 100)
        
        assert schema is not None
        assert "users" in schema.entities

    @pytest.mark.asyncio
    async def test_design_with_llm_invalid_response(self):
        """Test LLM schema design handles invalid response."""
        designer = SchemaDesigner()
        
        # Mock invalid LLM response
        mock_response = MagicMock()
        mock_response.content = "This is not valid JSON"
        
        mock_chat_model = AsyncMock()
        mock_chat_model.ainvoke.return_value = mock_response
        
        with patch('src.tools.datagen.schema_designer.model_router') as mock_router:
            mock_router.select_model_by_task.return_value = "test-model"
            mock_router.get_chat_model.return_value = mock_chat_model
            
            schema = await designer._design_with_llm("Create user data", 100)
        
        assert schema is None  # Should return None, not crash
