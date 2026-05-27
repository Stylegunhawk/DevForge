# DevForge API Documentation

Complete API reference for DevForge backend including authentication, tier pricing, rate limit overrides, tool endpoints, and admin analytics.

## Table of Contents

1. [Authentication](#authentication)
2. [Tier Pricing Management](#tier-pricing-management)
3. [API Key Management (Admin)](#api-key-management-admin)
4. [Rate Limit Overrides](#rate-limit-overrides)
5. [MCP Tool Endpoints](#mcp-tool-endpoints)
6. [Admin Analytics](#admin-analytics)
7. [User Key Management](#user-key-management)
8. [Complete Curl Examples](#complete-curl-examples)
9. [Environment Variables Reference](#environment-variables-reference)
10. [Error Reference](#error-reference)

---

## Authentication

### Register User
**POST** `/api/auth/register`

Create a new user account with email and password.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123",
  "name": "John Doe"
}
```

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "name": "John Doe",
  "avatar_url": null,
  "is_admin": false,
  "created_at": "2026-03-04T10:00:00Z"
}
```

**Error Responses:**
- `400` - Email already registered

---

### Login
**POST** `/api/auth/login`

Authenticate user and receive JWT token.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Notes:**
- Token expires in 24 hours
- Use `Authorization: Bearer <token>` header for protected endpoints

**Error Responses:**
- `401` - Invalid email or password
- `403` - Account is deactivated

---

### Google SSO
**POST** `/api/auth/google/dashboard`

Authenticate using Google OAuth for dashboard access.

**Request Body:**
```json
{
  "id_token": "google_id_token_here"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Notes:**
- Auto-registers users on first login
- Syncs profile data (name, avatar) from Google

---

### Get Current User
**GET** `/api/auth/me`

Get current user profile information.

**Headers:**
```
Authorization: Bearer <dashboard_jwt>
```

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "name": "John Doe",
  "avatar_url": "https://lh3.googleusercontent.com/...",
  "is_admin": false,
  "created_at": "2026-03-04T10:00:00Z"
}
```

**Error Responses:**
- `401` - Not authenticated
- `404` - User not found

---

## Tier Pricing Management

### Get All Tier Configurations
**GET** `/api/admin/pricing`

Retrieve all tier configurations with pricing, limits, and expiry settings.

**Headers:**
```
Authorization: Bearer <admin_jwt>
```

**Response:**
```json
{
  "success": true,
  "tiers": {
    "free": {
      "tier": "free",
      "hourly_limit": 50,
      "monthly_limit": 500,
      "cost_per_1k_tokens": 0.01,
      "max_expiry_days": 180,
      "is_active": true,
      "updated_at": null,
      "updated_by_email": null
    },
    "pro": {
      "tier": "pro",
      "hourly_limit": 500,
      "monthly_limit": 20000,
      "cost_per_1k_tokens": 0.008,
      "max_expiry_days": 180,
      "is_active": true,
      "updated_at": "2026-03-06T08:48:56.772754+00:00",
      "updated_by_email": "admin@devforge.ai"
    },
    "enterprise": {
      "tier": "enterprise",
      "hourly_limit": 2000,
      "monthly_limit": null,
      "cost_per_1k_tokens": 0.005,
      "max_expiry_days": 180,
      "is_active": true,
      "updated_at": null,
      "updated_by_email": null
    }
  }
}
```

---

### Update Tier Configuration
**PATCH** `/api/admin/pricing/{tier}`

Update pricing, limits, or expiry settings for a specific tier.

**Headers:**
```
Authorization: Bearer <admin_jwt>
Content-Type: application/json
```

**Path Parameters:**
- `tier` (required) - Tier name: `free`, `pro`, or `enterprise`

**Request Body:**
```json
{
  "hourly_limit": 100,
  "monthly_limit": 1000,
  "cost_per_1k_tokens": 0.009,
  "max_expiry_days": 90
}
```

**Response:**
```json
{
  "success": true,
  "tier": "free",
  "config": {
    "tier": "free",
    "hourly_limit": 100,
    "monthly_limit": 1000,
    "cost_per_1k_tokens": 0.009,
    "max_expiry_days": 90,
    "is_active": true,
    "updated_at": "2026-03-06T08:48:56.772754+00:00",
    "updated_by_email": "admin@devforge.ai"
  },
  "message": "free tier updated successfully"
}
```

**Validation Rules:**
- `hourly_limit`: 1-10000 requests per hour
- `monthly_limit`: 1-1000000 requests per month or null for unlimited
- `cost_per_1k_tokens`: 0.001-1.0 USD per 1000 tokens
- `max_expiry_days`: 30, 90, or 180 days

**Error Responses:**
- `400` - Invalid tier or validation error
- `403` - Admin privileges required
- `500` - Failed to update tier configuration

---

### Create API Key
**POST** `/api/admin/keys`

Generate a new API key with optional user assignment.

**Headers:**
```
Authorization: Bearer <admin_jwt>
```

**Request Body:**
```json
{
  "name": "Production API Key",
  "integration_name": "cursor-ide",
  "tenant_id": "production",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "tier": "pro",
  "scopes": ["generate_data", "refine_prompt"]
}
```

**Response:**
```json
{
  "success": true,
  "raw_key": "df_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz",
  "message": "Copy this key now. It will never be shown again in raw format."
}
```

**Notes:**
- `raw_key` is shown **ONCE** only
- `user_id` is optional - omit for admin/global keys
- `scopes` limits which tools the key can access
- Available tiers: `free`, `pro`, `enterprise`

---

### List API Keys
**GET** `/api/admin/keys`

List all API keys with metadata (no raw keys).

**Headers:**
```
Authorization: Bearer <admin_jwt>
```

**Response:**
```json
{
  "success": true,
  "keys": [
    {
      "id": "456e7890-f12b-23d4-b567-537714285111",
      "name": "Production API Key",
      "integration_name": "cursor-ide",
      "tier": "pro",
      "tenant_id": "production",
      "user_id": "123e4567-e89b-12d3-a456-426614174000",
      "is_active": true,
      "created_at": "2026-03-04T10:00:00Z",
      "last_used_at": "2026-03-04T11:30:00Z"
    }
  ]
}
```

---

### Revoke API Key
**DELETE** `/api/admin/keys/{key_id}`

Deactivate and revoke an API key.

**Headers:**
```
Authorization: Bearer <admin_jwt>
```

**Response:**
```json
{
  "success": true,
  "message": "API key 456e7890-f12b-23d4-b567-537714285111 revoked successfully"
}
```

---

## Rate Limit Overrides

### Get Key Overrides
**GET** `/api/admin/keys/{key_id}/overrides`

Retrieve current rate limit overrides and effective limits for a specific API key.

**Headers:**
```
Authorization: Bearer <admin_jwt>
```

**Path Parameters:**
- `key_id` (required) - UUID of the API key

**Response:**
```json
{
  "api_key_id": "f0a87b83-edae-470e-8426-254fbd100f47",
  "tier": "free",
  "name": "Test Free Tier Key",
  "integration_name": "test-rate-limit",
  "tier_defaults": {
    "hourly_limit": 50,
    "monthly_limit": 500
  },
  "overrides": {
    "hourly_limit_override": 100,
    "monthly_limit_override": null
  },
  "effective_limits": {
    "hourly": 100,
    "monthly": 500
  }
}
```

---

### Update Key Overrides
**PATCH** `/api/admin/keys/{key_id}/overrides`

Set or clear rate limit overrides for a specific API key.

**Headers:**
```
Authorization: Bearer <admin_jwt>
Content-Type: application/json
```

**Path Parameters:**
- `key_id` (required) - UUID of the API key

**Request Body:**
```json
{
  "hourly_limit_override": 150,
  "monthly_limit_override": 2000
}
```

**Response:**
```json
{
  "success": true,
  "api_key_id": "f0a87b83-edae-470e-8426-254fbd100f47",
  "effective_limits": {
    "hourly": 150,
    "monthly": 2000
  },
  "message": "Overrides updated successfully"
}
```

**Validation Rules:**
- `hourly_limit_override`: 1-10000 or null to clear
- `monthly_limit_override`: 1-1000000 or null to clear
- Cannot exceed enterprise tier limits (2000 hourly, unlimited monthly)
- At least one field must be provided

**Clear Override Example:**
```json
{
  "hourly_limit_override": null,
  "monthly_limit_override": null
}
```

**Error Responses:**
- `400` - Invalid override values or validation error
- `403` - Admin privileges required
- `404` - API key not found
- `500` - Failed to update overrides

---

### Enhanced Key Usage with Override Info
**GET** `/api/admin/keys/{key_id}/usage`

Get current rate limit usage with override information.

**Response:**
```json
{
  "api_key_id": "f0a87b83-edae-470e-8426-254fbd100f47",
  "tier": "free",
  "name": "Test Free Tier Key",
  "integration_name": "test-rate-limit",
  "hourly_used": 1,
  "hourly_limit": 100,
  "monthly_used": 13,
  "monthly_limit": 500,
  "hourly_reset_at": "2026-03-06T07:00:00+00:00",
  "monthly_reset_at": "2026-04-01T00:00:00+00:00",
  "hourly_remaining": 99,
  "monthly_remaining": 487,
  "hourly_limit_override": 100,
  "monthly_limit_override": null,
  "using_override": true
}
```

**Override Status Fields:**
- `hourly_limit_override`: Current hourly override or null
- `monthly_limit_override`: Current monthly override or null
- `using_override`: Boolean indicating if any override is active

---

## MCP Tool Endpoints

### Gateway (REST)
**POST** `/api/gateway`

Execute tools via REST API using API key authentication.

**Headers:**
```
x-api-key: <api_key>
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "generate_data",
  "arguments": {
    "rows": 100,
    "format": "json",
    "fields": ["name", "email", "age"]
  }
}
```

**Available Tools:**
- `generate_data` - Generate mock data
- `github_operation` - GitHub automation
- `refine_prompt` - Prompt optimization
- `generate_cheatsheet` - Code documentation

**Response:**
```json
{
  "success": true,
  "data": "[{\"name\": \"John Doe\", \"email\": \"john@example.com\", \"age\": 25}]",
  "message": "generate_data executed successfully"
}
```

**Important:** Use `"name"` field, NOT `"tool"`

**Error Responses:**
- `401` - API Key missing or invalid
- `400` - Tool not found or invalid arguments

---

### MCP Protocol (Streamable HTTP — MCP SDK)
**POST** `/mcp/`

Execute tools via the MCP Python SDK using the Streamable HTTP transport. The endpoint is a FastMCP ASGI sub-app mounted at `/mcp/` (**trailing slash required**).

**Headers:**
```
x-api-key: <api_key>
Content-Type: application/json
```

**Rate limit headers returned on every response:**
```
X-RateLimit-Limit-Hourly: 50
X-RateLimit-Used-Hourly: 3
X-RateLimit-Reset-Hourly: 2026-05-27T14:00:00+00:00
X-RateLimit-Limit-Monthly: 500
X-RateLimit-Used-Monthly: 17
X-RateLimit-Reset-Monthly: 2026-06-01T00:00:00+00:00
```

**Available Methods:**
- `initialize` - Initialize MCP session
- `tools/list` - List available tools
- `tools/call` - Execute a tool

**Example - List Tools:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "generate_data",
        "description": "Generate realistic mock CSV/JSON data",
        "inputSchema": {...}
      }
    ]
  }
}
```

**Example - Call Tool:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "generate_data",
    "arguments": {
      "rows": 10,
      "format": "json"
    }
  }
}
```

**Implementation notes:**
- The `/mcp/` sub-app is powered by `fastmcp` (MCP Python SDK). The old hand-rolled JSON-RPC handler has been removed.
- `APIKeyAuthMiddleware` protects both `/mcp` and all `/mcp/*` sub-paths.
- `MCPRateLimitHeadersMiddleware` (pure ASGI, `src/api/mcp/headers_middleware.py`) injects `X-RateLimit-*` headers on every response from `/mcp`.
- Per-call analytics are logged to `request_logs` via `dispatch.py` for all tool calls; LLM token usage is logged to `llm_usage` only when a language model is invoked.

---

## Admin Analytics

### List Users
**GET** `/api/admin/users`

List all registered users.

**Headers:**
```
Authorization: Bearer <admin_jwt>
```

**Response:**
```json
{
  "success": true,
  "users": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "email": "user@example.com",
      "name": "John Doe",
      "avatar_url": null,
      "auth_provider": "local",
      "is_admin": false,
      "is_active": true,
      "created_at": "2026-03-04T10:00:00Z"
    }
  ]
}
```

---

### User Usage Analytics
**GET** `/api/admin/users/{user_id}/usage`

Get detailed usage analytics for a specific user.

**Headers:**
```
Authorization: Bearer <admin_jwt>
```

**Query Parameters:**
- `days` (optional, default: 30) - Number of days to analyze

**Response:**
```json
{
  "success": true,
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "name": "John Doe",
    "member_since": "2026-03-04T10:00:00Z"
  },
  "period_days": 30,
  "token_usage": [
    {
      "model_name": "gpt-oss:20b-cloud",
      "task_type": "cheatsheet_personalization",
      "total_prompt_tokens": 1766,
      "total_completion_tokens": 1381,
      "total_tokens": 3147,
      "total_cost_usd": 0.03,
      "request_count": 1,
      "date": "2026-05-27"
    }
  ],
  "tool_usage": [
    {
      "tool_name": "generate_data",
      "call_count": 2,
      "avg_duration_ms": 340,
      "success_count": 2,
      "error_count": 0,
      "success_rate": 100.0
    },
    {
      "tool_name": "github_operation",
      "call_count": 10,
      "avg_duration_ms": 820,
      "success_count": 9,
      "error_count": 1,
      "success_rate": 90.0
    }
  ],
  "recent_requests": [
    {
      "tool_name": "github_operation",
      "success": true,
      "duration_ms": 760,
      "created_at": "2026-05-27T13:45:00+00:00",
      "input_summary": "{\"operation\": \"list_repos\"}"
    },
    {
      "tool_name": "generate_data",
      "success": true,
      "duration_ms": 310,
      "created_at": "2026-05-27T13:40:00+00:00",
      "input_summary": "{\"rows\": 50, \"format\": \"json\"}"
    }
  ],
  "daily_requests": [
    {
      "date": "2026-05-27",
      "request_count": 15
    },
    {
      "date": "2026-05-26",
      "request_count": 3
    }
  ],
  "total_tokens": 4768,
  "total_cost": 0.05,
  "total_requests": 15
}
```

**Field notes:**
- `token_usage` — LLM-only rows from `llm_usage` table. Only tools that invoke a language model appear here (e.g. `refine_prompt`, `generate_cheatsheet`, high-realism `generate_data`).
- `tool_usage` — aggregated per-tool stats from `request_logs`. Covers **all** tools including `generate_data` (Faker path) and `github_operation` (REST API ops).
- `recent_requests` — last 100 individual call log entries from `request_logs`, newest first. Covers all tools regardless of LLM use.
- `daily_requests` — per-day call counts from `request_logs`. Used by the dashboard "Daily Requests" chart.
- `total_requests` — sum of `call_count` across all tools in `tool_usage` (i.e. total calls from `request_logs`, not just LLM calls).

---

### LLM Usage Statistics
**GET** `/api/admin/usage`

Get LLM token usage with enhanced filtering.

**Headers:**
```
Authorization: Bearer <admin_jwt>
```

**Query Parameters:**
- `tenant_id` (optional) - Filter by tenant
- `user_id` (optional) - Filter by user
- `tool_name` (optional) - Filter by tool name
- `from_date` (optional) - Start date (ISO format)
- `to_date` (optional) - End date (ISO format)
- `days` (optional, default: 7) - Number of days if no date range

**Response:**
```json
{
  "success": true,
  "usage": [
    {
      "tenant_id": "production",
      "integration_name": "cursor-ide",
      "model_name": "gpt-oss:20b-cloud",
      "total_prompt_tokens": 5000,
      "total_completion_tokens": 2500,
      "total_tokens": 7500,
      "total_cost_usd": 0.075,
      "request_count": 50
    }
  ],
  "period_days": 7,
  "filters": {
    "tenant_id": "production",
    "user_id": null,
    "tool_name": "generate_data",
    "from_date": null,
    "to_date": null
  }
}
```

---

### Tool Performance Statistics
**GET** `/api/admin/tools/stats`

Get per-tool performance metrics.

**Headers:**
```
Authorization: Bearer <admin_jwt>
```

**Query Parameters:**
- `days` (optional, default: 30) - Number of days to analyze

**Response:**
```json
{
  "success": true,
  "period_days": 30,
  "tool_stats": [
    {
      "tool_name": "generate_data",
      "total_calls": 100,
      "avg_duration_ms": 150,
      "success_count": 95,
      "error_count": 5,
      "success_rate": 95.0,
      "unique_users": 10,
      "total_tokens": 15000,
      "total_cost_usd": 0.15
    }
  ],
  "summary": {
    "total_tools": 4,
    "total_calls": 250,
    "total_tokens": 45000,
    "total_cost": 0.45,
    "avg_success_rate": 94.5
  }
}
```

---

### Request Logs
**GET** `/api/admin/requests`

Get paginated request logs with filtering.

**Headers:**
```
Authorization: Bearer <admin_jwt>
```

**Query Parameters:**
- `page` (optional, default: 1) - Page number
- `limit` (optional, default: 50) - Items per page
- `user_id` (optional) - Filter by user
- `tool_name` (optional) - Filter by tool
- `success` (optional) - Filter by success status (true/false)
- `from_date` (optional) - Start date (ISO format)
- `to_date` (optional) - End date (ISO format)

**Response:**
```json
{
  "success": true,
  "requests": [
    {
      "id": "789e0123-g23b-34d5-c678-648814396222",
      "user_id": "123e4567-e89b-12d3-a456-426614174000",
      "tenant_id": "production",
      "integration_name": "cursor-ide",
      "tool_name": "generate_data",
      "input_summary": "{\"rows\": 100, \"format\": \"json\"}",
      "success": true,
      "duration_ms": 150,
      "created_at": "2026-03-04T11:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 150,
    "pages": 3
  },
  "filters": {
    "user_id": null,
    "tool_name": "generate_data",
    "success": null,
    "from_date": null,
    "to_date": null
  }
}
```

---

### Dashboard Summary
**GET** `/api/admin/dashboard/summary`

Get high-level dashboard metrics for home page.

**Headers:**
```
Authorization: Bearer <admin_jwt>
```

**Response:**
```json
{
  "success": true,
  "summary": {
    "total_users": 150,
    "total_requests_today": 250,
    "total_tokens_today": 50000,
    "total_cost_today": 0.5,
    "active_users_today": 25,
    "avg_duration_today": 180
  },
  "top_tools": [
    {
      "tool_name": "generate_data",
      "call_count": 100,
      "success_rate": 95.0
    },
    {
      "tool_name": "refine_prompt",
      "call_count": 75,
      "success_rate": 98.0
    },
    {
      "tool_name": "github_operation",
      "call_count": 50,
      "success_rate": 92.0
    }
  ],
  "recent_activity": [
    {
      "tool_name": "generate_data",
      "success": true,
      "duration_ms": 150,
      "created_at": "2026-03-04T11:30:00Z",
      "user_email": "user@example.com"
    }
  ],
  "generated_at": "2026-03-04T11:45:00Z"
}
```

---

### Update User
**PATCH** `/api/admin/users/{user_id}`

Update user privileges or status.

**Headers:**
```
Authorization: Bearer <admin_jwt>
```

**Request Body:**
```json
{
  "is_admin": true,
  "is_active": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "User 123e4567-e89b-12d3-a456-426614174000 updated successfully"
}
```

**Error Responses:**
- `400` - No updates provided
- `404` - User not found

---

## User Key Management

### List My Keys
**GET** `/api/users/keys`

List API keys owned by the authenticated user.

**Headers:**
```
Authorization: Bearer <dashboard_jwt>
```

**Response:**
```json
[
  {
    "id": "789e0123-g23b-34d5-c678-648814396222",
    "name": "My Development Key",
    "integration_name": "vscode",
    "tier": "free",
    "tenant_id": "user-123",
    "is_active": true,
    "created_at": "2026-03-04T10:00:00Z",
    "last_used_at": "2026-03-04T11:30:00Z"
  }
]
```

---

### Create My Key
**POST** `/api/users/keys`

Create a new API key owned by the authenticated user.

**Headers:**
```
Authorization: Bearer <dashboard_jwt>
```

**Request Body:**
```json
{
  "name": "My Development Key",
  "integration_name": "vscode",
  "tenant_id": "user-123",
  "tier": "free",
  "scopes": ["generate_data"]
}
```

**Response:**
```json
{
  "key": "df_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz",
  "message": "Save this key, it will not be shown again."
}
```

---

### Revoke My Key
**DELETE** `/api/users/keys/{key_id}`

Revoke an API key owned by the authenticated user.

**Headers:**
```
Authorization: Bearer <dashboard_jwt>
```

**Response:**
```json
{
  "success": true
}
```

**Error Responses:**
- `403` - Not authorized to revoke this key
- `404` - Key not found

---

## Complete Curl Examples

### Authentication Flow

```bash
# Register new user
curl -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "john@example.com", "password": "securePass123", "name": "John Doe"}'

# Login
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "john@example.com", "password": "securePass123"}'

# Get current user
curl -X GET http://localhost:8001/api/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Tier Pricing Management

```bash
# Get all tier configurations
curl -X GET http://localhost:8001/api/admin/pricing \
  -H "Authorization: Bearer <admin_jwt>"

# Update free tier hourly limit to 100
curl -X PATCH http://localhost:8001/api/admin/pricing/free \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit": 100}'

# Update pro tier pricing and limits
curl -X PATCH http://localhost:8001/api/admin/pricing/pro \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit": 1000, "cost_per_1k_tokens": 0.007, "max_expiry_days": 90}'

# Revert free tier back to defaults
curl -X PATCH http://localhost:8001/api/admin/pricing/free \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit": 50}'
```

### Rate Limit Overrides

```bash
# Get current overrides for a key
curl -X GET http://localhost:8001/api/admin/keys/f0a87b83-edae-470e-8426-254fbd100f47/overrides \
  -H "Authorization: Bearer <admin_jwt>"

# Set hourly override (higher than tier default)
curl -X PATCH http://localhost:8001/api/admin/keys/f0a87b83-edae-470e-8426-254fbd100f47/overrides \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit_override": 150}'

# Set both hourly and monthly overrides
curl -X PATCH http://localhost:8001/api/admin/keys/f0a87b83-edae-470e-8426-254fbd100f47/overrides \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit_override": 200, "monthly_limit_override": 5000}'

# Clear hourly override (revert to tier default)
curl -X PATCH http://localhost:8001/api/admin/keys/f0a87b83-edae-470e-8426-254fbd100f47/overrides \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit_override": null}'

# Clear all overrides
curl -X PATCH http://localhost:8001/api/admin/keys/f0a87b83-edae-470e-8426-254fbd100f47/overrides \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit_override": null, "monthly_limit_override": null}'

# Check usage with override info
curl -X GET http://localhost:8001/api/admin/keys/f0a87b83-edae-470e-8426-254fbd100f47/usage \
  -H "Authorization: Bearer <admin_jwt>"
```

### Admin API Key Management

```bash
# Create API key for user
curl -X POST http://localhost:8001/api/admin/keys \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Production Key", "integration_name": "cursor-ide", "tenant_id": "prod", "user_id": "123e4567-e89b-12d3-a456-426614174000", "tier": "pro", "scopes": ["generate_data", "refine_prompt"]}'

# List all keys
curl -X GET http://localhost:8001/api/admin/keys \
  -H "Authorization: Bearer <admin_jwt>"

# Revoke key
curl -X DELETE http://localhost:8001/api/admin/keys/456e7890-f12b-23d4-b567-537714285111 \
  -H "Authorization: Bearer <admin_jwt>"
```

### Tool Execution

```bash
# Generate data via REST gateway
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: df_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz" \
  -d '{"name": "generate_data", "arguments": {"rows": 10, "format": "json", "fields": ["name", "email"]}}'

# List tools via MCP (trailing slash required)
curl -X POST http://localhost:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "x-api-key: df_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'

# Execute tool via MCP
curl -X POST http://localhost:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "x-api-key: df_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "generate_data", "arguments": {"rows": 5, "format": "json"}}}'
```

### Admin Analytics

```bash
# Get dashboard summary
curl -X GET http://localhost:8001/api/admin/dashboard/summary \
  -H "Authorization: Bearer <admin_jwt>"

# Get user usage
curl -X GET http://localhost:8001/api/admin/users/123e4567-e89b-12d3-a456-426614174000/usage \
  -H "Authorization: Bearer <admin_jwt>"

# Get tool stats
curl -X GET http://localhost:8001/api/admin/tools/stats \
  -H "Authorization: Bearer <admin_jwt>"

# Get request logs with filters
curl -X GET "http://localhost:8001/api/admin/requests?tool_name=generate_data&success=true&page=1&limit=20" \
  -H "Authorization: Bearer <admin_jwt>"

# Get usage with date range
curl -X GET "http://localhost:8001/api/admin/usage?from_date=2026-03-01&to_date=2026-03-04&tool_name=generate_data" \
  -H "Authorization: Bearer <admin_jwt>"
```

### User Key Management

```bash
# Create user key
curl -X POST http://localhost:8001/api/users/keys \
  -H "Authorization: Bearer <user_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Dev Key", "integration_name": "vscode", "tenant_id": "personal", "tier": "free"}'

# List user keys
curl -X GET http://localhost:8001/api/users/keys \
  -H "Authorization: Bearer <user_jwt>"

# Revoke user key
curl -X DELETE http://localhost:8001/api/users/keys/789e0123-g23b-34d5-c678-648814396222 \
  -H "Authorization: Bearer <user_jwt>"
```

---

## Environment Variables Reference

### Authentication
```bash
# Dashboard JWT authentication
DASHBOARD_JWT_SECRET=your-secure-secret-here

# Google OAuth for Dashboard (optional)
GOOGLE_DASHBOARD_CLIENT_ID=your-google-client-id
GOOGLE_DASHBOARD_SECRET=your-google-client-secret
```

### API Key Management
```bash
# API Key cache TTL in seconds (default: 300)
API_KEY_CACHE_TTL=300
```

### Database
```bash
# PostgreSQL connection
DATABASE_URL=postgresql://user:password@localhost:5432/devforge
```

### Celery
```bash
# Redis broker for Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

## Error Reference

### 401 Unauthorized
```json
{
  "detail": "API Key missing"
}
```
```json
{
  "detail": "Invalid or inactive API Key"
}
```
```json
{
  "detail": "Authorization header missing"
}
```
```json
{
  "detail": "Invalid email or password"
}
```

### 403 Forbidden
```json
{
  "detail": "Admin privileges required"
}
```
```json
{
  "detail": "Account is deactivated"
}
```
```json
{
  "detail": "Not authorized to revoke this key"
}
```

### 404 Not Found
```json
{
  "detail": "User not found"
}
```
```json
{
  "detail": "Tool not found: invalid_tool"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "email"],
      "msg": "field required",
      "input": {"password": "pass123"}
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```

---

## Authentication Flow Summary

1. **Dashboard Users**: Use JWT authentication (`Authorization: Bearer <token>`)
   - Register/Login → Get JWT → Use in Authorization header
   - Token expires in 24 hours
   - Contains `user_id` and `is_admin` claims

2. **API Key Users**: Use API key authentication (`x-api-key: <key>`)
   - Admin creates keys via `/api/admin/keys`
   - Users create keys via `/api/users/keys`
   - Keys contain `user_id` for analytics tracking
   - Cache-first validation with Redis
   - **Rate Limit Overrides**: Per-key limits can override tier defaults

3. **RAG Users**: Use JWT authentication (`Authorization: Bearer <token>`)
   - Tenant-based tokens for RAG endpoints
   - Separate from Dashboard JWTs
   - Protected by `JWTAuthMiddleware`

4. **Tier-Based Rate Limiting**: 
   - Global tier configurations (`/api/admin/pricing`)
   - Dynamic limit fetching from database
   - Per-key overrides (`/api/admin/keys/{key_id}/overrides`)
   - Real-time limit updates without restart

---

## Feature Integration Examples

### Complete Workflow: Tier Management → Key Creation → Override Setting

```bash
# 1. Check current tier pricing
curl -X GET http://localhost:8001/api/admin/pricing \
  -H "Authorization: Bearer <admin_jwt>"

# 2. Update free tier limits
curl -X PATCH http://localhost:8001/api/admin/pricing/free \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit": 100}'

# 3. Create API key for user
curl -X POST http://localhost:8001/api/admin/keys \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name": "User Key", "integration_name": "vscode", "tier": "free", "user_id": "123e4567-e89b-12d3-a456-426614174000"}'

# 4. Set custom limits for the key
curl -X PATCH http://localhost:8001/api/admin/keys/{key_id}/overrides \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit_override": 200, "monthly_limit_override": 1000}'

# 5. Verify effective limits
curl -X GET http://localhost:8001/api/admin/keys/{key_id}/usage \
  -H "Authorization: Bearer <admin_jwt>"

# 6. Test API call with overridden limits
curl -X POST http://localhost:8001/api/gateway \
  -H "x-api-key: <api_key>" \
  -H "Content-Type: application/json" \
  -d '{"name": "generate_data", "arguments": {"rows": 10}}'
```

### Rate Limit Override Use Cases

```bash
# High-volume user: Increase limits temporarily
curl -X PATCH http://localhost:8001/api/admin/keys/{key_id}/overrides \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit_override": 1000, "monthly_limit_override": 50000}'

# Testing user: Reduce limits for safety
curl -X PATCH http://localhost:8001/api/admin/keys/{key_id}/overrides \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit_override": 10, "monthly_limit_override": 100}'

# Enterprise user: Custom high limits
curl -X PATCH http://localhost:8001/api/admin/keys/{key_id}/overrides \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit_override": 5000, "monthly_limit_override": null}'
```

---

*Last updated: 2026-05-27 — covers Phases 1–4 plus MCP SDK migration (FastMCP Streamable HTTP) and dashboard usage analytics.*
