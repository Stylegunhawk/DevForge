"""Tests for value_catalog_builder.py

Tests LLM-powered value catalog generation with mocked LLM responses.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.tools.datagen.value_catalog_builder import CatalogBuilder
from src.tools.datagen.semantic_models import (
    SemanticPlan,
    FieldSemanticInfo,
)


class TestCatalogBuilder:
    """Tests for CatalogBuilder class."""

    @pytest.mark.asyncio
    async def test_build_catalogs_success(self):
        """Test successful catalog generation."""
        
        builder = CatalogBuilder()
        
        # Mock LLM
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content='''
        ["Rose", "Tulip", "Orchid", "Lily", "Sunflower", "Daisy"]
        ''')
        
        # Patch model_router
        from src.core import model_router as mr
        original_select = mr.model_router.select_model_by_task
        original_get = mr.model_router.get_chat_model
        
        mr.model_router.select_model_by_task = lambda x: "test-model"
        mr.model_router.get_chat_model = lambda x: mock_llm
        
        try:
            # Semantic plan with value_catalog field
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
            
            # Build catalogs
            catalogs = await builder.build_catalogs(plan, "Generate flower catalog")
            
            # Verify
            assert len(catalogs) == 1
            catalog_key = list(catalogs.keys())[0]
            assert "Rose" in catalogs[catalog_key].values
            assert "Tulip" in catalogs[catalog_key].values
            assert catalogs[catalog_key].semantic_type == "flower_name"
            
        finally:
            mr.model_router.select_model_by_task = original_select
            mr.model_router.get_chat_model = original_get

    @pytest.mark.asyncio
    async def test_build_catalogs_caching(self):
        """Test catalog caching works."""
        
        builder = CatalogBuilder()
        
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content='["Value1", "Value2", "Value3"]')
        
        from src.core import model_router as mr
        original_select = mr.model_router.select_model_by_task
        original_get = mr.model_router.get_chat_model
        
        mr.model_router.select_model_by_task = lambda x: "test-model"
        mr.model_router.get_chat_model = lambda x: mock_llm
        
        try:
            plan = SemanticPlan(
                entities={
                    "test": [
                        FieldSemanticInfo(
                            entity_name="test",
                            field_name="name",
                            db_type="string",
                            semantic_type="test_name",
                            generator_strategy="value_catalog"
                        )
                    ]
                },
                value_catalogs={}
            )
            
            # First call
            await builder.build_catalogs(plan, "Test prompt")
            assert mock_llm.ainvoke.call_count == 1
            
            # Second call with same prompt/schema
            await builder.build_catalogs(plan, "Test prompt")
            # Should not make additional LLM call (cached)
            assert mock_llm.ainvoke.call_count == 1
            
        finally:
            mr.model_router.select_model_by_task = original_select
            mr.model_router.get_chat_model = original_get

    @pytest.mark.asyncio
    async def test_build_catalogs_empty_response(self):
        """Test handling of empty LLM response."""
        
        builder = CatalogBuilder()
        
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content='[]')
        
        from src.core import model_router as mr
        original_select = mr.model_router.select_model_by_task
        original_get = mr.model_router.get_chat_model
        
        mr.model_router.select_model_by_task = lambda x: "test-model"
        mr.model_router.get_chat_model = lambda x: mock_llm
        
        try:
            plan = SemanticPlan(
                entities={
                    "test": [
                        FieldSemanticInfo(
                            entity_name="test",
                            field_name="name",
                            db_type="string",
                            semantic_type="test_name",
                            generator_strategy="value_catalog"
                        )
                    ]
                },
                value_catalogs={}
            )
            
            # Should not crash
            catalogs = await builder.build_catalogs(plan, "Test")
            
            # Empty catalog should not be added
            assert len(catalogs) == 0
            
        finally:
            mr.model_router.select_model_by_task = original_select
            mr.model_router.get_chat_model = original_get

    @pytest.mark.asyncio
    async def test_build_catalogs_invalid_json(self):
        """Test handling of invalid JSON response."""
        
        builder = CatalogBuilder()
        
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content='This is not JSON')
        
        from src.core import model_router as mr
        original_select = mr.model_router.select_model_by_task
        original_get = mr.model_router.get_chat_model
        
        mr.model_router.select_model_by_task = lambda x: "test-model"
        mr.model_router.get_chat_model = lambda x: mock_llm
        
        try:
            plan = SemanticPlan(
                entities={
                    "test": [
                        FieldSemanticInfo(
                            entity_name="test",
                            field_name="name",
                            db_type="string",
                            semantic_type="test_name",
                            generator_strategy="value_catalog"
                        )
                    ]
                },
                value_catalogs={}
            )
            
            # Should not crash
            catalogs = await builder.build_catalogs(plan, "Test")
            
            # Failed catalog should not be added
            assert len(catalogs) == 0
            
        finally:
            mr.model_router.select_model_by_task = original_select
            mr.model_router.get_chat_model = original_get

    @pytest.mark.asyncio
    async def test_build_catalogs_deduplication(self):
        """Test that duplicate values are removed."""
        
        builder = CatalogBuilder()
        
        # LLM returns duplicates
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content='''
        ["Rose", "Tulip", "Rose", "Orchid", "Tulip", "Lily"]
        ''')
        
        from src.core import model_router as mr
        original_select = mr.model_router.select_model_by_task
        original_get = mr.model_router.get_chat_model
        
        mr.model_router.select_model_by_task = lambda x: "test-model"
        mr.model_router.get_chat_model = lambda x: mock_llm
        
        try:
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
            
            catalogs = await builder.build_catalogs(plan, "Flowers")
            
            # Should deduplicate
            catalog_key = list(catalogs.keys())[0]
            values = catalogs[catalog_key].values
            
            # Should have only unique values
            assert len(values) == 4  # Rose, Tulip, Orchid, Lily
            assert len(values) == len(set(values))
            
        finally:
            mr.model_router.select_model_by_task = original_select
            mr.model_router.get_chat_model = original_get

    @pytest.mark.asyncio
    async def test_build_catalogs_no_catalog_fields(self):
        """Test with plan that has no value_catalog fields."""
        
        builder = CatalogBuilder()
        
        plan = SemanticPlan(
            entities={
                "users": [
                    FieldSemanticInfo(
                        entity_name="users",
                        field_name="email",
                        db_type="string",
                        semantic_type="email_address",
                        generator_strategy="faker"  # Not value_catalog
                    )
                ]
            },
            value_catalogs={}
        )
        
        # Should not call LLM
        catalogs = await builder.build_catalogs(plan, "Test")
        
        # No catalogs generated
        assert len(catalogs) == 0

    def test_parse_catalog_response_with_markdown(self):
        """Test parsing response with markdown code fences."""
        
        builder = CatalogBuilder()
        
        response = '''```json
        ["Rose", "Tulip", "Orchid"]
        ```'''
        
        values = builder._parse_catalog_response(response, 3)
        
        assert len(values) == 3
        assert "Rose" in values
        assert "Tulip" in values

    def test_parse_catalog_response_plain_json(self):
        """Test parsing plain JSON response."""
        
        builder = CatalogBuilder()
        
        response = '["Value1", "Value2", "Value3"]'
        
        values = builder._parse_catalog_response(response, 3)
        
        assert len(values) == 3
        assert "Value1" in values

    def test_cache_key_generation(self):
        """Test cache key generation is consistent."""
        
        builder = CatalogBuilder()
        
        field_info = FieldSemanticInfo(
            entity_name="flowers",
            field_name="name",
            db_type="string",
            semantic_type="flower_name",
            generator_strategy="value_catalog"
        )
        
        # Same prompt should give same key
        key1 = builder._generate_cache_key(field_info, "Generate flowers")
        key2 = builder._generate_cache_key(field_info, "Generate flowers")
        
        assert key1 == key2
        
        # Different prompt should give different key
        key3 = builder._generate_cache_key(field_info, "Different prompt")
        
        assert key1 != key3
