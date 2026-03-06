# DevForge Backend Authentication Guide

## 📋 Overview

This document covers the comprehensive authentication architecture for DevForge, including user authentication, API key management, tier-based rate limiting, and per-key overrides.

**Authentication Methods:**
- 📑 **Dashboard Authentication** - User accounts, Google/Local login, and Admin features
- 🔑 **API Key Authentication** - Rate-limited access for IDEs and CLI tools  
- 🏢 **Tenant-based Authentication** - Stateless JWT for RAG endpoints
- ⚙️ **Tier-based Rate Limiting** - Dynamic limits with per-key overrides

---

## 🏗️ Architecture Overview

### Authentication Flow
```
Frontend → Google OAuth → JWT Token → Dashboard Endpoints (Protected)
          → API Keys → Rate Limiting → Tool Endpoints (Protected)
```

### Components
1. **User Authentication** (`src/core/auth.py`, `src/api/routers/auth.py`)
2. **API Key Authentication** (`src/core/api_key_middleware.py`)
3. **Rate Limiting** (`src/core/rate_limiter.py`, `src/storage/tier_config_store.py`)
4. **Tier Management** (`src/api/routers/admin.py`)
5. **Per-key Overrides** (`src/api/routers/admin.py`)

---

## 🔐 User Authentication

### Local Registration & Login

#### Register User
**POST** `/api/auth/register`

```bash
curl -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securePass123", "name": "John Doe"}'
```

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com", 
  "name": "John Doe",
  "is_admin": false,
  "created_at": "2026-03-06T10:00:00Z"
}
```

#### Login
**POST** `/api/auth/login`

```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securePass123"}'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Google OAuth Integration

#### Google SSO Login
**POST** `/api/auth/google/dashboard`

```bash
curl -X POST http://localhost:8001/api/auth/google/dashboard \
  -H "Content-Type: application/json" \
  -d '{"id_token": "google_id_token_here"}'
```

**Features:**
- ✅ Auto-registers users on first login
- ✅ Syncs profile data (name, avatar) from Google
- ✅ Supports admin privilege assignment
- ✅ JWT token generation for dashboard access

---

## 🔑 API Key Authentication

### API Key Management

#### Create API Key (Admin)
**POST** `/api/admin/keys`

```bash
curl -X POST http://localhost:8001/api/admin/keys \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production API Key",
    "integration_name": "cursor-ide", 
    "tenant_id": "production",
    "tier": "pro",
    "user_id": "123e4567-e89b-12d3-a456-426614174000"
  }'
```

**Response:**
```json
{
  "success": true,
  "raw_key": "df_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz",
  "message": "Copy this key now. It will never be shown again in raw format."
}
```

#### Create API Key (User)
**POST** `/api/users/keys`

```bash
curl -X POST http://localhost:8001/api/users/keys \
  -H "Authorization: Bearer <user_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Development Key",
    "integration_name": "vscode",
    "tier": "free"
  }'
```

### API Key Usage

#### Tool Execution with API Key
**POST** `/api/gateway`

```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "x-api-key: df_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_data",
    "arguments": {"rows": 10, "format": "json"}
  }'
```

**Rate Limit Headers:**
```
x-ratelimit-limit-hourly: 50
x-ratelimit-used-hourly: 1
x-ratelimit-limit-monthly: 500
x-ratelimit-used-monthly: 13
```

---

## ⚙️ Tier-Based Rate Limiting

### Tier Configuration Management

#### Get All Tier Configurations
**GET** `/api/admin/pricing`

```bash
curl -X GET http://localhost:8001/api/admin/pricing \
  -H "Authorization: Bearer <admin_jwt>"
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
      "is_active": true
    },
    "pro": {
      "tier": "pro", 
      "hourly_limit": 500,
      "monthly_limit": 20000,
      "cost_per_1k_tokens": 0.008,
      "max_expiry_days": 180,
      "is_active": true
    },
    "enterprise": {
      "tier": "enterprise",
      "hourly_limit": 2000,
      "monthly_limit": null,
      "cost_per_1k_tokens": 0.005,
      "max_expiry_days": 180,
      "is_active": true
    }
  }
}
```

#### Update Tier Configuration
**PATCH** `/api/admin/pricing/{tier}`

```bash
# Update free tier hourly limit
curl -X PATCH http://localhost:8001/api/admin/pricing/free \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit": 100}'

# Update pro tier pricing
curl -X PATCH http://localhost:8001/api/admin/pricing/pro \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "hourly_limit": 1000,
    "cost_per_1k_tokens": 0.007,
    "max_expiry_days": 90
  }'
```

**Validation Rules:**
- `hourly_limit`: 1-10000 requests per hour
- `monthly_limit`: 1-1000000 or null for unlimited
- `cost_per_1k_tokens`: 0.001-1.0 USD
- `max_expiry_days`: 30, 90, or 180 days

