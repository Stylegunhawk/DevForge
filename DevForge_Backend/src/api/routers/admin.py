"""Admin API for API key management.

Provides endpoints for creating, listing, and revoking API keys.
Protected by ADMIN_SECRET header check.
"""

from datetime import datetime, timezone
import uuid
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Header, HTTPException, Depends, Request

from src.core.config import settings
from src.storage.api_key_store import api_key_store
from src.storage.tier_config_store import tier_config_store
from src.storage.db import PostgresPoolManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

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

class CreateKeyRequest(BaseModel):
    name: str = Field(..., description="A friendly name for the key")
    integration_name: str = Field(..., description="Integration identifier (e.g., 'cursor-ide')")
    tenant_id: str = Field(default="default", description="Tenant isolation ID")
    tier: str = Field(default="free", description="Usage tier (free, pro, enterprise)")
    scopes: List[str] = Field(default_factory=list, description="List of allowed tools/scopes")
    user_id: Optional[str] = Field(default=None, description="User ID for user-scoped keys")
    expiry_duration: Optional[str] = Field(
        default=None,
        description="Key expiry: '30d', '90d', '180d', or null for no expiry"
    )

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
    # Validate expiry duration against tier limits
    if not await validate_expiry_for_tier(request.expiry_duration, request.tier):
        config = await tier_config_store.get_tier(request.tier)
        max_days = config.get("max_expiry_days", 180)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid expiry_duration for {request.tier} tier. Maximum allowed: {max_days}d"
        )
    
    # Validate expiry duration format
    if request.expiry_duration and request.expiry_duration not in ("30d", "90d", "180d"):
        raise HTTPException(
            status_code=400,
            detail="Invalid expiry_duration. Must be: 30d, 90d, 180d, or null"
        )
    
    raw_key = await api_key_store.create_key(
        name=request.name,
        tenant_id=request.tenant_id,
        integration_name=request.integration_name,
        tier=request.tier,
        scopes=request.scopes,
        user_id=request.user_id,  # NEW: Pass user_id to create_key
        expiry_duration=request.expiry_duration  # NEW: Pass expiry_duration
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
    tool_name: Optional[str] = None,  # NEW
    from_date: Optional[str] = None,  # NEW
    to_date: Optional[str] = None,    # NEW
    days: int = 7
):
    """Retrieve LLM usage statistics with enhanced filtering."""
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
        
        # NEW: Tool name filter (join with request_logs to get tool_name)
        if tool_name:
            query = """
                SELECT 
                    l.tenant_id, 
                    l.integration_name, 
                    l.model_name, 
                    SUM(l.prompt_tokens) as total_prompt_tokens,
                    SUM(l.completion_tokens) as total_completion_tokens,
                    SUM(l.total_tokens) as total_tokens,
                    SUM(l.cost_usd)::REAL as total_cost_usd,
                    COUNT(*) as request_count
                FROM llm_usage l
                INNER JOIN request_logs r ON l.created_at::date = r.created_at::date 
                    AND l.tenant_id = r.tenant_id AND l.integration_name = r.integration_name
                WHERE l.created_at > NOW() - (INTERVAL '1 day' * $1)
                AND r.tool_name = $2
            """
            params = [days, tool_name]
            
            if tenant_id:
                query += f" AND l.tenant_id = ${len(params) + 1}"
                params.append(tenant_id)
            
            if user_id:
                query += f" AND l.user_id = ${len(params) + 1}"
                params.append(user_id)
        
        # NEW: Date range filters
        if from_date:
            if tool_name:
                query += f" AND l.created_at >= ${len(params) + 1}"
            else:
                query += f" AND created_at >= ${len(params) + 1}"
            params.append(from_date)
        
        if to_date:
            if tool_name:
                query += f" AND l.created_at <= ${len(params) + 1}"
            else:
                query += f" AND created_at <= ${len(params) + 1}"
            params.append(to_date)
            
        if tool_name:
            query += " GROUP BY l.tenant_id, l.integration_name, l.model_name"
        else:
            query += " GROUP BY tenant_id, integration_name, model_name"
        
        rows = await conn.fetch(query, *params)
        return {
            "success": True,
            "usage": [dict(r) for r in rows],
            "period_days": days,
            "filters": {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "tool_name": tool_name,
                "from_date": from_date,
                "to_date": to_date
            }
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


# --- Phase 4 Analytics Endpoints ---

@router.get("/users/{user_id}/usage", dependencies=[Depends(verify_is_admin)])
async def get_user_usage(user_id: str, days: int = 30):
    """Token usage + cost breakdown for specific user."""
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        # Get user info
        user_info = await conn.fetchrow(
            "SELECT email, name, created_at FROM users WHERE id = $1",
            uuid.UUID(user_id)
        )
        
        if not user_info:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get usage stats
        usage_query = """
            SELECT 
                model_name,
                task_type,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(cost_usd)::REAL as total_cost_usd,
                COUNT(*) as request_count,
                DATE(created_at) as date
            FROM llm_usage
            WHERE user_id = $1 
            AND created_at > NOW() - (INTERVAL '1 day' * $2)
            GROUP BY model_name, task_type, DATE(created_at)
            ORDER BY date DESC, total_tokens DESC
        """
        
        usage_rows = await conn.fetch(usage_query, uuid.UUID(user_id), days)
        
        # Get tool usage from request_logs
        tools_query = """
            SELECT 
                tool_name,
                COUNT(*) as call_count,
                AVG(duration_ms)::INTEGER as avg_duration_ms,
                SUM(CASE WHEN success = true THEN 1 ELSE 0 END)::INTEGER as success_count,
                SUM(CASE WHEN success = false THEN 1 ELSE 0 END)::INTEGER as error_count,
                ROUND((SUM(CASE WHEN success = true THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 2) as success_rate
            FROM request_logs
            WHERE user_id = $1 
            AND created_at > NOW() - (INTERVAL '1 day' * $2)
            GROUP BY tool_name
            ORDER BY call_count DESC
        """
        
        tools_rows = await conn.fetch(tools_query, uuid.UUID(user_id), days)
        
        return {
            "success": True,
            "user": {
                "id": user_id,
                "email": user_info["email"],
                "name": user_info["name"],
                "member_since": user_info["created_at"]
            },
            "period_days": days,
            "token_usage": [dict(r) for r in usage_rows],
            "tool_usage": [dict(r) for r in tools_rows],
            "total_tokens": sum(r["total_tokens"] for r in usage_rows),
            "total_cost": sum(r["total_cost_usd"] for r in usage_rows),
            "total_requests": sum(r["request_count"] for r in usage_rows)
        }


@router.get("/tools/stats", dependencies=[Depends(verify_is_admin)])
async def get_tool_stats(days: int = 30):
    """Per-tool: call count, avg tokens, total cost, success rate."""
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        query = """
            SELECT 
                r.tool_name,
                COUNT(*) as total_calls,
                AVG(r.duration_ms)::INTEGER as avg_duration_ms,
                SUM(CASE WHEN r.success = true THEN 1 ELSE 0 END)::INTEGER as success_count,
                SUM(CASE WHEN r.success = false THEN 1 ELSE 0 END)::INTEGER as error_count,
                ROUND((SUM(CASE WHEN r.success = true THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 2) as success_rate,
                COUNT(DISTINCT r.user_id) as unique_users,
                COALESCE(SUM(l.total_tokens), 0) as total_tokens,
                COALESCE(SUM(l.cost_usd), 0)::REAL as total_cost_usd
            FROM request_logs r
            LEFT JOIN llm_usage l ON r.created_at::date = l.created_at::date 
                AND r.tenant_id = l.tenant_id 
                AND r.integration_name = l.integration_name
                AND (r.user_id = l.user_id OR (r.user_id IS NULL AND l.user_id IS NULL))
            WHERE r.created_at > NOW() - (INTERVAL '1 day' * $1)
            GROUP BY r.tool_name
            ORDER BY total_calls DESC
        """
        
        rows = await conn.fetch(query, days)
        
        return {
            "success": True,
            "period_days": days,
            "tool_stats": [dict(r) for r in rows],
            "summary": {
                "total_tools": len(rows),
                "total_calls": sum(r["total_calls"] for r in rows),
                "total_tokens": sum(r["total_tokens"] for r in rows),
                "total_cost": sum(r["total_cost_usd"] for r in rows),
                "avg_success_rate": sum(r["success_rate"] for r in rows) / len(rows) if rows else 0
            }
        }


@router.get("/requests", dependencies=[Depends(verify_is_admin)])
async def get_request_logs(
    page: int = 1,
    limit: int = 50,
    user_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    success: Optional[bool] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    """Paginated request log with filters."""
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        # Build WHERE clause
        where_conditions = []
        params = []
        param_count = 0
        
        if user_id:
            param_count += 1
            where_conditions.append(f"user_id = ${param_count}")
            params.append(uuid.UUID(user_id))
        
        if tool_name:
            param_count += 1
            where_conditions.append(f"tool_name = ${param_count}")
            params.append(tool_name)
        
        if success is not None:
            param_count += 1
            where_conditions.append(f"success = ${param_count}")
            params.append(success)
        
        if from_date:
            param_count += 1
            where_conditions.append(f"created_at >= ${param_count}")
            params.append(from_date)
        
        if to_date:
            param_count += 1
            where_conditions.append(f"created_at <= ${param_count}")
            params.append(to_date)
        
        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        
        # Get total count for pagination
        count_query = f"SELECT COUNT(*) as total FROM request_logs r LEFT JOIN users u ON r.user_id = u.id {where_clause}"
        total_count = await conn.fetchval(count_query, *params)
        
        # Get paginated results
        offset = (page - 1) * limit
        param_count += 1
        params.append(limit)
        param_count += 1
        params.append(offset)
        
        query = f"""
            SELECT 
                r.id,
                r.user_id,
                r.tenant_id,
                r.integration_name,
                r.tool_name,
                r.input_summary,
                r.success,
                r.duration_ms,
                r.created_at,
                COALESCE(u.email, 'Anonymous') as user_email,
                COALESCE(u.name, 'Anonymous') as user_name
            FROM request_logs r
            LEFT JOIN users u ON r.user_id = u.id
            {where_clause}
            ORDER BY r.created_at DESC
            LIMIT ${param_count-1} OFFSET ${param_count}
        """
        
        rows = await conn.fetch(query, *params)
        
        # Convert UUIDs to strings for JSON serialization
        results = []
        for row in rows:
            result = dict(row)
            if result["user_id"]:
                result["user_id"] = str(result["user_id"])
            results.append(result)
        
        return {
            "success": True,
            "requests": results,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            },
            "filters": {
                "user_id": user_id,
                "tool_name": tool_name,
                "success": success,
                "from_date": from_date,
                "to_date": to_date
            }
        }


@router.get("/dashboard/summary", dependencies=[Depends(verify_is_admin)])
async def get_dashboard_summary():
    """Single endpoint for dashboard home with key metrics."""
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        # Total users
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_active = true")
        
        # Today's metrics
        today_query = """
            SELECT 
                COUNT(*) as total_requests_today,
                COALESCE(SUM(duration_ms), 0) as total_duration_today,
                COUNT(DISTINCT user_id) as active_users_today
            FROM request_logs
            WHERE DATE(created_at) = CURRENT_DATE
        """
        today_stats = await conn.fetchrow(today_query)
        
        # Today's token usage
        tokens_query = """
            SELECT 
                COALESCE(SUM(total_tokens), 0) as total_tokens_today,
                COALESCE(SUM(cost_usd), 0)::REAL as total_cost_today
            FROM llm_usage
            WHERE DATE(created_at) = CURRENT_DATE
        """
        token_stats = await conn.fetchrow(tokens_query)
        
        # Top 3 tools by usage (last 7 days)
        top_tools_query = """
            SELECT 
                tool_name,
                COUNT(*) as call_count,
                ROUND((SUM(CASE WHEN success = true THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 2) as success_rate
            FROM request_logs
            WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY tool_name
            ORDER BY call_count DESC
            LIMIT 3
        """
        top_tools = await conn.fetch(top_tools_query)
        
        # Recent activity (last 24 hours)
        recent_query = """
            SELECT 
                tool_name,
                success,
                duration_ms,
                created_at,
                CASE 
                    WHEN user_id IS NOT NULL THEN (SELECT email FROM users WHERE id = user_id LIMIT 1)
                    ELSE 'Anonymous'
                END as user_email
            FROM request_logs
            WHERE created_at > NOW() - INTERVAL '24 hours'
            ORDER BY created_at DESC
            LIMIT 10
        """
        recent_activity = await conn.fetch(recent_query)
        
        return {
            "success": True,
            "summary": {
                "total_users": total_users,
                "total_requests_today": today_stats["total_requests_today"],
                "total_tokens_today": token_stats["total_tokens_today"],
                "total_cost_today": float(token_stats["total_cost_today"]) if token_stats["total_cost_today"] else 0.0,
                "active_users_today": today_stats["active_users_today"],
                "avg_duration_today": int(today_stats["total_duration_today"] / today_stats["total_requests_today"]) if today_stats["total_requests_today"] > 0 else 0
            },
            "top_tools": [dict(r) for r in top_tools],
            "recent_activity": [dict(r) for r in recent_activity],
            "generated_at": datetime.now(timezone.utc).isoformat()
        }


@router.get("/keys/{key_id}/usage", dependencies=[Depends(verify_is_admin)])
async def get_key_usage_status(key_id: str):
    """Get current rate limit counters for a specific API key."""
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        # Get key info
        row = await conn.fetchrow(
            "SELECT id, tier, name, integration_name, hourly_limit_override, monthly_limit_override "
            "FROM api_keys WHERE id = $1", 
            uuid.UUID(key_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Get usage status
        usage = await api_key_store.get_key_usage_status(
            str(row["id"]), 
            row["tier"],
            row["hourly_limit_override"],
            row["monthly_limit_override"]
        )
        
        # Calculate remaining
        hourly_remaining = None
        if usage["hourly_limit"] is not None:
            hourly_remaining = max(0, usage["hourly_limit"] - usage["hourly_used"])
        
        monthly_remaining = None
        if usage["monthly_limit"] is not None:
            monthly_remaining = max(0, usage["monthly_limit"] - usage["monthly_used"])
        
        return {
            "api_key_id": str(row["id"]),
            "tier": row["tier"],
            "name": row["name"],
            "integration_name": row["integration_name"],
            "hourly_used": usage["hourly_used"],
            "hourly_limit": usage["hourly_limit"],
            "monthly_used": usage["monthly_used"],
            "monthly_limit": usage["monthly_limit"],
            "hourly_reset_at": usage["hourly_reset_at"],
            "monthly_reset_at": usage["monthly_reset_at"],
            "hourly_remaining": hourly_remaining,
            "monthly_remaining": monthly_remaining,
            "hourly_limit_override": row["hourly_limit_override"],
            "monthly_limit_override": row["monthly_limit_override"],
            "using_override": bool(row["hourly_limit_override"] or row["monthly_limit_override"])
        }


# --- Pricing Management Endpoints ---

class UpdateTierRequest(BaseModel):
    hourly_limit: Optional[int] = Field(None, description="Hourly request limit (1-10000)")
    monthly_limit: Optional[int] = Field(None, description="Monthly request limit (1-1000000 or null for unlimited)")
    cost_per_1k_tokens: Optional[float] = Field(None, description="Cost per 1k tokens (0.001-1.0)")
    max_expiry_days: Optional[int] = Field(None, description="Maximum expiry days (30, 90, or 180)")


@router.get("/pricing", dependencies=[Depends(verify_is_admin)])
async def get_pricing():
    """Get all tier configurations."""
    try:
        tiers = await tier_config_store.get_all_tiers()
        return {
            "success": True,
            "tiers": tiers
        }
    except Exception as e:
        logger.error(f"Failed to get pricing: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve pricing information")


@router.patch("/pricing/{tier}", dependencies=[Depends(verify_is_admin)])
async def update_pricing(tier: str, request: UpdateTierRequest, req: Request):
    """Update tier configuration."""
    # Validate tier
    valid_tiers = ["free", "pro", "enterprise"]
    if tier not in valid_tiers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier. Must be one of: {', '.join(valid_tiers)}"
        )
    
    # Get user_id from request state or use admin user_id
    user_id = getattr(req.state, "user_id", None)
    if not user_id:
        # Fallback to admin user_id for admin routes
        user_id = "4909dad3-01e0-4e36-b088-7cf022a38984"  # Admin user ID
    
    # Build updates dict
    updates = {}
    if request.hourly_limit is not None:
        updates["hourly_limit"] = request.hourly_limit
    if request.monthly_limit is not None:
        updates["monthly_limit"] = request.monthly_limit
    if request.cost_per_1k_tokens is not None:
        updates["cost_per_1k_tokens"] = request.cost_per_1k_tokens
    if request.max_expiry_days is not None:
        updates["max_expiry_days"] = request.max_expiry_days
    
    if not updates:
        raise HTTPException(
            status_code=400,
            detail="At least one field must be provided for update"
        )
    
    try:
        updated_config = await tier_config_store.update_tier(tier, updates, user_id)
        return {
            "success": True,
            "tier": tier,
            "config": updated_config,
            "message": f"{tier} tier updated successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update tier {tier}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update tier configuration")


# TODO: Add pricing history endpoint
# @router.get("/pricing/history", dependencies=[Depends(verify_is_admin)])
# async def get_pricing_history():
#     """Get recent pricing changes history."""
#     pass


# --- Key Override Management Endpoints ---

@router.get("/keys/{key_id}/overrides", dependencies=[Depends(verify_is_admin)])
async def get_key_overrides(key_id: str):
    """Get current overrides for a specific API key."""
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        # Get key info
        row = await conn.fetchrow(
            "SELECT id, tier, name, integration_name, hourly_limit_override, monthly_limit_override "
            "FROM api_keys WHERE id = $1", 
            uuid.UUID(key_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Get tier defaults
        tier_config = await tier_config_store.get_tier(row["tier"])
        
        # Calculate effective limits
        effective_hourly = row["hourly_limit_override"] or tier_config["hourly_limit"]
        effective_monthly = row["monthly_limit_override"] or tier_config["monthly_limit"]
        
        return {
            "api_key_id": key_id,
            "tier": row["tier"],
            "name": row["name"],
            "integration_name": row["integration_name"],
            "tier_defaults": {
                "hourly_limit": tier_config["hourly_limit"],
                "monthly_limit": tier_config["monthly_limit"]
            },
            "overrides": {
                "hourly_limit_override": row["hourly_limit_override"],
                "monthly_limit_override": row["monthly_limit_override"]
            },
            "effective_limits": {
                "hourly": effective_hourly,
                "monthly": effective_monthly
            }
        }


class UpdateKeyOverridesRequest(BaseModel):
    hourly_limit_override: Optional[int] = Field(None, description="Hourly limit override (1-10000 or null to clear)")
    monthly_limit_override: Optional[int] = Field(None, description="Monthly limit override (1-1000000 or null to clear)")

    model_config = {
        "extra": "forbid"
    }


@router.patch("/keys/{key_id}/overrides", dependencies=[Depends(verify_is_admin)])
async def update_key_overrides(key_id: str, request: UpdateKeyOverridesRequest, req: Request):
    """Set or clear overrides for a specific API key."""
    # Get user_id from request state or use admin user_id
    user_id = getattr(req.state, "user_id", None)
    if not user_id:
        # Fallback to admin user_id for admin routes
        user_id = "4909dad3-01e0-4e36-b088-7cf022a38984"  # Admin user ID
    
    # Validate overrides
    if request.hourly_limit_override is not None:
        if not isinstance(request.hourly_limit_override, int) or request.hourly_limit_override < 1 or request.hourly_limit_override > 10000:
            raise HTTPException(
                status_code=400,
                detail="hourly_limit_override must be an integer between 1 and 10000, or null"
            )
    
    if request.monthly_limit_override is not None:
        if not isinstance(request.monthly_limit_override, int) or request.monthly_limit_override < 1 or request.monthly_limit_override > 1000000:
            raise HTTPException(
                status_code=400,
                detail="monthly_limit_override must be an integer between 1 and 1000000, or null"
            )
    
    # Check if key exists and get tier
    pool = await PostgresPoolManager.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT tier FROM api_keys WHERE id = $1", 
            uuid.UUID(key_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="API key not found")
        
        key_tier = row["tier"]
        
        # Get enterprise limits for validation
        enterprise_config = await tier_config_store.get_tier("enterprise")
        enterprise_hourly = enterprise_config["hourly_limit"]
        enterprise_monthly = enterprise_config["monthly_limit"]
        
        # Cannot exceed enterprise limits
        if request.hourly_limit_override and enterprise_hourly and request.hourly_limit_override > enterprise_hourly:
            raise HTTPException(
                status_code=400,
                detail=f"hourly_limit_override cannot exceed enterprise tier limit of {enterprise_hourly}"
            )
        
        if request.monthly_limit_override and enterprise_monthly and request.monthly_limit_override > enterprise_monthly:
            raise HTTPException(
                status_code=400,
                detail=f"monthly_limit_override cannot exceed enterprise tier limit of {enterprise_monthly}"
            )
        
        # Update overrides
        update_fields = []
        update_values = []
        param_idx = 1
        
        # Check if fields are explicitly provided in the request
        request_dict = request.model_dump(exclude_unset=True)
        
        if "hourly_limit_override" in request_dict:
            update_fields.append(f"hourly_limit_override = ${param_idx}")
            update_values.append(request.hourly_limit_override)
            param_idx += 1
        
        if "monthly_limit_override" in request_dict:
            update_fields.append(f"monthly_limit_override = ${param_idx}")
            update_values.append(request.monthly_limit_override)
            param_idx += 1
        
        if not update_fields:
            raise HTTPException(
                status_code=400,
                detail="At least one override field must be provided"
            )
        
        # Add updated_by
        update_fields.append(f"updated_by = ${param_idx}")
        update_values.append(user_id)
        param_idx += 1
        
        await conn.execute(f"""
            UPDATE api_keys 
            SET {', '.join(update_fields)}
            WHERE id = ${param_idx}
        """, *update_values, uuid.UUID(key_id))
        
        # Invalidate API key cache
        try:
            key_hash_row = await conn.fetchrow("SELECT key_hash FROM api_keys WHERE id = $1", uuid.UUID(key_id))
            if key_hash_row:
                from src.storage.redis_file_store import RedisFileStore
                redis = RedisFileStore().client
                await redis.delete(f"api_key:v2:{key_hash_row['key_hash']}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for key {key_id}: {e}")
        
        # Get updated overrides
        updated_row = await conn.fetchrow(
            "SELECT hourly_limit_override, monthly_limit_override FROM api_keys WHERE id = $1", 
            uuid.UUID(key_id)
        )
        
        # Get tier defaults for effective limits
        tier_config = await tier_config_store.get_tier(key_tier)
        effective_hourly = updated_row["hourly_limit_override"] or tier_config["hourly_limit"]
        effective_monthly = updated_row["monthly_limit_override"] or tier_config["monthly_limit"]
        
        return {
            "success": True,
            "api_key_id": key_id,
            "effective_limits": {
                "hourly": effective_hourly,
                "monthly": effective_monthly
            },
            "message": "Overrides updated successfully"
        }
