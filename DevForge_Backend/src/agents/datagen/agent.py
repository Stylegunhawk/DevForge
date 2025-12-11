"""DataGen agent - Simple async function for Phase 1.

No LangGraph complexity - direct tool invocation.
Ready for Phase 2 when supervisor routing is added.

Phase 1 Semantic Analyzer: LLM confined to classification only, never value generation.
"""

import asyncio
import logging
import os
from typing import Any

from src.core.schemas import DataGenArgs
from src.tools.datagen.tools import generate_mock_data
from src.tools.datagen.advanced_generator_v2 import generate_advanced_data_v2 as generate_advanced_data

# Phase 1: Feature flag for semantic analyzer
ENABLE_SEMANTIC_ANALYZER = os.getenv("ENABLE_SEMANTIC_ANALYZER", "true").lower() == "true"



async def datagen_agent(args: dict[str, Any]) -> dict[str, Any]:
    """Execute DataGen agent with provided arguments.

    Supports two modes:
    - V1 (simple): Uses original Faker-based generation for backward compatibility
    - V2 (advanced): Uses Phase 8 components (schema designer, relationships, realism)
    
    Mode selection:
    - V2 if `prompt` or `domain` is provided
    - V1 otherwise (backward compatible)

    Args:
        args: Dictionary containing:
            # V1 parameters (backward compatible)
            - rows (int): Number of rows to generate
            - format (str): "csv" or "json" (default: "json")
            - fields (list[str] | None): Optional custom field names
            
            # V2 parameters (Phase 8)
            - prompt (str | None): Natural language schema description
            - domain (str | None): Pre-defined domain ("ecommerce" or "saas")
            - realism_level (str): Data quality level ("basic", "medium", "high")

    Returns:
        Dictionary with:
            - success (bool): Always True if no exception
            - data (str | dict): Generated data
            - format (str): Output format used
            - rows (int): Number of rows generated
            - mode (str): "v1" or "v2"

    Raises:
        ValueError: If arguments are invalid
    """
    logging.info(
        "DataGen agent invoked",
        extra={"agent": "datagen", "input_args": args},
    )

    try:
        # Validate and parse arguments
        datagen_args = DataGenArgs(**args)
        
        # Determine mode: V2 if prompt or domain provided, else V1
        use_v2 = datagen_args.prompt is not None or datagen_args.domain is not None
        
        if use_v2:
            # V2: Advanced multi-entity generation
            # Check semantic analyzer feature flag
            semantic_enabled = ENABLE_SEMANTIC_ANALYZER and getattr(datagen_args, 'enable_semantic_generation', True)
            logging.info(f"Using V2 (advanced) data generation with Phase 8 components (semantic={semantic_enabled})")
            
            result = await generate_advanced_data(
                prompt=datagen_args.prompt,
                domain=datagen_args.domain,
                realism_level=datagen_args.realism_level,
                default_rows=datagen_args.rows,
                output_format=datagen_args.format,
                enable_semantic_generation=semantic_enabled  # Phase 1: Pass semantic flag
            )
            
            logging.info(
                f"V2 generation completed: {result['schema']['entity_count']} entities"
            )
            
            return {
                "success": True,
                "data": result,  # Full multi-entity result
                "format": datagen_args.format,
                "rows": datagen_args.rows,
                "mode": "v2"
            }
        else:
            # V1: Simple Faker-based generation (backward compatible)
            logging.info("Using V1 (simple) Faker-based generation - backward compatible mode")
            
            result = await asyncio.to_thread(
                generate_mock_data,
                rows=datagen_args.rows,
                format=datagen_args.format,
                fields=datagen_args.fields,
            )

            logging.info(
                f"V1 generation completed: {datagen_args.rows} rows in {datagen_args.format} format"
            )

            return {
                "success": True,
                "data": result,  # CSV → plain text, JSON → JSON string
                "format": datagen_args.format,
                "rows": datagen_args.rows,
                "mode": "v1"
            }

    except ValueError as e:
        logging.error(f"DataGen agent validation error: {str(e)}", extra={"error": str(e)})
        raise
    except Exception as e:
        logging.error(f"DataGen agent unexpected error: {str(e)}", extra={"error": str(e)}, exc_info=True)
        raise