---

## 🎯 Per-Key Rate Limit Overrides

### Override Management

#### Get Key Overrides
**GET** `/api/admin/keys/{key_id}/overrides`

```bash
curl -X GET http://localhost:8001/api/admin/keys/f0a87b83-edae-470e-8426-254fbd100f47/overrides \
  -H "Authorization: Bearer <admin_jwt>"
```

**Response:**
```json
{
  "api_key_id": "f0a87b83-edae-470e-8426-254fbd100f47",
  "tier": "free",
  "name": "Test Free Tier Key",
  "tier_defaults": {
    "hourly_limit": 50,
    "monthly_limit": 500
  },
  "overrides": {
    "hourly_limit_override": 150,
    "monthly_limit_override": 2000
  },
  "effective_limits": {
    "hourly": 150,
    "monthly": 2000
  }
}
```

#### Set Key Overrides
**PATCH** `/api/admin/keys/{key_id}/overrides`

```bash
# Set custom limits
curl -X PATCH http://localhost:8001/api/admin/keys/f0a87b83-edae-470e-8426-254fbd100f47/overrides \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "hourly_limit_override": 200,
    "monthly_limit_override": 5000
  }'

# Clear override (revert to tier default)
curl -X PATCH http://localhost:8001/api/admin/keys/f0a87b83-edae-470e-8426-254fbd100f47/overrides \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit_override": null}'
```

**Validation Rules:**
- `hourly_limit_override`: 1-10000 or null to clear
- `monthly_limit_override`: 1-1000000 or null to clear
- Cannot exceed enterprise tier limits
- At least one field must be provided

#### Usage with Override Info
**GET** `/api/admin/keys/{key_id}/usage`

```bash
curl -X GET http://localhost:8001/api/admin/keys/f0a87b83-edae-470e-8426-254fbd100f47/usage \
  -H "Authorization: Bearer <admin_jwt>"
```

**Response:**
```json
{
  "api_key_id": "f0a87b83-edae-470e-8426-254fbd100f47",
  "hourly_used": 1,
  "hourly_limit": 150,
  "monthly_used": 13,
  "monthly_limit": 2000,
  "hourly_limit_override": 150,
  "monthly_limit_override": 2000,
  "using_override": true
}
```

---

## 🏢 Tenant-Based Authentication (RAG)

### JWT Token for RAG Endpoints

#### Get RAG JWT Token
**POST** `/api/auth/google`

```bash
curl -X POST http://localhost:8001/api/auth/google \
  -H "Content-Type: application/json" \
  -d '{
    "google_token": "google_oauth_id_token",
    "mongodb_id": "tenant-123"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### Use RAG Endpoints
**GET** `/api/v1/rag/files`

```bash
curl -X GET http://localhost:8001/api/v1/rag/files \
  -H "Authorization: Bearer <rag_jwt>"
```

**JWT Payload:**
```json
{
  "tenant_id": "tenant-123",
  "exp": 1772452532,
  "original_issued_at": "2026-03-06T10:55:32.319271+00:00"
}
```

---

## 🧪 Complete Testing Guide

### Prerequisites
1. **DevForge backend running** on `http://localhost:8001`
2. **Admin credentials**: `admin@devforge.ai` / `adminpass123`
3. **Test user**: Create via registration or use existing

### Step 1: Admin Authentication

```bash
# Login as admin
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@devforge.ai", "password": "adminpass123"}' | \
  jq -r '.access_token')

echo "Admin Token: $ADMIN_TOKEN"
```

### Step 2: Tier Management Testing

```bash
# Check current tiers
curl -X GET http://localhost:8001/api/admin/pricing \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.tiers.free.hourly_limit'

# Update free tier
curl -X PATCH http://localhost:8001/api/admin/pricing/free \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit": 100}'

# Verify update
curl -X GET http://localhost:8001/api/admin/pricing \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.tiers.free.hourly_limit'

# Revert change
curl -X PATCH http://localhost:8001/api/admin/pricing/free \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit": 50}'
```

### Step 3: API Key Creation

```bash
# Create API key
KEY_RESPONSE=$(curl -s -X POST http://localhost:8001/api/admin/keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Override Key",
    "integration_name": "test-override",
    "tier": "free"
  }')

API_KEY=$(echo $KEY_RESPONSE | jq -r '.raw_key')
KEY_ID=$(echo $KEY_RESPONSE | jq -r '.key_id')

echo "API Key: $API_KEY"
echo "Key ID: $KEY_ID"
```

### Step 4: Override Testing

