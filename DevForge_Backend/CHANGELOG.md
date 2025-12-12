# Changelog

All notable changes to DevForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.8.0] - 2025-12-12

### 🎉 Major Release: GitOps Intelligence & Specialized Tools

This release transforms DevForge into an intelligent GitOps automation platform with Phase 1 & 2 complete.

### ✨ Added - Phase 1: Enhanced `github_operation`

***Foundation Infrastructure (Week 1)**
- **Session Management** (`src/core/session.py`) - Multi-turn conversation context with artifact storage and TTL
- **Feature Flags** (`src/core/features.py`) - Gradual rollout framework with environment variable overrides
- **Async Job Queue** (`src/core/jobs.py`) - Background execution for long-running operations with progress tracking
- **Enhanced Configuration** (`src/core/config.py`) - 18 new GitOps settings for storage, thresholds, and performance tuning
- **Job Status Endpoint** (`/api/jobs/{job_id}`) - Real-time async job monitoring

**Intelligence Components (Week 2)**
- **FuzzyRepo Discovery** (`intelligence/repo_discovery.py`) - Fuzzy matching with Levenshtein similarity and confidence scoring
- **AI Commit Generator** (`intelligence/commit_generator.py`) - Auto-generates Conventional Commits from diffs with confidence scoring
- **Multi-Language Log Parser** (`intelligence/log_parser.py`) - Parses Python/JS/Java/Go stack traces, infers root cause, suggests labels
- **LLM Confidence Policy** (`src/core/confidence.py`) - Automatic safety thresholds with draft PR fallback for medium confidence

**Integration & Testing (Week 3)**
- **Enhanced GitHub Agent** (`src/agents/github/agent.py`) - Integrated all intelligence components with backward compatibility
- **Audit & Timeline System** (`src/core/audit.py`) - Every operation tracked with `audit_id` and event timeline
- **Rollback Feasibility Matrix** (`workflows/rollback.py`) - Defines rollback actions, prechecks, time bounds, and compensating actions
- **70+ Unit Tests** - Comprehensive test coverage for session, features, jobs, rollback, log parser, and confidence policy
- **API Context Support** - `/api/gateway` now accepts optional `context` parameter for enhanced intelligence

### ✨ Added - Phase 2: Specialized Tools

**New Tools**
- **`generate_changelog`** (`src/tools/changelog.py`) - Generate release notes from git history
  - Conventional commits parsing (feat, fix, docs, etc.)
  - Categorized markdown/JSON output
  - Automatic change type classification
  - 10+ unit tests

- **`analyze_ci_failure`** (`src/tools/ci_diagnostics.py`) - AI-powered CI/CD failure analysis
  - Pattern detection (test failures, build errors, dependencies, timeouts)
  - LLM-based fix suggestions
  - Auto-fix policy enforcement (confidence ≥0.95 + safe types only)
  - 12+ unit tests

- **`scaffold_repository`** (`src/tools/scaffold.py`) - Create repos from templates with CI/CD
  - 5 templates: fastapi, react, nextjs, microservice, docs
  - Token scope validation before execution
  - Idempotency checks (fails if repo exists unless `force=true`)
  - Async fallback for large templates (>50 files)
  - Automatic rollback on failure
  - 12+ unit tests

**Production Guardrails**
- **Security Validator** (`src/core/security.py`)
  - Token scope checking (prevents permission errors)
  - Input sanitization (repo names, descriptions, commit messages)
  - Idempotency validation
  - Rate limit monitoring

- **Auto-Fix Policy** - CI diagnostics only auto-applies fixes if:
  1. Confidence ≥ 0.95 (95%+)
  2. Type in `["format", "dependency_patch", "lint"]`

### 📝 Changed

- **Manifest Version** - Bumped from v0.7.0 to v0.8.0
- **Manifest Description** - Updated to reflect intelligent GitHub automation capabilities
- **API Router** - Registered 3 new specialized tools in `SUPPORTED_TOOLS`
- **GitHub Agent** - Now includes:
  - Fuzzy repo matching (handles "backend" → "user/backend-api")
  - Auto-generated commit messages from diffs
  - Log-to-issue parsing for error reports
  - Confidence-based branching (auto-commit vs draft PR vs confirmation)

### 🔧 Configuration

**New Environment Variables:**
```bash
# Storage & Sessions
GITOPS_STORAGE=memory  # memory|redis|postgres
GITOPS_SESSION_TTL=1800

# Feature Toggles
GITOPS_ENABLE_FUZZY_SEARCH=true
GITOPS_ENABLE_COMMIT_GEN=true
GITOPS_ENABLE_LOG_PARSING=true
GITOPS_ENABLE_ASYNC_JOBS=true
GITOPS_ENABLE_CONFIDENCE_GATING=true

# Confidence Thresholds
GITOPS_FUZZY_THRESHOLD=0.85
GITOPS_COMMIT_CONFIDENCE_THRESHOLD=0.90
GITOPS_AUTO_FIX_THRESHOLD=0.95
GITOPS_AUTO_FIX_TYPES=format,dependency_patch,lint

# Performance
GITOPS_REPO_CACHE_TTL=3600
GITOPS_LLM_TIMEOUT=10
GITOPS_JOB_CLEANUP_HOURS=24
MAX_SYNC_WORK_UNITS=50
```

### 📚 Documentation

- **USAGE.md** - Comprehensive guide for Phase 2 tools with cURL examples
- **SECURITY.md** - Token handling, no-raw-logs policy, auto-fix security, deployment checklist
- **CHANGELOG.md** - This file
- **Phase 1 Walkthrough** - Detailed implementation documentation with code examples

### 🧪 Testing

**Test Coverage: 90+ Tests**
- Phase 1: 70+ tests (session, features, jobs, rollback, log parser, confidence, GitHub agent integration)
- Phase 2: 30+ tests (changelog, CI diagnostics, scaffold)
- All tests include edge cases, error handling, and security validation

### ⚡ Performance

**Targets Met:**
- Intent classification: <1s (P95)
- Fuzzy repo search: <200ms (cached, 1hr TTL)
- Commit generation: <2s (P95)
- Log parsing: <500ms (regex + optional LLM)
- Total operation (sync): <10s (P95)
- Job enqueue: <100ms

### 🚀 Breaking Changes

**None** - Full backward compatibility maintained:
- Existing `github_operation` calls work unchanged
- New `context` parameter is optional
- All Phase 2 tools are net-new

### 🐛 Bug Fixes

- Fixed potential race conditions in session cleanup
- Fixed job queue cleanup to prevent memory leaks
- Fixed confidence policy handling of edge case scores

### 🔒 Security

- Implemented token scope validation
- Added input sanitization for all user inputs
- Enforced auto-fix policy for CI diagnostics
- No sensitive data in logs (tokens, keys redacted)
- Opt-in only for prompt storage

---

## [0.7.0] - 2025-11-XX

### Added
- Basic `github_operation` tool
- `generate_data` tool for mock data
- `retrieve_docs` RAG tool
- `refine_prompt` tool
- `generate_cheatsheet` tool

---

**Legend:**
- ✨ Added - New features
- 📝 Changed - Changes to existing functionality
- 🐛 Bug Fixes - Bug fixes
- 🔒 Security - Security improvements
- ⚡ Performance - Performance improvements
- 📚 Documentation - Documentation updates
- 🧪 Testing - Test coverage
- 🚀 Breaking Changes - Breaking changes
