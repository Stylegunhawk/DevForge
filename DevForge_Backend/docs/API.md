# DevForge API Documentation

Complete API reference for DevForge backend including authentication, tool endpoints, and admin analytics.

## Table of Contents

1. [Authentication](#authentication)
2. [API Key Management (Admin)](#api-key-management-admin)
3. [MCP Tool Endpoints](#mcp-tool-endpoints)
4. [Admin Analytics](#admin-analytics)
5. [User Key Management](#user-key-management)
6. [Complete Curl Examples](#complete-curl-examples)
7. [Environment Variables Reference](#environment-variables-reference)
8. [Error Reference](#error-reference)

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

## API Key Management (Admin)

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

### MCP Protocol (JSON-RPC 2.0)
**POST** `/mcp`

Execute tools via MCP JSON-RPC 2.0 protocol.

**Headers:**
```
x-api-key: <api_key>
Content-Type: application/json
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
      "task_type": "data_generation",
      "total_prompt_tokens": 1000,
      "total_completion_tokens": 500,
      "total_tokens": 1500,
      "total_cost_usd": 0.015,
      "request_count": 10,
      "date": "2026-03-04"
    }
  ],
  "tool_usage": [
    {
      "tool_name": "generate_data",
      "call_count": 10,
      "avg_duration_ms": 150,
      "success_count": 9,
      "error_count": 1,
      "success_rate": 90.0
    }
  ],
  "total_tokens": 1500,
  "total_cost": 0.015,
  "total_requests": 10
}
```

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

# List tools via MCP
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: df_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'

# Execute tool via MCP
curl -X POST http://localhost:8001/mcp \
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

3. **RAG Users**: Use JWT authentication (`Authorization: Bearer <token>`)
   - Tenant-based tokens for RAG endpoints
   - Separate from Dashboard JWTs
   - Protected by `JWTAuthMiddleware`

---

*This documentation covers all endpoints implemented in DevForge backend Phases 1-4.*
