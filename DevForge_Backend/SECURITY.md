# Security Policy - DevForge GitOps Tools

## Token Handling & Storage

### GitHub Personal Access Tokens (PATs)

**Storage:**
- Tokens stored in environment variable `GITHUB_TOKEN`
- **NOT** stored in logs, databases, or committed to version control
- Recommend using secret management service (AWS Secrets Manager, HashiCorp Vault) for production

**Required Scopes by Tool:**

| Tool | Minimum Scopes | Reason |
|------|----------------|--------|
| `github_operation` | `repo` | Read/write repository access |
| `generate_changelog` | `repo` (read-only) | Read git history |
| `analyze_ci_failure` | `repo`, `actions:read` | Read workflow runs |
| `scaffold_repository` | `repo`, `admin:org`, `delete_repo` | Create repos, setup CI, rollback on failure |

**Best Practices:**
1. Use **fine-grained** Personal Access Tokens (not classic)
2. Set **expiration** (recommend 90 days)
3. Grant **minimum required scopes** per tool
4. **Rotate** tokens regularly
5. Use **different tokens** for different environments (dev/staging/prod)

---

## No Raw Logs Policy

**Log Sanitization:**
- GitHub tokens **automatically redacted** from logs
- Sensitive data (passwords, API keys) **never logged**
- User prompts logged **only** with opt-in (`GITOPS_LOG_PROMPTS=true`)

**Audit Logging:**
- All operations produce `audit_id` for traceability
- Timeline includes: operation start/end, steps, duration
- **NO sensitive data** (tokens, keys, passwords) in audit logs
- Audit logs retained in memory (configurable TTL: `GITOPS_SESSION_TTL=1800` seconds)

**Environment Variables:**
```bash
GITOPS_LOG_PROMPTS=false  # Default: prompts NOT logged
GITOPS_SESSION_TTL=1800   # Audit/session retention (30 minutes)
```

---

## Prompt Storage - Opt-In Only

**Default Behavior:**
- User prompts **NOT stored** by default
- LLM responses **NOT stored** by default
- Only operation metadata (operation type, success/failure, duration) logged

**Opt-In for Development/Debugging:**
```bash
# Enable prompt logging (development only!)
GITOPS_LOG_PROMPTS=true
GITOPS_STORE_LLM_RESPONSES=true
```

**⚠️ Warning:** Only enable prompt storage in development. Prompts may contain:
- Repository names
- File paths
- Code snippets
- Internal project details

---

## Input Validation & Sanitization

All user inputs are validated before processing:

### Repository Names
- **Regex:** `^[a-z0-9._-]+$`
- **Max Length:** 100 characters
- **Auto-lowercase:** `My-Repo` → `my-repo`
- **Rejects:** Spaces, control characters, special symbols

### Descriptions
- **Max Length:** 200 characters
- **HTML Stripped:** `<script>alert('xss')</script>` → (removed)
- **Whitespace Normalized:** Multiple spaces → single space

### Commit Messages
- **Max Length:** 500 characters
- **Control Characters Removed:** Preserves `\n`, `\r`, `\t` only
- **Validation:** Non-empty, printable characters

---

## Auto-Fix Security Policy

### CI Diagnostics Auto-Fix Rules

Auto-fixes **automatically applied** only when:
1. **Confidence ≥ 0.95** (95% or higher)
2. **Type** in allowed list: `["format", "dependency_patch", "lint"]`

All other fixes:
- Require manual review
- **OR** create draft PR with suggested changes

**Prohibited Auto-Fix Types:**
- `code_change` - Logic/functionality changes
- `config` - Configuration changes (may affect behavior)
- `security` - Security-related changes (require review)

**Configuration:**
```bash
GITOPS_AUTO_FIX_THRESHOLD=0.95  # Minimum confidence
GITOPS_AUTO_FIX_TYPES=format,dependency_patch,lint  # Comma-separated
```

---

## Idempotency & Safe Defaults

### Scaffold Repository
- **Default:** Fails if repository already exists
- **Opt-in force:** Must explicitly set `force=true` to override
- **Rollback:** Auto-deletes repo if CI setup fails (prevents partial state)

### Changelog Generation
- **Read-only:** Never modifies repository
- **No side effects:** Safe to run multiple times

### CI Analysis
- **Read-only:** Analyzes workflow logs
- **No auto-execution:** Suggestions only, no automatic fixes (unless policy allows)

---

## Rate Limiting & Abuse Prevention

**GitHub API Rate Limits:**
- Authenticated: 5,000 requests/hour
- Tool checks remaining quota before operations
- **429 errors** handled gracefully (returns error, no retry storm)

**Internal Rate Limiting:**
```bash
GITOPS_MAX_CONCURRENT_JOBS=5  # Max parallel async jobs
GITOPS_JOB_CLEANUP_HOURS=24   # Auto-cleanup old jobs
```

**Monitoring Alerts (Recommended):**
- Job failure rate > 5% in 1 hour
- Rate limit usage > 80%
- Frequent rollbacks > 3/day per user

---

## RBAC & Access Control

### Current State (v0.8.0)
- **Single token** for all operations (environment variable)
- **No user-level permissions**

### Planned (Future)
- Per-user GitHub PAT selection
- Role-based access control (RBAC)
- Audit logs with user attribution
- Separate tokens for read-only vs admin operations

---

## Vulnerability Reporting

**Report security vulnerabilities to:** [your-security-email@example.com]

**Do NOT:**
- Open public GitHub issues for security vulnerabilities
- Share exploit details publicly

**Response SLA:**
- Acknowledgment: 48 hours
- Initial assessment: 7 days
- Fix timeline: Based on severity

---

## Security Checklist for Deployment

- [ ] GitHub PAT stored in **environment variable** (not code)
- [ ] Token has **minimum required scopes** only
- [ ] Token **expiration** set (90 days recommended)
- [ ] Prompt logging **disabled** in production (`GITOPS_LOG_PROMPTS=false`)
- [ ] Audit retention **configured** (`GITOPS_SESSION_TTL`)
- [ ] Auto-fix threshold **reviewed** (default: 0.95)
- [ ] Rate limiting **monitored**
- [ ] Secret management service **considered** (AWS Secrets Manager, Vault)
- [ ] HTTPS **enforced** for API endpoints
- [ ] Input validation **enabled** (default)

---

**Last Updated:** December 12, 2025  
**Version:** DevForge v0.8.0  
**Next Review:** March 12, 2026
