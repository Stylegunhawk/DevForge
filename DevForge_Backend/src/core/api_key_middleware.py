"""FastAPI middleware for API key authentication.

Protects unified gateway and MCP endpoints using X-API-Key header.
Populates request state with tenant, integration, and tier information.
"""

import json
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.storage.api_key_store import api_key_store
from src.workers.tasks.auth_tasks import update_key_last_used

logger = logging.getLogger(__name__)

class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to protect gateway and MCP routes with API key authentication.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        
        # Only protect specific routes exactly
        if path == "/api/gateway" or path == "/mcp":
            auth_key = request.headers.get("x-api-key")
            
            if not auth_key:
                logger.warning(f"[API_KEY] Missing x-api-key header for {path}")
                return Response(
                    content=json.dumps({"success": False, "detail": "API Key missing"}),
                    status_code=401,
                    media_type="application/json",
                )

            # Validate key via store (uses cache)
            metadata = await api_key_store.validate_key(auth_key)
            
            if not metadata:
                logger.warning(f"[API_KEY] Invalid or inactive API key for {path}")
                return Response(
                    content=json.dumps({"success": False, "detail": "Invalid or inactive API Key"}),
                    status_code=401,
                    media_type="application/json",
                )

            # Populate request state for downstream use
            request.state.tenant_id = metadata.tenant_id
            request.state.integration_name = metadata.integration_name
            request.state.tier = metadata.tier
            request.state.scopes = metadata.scopes
            request.state.api_key_id = metadata.id
            request.state.user_id = metadata.user_id  # NEW: Phase 4 analytics support
            
            logger.info(f"[API_KEY] Authenticated {metadata.integration_name} ({metadata.tier}) for {path}")
            
            # Offload usage tracking to Celery (Async)
            try:
                update_key_last_used.delay(metadata.id)
            except Exception as e:
                # Log but don't block the request if Celery fails
                logger.error(f"Failed to dispatch last_used update: {e}")

        return await call_next(request)
