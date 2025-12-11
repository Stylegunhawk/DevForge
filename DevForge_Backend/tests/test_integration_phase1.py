"""Integration tests for Phase 1 semantic analyzer."""

import pytest
import json
import asyncio
from src.agents.datagen.agent import datagen_agent

@pytest.mark.asyncio
async def test_no_llm_prose_integration():
    """
    CRITICAL: Verify LLM prose cannot appear via agent.
    This tests the full integration path including agent -> advanced_generator_v2 -> semantic_analyzer.
    """
    args = {
        "rows": 10,
        "format": "json",
        "prompt": "Generate bank accounts with account_number (numeric) and balance.",
        "enable_semantic_generation": True
    }
    
    result = await datagen_agent(args)
    
    assert result["success"] is True
    assert result["mode"] == "v2"
    
    # Result data structure from agent:
    # {
    #   "entities": [...],
    #   "schema": {...},
    #   "data": { "entity_name": "json_string" },
    #   "semantic_generation_used": True,
    #   "metadata": {...}
    # }
    
    data_dict = result["data"]["data"]
    metadata = result["data"]["metadata"]
    
    # Verify semantic analysis was actually used
    assert result["data"]["semantic_generation_used"] is True
    assert metadata["semantic_analysis_summary"]["enabled"] is True
    
    # Check for LLM prose contamination
    for entity_name, json_str in data_dict.items():
        # CRITICAL CHECK: No "Agent every" or "Choice whatever"
        assert "Agent every" not in json_str
        assert "Choice whatever" not in json_str
        
        records = json.loads(json_str)
        assert len(records) == 10
        
        for record in records:
            # Check values are not long prose
            for key, value in record.items():
                if isinstance(value, str):
                    # Prose usually > 5 words
                    assert len(value.split()) < 10, f"Value looks like prose: {value}"
                    
            # Check specific fields if they exist
            if "account_number" in record:
                val = record["account_number"]
                # Should be numeric-ish (digits, maybe dashes)
                # Definitely not "Agent every..."
                assert any(c.isdigit() for c in val), f"Account number has no digits: {val}"

@pytest.mark.asyncio
async def test_enum_constraint_integration():
    """Verify enum constraints are respected."""
    args = {
        "rows": 10,
        "format": "json",
        "prompt": 'Generate orders with status (enum: ["pending", "shipped", "delivered"]).',
        "enable_semantic_generation": True
    }
    
    result = await datagen_agent(args)
    data_dict = result["data"]["data"]
    
    # Find orders entity
    orders_json = None
    for name, json_str in data_dict.items():
        if "order" in name.lower():
            orders_json = json_str
            break
            
    if orders_json:
        records = json.loads(orders_json)
        valid_statuses = ["pending", "shipped", "delivered"]
        
        for record in records:
            if "status" in record:
                assert record["status"] in valid_statuses, f"Invalid status: {record['status']}"
