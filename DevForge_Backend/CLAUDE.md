# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository DevForge_Backend Folder.

## Skills
- devforge-workflow — use for all code changes in this project
- enterprise-audit-planner — use when given any audit .md file
- system-auditor — use to create audit .md file

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start development server
uvicorn src.main:app --reload --port 8001

# Run tests
pytest tests/ -v
```

### Docker Deployment

The project is fully containerized with Docker Compose using profiles for modular service management.

**Services:**
| Service | Purpose | Profile |
|---------|---------|---------|
| `api` | FastAPI backend (port 8001) | Always |
| `redis` | Celery broker & result backend | `rag` |
| `postgres` | PostgreSQL with pgvector | `rag` |
| `celery-worker` | Primary async worker | `rag` |
| `celery-worker-analytics` | Dedicated analytics worker | `rag` |
| `celery-worker-secondary` | Load balancing worker | `rag`, `scale` |
| `flower` | Celery monitoring UI (port 5555) | `rag` |

```bash
# Initialize environment
cp .env.docker .env

# Start API only (minimal - no RAG)
docker compose up api -d --build

# Start full stack with RAG (Redis, PostgreSQL, Celery)
docker compose --profile rag up -d --build

# Stop all services
docker compose --profile rag down
```

**Volumes:** The `api` service mounts the project directory (`.: /app`) and `./data` folder for file uploads and persistence.

See `docs/DOCKER_GUIDE.md` for detailed Docker setup and troubleshooting.

## Architecture Overview

DevForge is a FastAPI-based backend with a modular agent-based architecture for AI-powered developer tools:

### Core Layers

| Layer | Purpose | Key Files |
|-------|---------|-----------|
| **API** | HTTP endpoints (MCP, REST, RAG) | `src/api/routers.py`, `src/api/rag.py` |
| **Agents** | Business logic & orchestration | `src/agents/*/agent.py` |
| **Tools** | Reusable functions | `src/tools/*/tools.py` |
| **Storage** | Vector store abstraction | `src/storage/base_store.py`, `chroma_store.py`, `pgvector_store.py` |
| **Workers** | Async task processing | `src/workers/celery_app.py` |

### Agent Modules

- **datagen/** - Mock data generation (CSV/JSON)
- **supervisor.py** - Intent classification & routing (LangGraph)
- **rag/** - Document retrieval with code-aware features (Hybrid Search, Reranking, Query Cache)
- **github/** - GitOps automation with fuzzy repo matching & commit generation
- **prompt_refiner/** - Domain-aware prompt optimization
- **cheatsheet/** - Code documentation generation
- **reranker.py** - Cross-encoder document reranking

### Key Technologies

- **FastAPI** - Web framework with async support
- **LangGraph** - Agent orchestration & state machines
- **Celery** - Async task queue (Redis broker)
- **ChromaDB/pgvector** - Vector storage with abstraction layer
- **Tree-sitter** - AST-based code chunking
- **Cross-encoder** - ms-marco-MiniLM-L-6-v2 for reranking

## Project Status

**Current Version:** v0.8.0
**Completed Phases:** 1-7, 10.1, 11, 11.2, 12, 12A, 15.3
**Deferred:** Phase 5 (Deployment - partially implemented)

See `BACKEND_PLAN.md` and `CHANGELOG.md` for detailed phase history.

## Testing

```bash
# All tests
pytest tests/ -v

# Specific test suites
pytest tests/test_datagen.py -v
pytest tests/test_rag.py -v
pytest tests/test_github_integration.py -v
pytest tests/test_end_to_end.py -v
```

**Total: 90+ tests** covering unit, integration, and end-to-end scenarios.

### Docker Testing & Troubleshooting

```bash
# Check if services are healthy
docker compose --profile rag ps

# View API logs
docker compose logs -f api

# Check Redis connectivity
docker exec devforge-redis redis-cli ping

# Check PostgreSQL connectivity
docker exec devforge-postgres pg_isready -U devforge

# View Celery worker logs
docker compose logs -f celery-worker

# Access Flower monitoring
http://localhost:5555
```

**Common Issues (see `docs/DOCKER_GUIDE.md` for details):**
- **Port 8001 busy:** Stop local Python servers running on 8001
- **Database connection failed:** Ensure `--profile rag` is used to start postgres/redis
- **Ollama errors:** Verify Ollama is running and `OLLAMA_HOST=http://host.docker.internal:11434`

## Configuration

### Environment Files

| File | Purpose |
|------|---------|
| `.env` | Local development (default port 8001) |
| `.env.docker` | Docker deployment (uses service names for DB/Redis) |

**Key variables:**
- `OLLAMA_HOST` - Ollama endpoint (use `http://host.docker.internal:11434` in Docker)
- `POSTGRES_URL` - PostgreSQL connection (auto-constructed from `POSTGRES_*` vars)
- `REDIS_URL` - Redis broker URL
- `CORS_ORIGINS` - Comma-separated allowed origins

See `.env.example` and `.env.docker` for all available options.

## RAG Architecture Highlights

The RAG system includes:

- **Two-stage retrieval:** Vector search → Cross-encoder reranking
- **Code-aware features:** AST parsing, dependency graph, test-source linking
- **Query intelligence:** Intent classification, query expansion, semantic caching
- **Hybrid search:** BM25 + Vector fusion (configurable alpha)
- **Performance:** <50ms cached, <200ms reranking overhead

See `docs/tools/rag_architecture.md` for detailed architecture.

## API Authentication

Two authentication systems:

1. **Dashboard JWT** - User-facing endpoints (`/api/auth/*`, `/api/users/*`, `/api/admin/*`)
2. **API Keys** - Programmatic access (`/api/gateway`, `/mcp`, RAG endpoints)

See `docs/API.md` for complete endpoint documentation.

## Celery Workers

Three worker types for horizontal scaling:

| Worker | Queues | Purpose |
|--------|--------|---------|
| `celery-worker` | default, analytics | General tasks, key updates |
| `celery-worker-analytics` | analytics, usage | Request logging, LLM tracking |
| `celery-worker-secondary` | default, usage | Load balancing |

Run with: `./scripts/scale_celery.sh rag start`

## Common Tasks

### Adding a New Tool

1. Create tool in `src/tools/<feature>/tools.py`
2. Create agent in `src/agents/<feature>/agent.py` (if needed)
3. Add to `SUPPORTED_TOOLS` in `src/api/routers.py`
4. Update `manifests/devforge.json`
5. Add tests in `tests/test_<feature>.py`

### Debugging RAG

```bash
# Check vector store health
python -c "from src.storage.chroma_store import ChromaVectorStore; print(ChromaVectorStore().get_stats())"

# Test retrieval
pytest tests/test_rag.py::test_semantic_search -v -s
```

### Scaling

```bash
# Scale to production configuration
./scripts/scale_celery.sh rag scale

# Monitor with Flower
http://localhost:5555
```

### Docker Scaling

```bash
# Scale up all workers
docker compose --profile rag,scale up -d

# Restart specific service
docker compose --profile rag restart celery-worker

# Check worker status
docker exec devforge-celery-worker celery -A src.workers.celery_app inspect active
```
