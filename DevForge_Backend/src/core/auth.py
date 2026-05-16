
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import bcrypt
from google.oauth2 import id_token
from google.auth.transport import requests
from fastapi import HTTPException, status

# Configure logging for auth
auth_logger = logging.getLogger("auth")
auth_logger.setLevel(logging.DEBUG)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
JWT_SECRET = os.environ.get("JWT_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

GOOGLE_DASHBOARD_CLIENT_ID = os.environ.get("GOOGLE_DASHBOARD_CLIENT_ID")
DASHBOARD_JWT_SECRET = os.environ.get("DASHBOARD_JWT_SECRET")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    pw_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def verify_google_token(token: str, mongodb_id: str) -> str:
    """
    Verifies Google ID token.
    Checks if the audience of the token matches the GOOGLE_CLIENT_ID.
    Returns the OIDC subject (sub) on success.
    Raises HTTPException with status 401 on failure.
    """
    auth_logger.info(f"[AUTH] Google token verification started")
    
    if not GOOGLE_CLIENT_ID:
        auth_logger.error("[AUTH] Google Client ID is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google Client ID is not configured.",
        )
    try:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        
        # The 'sub' claim is a unique identifier for the user.
        oidc_sub = idinfo.get("sub")
        
        if not oidc_sub:
            auth_logger.error("[AUTH] Invalid Google token: 'sub' claim missing")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token: 'sub' claim missing.",
            )
        
        auth_logger.info(f"[AUTH] Google token verified successfully for sub: {oidc_sub}")
        return oidc_sub

    except ValueError as e:
        auth_logger.error(f"[AUTH] Google token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {e}",
        )


def create_jwt(mongodb_id: str) -> str:
    """
    Issues a JWT.
    Payload contains tenant_id, expiration time, and original_issued_at.
    """
    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET is not configured.",
        )
        
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    original_issued_at = datetime.now(timezone.utc)
    to_encode = {
        "tenant_id": mongodb_id, 
        "exp": expire,
        "original_issued_at": original_issued_at.isoformat()
    }
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


def verify_jwt(token: str) -> Optional[dict]:
    """
    Verifies a JWT.
    Returns the payload on success, otherwise raises HTTPException.
    """
    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET is not configured.",
        )

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def refresh_jwt_token(refresh_token: str) -> str:
    """
    Refreshes a JWT token.
    Checks if original_issued_at > 24hrs.
    If yes, returns 401 with message "Session expired, please re-authenticate with Google".
    """
    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET is not configured.",
        )

    try:
        # Verify the existing token
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[ALGORITHM])
        
        # Extract tenant_id and original_issued_at from payload
        tenant_id = payload.get("tenant_id")
        original_issued_at_str = payload.get("original_issued_at")
        
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing tenant_id"
            )
        
        if not original_issued_at_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing original_issued_at"
            )
        
        # Parse original_issued_at and check if > 24hrs
        try:
            original_issued_at = datetime.fromisoformat(original_issued_at_str.replace('Z', '+00:00'))
            if original_issued_at.tzinfo is None:
                original_issued_at = original_issued_at.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: malformed original_issued_at"
            )
        
        # Check if session is older than 24 hours
        now = datetime.now(timezone.utc)
        session_age = now - original_issued_at
        
        if session_age > timedelta(hours=24):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired, please re-authenticate with Google"
            )
        
        # Create new JWT token with same original_issued_at
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "tenant_id": tenant_id, 
            "exp": expire,
            "original_issued_at": original_issued_at_str  # Keep original issue time
        }
        new_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
        
        return new_jwt
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired, please re-authenticate with Google",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def verify_google_dashboard_token(token: str) -> dict:
    """Verifies Google ID token for Dashboard."""
    if not GOOGLE_DASHBOARD_CLIENT_ID:
        auth_logger.error("[AUTH] Google Dashboard Client ID is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google Dashboard Client ID is not configured.",
        )
    try:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_DASHBOARD_CLIENT_ID)
        auth_logger.info(f"[AUTH] Google dashboard token verified for: {idinfo.get('email')}")
        return idinfo
    except Exception as e:
        auth_logger.error(f"[AUTH] Google dashboard token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google dashboard token: {e}",
        )

def create_dashboard_jwt(user_id: str, is_admin: bool = False) -> str:
    """Create a JWT for dashboard authentication."""
    if not DASHBOARD_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DASHBOARD_JWT_SECRET is not configured.",
        )
    
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode = {
        "user_id": user_id,
        "is_admin": is_admin,
        "exp": expire,
        "aud": "dashboard",
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(to_encode, DASHBOARD_JWT_SECRET, algorithm=ALGORITHM)

def verify_dashboard_jwt(token: str) -> dict:
    """Verify a dashboard JWT."""
    if not DASHBOARD_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DASHBOARD_JWT_SECRET is not configured.",
        )
    
    try:
        payload = jwt.decode(
            token, 
            DASHBOARD_JWT_SECRET, 
            algorithms=[ALGORITHM],
            audience="dashboard"
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Dashboard token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate dashboard credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
