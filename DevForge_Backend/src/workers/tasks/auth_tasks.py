"""Celery tasks for authentication-related operations.

Includes background tasks for updating API key usage statistics to avoid
latency in the request/response hot path.
"""

import logging
from celery import shared_task
from src.storage.db import PostgresPoolManager

logger = logging.getLogger(__name__)

@shared_task
def update_key_last_used(key_id: str):
    """Update the last_used_at timestamp for an API key.
    
    Args:
        key_id: UUID string of the API key to update.
    """
    import asyncio
    
    async def _update():
        try:
            pool = await PostgresPoolManager.get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE id = $1",
                    key_id
                )
                logger.debug(f"Updated last_used_at for API key: {key_id}")
        except Exception as e:
            logger.error(f"Failed to update last_used_at for API key {key_id}: {e}")

    # Use existing event loop if available, or create a new one
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    return loop.run_until_complete(_update())