```bash
# Set override
curl -X PATCH http://localhost:8001/api/admin/keys/$KEY_ID/overrides \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit_override": 150}'

# Check override
curl -X GET http://localhost:8001/api/admin/keys/$KEY_ID/overrides \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.effective_limits'

# Check usage with override
curl -X GET http://localhost:8001/api/admin/keys/$KEY_ID/usage \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '{hourly_limit, using_override}'

# Test API call with override
curl -X POST http://localhost:8001/api/gateway \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "generate_data", "arguments": {"rows": 5}}'

# Clear override
curl -X PATCH http://localhost:8001/api/admin/keys/$KEY_ID/overrides \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"hourly_limit_override": null}'
```

### Step 5: User Authentication Testing

```bash
# Register test user
curl -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testPass123", "name": "Test User"}'

# Login as test user
USER_TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testPass123"}' | \
  jq -r '.access_token')

# Create user key
USER_KEY=$(curl -s -X POST http://localhost:8001/api/users/keys \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "User Test Key", "integration_name": "vscode", "tier": "free"}' | \
  jq -r '.key')

# Test user key
curl -X POST http://localhost:8001/api/gateway \
  -H "x-api-key: $USER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "generate_data", "arguments": {"rows": 3}}'
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Dashboard Authentication
DASHBOARD_JWT_SECRET=your-secure-dashboard-secret-here

# Google OAuth (Optional)
GOOGLE_DASHBOARD_CLIENT_ID=your-google-client-id
GOOGLE_DASHBOARD_SECRET=your-google-client-secret

# API Key Management
API_KEY_CACHE_TTL=300

# Rate Limiting & Tier Config
REDIS_URL=redis://localhost:6379/0

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/devforge
```

### Database Schema

#### Users Table
```sql
users (
  id UUID PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT,
  name TEXT,
  is_admin BOOLEAN DEFAULT false,
  is_active BOOLEAN DEFAULT true,
  auth_provider TEXT DEFAULT 'local',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
)
```

#### API Keys Table
```sql
api_keys (
  id UUID PRIMARY KEY,
  key_hash TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  integration_name TEXT NOT NULL,
  tier TEXT DEFAULT 'free',
  tenant_id TEXT NOT NULL,
  user_id UUID REFERENCES users(id),
  hourly_limit_override INTEGER,
  monthly_limit_override INTEGER,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_by UUID REFERENCES users(id),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
)
```

#### Tier Config Table
```sql
tier_config (
  tier TEXT PRIMARY KEY,
  hourly_limit INTEGER NOT NULL,
  monthly_limit INTEGER,
  cost_per_1k_tokens DECIMAL(10,6) NOT NULL,
  max_expiry_days INTEGER DEFAULT 180,
  is_active BOOLEAN DEFAULT true,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_by UUID REFERENCES users(id)
)
```

---

## 🛡️ Security Features

### ✅ Implemented Security Measures

1. **Multi-layer Authentication**
   - JWT tokens for dashboard users
   - API keys for tool access
   - Tenant-based tokens for RAG

2. **Rate Limiting & Abuse Prevention**
   - Tier-based rate limits
   - Per-key override capabilities
   - Real-time limit enforcement

3. **Data Isolation**
   - User-scoped API keys
   - Tenant-based RAG data isolation
   - Admin privilege separation

4. **Token Security**
   - 24-hour session limits
   - Automatic token refresh
   - Secure JWT secrets

5. **Audit Trail**
   - Override change tracking
   - User activity logging
   - Admin action attribution

### ⚠️ Security Considerations

1. **API Key Management**
   - Keys shown only once during creation
   - Secure storage required for key management
   - Regular key rotation recommended

2. **Rate Limit Override**
   - Admin-only access to override settings
   - Validation prevents exceeding enterprise limits
   - Audit trail tracks all changes

3. **JWT Token Security**
   - Use strong secrets (32+ characters)
   - Different secrets per environment
   - Regular secret rotation

---

## 📞 Support & Troubleshooting

### Common Issues

#### Authentication Errors
```bash
# Check admin credentials
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@devforge.ai", "password": "adminpass123"}'

# Check JWT token validity
curl -X GET http://localhost:8001/api/auth/me \
  -H "Authorization: Bearer <token>"
```

#### Rate Limit Issues
```bash
# Check current tier limits
curl -X GET http://localhost:8001/api/admin/pricing \
  -H "Authorization: Bearer <admin_token>"

# Check key overrides
curl -X GET http://localhost:8001/api/admin/keys/<key_id>/overrides \
  -H "Authorization: Bearer <admin_token>"

# Check key usage
curl -X GET http://localhost:8001/api/admin/keys/<key_id>/usage \
  -H "Authorization: Bearer <admin_token>"
```

