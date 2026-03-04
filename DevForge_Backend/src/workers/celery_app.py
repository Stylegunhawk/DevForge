"""Celery application configuration for async task processing.

Phase 10.1: Async document ingestion with progress tracking.
"""

from celery import Celery

from src.core.config import settings


def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    app = Celery(
        "devforge",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[
            "src.workers.tasks.rag_tasks",
            "src.workers.tasks.auth_tasks",
            "src.workers.tasks.usage_tasks",
            "src.workers.tasks.analytics_tasks"  # NEW: Phase 4 analytics
        ],
    )

    app.conf.update(
        # Task execution limits
        task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
        task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
        
        # Task tracking
        task_track_started=True,
        task_send_sent_event=True,
        
        # Result backend settings
        result_expires=3600,  # 1 hour
        result_extended=True,
        
        # Broker connection settings
        broker_connection_retry_on_startup=True,
        
        # Serialization
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        
        # Timezone
        timezone="UTC",
        enable_utc=True,
        
        # Worker settings
        worker_prefetch_multiplier=1,
        worker_concurrency=4,
        
        # Queue routing for Phase 4 analytics
        task_routes={
            'src.workers.tasks.analytics_tasks.log_request_call': {'queue': 'analytics'},
            'src.workers.tasks.usage_tasks.log_llm_usage': {'queue': 'usage'},
            'src.workers.tasks.auth_tasks.update_key_last_used': {'queue': 'default'},
            'src.workers.tasks.rag_tasks.*': {'queue': 'rag'},
        },
        
        # Queue definitions
        task_queues={
            'default': {
                'exchange': 'default',
                'routing_key': 'default',
            },
            'analytics': {
                'exchange': 'analytics',
                'routing_key': 'analytics',
            },
            'usage': {
                'exchange': 'usage', 
                'routing_key': 'usage',
            },
            'rag': {
                'exchange': 'rag',
                'routing_key': 'rag',
            },
        },
    )

    return app


# Application instance
celery_app = create_celery_app()


if __name__ == "__main__":
    celery_app.start()
