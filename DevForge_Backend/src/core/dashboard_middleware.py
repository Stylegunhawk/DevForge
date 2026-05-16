
import json
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from src.core.auth import verify_dashboard_jwt

logger = logging.getLogger("dashboard_middleware")
logger.setLevel(logging.INFO)

class DashboardAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to protect dashboard and admin routes with Dashboard JWT.
    Target: /api/users/* and /api/admin/*
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        
        # Dashboard or Admin route check
        if path.startswith("/api/users/") or path.startswith("/api/admin/"):
            auth_header = request.headers.get("Authorization")
            
            if not auth_header:
                logger.warning(f"[DASH_MW] No Authorization header for {path}")
                return Response(
                    content=json.dumps({"detail": "Dashboard authorization header missing"}),
                    status_code=401,
                    media_type="application/json",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                logger.warning(f"[DASH_MW] Invalid Authorization header format for {path}")
                return Response(
                    content=json.dumps({"detail": "Invalid Authorization header format. Use 'Bearer <token>'"}),
                    status_code=401,
                    media_type="application/json",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            token = parts[1]
            
            try:
                # Verify Dashboard JWT (with aud="dashboard" check)
                payload = verify_dashboard_jwt(token)
                
                request.state.user_id = payload.get("user_id")
                request.state.is_admin = payload.get("is_admin", False)
                
                logger.info(f"[DASH_MW] Verified user={request.state.user_id}, is_admin={request.state.is_admin} for {path}")
                
                # Strictly enforce Admin Check for admin routes
                if path.startswith("/api/admin/") and not request.state.is_admin:
                    logger.warning(f"[DASH_MW] Access denied: {request.state.user_id} is not an admin")
                    return Response(
                        content=json.dumps({"detail": "Admin privileges required to access this resource."}),
                        status_code=403,
                        media_type="application/json",
                    )
                    
            except Exception as e:
                logger.error(f"[DASH_MW] JWT verification failed for {path}: {str(e)}")
                return Response(
                    content=json.dumps({"detail": str(e)}),
                    status_code=401,
                    media_type="application/json",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        
        return await call_next(request)