#### API Key Issues
```bash
# List all keys
curl -X GET http://localhost:8001/api/admin/keys \
  -H "Authorization: Bearer <admin_token>"

# Test key validity
curl -X POST http://localhost:8001/api/gateway \
  -H "x-api-key: <api_key>" \
  -H "Content-Type: application/json" \
  -d '{"name": "generate_data", "arguments": {"rows": 1}}'
```

### Debug Commands

```bash
# Check application health
curl http://localhost:8001/health

# Check environment variables
docker exec devforge-api env | grep -E "(JWT_SECRET|GOOGLE_CLIENT_ID|REDIS_URL)"

# Check database connections
docker exec devforge-postgres psql -U devforge -c "SELECT COUNT(*) FROM users;"

# Check Redis connectivity
docker exec devforge-redis redis-cli ping
```

---

*Last updated: 2026-03-06*

---

## 🔐 Authentication Implementation

### 1. Core Authentication (`src/core/auth.py`)

#### Functions

##### `verify_google_token(token: str, mongodb_id: str) -> str`
```python
def verify_google_token(token: str, mongodb_id: str) -> str:
    """
    Verifies Google ID token.
    Checks if the audience of the token matches the GOOGLE_CLIENT_ID.
    Returns the OIDC subject (sub) on success.
    Raises HTTPException with status 401 on failure.
    """
```

**Key Points:**
- ✅ **No MongoDB verification** - `mongodb_id` parameter is ignored
- ✅ **Only validates Google token** against `GOOGLE_CLIENT_ID`
- ✅ **Returns Google's `sub` claim** (unique user identifier)
- ✅ **Stateless operation** - no database calls

##### `create_jwt(mongodb_id: str) -> str`
```python
def create_jwt(mongodb_id: str) -> str:
    """
    Issues a JWT.
    Payload contains tenant_id, expiration time, and original_issued_at.
    """
```

**Key Points:**
- ✅ **Uses `mongodb_id` as `tenant_id`** directly
- ✅ **1-hour expiration** (`ACCESS_TOKEN_EXPIRE_MINUTES = 60`)
- ✅ **HS256 algorithm** with `JWT_SECRET`
- ✅ **No database validation**
- ✅ **Adds `original_issued_at`** timestamp for session tracking

**JWT Payload Structure:**
```json
{
  "tenant_id": "6989d05d6aef175968c3cae5",
  "exp": 1772452532,
  "original_issued_at": "2026-03-02T10:55:32.319271+00:00"
}
```

##### `verify_jwt(token: str) -> Optional[dict]`
```python
def verify_jwt(token: str) -> Optional[dict]:
    """
    Verifies a JWT.
    Returns the payload on success, otherwise raises HTTPException.
    """
```

**Key Points:**
- ✅ **Validates JWT signature** using `JWT_SECRET`
- ✅ **Checks expiration** automatically
- ✅ **Returns payload** with `tenant_id`, `exp`, and `original_issued_at`

##### `refresh_jwt_token(refresh_token: str) -> str`
```python
def refresh_jwt_token(refresh_token: str) -> str:
    """
    Refreshes a JWT token.
    Checks if original_issued_at > 24hrs.
    If yes, returns 401 with message "Session expired, please re-authenticate with Google".
    """
```

**Key Points:**
- ✅ **Validates existing JWT** signature and expiration
- ✅ **Extracts `tenant_id` and `original_issued_at`** from payload
- ✅ **Checks session age** against 24-hour limit
- ✅ **Issues new JWT** with same `original_issued_at` if within 24hrs
- ✅ **Returns 401** with session expired message if >24hrs
- ✅ **Maintains session continuity** by preserving original issue time

**Session Management Logic:**
```python
# Check if session is older than 24 hours
session_age = now - original_issued_at
if session_age > timedelta(hours=24):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expired, please re-authenticate with Google"
    )
```

### 2. Authentication Endpoint (`src/api/routers/auth.py`)

#### Route: `POST /api/auth/google`

```python
@router.post("/auth/google", response_model=Token)
async def login_with_google(request: GoogleLoginRequest):
    """
    Authenticates with Google and returns a JWT.
    """
```

**Request Body:**
```json
{
  "google_token": "google_oauth_id_token",
  "mongodb_id": "tenant_identifier"
}
```

**Response:**
```json
{
  "access_token": "jwt_token_here",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Key Points:**
- ✅ **Route is `/api/auth/google`** (NOT `/api/v1/auth/google`)
- ✅ **Validates Google token** first
- ✅ **Issues JWT with `mongodb_id` as `tenant_id`**
- ✅ **No database verification** of `mongodb_id`
- ✅ **Includes `original_issued_at`** for session tracking

#### Route: `POST /api/auth/refresh`

```python
@router.post("/auth/refresh", response_model=Token)
async def refresh_token(refresh_request: RefreshTokenRequest):
    """
    Refresh JWT token using existing valid token.
    Checks if original_issued_at > 24hrs.
    If yes, returns 401 with message "Session expired, please re-authenticate with Google".
    """
