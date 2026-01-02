"""Tests for semantic_analyzer.py

Tests LLM-powered semantic field analysis with mocked LLM responses.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.tools.datagen.semantic_analyzer import SemanticAnalyzer
from src.tools.datagen.schema_models import SchemaDesign, EntitySchema, FieldSchema


class TestSemanticAnalyzer:
    """Tests for SemanticAnalyzer class."""

    @pytest.mark.asyncio
    async def test_analyze_schema_success(self):
        """Test successful LLM semantic analysis."""
        
        # Mock model_router
        analyzer = SemanticAnalyzer()
        
        # Mock LLM response
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content='''[
          {
            "entity_name": "flowers",
            "field_name": "name",
            "db_type": "string",
            "semantic_type": "flower_name",
            "generator_strategy": "value_catalog",
            "constraints": {"examples": ["Rose", "Tulip"]},
            "notes": "Botanical names"
          },
          {
            "entity_name": "flowers",
            "field_name": "price",
            "db_type": "float",
            "semantic_type": "price_amount",
            "generator_strategy": "numeric_distribution",
            "constraints": {"min": 0, "max": 100},
            "notes": "Price per stem"
          }
        ]''')
        
        # Patch model_router
        from src.core import model_router as mr
        original_select = mr.model_router.select_model_by_task
        original_get = mr.model_router.get_chat_model
        
        mr.model_router.select_model_by_task = lambda x: "test-model"
        mr.model_router.get_chat_model = lambda x: mock_llm
        
        try:
            # Test schema
            schema = SchemaDesign(
                entities={
                    "flowers": EntitySchema(
                        name="flowers",
                        fields=[
                            FieldSchema(name="name", type="string"),
                            FieldSchema(name="price", type="float")
                        ],
                        count=100
                    )
                },
                relationships=[]
            )
            
            # Analyze
            plan = await analyzer.analyze_schema(schema, "Generate flower catalog")
            
            # Verify
            assert "flowers" in plan.entities
            assert len(plan.entities["flowers"]) == 2
            
            # Check name field
            name_field = plan.entities["flowers"][0]
            assert name_field.field_name == "name"
            assert name_field.semantic_type == "flower_name"
            assert name_field.generator_strategy == "value_catalog"
            
            # Check price field
            price_field = plan.entities["flowers"][1]
            assert price_field.field_name == "price"
            assert price_field.semantic_type == "price_amount"
            assert price_field.generator_strategy == "numeric_distribution"
            
        finally:
            # Restore
            mr.model_router.select_model_by_task = original_select
            mr.model_router.get_chat_model = original_get

    @pytest.mark.asyncio
    async def test_analyze_schema_fallback_on_llm_timeout(self):
        """Test fallback to heuristics when LLM times out."""
        
        analyzer = SemanticAnalyzer()
        
        # Mock LLM (timeout)
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = TimeoutError("LLM timeout")
        
        # Patch model_router
        from src.core import model_router as mr
        original_select = mr.model_router.select_model_by_task
        original_get = mr.model_router.get_chat_model
        
        mr.model_router.select_model_by_task = lambda x: "test-model"
        mr.model_router.get_chat_model = lambda x: mock_llm
        
        try:
            schema = SchemaDesign(
                entities={
                    "users": EntitySchema(
                        name="users",
                        fields=[
                            FieldSchema(name="email", type="string"),
                            FieldSchema(name="country", type="string")
                        ],
                        count=100
                    )
                },
                relationships=[]
            )
            
            # Should not crash
            plan = await analyzer.analyze_schema(schema, "Generate users")
            
            # Verify heuristic fallback
            assert "users" in plan.entities
            
            # Filter out auto-generated id field
            non_id_fields = [f for f in plan.entities["users"] if f.field_name != "id"]
            assert len(non_id_fields) == 2
            
            email_field = non_id_fields[0]
            assert email_field.semantic_type == "email_address"
            assert email_field.generator_strategy == "faker"
            assert email_field.notes == "Heuristic fallback (LLM unavailable)"
            
        finally:
            mr.model_router.select_model_by_task = original_select
            mr.model_router.get_chat_model = original_get

    @pytest.mark.asyncio
    async def test_analyze_schema_fallback_on_invalid_json(self):
        """Test fallback when LLM returns invalid JSON."""
        
        analyzer = SemanticAnalyzer()
        
        # Mock LLM (invalid JSON)
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="This is not JSON {broken")
        
        # Patch model_router
        from src.core import model_router as mr
        original_select = mr.model_router.select_model_by_task
        original_get = mr.model_router.get_chat_model
        
        mr.model_router.select_model_by_task = lambda x: "test-model"
        mr.model_router.get_chat_model = lambda x: mock_llm
        
        try:
            schema = SchemaDesign(
                entities={
                    "products": EntitySchema(
                        name="products",
                        fields=[FieldSchema(name="name", type="string")],
                        count=10
                    )
                },
                relationships=[]
            )
            
            # Should fallback to heuristics
            plan = await analyzer.analyze_schema(schema, "Generate products")
            
            assert "products" in plan.entities
            assert plan.entities["products"][0].notes == "Heuristic fallback (LLM unavailable)"
            
        finally:
            mr.model_router.select_model_by_task = original_select
            mr.model_router.get_chat_model = original_get


class TestHeuristicFallback:
    """Tests for heuristic fallback analysis."""

    def test_heuristic_email_detection(self):
        """Test heuristic detects email fields."""
        analyzer = SemanticAnalyzer()
        
        schema = SchemaDesign(
            entities={
                "users": EntitySchema(
                    name="users",
                    fields=[FieldSchema(name="email", type="string")],
                    count=10
                )
            },
            relationships=[]
        )
        
        plan = analyzer._fallback_heuristic_analysis(schema)
        
        # Filter out auto-generated id field
        non_id_fields = [f for f in plan.entities["users"] if f.field_name != "id"]
        email_field = non_id_fields[0]
        assert email_field.semantic_type == "email_address"
        assert email_field.generator_strategy == "faker"

    def test_heuristic_phone_detection(self):
        """Test heuristic detects phone fields."""
        analyzer = SemanticAnalyzer()
        
        schema = SchemaDesign(
            entities={
                "contacts": EntitySchema(
                    name="contacts",
                    fields=[
                        FieldSchema(name="phone", type="string"),
                        FieldSchema(name="mobile", type="string")
                    ],
                    count=10
                )
            },
            relationships=[]
        )
        
        plan = analyzer._fallback_heuristic_analysis(schema)
        
        # Filter out id field
        non_id_fields = [f for f in plan.entities["contacts"] if f.field_name != "id"]
        assert non_id_fields[0].semantic_type == "phone_number"
        assert non_id_fields[1].semantic_type == "phone_number"

    def test_heuristic_price_detection(self):
        """Test heuristic detects price fields."""
        analyzer = SemanticAnalyzer()
        
        schema = SchemaDesign(
            entities={
                "products": EntitySchema(
                    name="products",
                    fields=[
                        FieldSchema(name="price", type="float"),
                        FieldSchema(name="cost", type="float"),
                        FieldSchema(name="amount", type="float")
                    ],
                    count=10
                )
            },
            relationships=[]
        )
        
        plan = analyzer._fallback_heuristic_analysis(schema)
        
        # Filter out id field
        non_id_fields = [f for f in plan.entities["products"] if f.field_name != "id"]
        for field in non_id_fields:
            assert field.semantic_type == "price_amount"
            assert field.generator_strategy == "numeric_distribution"

    def test_heuristic_name_field_with_entity_context(self):
        """Test heuristic uses entity context for name fields."""
        analyzer = SemanticAnalyzer()
        
        schema = SchemaDesign(
            entities={
                "flowers": EntitySchema(
                    name="flowers",
                    fields=[FieldSchema(name="name", type="string")],
                    count=10
                ),
                "universities": EntitySchema(
                    name="universities",
                    fields=[FieldSchema(name="name", type="string")],
                    count=10
                )
            },
            relationships=[]
        )
        
        plan = analyzer._fallback_heuristic_analysis(schema)
        
        # Filter out id fields
        flowers_name = [f for f in plan.entities["flowers"] if f.field_name == "name"][0]
        universities_name = [f for f in plan.entities["universities"] if f.field_name == "name"][0]
        
        # Should use entity name as context
        assert flowers_name.semantic_type == "flowers_name"
        assert universities_name.semantic_type == "universities_name"
        
        # Should suggest value catalogs for entity-specific names
        assert flowers_name.generator_strategy == "value_catalog"
        assert universities_name.generator_strategy == "value_catalog"

    def test_heuristic_type_field_with_entity_context(self):
        """Test heuristic uses entity context for type fields."""
        analyzer = SemanticAnalyzer()
        
        schema = SchemaDesign(
            entities={
                "flowers": EntitySchema(
                    name="flowers",
                    fields=[FieldSchema(name="type", type="string")],
                    count=10
                )
            },
            relationships=[]
        )
        
        plan = analyzer._fallback_heuristic_analysis(schema)
        
        # Filter out id field  
        type_field = [f for f in plan.entities["flowers"] if f.field_name == "type"][0]
        assert type_field.semantic_type == "flowers_type"
        assert type_field.generator_strategy == "value_catalog"

    def test_heuristic_datetime_fields(self):
        """Test heuristic detects datetime fields."""
        analyzer = SemanticAnalyzer()
        
        schema = SchemaDesign(
            entities={
                "events": EntitySchema(
                    name="events",
                    fields=[
                        FieldSchema(name="created_at", type="datetime"),
                        FieldSchema(name="date", type="date"),
                        FieldSchema(name="timestamp", type="string")
                    ],
                    count=10
                )
            },
            relationships=[]
        )
        
        plan = analyzer._fallback_heuristic_analysis(schema)
        
        # Filter out id field
        non_id_fields = [f for f in plan.entities["events"] if f.field_name != "id"]
        for field in non_id_fields:
            assert field.semantic_type == "timestamp"
            assert field.generator_strategy == "datetime_range"

    def test_heuristic_id_fields(self):
        """Test heuristic detects ID fields."""
        analyzer = SemanticAnalyzer()
        
        schema = SchemaDesign(
            entities={
                "records": EntitySchema(
                    name="records",
                    fields=[
                        FieldSchema(name="id", type="uuid"),
                        FieldSchema(name="user_id", type="uuid"),
                        FieldSchema(name="parent_id", type="uuid")
                    ],
                    count=10
                )
            },
            relationships=[]
        )
        
        plan = analyzer._fallback_heuristic_analysis(schema)
        
        # All fields including auto-generated id should be identifiers
        for field in plan.entities["records"]:
            assert field.semantic_type == "identifier"
            assert field.generator_strategy == "uuid"
