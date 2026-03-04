# Dashboard Authentication & User Management (Phase 3)

## 📋 Overview
Phase 3 introduced a robust, user-centric authentication system for the DevForge Dashboard. Unlike the RAG session auth (which is tenant-based and stateless), the Dashboard auth is **user-based** and backed by a PostgreSQL `users` table.

---

## 🏗️ Architecture

### Secure Isolation
Dashboard JWTs are strictly isolated from RAG session JWTs:
- **Separate Secret**: Uses `DASHBOARD_JWT_SECRET`.
- **Audience Protection**: JWTs include `"aud": "dashboard"` to prevent cross-service token replay.
- **Expiry**: Default session duration is 24 hours.

### Components
1. **Users Table**: Stores identity, `password_hash` (Bcrypt), and `is_admin` flags.
2. **DashboardAuthMiddleware**: Gates `/api/users/*` and `/api/admin/*`.
3. **Users Router**: Handles `/api/auth/*` and `/api/users/*` endpoints.

---

## 🔐 Authentication Flows

### 1. Local Registration & Login
Users can register with an email and password. Passwords are salted and hashed using **Bcrypt**.

- **Endpoint**: `POST /api/auth/register`
- **Endpoint**: `POST /api/auth/login`

### 2. Google OAuth (Dashboard)
Isolated from the RAG Google login to allow for different OAuth Client IDs if needed.
- **Endpoint**: `POST /api/auth/google/dashboard`
- **Behavior**: Auto-registers users on first login and syncs profile data (name, avatar).

### 3. User Identity (`/api/auth/me`)
Requires a valid Dashboard JWT. Returns the full user profile including admin status.

---

## 🔑 User-Scoped API Keys
Users can now manage their own API keys via the dashboard. These keys are linked to the `user_id` for ownership tracking and auditing.

- **List Keys**: `GET /api/users/keys`
- **Create Key**: `POST /api/users/keys` (Returns raw key once)
- **Revoke Key**: `DELETE /api/users/keys/{id}`

---

## 🛡️ Admin Management
The admin dashboard is protected by the same `DashboardAuthMiddleware` but requires the `is_admin` claim to be `True`.

### Migration from Secrets to JWT
We have migrated from the legacy `X-Admin-Secret` header to a more secure JWT-based system:
- **Legacy**: Required sharing a server secret with clients.
- **Modern**: Relies on cryptographically signed JWT claims issued by the server.

### Admin Features
- **User List**: `GET /api/admin/users` - View all registered users.
- **User Control**: `PATCH /api/admin/users/{id}` - Promote to admin or deactivate accounts.
- **Advanced Usage**: `GET /api/admin/usage` - Usage stats now support filtering by `user_id`.

---

## 🛠️ CLI Bootstrap
To create the first administrator when no UI or admin users exist:

```bash
docker exec devforge-api env PYTHONPATH=/app python3 scripts/create_admin.py \
  --email admin@devforge.ai \
  --password your-secure-password \
  --name "Super Admin"
```

---

## ⚙️ Configuration
Add these to your `.env` or `.env.docker`:

```bash
DASHBOARD_JWT_SECRET=your-secure-secret-here
# Optional for Google Auth
GOOGLE_DASHBOARD_CLIENT_ID=...
GOOGLE_DASHBOARD_SECRET=...
```