```

**Request Body:**
```json
{
  "refresh_token": "current_jwt_token"
}
```

**Response (Success):**
```json
{
  "access_token": "new_jwt_token_here",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Response (Session Expired):**
```json
{
  "detail": "Session expired, please re-authenticate with Google"
}
```

**Key Points:**
- ✅ **Route is `/api/auth/refresh`** 
- ✅ **Validates existing JWT** signature and expiration
- ✅ **Checks session age** using `original_issued_at`
- ✅ **Issues new JWT** with same `original_issued_at` if within 24hrs
- ✅ **Forces Google re-authentication** after 24-hour session limit
- ✅ **Maintains tenant continuity** during refresh

**Session Flow:**
```
Google Auth → JWT (original_issued_at = now) → Refresh (within 24hrs) → New JWT (same original_issued_at)
                                                    ↓
                                              After 24hrs → 401 "Session expired, re-authenticate with Google"
```

---

## 🛡️ Middleware Implementation

### JWT Authentication Middleware (`src/core/middleware.py`)

#### `JWTAuthMiddleware`

```python
class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to protect routes with JWT authentication.
    """
```

**Behavior:**
- ✅ **Only protects `/api/v1/rag/*` routes**
- ✅ **Extracts Bearer token** from `Authorization` header
- ✅ **Validates JWT** using `verify_jwt()`
- ✅ **Injects `request.state.tenant_id`**
- ✅ **Returns 401** for missing/invalid tokens

#### Middleware Registration Order (`src/main.py`)

```python
# 1. CORS Middleware (FIRST)
app.add_middleware(CORSMiddleware, ...)

# 2. JWT Auth Middleware (SECOND)  
app.add_middleware(JWTAuthMiddleware)

# 3. Router Registration (LAST)
app.include_router(auth_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
```

**✅ Order is CRITICAL:**
1. **CORS** processes headers first
2. **JWT Auth** validates tokens second
3. **Routes** handle requests last

---

## 🔒 Protected Endpoints

### RAG Endpoints (`src/api/routers/rag.py`)

All RAG endpoints are protected with JWT authentication:

| Endpoint | Method | Protection | Description |
|----------|--------|-------------|-------------|
| `/api/v1/rag/file/upload` | POST | ✅ JWT Required | Upload files for RAG ingestion |
| `/api/v1/rag/file/{file_id}` | GET | ✅ JWT Required | Get file processing status |
| `/api/v1/rag/files` | GET | ✅ JWT Required | List all tenant files |
| `/api/v1/rag/chunk/semanticSearchForChat` | POST | ✅ JWT Required | Semantic search |
| `/api/v1/rag/file/{file_id}` | DELETE | ✅ JWT Required | Delete file |

### Swagger Documentation

All endpoints include:
- 🔒 **HTTPBearer security scheme**
- 📝 **Authentication requirement descriptions**
- 🛡️ **`dependencies=[Depends(security_scheme)]`**

Access at: `http://localhost:8001/docs`

---

## 🧪 Testing Guide

### Prerequisites

1. **Google OAuth Client ID** configured in `.env`
2. **DevForge backend running** on `http://localhost:8001`
3. **Google OAuth token** (see methods below)

### Step 1: Get Google OAuth Token

#### Method A: Google OAuth 2.0 Playground (Recommended)
1. Go to: https://developers.google.com/oauthplayground
2. Click **Settings (⚙️)** → Check **Use your own OAuth credentials**
3. Enter your **Client ID** and **Client Secret**
4. **Step 1**: Select **Google OAuth2 API v2** → **https://www.googleapis.com/auth/userinfo.email**
5. Click **Authorize APIs** → Sign in with Google
6. **Step 2**: Click **Exchange authorization code for tokens**
7. **Copy the Access Token**

#### Method B: gcloud CLI
```bash
# Install gcloud CLI first
gcloud auth login
gcloud auth print-identity-token
```

#### Method C: Manual OAuth Flow
```bash
# Replace YOUR_CLIENT_ID
https://accounts.google.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:8000&scope=https://www.googleapis.com/auth/userinfo.email&response_type=code
```

### Step 2: Get JWT Token

```bash
curl -X POST http://localhost:8001/api/auth/google \
  -H "Content-Type: application/json" \
  -d '{
    "google_token": "YOUR_GOOGLE_TOKEN_HERE",
    "mongodb_id": "test-tenant-123"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI2OTg5ZDA1ZDZhZWYxNzU5NjhjM2NhZTUiLCJleHAiOjE3NzI0NTI1MzIsIm9yaWdpbmFsX2lzc3VlZF9hdCI6IjIwMjYtMDMtMDJUMTA6NTU6MzIuMzE5MjcxKzAwOjAwIn0.qEEzQYakaB7Ni42OgYL5N7ZFJJxNJ7xcXsYAbMbRYyo",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Note:** The JWT now includes `original_issued_at` for session tracking.

### Step 3: Refresh JWT Token

```bash
curl -X POST http://localhost:8001/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "YOUR_JWT_TOKEN_HERE"
  }'
