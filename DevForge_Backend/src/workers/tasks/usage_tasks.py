import logging
import asyncio
from celery import shared_task
from src.storage.db import PostgresPoolManager

logger = logging.getLogger(__name__)

@shared_task(name="src.workers.tasks.usage_tasks.log_llm_usage")
def log_llm_usage(
    tenant_id: str,
    integration_name: str,
    model_name: str,
    task_type: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    user_id: str = None  # NEW - Optional to prevent breaking existing callers
):
    """Log LLM token usage to Postgres."""
    
    async def _log():
        try:
            from src.core.model_router import model_router
            cost = model_router.estimate_cost(model_name, total_tokens)
            
            query = """
                INSERT INTO llm_usage (
                    tenant_id, integration_name, model_name, task_type,
                    prompt_tokens, completion_tokens, total_tokens, cost_usd, user_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """
            
            pool = await PostgresPoolManager.get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    tenant_id,
                    integration_name,
                    model_name,
                    task_type,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    cost,
                    user_id  # NEW user_id parameter
                )
                logger.info(f"Logged {total_tokens} tokens for {tenant_id}/{integration_name} on {model_name} (task: {task_type}, user: {user_id})")
        except Exception as e:
            logger.error(f"Failed to log LLM usage: {str(e)}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(_log())
