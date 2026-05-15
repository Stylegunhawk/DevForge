"""Tests for CatalogFactory.get_entity_catalogs (v0.9 catalog-sandbox).

Verifies the batched per-entity catalog method:
  - LLM is called via model_router.invoke_with_usage with the right task_type
  - Result is parsed into {field_name: [50 strings]}
  - L1/L2 cache keys are honored
  - Fallback to _smart_field_fallback on LLM failure / malformed JSON
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.tools.datagen.catalog_factory import CatalogFactory


@pytest.fixture
def factory():
    return CatalogFactory(cache_ttl_seconds=3600)


def _ok_response(payload: dict) -> MagicMock:
    """Build a fake UsageResult-shaped object with `.content`."""
    obj = MagicMock()
    obj.content = json.dumps(payload)
    return obj


# ---------- Happy path ----------

@pytest.mark.asyncio
async def test_returns_dict_of_string_fields_only(factory):
    fields = [("name", "string"), ("age", "int"), ("email", "string")]
    payload = {"name": [f"name_{i}" for i in range(50)],
               "email": [f"e{i}@ex.com" for i in range(50)]}
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=_ok_response(payload))
        result = await factory.get_entity_catalogs(
            entity_name="customer", fields=fields,
            user_prompt="customers for ecommerce", count=50,
        )
    assert set(result.keys()) == {"name", "email"}
    assert len(result["name"]) == 50
    assert len(result["email"]) == 50

@pytest.mark.asyncio
async def test_invokes_model_router_with_correct_task_type(factory):
    fields = [("name", "string")]
    payload = {"name": [f"n{i}" for i in range(50)]}
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=_ok_response(payload))
        await factory.get_entity_catalogs(
            entity_name="x", fields=fields, user_prompt="prompt",
            tenant_id="t1", integration_name="vscode", user_id="u1",
        )
    call_kwargs = mr.invoke_with_usage.call_args.kwargs
    assert call_kwargs["task_type"] == "datagen_catalog_generation"
    assert call_kwargs["tenant_id"] == "t1"
    assert call_kwargs["integration_name"] == "vscode"
    assert call_kwargs["user_id"] == "u1"


# ---------- Caching ----------

@pytest.mark.asyncio
async def test_l1_cache_hit_avoids_second_llm_call(factory):
    fields = [("name", "string")]
    payload = {"name": [f"n{i}" for i in range(50)]}
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=_ok_response(payload))
        await factory.get_entity_catalogs("e", fields, "p")
        await factory.get_entity_catalogs("e", fields, "p")
    assert mr.invoke_with_usage.call_count == 1


@pytest.mark.asyncio
async def test_different_prompt_misses_cache(factory):
    fields = [("name", "string")]
    payload = {"name": [f"n{i}" for i in range(50)]}
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=_ok_response(payload))
        await factory.get_entity_catalogs("e", fields, "prompt-A")
        await factory.get_entity_catalogs("e", fields, "prompt-B")
    assert mr.invoke_with_usage.call_count == 2


@pytest.mark.asyncio
async def test_different_entity_misses_cache(factory):
    fields = [("name", "string")]
    payload = {"name": [f"n{i}" for i in range(50)]}
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=_ok_response(payload))
        await factory.get_entity_catalogs("customer", fields, "p")
        await factory.get_entity_catalogs("product", fields, "p")
    assert mr.invoke_with_usage.call_count == 2


# ---------- Fallback ----------

@pytest.mark.asyncio
async def test_llm_exception_triggers_fallback(factory):
    fields = [("name", "string"), ("email", "string")]
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        result = await factory.get_entity_catalogs("x", fields, "p")
    assert set(result.keys()) == {"name", "email"}
    assert len(result["name"]) == 50
    assert len(result["email"]) == 50
    # Fallback values should be plausible Faker output (not "name_value_1")
    assert all(isinstance(v, str) and v for v in result["name"])
    assert not any(v.startswith("name_value_") for v in result["name"])


@pytest.mark.asyncio
async def test_malformed_json_triggers_fallback(factory):
    fields = [("name", "string")]
    bad_response = MagicMock()
    bad_response.content = "{ not json at all"
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=bad_response)
        result = await factory.get_entity_catalogs("x", fields, "p")
    assert len(result["name"]) == 50


@pytest.mark.asyncio
async def test_too_few_values_per_field_triggers_fallback(factory):
    fields = [("name", "string")]
    payload = {"name": [f"n{i}" for i in range(10)]}  # only 10, need >=40
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task.return_value = "test-model"
        mr.invoke_with_usage = AsyncMock(return_value=_ok_response(payload))
        result = await factory.get_entity_catalogs("x", fields, "p")
    assert len(result["name"]) == 50  # padded by fallback


# ---------- Schema ----------

@pytest.mark.asyncio
async def test_empty_fields_returns_empty_dict(factory):
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task = MagicMock(return_value="test-model")
        mr.invoke_with_usage = AsyncMock()
        result = await factory.get_entity_catalogs("x", fields=[], user_prompt="p")
    assert result == {}
    mr.invoke_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_no_string_fields_returns_empty_dict(factory):
    with patch("src.tools.datagen.catalog_factory.model_router") as mr:
        mr.select_model_by_task = MagicMock(return_value="test-model")
        mr.invoke_with_usage = AsyncMock()
        result = await factory.get_entity_catalogs(
            "x", fields=[("age", "int"), ("ok", "boolean")], user_prompt="p",
        )
    assert result == {}
    mr.invoke_with_usage.assert_not_called()