```

**Response (Success):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Response (Session Expired):**
```json
{
  "detail": "Session expired, please re-authenticate with Google"
}
```

**Important:** 
- Refresh works within 24 hours of original authentication
- After 24 hours, you must re-authenticate with Google
- The new JWT preserves the original `original_issued_at` timestamp

### Step 4: Test Protected Endpoints

#### Test File Listing
```bash
curl -X GET http://localhost:8001/api/v1/rag/files \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE"
```

#### Test File Upload
```bash
# Create test file
echo "This is a test document for RAG." > test.txt

# Upload with JWT
curl -X POST http://localhost:8001/api/v1/rag/file/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \
  -F "files=@test.txt" \
  -F "collection=default"
```

#### Test Semantic Search
```bash
curl -X POST http://localhost:8001/api/v1/rag/chunk/semanticSearchForChat \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "userQuery": "test document",
    "top_k": 5,
    "messageId": "msg-123"
  }'
```

### Step 5: Test Authentication Failures

#### Test Without Token (Should Return 401)
```bash
curl -X GET http://localhost:8001/api/v1/rag/files
# Response: {"detail": "Authorization header missing"}
```

#### Test With Invalid Token (Should Return 401)
```bash
curl -X GET http://localhost:8001/api/v1/rag/files \
  -H "Authorization: Bearer invalid-token"
# Response: {"detail": "Could not validate credentials"}
```

#### Test Session Expired (Should Return 401)
```bash
# After 24 hours, refresh will fail
curl -X POST http://localhost:8001/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "EXPIRED_SESSION_JWT"}'
# Response: {"detail": "Session expired, please re-authenticate with Google"}
```

#### Test Wrong Tenant (Should Return 403)
```bash
# Upload file with tenant A
curl -X POST http://localhost:8001/api/v1/rag/file/upload \
  -H "Authorization: Bearer TENANT_A_JWT" \
  -F "files=@test.txt" \
  -F "collection=default"

# Try to access with tenant B JWT
curl -X GET http://localhost:8001/api/v1/rag/files \
  -H "Authorization: Bearer TENANT_B_JWT"
# Response: Should only show tenant B's files, not tenant A's
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Required for Google OAuth
GOOGLE_CLIENT_ID=your-google-oauth-client-id

# Required for JWT signing  
JWT_SECRET=your-jwt-secret-key-min-32-chars

# Optional: JWT expiration (default: 60 minutes)
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### Docker Configuration

The application uses `.env.docker` in Docker:

```yaml
# docker-compose.yml
env_file:
  - .env.docker
```

---

## 🏗️ Integration Examples

### Frontend JavaScript Integration

```javascript
class DevForgeAuth {
  constructor(baseUrl = 'http://localhost:8001') {
    this.baseUrl = baseUrl;
    this.token = null;
    this.tokenExpiry = null;
    this.originalIssuedAt = null;
  }

  // Authenticate with Google
  async authenticate(googleToken, tenantId) {
    const response = await fetch(`${this.baseUrl}/api/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        google_token: googleToken,
        mongodb_id: tenantId
      })
    });
    
    const data = await response.json();
    this.setToken(data.access_token, data.expires_in);
    return data;
  }

  // Set token with expiry tracking
  setToken(token, expiresIn = 3600) {
    this.token = token;
    this.tokenExpiry = Date.now() + (expiresIn * 1000);
    
    // Extract original_issued_at from JWT payload
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      this.originalIssuedAt = new Date(payload.original_issued_at);
    } catch (e) {
      console.warn('Could not extract original_issued_at from token');
    }
  }

  // Refresh token
  async refreshToken() {
    if (!this.token) {
      throw new Error('No token to refresh');
    }

    try {
      const response = await fetch(`${this.baseUrl}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          refresh_token: this.token
        })
      });
      
      if (!response.ok) {
        const error = await response.json();
        if (error.detail === 'Session expired, please re-authenticate with Google') {
          throw new Error('SESSION_EXPIRED');
        }
        throw new Error(error.detail || 'Refresh failed');
      }
      
      const data = await response.json();
      this.setToken(data.access_token, data.expires_in);
      return data;
    } catch (error) {
      if (error.message === 'SESSION_EXPIRED') {
        // Clear token and force re-authentication
        this.clearToken();
        throw new Error('Session expired, please re-authenticate with Google');
      }
      throw error;
    }
  }

  // Make authenticated request with auto-refresh
  async request(endpoint, options = {}) {
    // Check if token is expiring soon (within 5 minutes)
    if (this.tokenExpiry && Date.now() >= (this.tokenExpiry - 5 * 60 * 1000)) {
      try {
        await this.refreshToken();
      } catch (error) {
        if (error.message.includes('Session expired')) {
          throw error;
        }
        console.warn('Token refresh failed, using existing token');
      }
    }
    
    if (!this.token) {
      throw new Error('No valid token, please authenticate');
    }

    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${this.token}`
    };
    
    try {
      return fetch(url, { ...options, headers });
    } catch (error) {
      // If 401, try refresh once
      if (error.status === 401) {
        try {
          await this.refreshToken();
          headers['Authorization'] = `Bearer ${this.token}`;
          return fetch(url, { ...options, headers });
        } catch (refreshError) {
          if (refreshError.message.includes('Session expired')) {
            throw refreshError;
          }
          throw error;
        }
      }
      throw error;
    }
  }

  clearToken() {
    this.token = null;
    this.tokenExpiry = null;
    this.originalIssuedAt = null;
  }

  // Check if session is expired (24-hour check)
  isSessionExpired() {
    if (!this.originalIssuedAt) return false;
    const sessionAge = Date.now() - this.originalIssuedAt.getTime();
    return sessionAge > (24 * 60 * 60 * 1000); // 24 hours
  }
}

