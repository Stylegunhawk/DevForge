# Gateway & MCP Authentication Guide

## 📋 Overview
Access to the **MCP Gateway** (`/api/gateway`) and **MCP Direct Endpoints** (`/mcp`) is protected by **API Key Authentication**. This system is designed for high-performance, server-to-server or local-to-server communication (e.g., from an IDE or CLI).

---

## 🏗️ Architecture

### High-Performance Validation
To avoid database bottlenecks on every request, we use a **cache-first strategy**:
1. **Middleware Check**: `APIKeyAuthMiddleware` extracts `x-api-key` header.
2. **Redis Cache**: Checks for hashed key metadata in Redis.
3. **Postgres Fallback**: Validates against the `api_keys` table if cache misses.
4. **LRU Caching**: Metadata is cached for 5 minutes (configurable via `API_KEY_CACHE_TTL`).

### User Ownership (Phase 3)
Starting with Phase 3, API keys are linked to a specific `user_id`. This allows:
- **Dashboard Visibility**: Users can view and revoke their own keys.
- **Auditing**: Usage is tracked back to both the integration (e.g., Cursor) and the individual user.

---

## 🔐 Authentication Header
Clients must provide the API key in the `x-api-key` header (case-insensitive in middleware, usually lowercase recommended).

```http
POST /api/gateway
Content-Type: application/json
x-api-key: df_your_secure_api_key_here
```

---

## 🛡️ Protected Routes

| Route | Purpose | Protection |
|-------|---------|-------------|
| `/api/gateway` | Unified AI Reasoning Gateway | ✅ API Key Required |
| `/mcp` | Model Context Protocol entry | ✅ API Key Required |

---

## 🔑 API Key Tiers & Scopes
Keys can be configured with metadata to enforce limits:
- **Integration Name**: Identifies the source (e.g., `cursor-ide`, `devforge-cli`).
- **Tier**: `free`, `pro`, or `enterprise` (used for rate limiting/usage caps).
- **Scopes**: A list of allowed tools or operations (e.g., `["github", "rag"]`).

---

## 🛠️ Management

### For Developers (Dashboard)
Users can generate keys via the Dashboard at `/api/users/keys`. 
> [!IMPORTANT]
> The raw API key is only displayed **once** upon creation for security.

### For Administrators
Admins can oversee all keys, list active integrations, and revoke keys globally if compromise is suspected.
- `GET /api/admin/keys`
- `DELETE /api/admin/keys/{id}`

---

## ⚙️ Implementation Details
- **Core Storage**: `src/storage/api_key_store.py`
- **Middleware**: `src/core/api_key_middleware.py`
- **Hashing**: Keys are stored as **SHA-256** hashes; raw keys never touch the database.


curls :
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@devforge.ai", "password": "adminpass123"}'

  # Should succeed - admin access
curl http://localhost:8001/api/admin/users \
  -H "Authorization: Bearer ADMIN_JWT_HERE"

# Login as test user first, then try admin route
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@devforge.ai", "password": "test123"}'

# Should return 403 - non-admin blocked
curl http://localhost:8001/api/admin/users \
  -H "Authorization: Bearer TEST_USER_JWT_HERE"