"""DataGen agent - Simple async function for Phase 1.

No LangGraph complexity - direct tool invocation.
Ready for Phase 2 when supervisor routing is added.
"""

import asyncio
import logging
from typing import Any

from src.core.schemas import DataGenArgs
from src.tools.datagen.tools import generate_mock_data


async def datagen_agent(args: dict[str, Any]) -> dict[str, Any]:
    """Execute DataGen agent with provided arguments.

    This is a simple async wrapper around the synchronous data generation tool.
    Phase 1: Direct execution without LLM parsing.
    Phase 2: Will be invoked by supervisor router.

    Args:
        args: Dictionary containing:
            - rows (int): Number of rows to generate
            - format (str): "csv" or "json" (default: "json")
            - fields (list[str] | None): Optional custom field names

    Returns:
        Dictionary with:
            - success (bool): Always True if no exception
            - format (str): Output format used
            - data (str): Generated data as string (CSV or JSON)

    Raises:
        ValueError: If arguments are invalid
    """
    logging.info(
        "DataGen agent invoked - using Faker+Pandas (no LLM required)",
        extra={"agent": "datagen", "input_args": args},  # ✅ changed key name
    )

    try:
        # Validate and parse arguments
        datagen_args = DataGenArgs(**args)

        # Run blocking operation in thread pool
        # This keeps FastAPI async and non-blocking
        result = await asyncio.to_thread(
            generate_mock_data,
            rows=datagen_args.rows,
            format=datagen_args.format,
            fields=datagen_args.fields,
        )

        logging.info(
            f"DataGen agent completed: {datagen_args.rows} rows in {datagen_args.format} format",
            extra={
                "rows": datagen_args.rows,
                "format": datagen_args.format,
                "data_length": len(result),
            },
        )

        return {
            "success": True,
            "format": datagen_args.format,
            "data": result,
        }

    except ValueError as e:
        logging.error(f"DataGen agent validation error: {str(e)}", extra={"error": str(e)})
        raise
    except Exception as e:
        logging.error(f"DataGen agent unexpected error: {str(e)}", extra={"error": str(e)}, exc_info=True)
        raise