// Usage example
const auth = new DevForgeAuth();

// Initial authentication
try {
  await auth.authenticate('google_oauth_token', 'tenant-123');
  console.log('Authenticated successfully');
} catch (error) {
  console.error('Authentication failed:', error);
}

// Use authenticated endpoints with auto-refresh
try {
  const files = await auth.request('/api/v1/rag/files');
  console.log('Files:', await files.json());
} catch (error) {
  if (error.message.includes('Session expired')) {
    console.log('Session expired, please re-authenticate with Google');
    // Redirect to Google OAuth flow
  }
}
```

### Python Client Integration

```python
import requests
from datetime import datetime, timezone, timedelta
import jwt

class DevForgeClient:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.token = None
        self.token_expiry = None
        self.original_issued_at = None
    
    def authenticate(self, google_token, tenant_id):
        """Authenticate with Google OAuth and get JWT"""
        response = requests.post(
            f"{self.base_url}/api/auth/google",
            json={
                "google_token": google_token,
                "mongodb_id": tenant_id
            }
        )
        data = response.json()
        self.set_token(data["access_token"], data["expires_in"])
        return data
    
    def set_token(self, token, expires_in=3600):
        """Set token with expiry tracking"""
        self.token = token
        self.token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        # Extract original_issued_at from JWT payload
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            self.original_issued_at = datetime.fromisoformat(
                payload["original_issued_at"].replace('Z', '+00:00')
            )
        except (jwt.PyJWTError, KeyError, ValueError):
            print("Warning: Could not extract original_issued_at from token")
    
    def refresh_token(self):
        """Refresh JWT token"""
        if not self.token:
            raise Exception("No token to refresh")
        
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/refresh",
                json={"refresh_token": self.token}
            )
            
            if response.status_code == 401:
                error = response.json()
                if "Session expired" in error.get("detail", ""):
                    self.clear_token()
                    raise Exception("Session expired, please re-authenticate with Google")
                raise Exception(error.get("detail", "Refresh failed"))
            
            response.raise_for_status()
            data = response.json()
            self.set_token(data["access_token"], data["expires_in"])
            return data
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Token refresh failed: {e}")
    
    def _get_headers(self):
        """Get headers with JWT token"""
        if not self.token:
            raise Exception("No valid token, please authenticate")
        return {"Authorization": f"Bearer {self.token}"}
    
    def request(self, endpoint, **kwargs):
        """Make authenticated request with auto-refresh"""
        # Check if token is expiring soon (within 5 minutes)
        if self.token_expiry and datetime.now(timezone.utc) >= (self.token_expiry - timedelta(minutes=5)):
            try:
                self.refresh_token()
            except Exception as e:
                if "Session expired" in str(e):
                    raise e
                print(f"Token refresh failed: {e}, using existing token")
        
        headers = kwargs.pop("headers", {})
        headers.update(self._get_headers())
        
        try:
            return requests.get(f"{self.base_url}{endpoint}", headers=headers, **kwargs)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                try:
                    self.refresh_token()
                    headers.update(self._get_headers())
                    return requests.get(f"{self.base_url}{endpoint}", headers=headers, **kwargs)
                except Exception as refresh_error:
                    if "Session expired" in str(refresh_error):
                        raise refresh_error
                    raise e
            raise e
    
    def get_files(self):
        """Get all files for tenant"""
        return self.request("/api/v1/rag/files")
    
    def upload_file(self, file_path, collection="default"):
        """Upload file for RAG processing"""
        with open(file_path, 'rb') as f:
            files = {"files": f}
            data = {"collection": collection}
            headers = self._get_headers()
            response = requests.post(
                f"{self.base_url}/api/v1/rag/file/upload",
                files=files,
                data=data,
                headers=headers
            )
        return response.json()
    
    def is_session_expired(self):
        """Check if session is expired (24-hour check)"""
        if not self.original_issued_at:
            return False
        session_age = datetime.now(timezone.utc) - self.original_issued_at
        return session_age > timedelta(hours=24)
    
    def clear_token(self):
        """Clear all token data"""
        self.token = None
        self.token_expiry = None
        self.original_issued_at = None

