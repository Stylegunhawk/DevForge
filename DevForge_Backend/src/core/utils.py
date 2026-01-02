"""Utility functions for logging and performance tracking.

Uses custom JSONFormatter without external dependencies.
"""

import json
import logging
import time
from datetime import datetime
from functools import wraps
from typing import Any, Callable, TypeVar

# Type variable for function return type
F = TypeVar("F", bound=Callable[..., Any])


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: str = "INFO") -> None:
    """Configure JSON logging for production readiness.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Remove existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Create console handler with JSON formatter
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    # Set logging level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def track_performance(func: F) -> F:
    """Decorator to log execution time for async functions.

    Usage:
        @track_performance
        async def my_function():
            ...
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrapper that tracks execution time."""
        start = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start
            logging.info(
                f"{func.__name__} completed successfully in {duration:.3f}s",
                extra={"function": func.__name__, "duration": duration},
            )
            return result
        except Exception as e:
            duration = time.time() - start
            logging.error(
                f"{func.__name__} failed after {duration:.3f}s: {str(e)}",
                extra={"function": func.__name__, "duration": duration, "error": str(e)},
                exc_info=True,
            )
            raise

    return wrapper  # type: ignore


def track_performance_sync(func: F) -> F:
    """Decorator to log execution time for sync functions.

    Usage:
        @track_performance_sync
        def my_function():
            ...
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrapper that tracks execution time."""
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start
            logging.info(
                f"{func.__name__} completed successfully in {duration:.3f}s",
                extra={"function": func.__name__, "duration": duration},
            )
            return result
        except Exception as e:
            duration = time.time() - start
            logging.error(
                f"{func.__name__} failed after {duration:.3f}s: {str(e)}",
                extra={"function": func.__name__, "duration": duration, "error": str(e)},
                exc_info=True,
            )
            raise

    return wrapper  # type: ignore

