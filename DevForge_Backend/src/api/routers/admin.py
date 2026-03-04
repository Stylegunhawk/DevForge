"""Admin API for API key management.

Provides endpoints for creating, listing, and revoking API keys.
Protected by ADMIN_SECRET header check.
"""

import uuid
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Header, HTTPException, Depends, Request

from src.core.config import settings
from src.storage.api_key_store import api_key_store
from src.storage.db import PostgresPoolManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

class CreateKeyRequest(BaseModel):
    name: str = Field(..., description="A friendly name for the key")
    integration_name: str = Field(..., description="Integration identifier (e.g., 'cursor-ide')")
    tenant_id: str = Field(default="default", description="Tenant isolation ID")
    tier: str = Field(default="free", description="Usage tier (free, pro, enterprise)")
    scopes: List[str] = Field(default_factory=list, description="List of allowed tools/scopes")

def verify_is_admin(request: Request):
    """Verify that the user has admin privileges (from DashboardAuthMiddleware)."""
    if not getattr(request.state, "is_admin", False):
        raise HTTPException(
            status_code=403, 
            detail="Admin privileges required"
        )
    return True

@router.post("/keys", dependencies=[Depends(verify_is_admin)])
async def create_api_key(request: CreateKeyRequest):
    """Generate a new API key."""
    raw_key = await api_key_store.create_key(
        name=request.name,
        tenant_id=request.tenant_id,
        integration_name=request.integration_name,
        tier=request.tier,
        scopes=request.scopes
    )
    return {
        "success": True,
        "raw_key": raw_key,
        "message": "Copy this key now. It will never be shown again in raw format."
    }

@router.get("/keys", dependencies=[Depends(verify_is_admin)])
async def list_api_keys():
    """List all API keys (metadata only)."""
    keys = await api_key_store.list_keys()
    return {"success": True, "keys": keys}

@router.delete("/keys/{key_id}", dependencies=[Depends(verify_is_admin)])
async def revoke_api_key(key_id: str):
    """Revoke and deactivate an API key."""
    await api_key_store.revoke_key(key_id)
    return {"success": True, "message": f"API key {key_id} revoked successfully"}


@router.get("/usage", dependencies=[Depends(verify_is_admin)])
async def get_llm_usage(
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    days: int = 7
):
    """Retrieve LLM usage statistics."""
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        query = """
            SELECT 
                tenant_id, 
                integration_name, 
                model_name, 
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(cost_usd)::REAL as total_cost_usd,
                COUNT(*) as request_count
            FROM llm_usage
            WHERE created_at > NOW() - (INTERVAL '1 day' * $1)
        """
        params = [days]
        
        if tenant_id:
            query += f" AND tenant_id = ${len(params) + 1}"
            params.append(tenant_id)

        if user_id:
            query += f" AND user_id = ${len(params) + 1}"
            params.append(user_id)
            
        query += " GROUP BY tenant_id, integration_name, model_name"
        
        rows = await conn.fetch(query, *params)
        return {
            "success": True,
            "usage": [dict(r) for r in rows],
            "period_days": days
        }

# --- User Management (Admin Only) ---

@router.get("/users", dependencies=[Depends(verify_is_admin)])
async def list_users():
    """List all registered users."""
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, email, name, avatar_url, auth_provider, is_admin, is_active, created_at FROM users ORDER BY created_at DESC")
        return {"success": True, "users": [dict(r) for r in rows]}

@router.patch("/users/{user_id}", dependencies=[Depends(verify_is_admin)])
async def update_user(user_id: str, is_admin: Optional[bool] = None, is_active: Optional[bool] = None):
    """Modify user status or privileges."""
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        updates = []
        params = [uuid.UUID(user_id)]
        
        if is_admin is not None:
            updates.append(f"is_admin = ${len(params) + 1}")
            params.append(is_admin)
        
        if is_active is not None:
            updates.append(f"is_active = ${len(params) + 1}")
            params.append(is_active)
            
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
            
        await conn.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = $1",
            *params
        )
        return {"success": True, "message": f"User {user_id} updated successfully"}
