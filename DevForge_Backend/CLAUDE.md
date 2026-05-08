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
| API | HTTP endpoints (REST gateway, MCP JSON-RPC, RAG, auth, admin) | `src/api/routers/__init__.py`, `src/api/routers/{rag,auth,users,admin}.py` |
| Agents | Business logic & orchestration | `src/agents/*/agent.py`, `src/agents/supervisor.py` |
| Tools | Reusable functions invoked by agents | `src/tools/*/tools.py` |
| Storage | Vector store abstraction | `src/storage/base_store.py`, `chroma_store.py`, `pgvector_store.py` |
| Workers | Async Celery tasks | `src/workers/celery_app.py` |
| Core | Config, middleware, auth | `src/core/config.py`, `src/core/{middleware,api_key_middleware,dashboard_middleware}.py` |

### Request flow (tool execution)

`POST /api/gateway` (REST) or `POST /mcp` (JSON-RPC) → `APIKeyAuthMiddleware` validates `x-api-key` → `src/api/routers.py` resolves tool name → `src/agents/supervisor.py` classifies intent (LangGraph) → individual agent (datagen / github / prompt_refiner / cheatsheet / rag) → response.

### Agent modules

- `datagen/` — mock data generation (CSV/JSON, uses Faker + rstr)
- `supervisor.py` — intent classification & routing (LangGraph)
- `rag/` — document retrieval with hybrid search, reranking, query cache, intent-aware expansion
- `github/` — GitOps automation with fuzzy repo matching & LLM-generated commits
- `prompt_refiner/` — domain-aware prompt optimization
- `cheatsheet/` — code documentation generation
- `rag/reranking/cross_encoder_reranker.py` — cross-encoder reranking (`ms-marco-MiniLM-L-6-v2`), internal stage of `retrieve_docs`

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

1. Implement in `src/tools/<feature>/tools.py`
2. Add an agent in `src/agents/<feature>/agent.py` if it needs orchestration
3. Register in `SUPPORTED_TOOLS` in `src/api/routers/__init__.py`
4. Update `manifests/devforge.json`
5. Add `tests/test_<feature>.py`

### Debug RAG

```bash
# Vector store stats
python -c "from src.storage.chroma_store import ChromaVectorStore; print(ChromaVectorStore().get_stats())"

# Run a single retrieval test with output
pytest tests/test_rag.py::test_semantic_search -v -s
```

### Database migrations

Migrations live in `migrations/`. Apply them via `scripts/` helpers (see `docs/`).
