"""Admin API for API key management.

Provides endpoints for creating, listing, and revoking API keys.
Protected by ADMIN_SECRET header check.
"""

from datetime import datetime, timezone
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
    user_id: Optional[str] = Field(default=None, description="User ID for user-scoped keys")

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
        scopes=request.scopes,
        user_id=request.user_id  # NEW: Pass user_id to create_key
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
        count_query = f"SELECT COUNT(*) as total FROM request_logs {where_clause}"
        total_count = await conn.fetchval(count_query, *params)
        
        # Get paginated results
        offset = (page - 1) * limit
        param_count += 1
        params.append(limit)
        param_count += 1
        params.append(offset)
        
        query = f"""
            SELECT 
                id,
                user_id,
                tenant_id,
                integration_name,
                tool_name,
                input_summary,
                success,
                duration_ms,
                created_at
            FROM request_logs
            {where_clause}
            ORDER BY created_at DESC
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
