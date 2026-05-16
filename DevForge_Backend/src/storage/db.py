"""Shared PostgreSQL connection pool manager using asyncpg.

Ensures that multiple components (API Key Store, PgVector Store) share the same
database connection pool to optimize resource usage.
"""

import logging
from typing import Optional

import asyncpg
from src.core.config import settings

logger = logging.getLogger(__name__)

class PostgresPoolManager:
    """Manages a shared asyncpg connection pool."""
    
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """Get or initialize the shared connection pool.
        
        Returns:
            The shared asyncpg.Pool instance.
        """
        if cls._pool is None:
            if not settings.POSTGRES_URL:
                raise ValueError("POSTGRES_URL must be configured in environment variables.")
                
            logger.info("Initializing shared PostgreSQL connection pool...")
            cls._pool = await asyncpg.create_pool(
                dsn=settings.POSTGRES_URL,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
            logger.info("Shared PostgreSQL connection pool initialized.")
            
        return cls._pool

    @classmethod
    async def close_pool(cls):
        """Close the shared connection pool."""
        if cls._pool:
            logger.info("Closing shared PostgreSQL connection pool...")
            await cls._pool.close()
            cls._pool = None
            logger.info("Shared PostgreSQL connection pool closed.")

# Convenience instance if needed, though class methods are preferred
db_pool_manager = PostgresPoolManager