# Usage example
client = DevForgeClient()

try:
    # Initial authentication
    client.authenticate("google_oauth_token", "tenant-123")
    print("Authenticated successfully")
    
    # Use authenticated endpoints with auto-refresh
    files = client.get_files()
    print("Files:", files.json())
    
except Exception as e:
    if "Session expired" in str(e):
        print("Session expired, please re-authenticate with Google")
        # Redirect to Google OAuth flow
    else:
        print(f"Error: {e}")
```

---

## 🔒 Security Considerations

### ✅ Security Best Practices Implemented

1. **Stateless Authentication**
   - No database calls for token validation
   - JWT contains all necessary information

2. **Proper Token Expiration**
   - 1-hour JWT expiration
   - Automatic token refresh required
   - 24-hour session limit for security

3. **Tenant Isolation**
   - Each tenant can only access their own data
   - Middleware injects `tenant_id` from JWT

4. **Secure Middleware Order**
   - CORS processed before authentication
   - Authentication before route logic

5. **Session Management**
   - `original_issued_at` tracking for session age
   - Forced re-authentication after 24 hours
   - Session continuity during refresh

6. **No Hardcoded Secrets**
   - All secrets from environment variables
   - JWT secret properly configured

### ⚠️ Security Notes

1. **Google OAuth Token Validation**
   - Only validates token signature and audience
   - Does not verify token against user database
   - Suitable for stateless applications

2. **JWT Secret Security**
   - Use strong, random JWT secrets (32+ characters)
   - Different secrets per environment
   - Regular secret rotation recommended

3. **Session Expiration**
   - 24-hour session limit prevents indefinite access
   - Forces Google re-authentication for security
   - Maintains audit trail with `original_issued_at`

4. **HTTPS in Production**
   - Always use HTTPS in production
   - Prevents token interception

---

## 🚀 Deployment Checklist

### Environment Setup
- [ ] `GOOGLE_CLIENT_ID` configured
- [ ] `JWT_SECRET` set (32+ characters)
- [ ] CORS origins configured properly
- [ ] HTTPS enabled in production

### Testing
- [ ] Google OAuth flow working
- [ ] JWT token generation working
- [ ] RAG endpoints protected
- [ ] Tenant isolation working
- [ ] Token expiration working

### Monitoring
- [ ] Authentication error logging
- [ ] JWT validation failures
- [ ] Google token validation failures
- [ ] Middleware performance monitoring

---

## 🐛 Troubleshooting

### Common Issues

#### 1. "Google Client ID is not configured"
**Solution:** Set `GOOGLE_CLIENT_ID` in environment variables

#### 2. "JWT_SECRET is not configured"  
**Solution:** Set `JWT_SECRET` in environment variables (32+ chars)

#### 3. "Authorization header missing"
**Solution:** Include `Authorization: Bearer <token>` header

#### 4. "Could not validate credentials"
**Solution:** Check JWT token format and expiration

#### 5. "Invalid Google token"
**Solution:** Verify Google OAuth token is valid and not expired

### Debug Commands

```bash
# Check environment variables
docker exec devforge-api env | grep -E "(GOOGLE_CLIENT_ID|JWT_SECRET)"

# Check application logs
docker logs devforge-api

# Test health endpoint
curl http://localhost:8001/health

# Test auth endpoint directly
curl -X POST http://localhost:8001/api/auth/google \
  -H "Content-Type: application/json" \
  -d '{"google_token": "test", "mongodb_id": "test"}'
```

---

## 📚 Additional Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [JWT Documentation](https://jwt.io/)
- [FastAPI Security Documentation](https://fastapi.tiangolo.com/tutorial/security/)
- [Swagger/OpenAPI Documentation](https://swagger.io/docs/)

---

## 📞 Support

For authentication-related issues:
1. Check this documentation first
2. Review application logs
3. Verify environment configuration
4. Test with provided curl commands

---

*Last updated: 2026-03-02*
