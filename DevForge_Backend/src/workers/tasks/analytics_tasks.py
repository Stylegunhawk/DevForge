"""Celery tasks for analytics and request logging."""

import logging
import asyncio
from celery import shared_task
from src.storage.db import PostgresPoolManager

logger = logging.getLogger(__name__)


@shared_task(name="src.workers.tasks.analytics_tasks.log_request_call")
def log_request_call(
    user_id: str,
    tenant_id: str,
    integration_name: str,
    tool_name: str,
    input_summary: str,
    success: bool,
    duration_ms: int
):
    """Log detailed request information for analytics.
    
    Args:
        user_id: User ID (nullable for anonymous requests)
        tenant_id: Tenant identifier
        integration_name: Integration name (e.g., 'cursor-ide')
        tool_name: Tool name (e.g., 'github_operation')
        input_summary: Sanitized and truncated input summary
        success: Whether the tool execution succeeded
        duration_ms: Execution duration in milliseconds
    """
    
    async def _log():
        try:
            query = """
                INSERT INTO request_logs (
                    user_id, tenant_id, integration_name, tool_name,
                    input_summary, success, duration_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            
            pool = await PostgresPoolManager.get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    user_id,
                    tenant_id,
                    integration_name,
                    tool_name,
                    input_summary,
                    success,
                    duration_ms
                )
                
                logger.info(
                    f"Logged request: {tool_name} for tenant {tenant_id} "
                    f"(user: {user_id}, success: {success}, duration: {duration_ms}ms)"
                )
                
        except Exception as e:
            logger.error(f"Failed to log request call: {str(e)}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(_log())
