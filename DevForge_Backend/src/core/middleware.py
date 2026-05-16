"""Request/Response logging middleware for FastAPI.

Logs all incoming requests and outgoing responses with detailed information
including headers, body, status codes, and execution time.
"""

import json
import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message

from src.core.auth import verify_jwt

# Configure logging for middleware
middleware_logger = logging.getLogger("middleware")
middleware_logger.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log request/response details."""
        start_time = time.time()

        # Read request body
        body = await request.body()
        request_body = None

        if body:
            try:
                request_body = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                request_body = body.decode("utf-8", errors="replace")[:500]  # Truncate if too long

        # Log incoming request
        logger.info(
            f"📥 REQUEST: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "headers": dict(request.headers),
                "body": request_body,
            },
        )

        # Recreate request with body (FastAPI needs this)
        async def receive() -> Message:
            return {"type": "http.request", "body": body}

        request._receive = receive

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"❌ ERROR: {request.method} {request.url.path} ({execution_time:.3f}s)",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "execution_time": execution_time,
                },
                exc_info=True,
            )
            raise

        execution_time = time.time() - start_time

        # Read response body (can only be consumed once)
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        # Parse response body if JSON
        response_body_parsed = None
        if response_body:
            try:
                response_body_parsed = json.loads(response_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                response_body_parsed = response_body.decode("utf-8", errors="replace")[:500]

        # Log outgoing response
        logger.info(
            f"📤 RESPONSE: {response.status_code} ({execution_time:.3f}s)",
            extra={
                "status_code": response.status_code,
                "path": request.url.path,
                "body": response_body_parsed,
                "execution_time": execution_time,
            },
        )

        # Recreate response with body (FastAPI needs this)
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )


from src.core.auth import verify_jwt
from fastapi import HTTPException
import logging

# Configure logging for JWT middleware
jwt_middleware_logger = logging.getLogger("jwt_middleware")
jwt_middleware_logger.setLevel(logging.DEBUG)

class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to protect routes with JWT authentication.
    """
    PROTECTED_EXACT = {"/api/rag/ingest-async"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if (
            request.url.path.startswith("/api/v1/rag/")
            or request.url.path in self.PROTECTED_EXACT
        ):
            auth_header = request.headers.get("Authorization")
            
            if not auth_header:
                jwt_middleware_logger.warning(f"[JWT_MW] No Authorization header for {request.url.path}")
                return Response(
                    content=json.dumps({"detail": "Authorization header missing"}),
                    status_code=401,
                    media_type="application/json",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                jwt_middleware_logger.warning(f"[JWT_MW] Invalid Authorization header for {request.url.path}")
                return Response(
                    content=json.dumps({"detail": "Invalid Authorization header"}),
                    status_code=401,
                    media_type="application/json",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            token = parts[1]
            
            try:
                payload = verify_jwt(token)
                request.state.tenant_id = payload.get("tenant_id")
                jwt_middleware_logger.info(f"[JWT_MW] JWT verified for tenant: {request.state.tenant_id}")
            except HTTPException as e:
                jwt_middleware_logger.warning(f"[JWT_MW] JWT verification failed for {request.url.path}: {e.detail}")
                return Response(
                    content=json.dumps({"detail": e.detail}),
                    status_code=e.status_code,
                    media_type="application/json",
                    headers=e.headers if hasattr(e, 'headers') else {"WWW-Authenticate": "Bearer"},
                )
        
        return await call_next(request)
