# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository (DevForge_Backend folder).

## Skills

- `devforge-workflow` — use for all code changes in this project
- `enterprise-audit-planner` — use when given any audit `.md` file
- `system-auditor` — use to create an audit `.md` file

## Quick start

### Local development

```bash
# Create venv (Python 3.12 — matches Dockerfile)
python -m venv venv && source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate                            # Windows

pip install -r requirements.txt
uvicorn src.main:app --reload --port 8001
pytest tests/ -v
```

> **PyTorch note:** `requirements.txt` pins `torch==2.9.1+cpu`. If pip resolves the GPU wheel by default on Linux, install with `--extra-index-url https://download.pytorch.org/whl/cpu` (this is what the Dockerfile does). Avoids a 1–2 GB CUDA download.

### Docker deployment

Multi-stage Dockerfile based on `python:3.12-slim`. Runs as non-root user `devforge` (uid 1000). Production CMD uses **Gunicorn** with **6 Uvicorn workers** on port 8001 (`docker-compose` overrides this for hot-reload).

Compose profiles for modular service management:

| Service | Purpose | Profile |
|---------|---------|---------|
| `api` | FastAPI backend (port 8001) | always |
| `redis` | Celery broker, query cache, result backend | `rag` |
| `postgres` | PostgreSQL with pgvector | `rag` |
| `celery-worker` | Primary async worker | `rag` |
| `celery-worker-analytics` | Dedicated analytics worker | `rag` |
| `celery-worker-secondary` | Load-balancing worker | `rag`, `scale` |
| `flower` | Celery monitoring UI (port 5555) | `rag` |

```bash
cp .env.docker .env

# API only (no RAG dependencies)
docker compose up api -d --build

# Full stack with RAG (Redis, Postgres, Celery, Flower)
docker compose --profile rag up -d --build

# Production-grade scale-out (adds celery-worker-secondary)
docker compose --profile rag --profile scale up -d --build

docker compose --profile rag down
```

The `api` service mounts the project directory and `./data` for uploads / Chroma persistence. See `docs/DOCKER_GUIDE.md` for troubleshooting.

## Architecture

FastAPI backend with a modular agent/tool/storage split. The supervisor agent (LangGraph state machine) classifies intent and routes to a per-feature agent.

### Layers

| Layer | Purpose | Key files |
|-------|---------|-----------|
| API | HTTP endpoints (REST gateway, MCP Streamable HTTP, RAG, auth, admin) | `src/api/routers/__init__.py`, `src/api/routers/{rag,auth,users,admin}.py`, `src/api/mcp/{server,dispatch,schemas,descriptions,headers_middleware}.py` |
| Agents | Business logic & orchestration | `src/agents/*/agent.py`, `src/agents/supervisor.py` |
| Tools | Reusable functions invoked by agents | `src/tools/*/tools.py` |
| Storage | Vector store abstraction | `src/storage/base_store.py`, `chroma_store.py`, `pgvector_store.py` |
| Workers | Async Celery tasks | `src/workers/celery_app.py` |
| Core | Config, middleware, auth | `src/core/config.py`, `src/core/{middleware,api_key_middleware,dashboard_middleware}.py` |

### Request flow (tool execution)

Two callers, one shared dispatch table (`SUPPORTED_TOOLS` in `src/api/routers/__init__.py`):

- **REST gateway:** `POST /api/gateway` → `APIKeyAuthMiddleware` validates `x-api-key` → `gateway_endpoint` in `src/api/routers/__init__.py` → resolves `tool_name` against `SUPPORTED_TOOLS` → agent invoke.
- **MCP Streamable HTTP:** `POST /mcp/` (**trailing slash required** — `/mcp` is a FastMCP ASGI sub-app mounted at `/mcp`) → `APIKeyAuthMiddleware` → FastMCP routes `tools/call` to the registered `@mcp.tool` function in `src/api/mcp/server.py` → cross-cutting wrapper `_dispatch` (or `_dispatch_github`) in `src/api/mcp/dispatch.py` → same `SUPPORTED_TOOLS` agent invoke.

Both paths converge on the same per-feature agent (datagen / github / prompt_refiner / cheatsheet / testgen / rag). `src/agents/supervisor.py` (LangGraph) is used by the natural-language `github_operation` query route; the simple tools dispatch directly.

### MCP SDK migration (2026-05-27)

The hand-rolled `/mcp` JSON-RPC handler was replaced with the official **MCP Python SDK** (`fastmcp`) using the Streamable HTTP transport. The sub-app is created in `src/api/mcp/server.py` with `stateless_http=True, json_response=True` and mounted at `/mcp` in `src/main.py`. Key per-file responsibilities under `src/api/mcp/`:

| File | Role |
|------|------|
| `server.py` | FastMCP instance + `@mcp.tool` registrations (flat parameters so the SDK auto-generates the JSON schema). |
| `dispatch.py` | Cross-cutting wrapper run on every tool call: rate-limit pre-check (atomic Lua acquire), agent dispatch, analytics log, release-on-failure, response-state stashing. |
| `schemas.py` | Pydantic input models for the simple tools + the hand-rolled `oneOf` schema for `github_operation`. |
| `descriptions.py` | `TOOL_DESCRIPTIONS` — agent-instructive strings surfaced via `tools/list`. **Source of truth** for tool descriptions; do not duplicate. |
| `headers_middleware.py` | Pure ASGI middleware that injects `X-RateLimit-*` headers on every `/mcp` response (FastMCP doesn't allow direct response-header mutation from inside a tool). |

The legacy `routers/__init__.py:gateway_endpoint` REST path remains for non-MCP clients and uses the same `SUPPORTED_TOOLS` table.

### Agent modules

- `datagen/` — mock data generation (CSV/JSON, uses Faker + rstr). **v0.9 (2026-05-15)** adds catalog-sandbox (per-entity LLM-generated value catalogs cached L1/L2), SchemaValidator (post-LLM enum-swap fix + range inference), and consolidated realism through `realism_engine`. See [docs/tools/generate_data.md](docs/tools/generate_data.md) and [v0.9 spec](../docs/superpowers/specs/2026-05-15-generate-data-production-grade-design.md).
- `supervisor.py` — intent classification & routing (LangGraph)
- `rag/` — document retrieval with hybrid search, reranking, query cache, intent-aware expansion
- `github/` — GitOps automation. **v1.0 (2026-05-19)** expands to 26 structured ops: PR inspection, issue CRUD, commit history, release management, GitHub Actions, webhooks, pagination, enriched error messages (PAT scope guidance for 403/404/422). Fuzzy repo matching, LLM commit generation, risk gate with contextual escalation. Verified: 64/64 live MCP tests. See [docs/tools/github_operation.md](docs/tools/github_operation.md) and [curl tests](docs/tools/github_operation_curl_tests.md).
- `prompt_refiner/` — domain-aware prompt optimization. **v0.10 (2026-05-14)** adds polyglot manifest coverage (8 ecosystems), typed `chosen_stack` lists, deterministic `quality` block, and anti-hallucination guard for vague code prompts. See [docs/tools/refine_prompt.md](docs/tools/refine_prompt.md) and [v0.10 spec](../docs/superpowers/specs/2026-05-14-refine-prompt-robustness-design.md).
- `cheatsheet/` — code cheat sheet generation. **v0.11 (2026-05-15)** rewrites the tool around curated YAML knowledge packs (`data/cheatsheet_packs/`) + a single LLM personalization call. 9 supported languages (python, javascript, typescript, go, rust, java, ruby, php, csharp), tree-sitter-validated syntax in CI, no LLM-invented code, new optional `intent` parameter for activity-driven ranking. **Verified through 16-scenario MCP stress test** including prompt-injection resistance (hallucinated-id drop guard), length-limit Pydantic gate, concurrency, unicode, and explicit-input precedence. **Pack status:** only `languages/python/beginner.yaml` (hand-written seed) ships in this commit — run `scripts/bootstrap_cheatsheet_packs.py --all` to LLM-bootstrap the remaining 68 packs. See [docs/tools/generate_cheatsheet.md](docs/tools/generate_cheatsheet.md) and [v0.11 spec](../docs/superpowers/specs/2026-05-15-generate-cheatsheet-production-grade-design.md).
- `testgen/` — AI unit-test generation. **v1.0 (2026-05-27)** generates a ready-to-run test file from pasted source for **Python (pytest) and JavaScript/TypeScript (Jest default, Vitest opt-in)**. One Ollama `code_gen` call + **static validation**: tree-sitter parse-check plus an import-symbol guard that ensures every name imported from the module-under-test exists in the pasted source. `validated` is reported as `"static"` / `"partial"` / `"unparseable"` so callers know exactly what guarantee they got. Optional `use_repo_context` enriches the prompt with RAG-retrieved dependency snippets (best-effort, no-op when no repo is indexed). No code execution. See [docs/tools/generate_tests.md](docs/tools/generate_tests.md) and [v1.0 spec](docs/superpowers/specs/2026-05-27-generate-tests-design.md).
- `rag/reranking/cross_encoder_reranker.py` — cross-encoder reranking (`ms-marco-MiniLM-L-6-v2`), internal stage of `retrieve_docs`

### Current tool versions

| Tool | Version | Manifest version | Highlights |
|------|---------|------------------|------------|
| `generate_data` | 0.9.0 | 0.11.0 | Catalog-sandbox + realism consolidation |
| `refine_prompt` | 0.10.0 | 0.11.0 | Polyglot + quality block + anti-hallucination |
| `github_operation` | 1.0.0 | 0.12.0 | 26 structured ops: PR inspection, issue CRUD, commit history, releases, Actions, webhooks + enriched error messages |
| `generate_cheatsheet` | 0.11.0 | 0.11.0 | Curated YAML packs + LLM personalization (9 languages) |
| `generate_tests` | 1.0.0 | 1.0.0 | Pytest / Jest / Vitest test generation; static validation (tree-sitter parse + import-symbol guard); optional RAG enrichment |

The MCP `tools/list` description for `generate_data` and `refine_prompt` now teaches calling agents the iterative call pattern + cold/warm cache latency expectations. When adding new tools or updating an existing one, follow the same agent-instructive style — see `src/api/mcp/descriptions.py:TOOL_DESCRIPTIONS` (single source of truth since the MCP SDK migration).

### Middleware order

Starlette wraps middleware so the **last** `app.add_middleware(...)` call in `src/main.py` runs **first** on the request. Effective request-flow order:

1. `DashboardAuthMiddleware` — `Authorization: Bearer <dashboard_jwt>` for `/api/users/*`, `/api/admin/*`
2. `APIKeyAuthMiddleware` — `x-api-key` for `/api/gateway`, `/mcp`
3. `JWTAuthMiddleware` — tenant JWTs for RAG endpoints
4. `CORSMiddleware` — innermost, applied last before the route handler

### Key technologies (pinned in `requirements.txt`)

- **FastAPI 0.120**, **Pydantic 2.12**, **Uvicorn 0.38**, Gunicorn (prod)
- **LangChain 1.0**, **LangGraph 1.0**, `langchain-ollama`, `langchain-qdrant`, `langchain-chroma`
- **Celery 5.3** + **Redis 5.0** (broker / result backend / query cache)
- **ChromaDB 1.3.5** + **pgvector 0.2.5** + **qdrant-client 1.16** (three vector backends)
- **SQLAlchemy 2.0** + **asyncpg 0.30** (async Postgres pool)
- **Tree-sitter 0.21** + `tree-sitter-languages 1.10.2` (AST chunking)
- **sentence-transformers 2.6**, **transformers 4.38**, **torch 2.9 (CPU)**, **onnxruntime**
- **rank-bm25** (hybrid search), **PyGithub 2.8** (GitOps), **PyJWT** + **python-jose** + **bcrypt** (auth), **python-magic** (MIME detection)

## Testing

```bash
pytest tests/ -v                                    # all tests (90+)
pytest tests/test_rag.py -v                         # one file
pytest tests/test_rag.py::test_semantic_search -v -s  # one test, show prints
pytest tests/ -k "rag and not slow" -v              # by keyword
```

Suites: `test_datagen.py`, `test_rag.py`, `test_github_integration.py`, `test_end_to_end.py`, plus phase-specific suites in `tests/`.

### Docker debugging

```bash
docker compose --profile rag ps                                     # service health
docker compose logs -f api                                          # API logs
docker compose logs -f celery-worker                                # worker logs
docker exec devforge-redis redis-cli ping                           # Redis check
docker exec devforge-postgres pg_isready -U devforge                # Postgres check
docker exec devforge-celery-worker celery -A src.workers.celery_app inspect active
# Flower UI: http://localhost:5555
```

Common issues:
- **Port 8001 busy:** stop any local `uvicorn` on 8001
- **DB connection failed:** include `--profile rag` so `postgres`/`redis` start
- **Ollama errors:** in Docker set `OLLAMA_HOST=http://host.docker.internal:11434`

## Configuration

Pydantic Settings (`src/core/config.py`) reads `.env` (local) or `.env.docker` (Docker). Auto-detects Docker via `/.dockerenv` and rewrites `redis:6379` → `localhost:6379` for local dev. Validates Redis/Postgres URL formats and warns on `localhost` URLs in `ENVIRONMENT=production`.

| Variable | Purpose | Default |
|----------|---------|---------|
| `OLLAMA_HOST` | LLM inference endpoint | required |
| `CORS_ORIGINS` | Comma-separated allowed origins | required |
| `FILE_BASE_URL` | Public base URL for `/static/uploads/...` | required |
| `VECTOR_BACKEND` | `chroma`, `postgres`, or `qdrant` | `postgres` |
| `POSTGRES_URL` | pgvector + app DB | optional |
| `REDIS_URL` | Celery broker, query cache, GitOps storage | optional |
| `QDRANT_URL` / `QDRANT_API_KEY` | Qdrant Cloud connection | optional |
| `DASHBOARD_JWT_SECRET` | Signs dashboard JWTs | required for dashboard auth |
| `ENABLE_HYBRID_SEARCH` / `HYBRID_ALPHA` | BM25+vector fusion | `true` / `0.5` |
| `ENABLE_RERANKING` / `RERANK_MODEL` | Cross-encoder rerank | `true` / `ms-marco-MiniLM-L-6-v2` |

See `.env.example` and `.env.docker` for the full list.

## RAG architecture highlights

- **Two-stage retrieval:** vector search (top-30 candidates) → cross-encoder reranking (top-K)
- **Code-aware:** AST chunking via tree-sitter, dependency-graph expansion (BFS depth 2), test↔source linking, function/class boost factors
- **Query intelligence:** rule-based + LLM intent classification, intent-driven query expansion, exact + semantic caching (cosine ≥ 0.92)
- **Hybrid search:** BM25 + vector with configurable `HYBRID_ALPHA`
- **Targets:** <50 ms cached, <200 ms reranking overhead

See `docs/tools/rag_architecture.md` for details.

## API authentication

| System | Used by | Header | Endpoints |
|--------|---------|--------|-----------|
| Dashboard JWT | Web dashboard users | `Authorization: Bearer <jwt>` | `/api/auth/*`, `/api/users/*`, `/api/admin/*` |
| API key | Programmatic clients (IDE integrations, MCP) | `x-api-key: <key>` | `/api/gateway`, `/mcp` |
| Tenant JWT | Multi-tenant RAG callers | `Authorization: Bearer <jwt>` | RAG endpoints (via `JWTAuthMiddleware`) |

Per-tier rate limits (free/pro/enterprise) with per-key overrides — see `docs/API.md`.

## Celery workers

| Worker | Queues | Purpose |
|--------|--------|---------|
| `celery-worker` | `default`, `analytics` | General tasks, key updates |
| `celery-worker-analytics` | `analytics`, `usage` | Request logging, LLM usage tracking |
| `celery-worker-secondary` | `default`, `usage` | Load-balancing (profile `scale`) |

Start locally: `./scripts/scale_celery.sh rag start`. Scale up in Docker: `docker compose --profile rag --profile scale up -d`.

## Common tasks

### Add a new tool

The newest tools (`generate_cheatsheet`, `generate_tests`) skip the `src/tools/<feature>/tools.py` split and keep all logic under `src/agents/<feature>/` with `agent.py` as the entry. Follow that pattern for new work.

1. **Agent module:** `src/agents/<feature>/agent.py` exporting `async def <tool>_invoke(args, tenant_id="unknown", integration_name="unknown", user_id=None) -> dict`. Add focused helper modules alongside (`ast_tools.py`, `prompt_builder.py`, etc.) rather than packing it all into `agent.py`.
2. **Shared dispatch table:** add `"<tool_name>": <tool>_invoke` to `SUPPORTED_TOOLS` in `src/api/routers/__init__.py`. Both `/api/gateway` (REST) and `/mcp/` (FastMCP) read from this same dict.
3. **MCP SDK surface** (all four files):
   - `src/api/mcp/schemas.py` — add a `<Tool>Input` Pydantic model with flat fields + Pydantic gates (max-length, enums).
   - `src/api/mcp/descriptions.py` — add `TOOL_DESCRIPTIONS["<tool_name>"]` written agent-instructively (inputs, outputs, latency expectation, when-to-call). This is the **single source of truth**.
   - `src/api/mcp/server.py` — `@mcp.tool(name="<tool_name>", description=TOOL_DESCRIPTIONS["<tool_name>"])` flat-param function that builds the input model and calls `_dispatch("<tool_name>", args.model_dump(exclude_none=True), ctx)`. Use the `_PassThroughArgs + direct Tool` pattern in `server.py:107-128` only if the schema needs `oneOf`.
4. **Manifest:** add the tool entry to `manifests/devforge.json` (used by `/api/manifest`).
5. **Per-tool doc:** add `docs/tools/<tool_name>.md` mirroring `docs/tools/generate_cheatsheet.md` (overview, inputs, outputs, pipeline, examples, failure modes).
6. **Tests:** `tests/test_<feature>.py`. Mock `model_router.invoke_with_usage` / your tool's LLM call so tests are deterministic and don't hit Ollama. Assert on response shape, not internals.

### Debug RAG

```bash
# Vector store stats
python -c "from src.storage.chroma_store import ChromaVectorStore; print(ChromaVectorStore().get_stats())"

# Run a single retrieval test with output
pytest tests/test_rag.py::test_semantic_search -v -s
```

### Database migrations

Migrations live in `migrations/`. Apply them via `scripts/` helpers (see `docs/`).
