
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import logging

from src.core.auth import verify_google_token, create_jwt, refresh_jwt_token

# Configure logging for auth router
auth_router_logger = logging.getLogger("auth_router")
auth_router_logger.setLevel(logging.DEBUG)

router = APIRouter()

class GoogleLoginRequest(BaseModel):
    google_token: str
    mongodb_id: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600

class RefreshTokenRequest(BaseModel):
    refresh_token: str

@router.post("/auth/google", response_model=Token)
async def login_with_google(request: GoogleLoginRequest):
    """
    Authenticates with Google and returns a JWT.
    """
    auth_router_logger.info(f"[AUTH_ROUTER] Google authentication request")
    
    try:
        verify_google_token(request.google_token, request.mongodb_id)
        access_token = create_jwt(mongodb_id=request.mongodb_id)
        
        auth_router_logger.info(f"[AUTH_ROUTER] Authentication successful for tenant: {request.mongodb_id}")
        return {"access_token": access_token, "expires_in": 3600}
        
    except HTTPException as e:
        auth_router_logger.error(f"[AUTH_ROUTER] Authentication failed: {e.detail}")
        raise e
    except Exception as e:
        auth_router_logger.error(f"[AUTH_ROUTER] Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )

@router.post("/auth/refresh", response_model=Token)
async def refresh_token(refresh_request: RefreshTokenRequest):
    """
    Refresh JWT token using existing valid token.
    Checks if original_issued_at > 24hrs.
    If yes, returns 401 with message "Session expired, please re-authenticate with Google".
    """
    try:
        new_access_token = refresh_jwt_token(refresh_request.refresh_token)
        return {"access_token": new_access_token, "expires_in": 3600}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}"
        )
