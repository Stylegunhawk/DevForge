
import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from src.core.auth import (
    hash_password, verify_password, 
    create_dashboard_jwt, verify_google_dashboard_token
)
from src.storage.db import PostgresPoolManager
from src.storage.api_key_store import api_key_store
from src.storage.tier_config_store import tier_config_store

logger = logging.getLogger(__name__)
router = APIRouter()

async def validate_expiry_for_tier(expiry_duration: Optional[str], tier: str) -> bool:
    """Validate expiry duration against tier's max_expiry_days."""
    if not expiry_duration:
        return True  # null expiry is always valid
    
    try:
        config = await tier_config_store.get_tier(tier)
        max_days = config.get("max_expiry_days", 180)
        duration_days = {"30d": 30, "90d": 90, "180d": 180}
        requested_days = duration_days.get(expiry_duration, 0)
        return requested_days <= max_days
    except Exception:
        # Fallback to 180 days if tier config unavailable
        duration_days = {"30d": 30, "90d": 90, "180d": 180}
        return duration_days.get(expiry_duration, 0) <= 180

# --- Schemas ---

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginRequest(BaseModel):
    id_token: str

class APIKeyCreateRequest(BaseModel):
    name: str
    integration_name: str
    tenant_id: str
    tier: str = "free"
    scopes: List[str] = []
    expiry_duration: Optional[str] = Field(
        default=None,
        description="30d, 90d, or 180d"
    )

class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    avatar_url: Optional[str]
    is_admin: bool
    created_at: str

# --- Auth Endpoints ---

@router.post("/auth/register", response_model=UserResponse)
async def register(req: UserRegisterRequest):
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        # Check existing
        existing = await conn.fetchval("SELECT id FROM users WHERE email = $1", req.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        user_id = uuid.uuid4()
        pw_hash = hash_password(req.password)
        
        await conn.execute(
            """
            INSERT INTO users (id, email, password_hash, name, auth_provider)
            VALUES ($1, $2, $3, $4, 'local')
            """,
            user_id, req.email, pw_hash, req.name
        )
        
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return {
            **dict(row),
            "id": str(row["id"]),
            "created_at": row["created_at"].isoformat()
        }

@router.post("/auth/login")
async def login(req: UserLoginRequest):
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE email = $1 AND auth_provider = 'local'", req.email)
        if not row or not verify_password(req.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        if not row["is_active"]:
            raise HTTPException(status_code=403, detail="Account is deactivated")
            
        token = create_dashboard_jwt(str(row["id"]), row["is_admin"])
        return {"access_token": token, "token_type": "bearer"}

@router.post("/auth/google/dashboard")
async def google_login(req: GoogleLoginRequest):
    # Verify Google Token specifically for Dashboard Client ID
    idinfo = verify_google_dashboard_token(req.id_token)
    email = idinfo.get("email")
    name = idinfo.get("name")
    picture = idinfo.get("picture")
    
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
        
        if not row:
            # Auto-register google user
            user_id = uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO users (id, email, name, avatar_url, auth_provider, is_active)
                VALUES ($1, $2, $3, $4, 'google', true)
                """,
                user_id, email, name, picture
            )
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        else:
            # Sync name/avatar if changed
            await conn.execute(
                "UPDATE users SET name = $1, avatar_url = $2 WHERE id = $3",
                name, picture, row["id"]
            )
            
        if not row["is_active"]:
            raise HTTPException(status_code=403, detail="Account is deactivated")
            
        token = create_dashboard_jwt(str(row["id"]), row["is_admin"])
        return {"access_token": token, "token_type": "bearer"}

@router.get("/auth/me", response_model=UserResponse)
async def get_me(request: Request):
    # Extract token directly from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header.split(" ")[1]
    
    try:
        from src.core.auth import verify_dashboard_jwt
        payload = verify_dashboard_jwt(token)
        user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1", 
            uuid.UUID(user_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
            
        return {
            **dict(row),
            "id": str(row["id"]),
            "created_at": row["created_at"].isoformat()
        }

# --- User-Scoped Key Management ---

@router.get("/users/keys")
async def list_my_keys(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return await api_key_store.list_user_keys(user_id)

@router.post("/users/keys")
async def create_my_key(request: Request, req: APIKeyCreateRequest):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Validate expiry duration against tier limits
    if not await validate_expiry_for_tier(req.expiry_duration, req.tier):
        config = await tier_config_store.get_tier(req.tier)
        max_days = config.get("max_expiry_days", 180)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid expiry_duration for {req.tier} tier. Maximum allowed: {max_days}d"
        )
    
    # Validate expiry duration format
    if req.expiry_duration and req.expiry_duration not in ("30d", "90d", "180d"):
        raise HTTPException(
            status_code=400,
            detail="Invalid expiry_duration. Must be: 30d, 90d, 180d, or null"
        )
        
    raw_key = await api_key_store.create_key(
        name=req.name,
        tenant_id=req.tenant_id,
        integration_name=req.integration_name,
        tier=req.tier,
        scopes=req.scopes,
        user_id=user_id,
        expiry_duration=req.expiry_duration  # NEW: Pass expiry_duration
    )
    return {"key": raw_key, "message": "Save this key, it will not be shown again."}

@router.delete("/users/keys/{key_id}")
async def revoke_my_key(request: Request, key_id: str):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    # Verify ownership before revocation
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        owner = await conn.fetchval("SELECT user_id FROM api_keys WHERE id = $1", uuid.UUID(key_id))
        if not owner or str(owner) != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to revoke this key")
            
    await api_key_store.revoke_key(key_id)
    return {"success": True}
