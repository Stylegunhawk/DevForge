"""Integration tests for Phase 1 pattern constraints."""

import pytest
import json
import asyncio
import re
from src.agents.datagen.agent import datagen_agent

@pytest.mark.asyncio
async def test_pattern_constraint_integration():
    """Verify pattern constraints are respected."""
    args = {
        "rows": 10,
        "format": "json",
        "prompt": 'Generate products with sku (pattern: "^[A-Z]{3}-[0-9]{6}$").',
        "enable_semantic_generation": True
    }
    
    result = await datagen_agent(args)
    
    assert result["success"] is True
    data_dict = result["data"]["data"]
    
    # Find products entity
    products_json = None
    for name, json_str in data_dict.items():
        if "product" in name.lower():
            products_json = json_str
            break
            
    assert products_json is not None, "Product entity not found"
    
    records = json.loads(products_json)
    pattern = re.compile(r'^[A-Z]{3}-[0-9]{6}$')
    
    for record in records:
        if "sku" in record:
            assert pattern.match(record["sku"]), f"Invalid SKU: {record['sku']}"
