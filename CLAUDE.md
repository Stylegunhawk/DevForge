# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Monorepo layout

| Folder | Stack | Port | Sub-project guide |
|--------|-------|------|-------------------|
| `DevForge_Backend/` | Python 3.12, FastAPI, LangGraph, Celery | 8001 | `DevForge_Backend/CLAUDE.md` |
| `dashboard/` | Next.js 14 App Router, TypeScript, shadcn/ui | 3000 | `dashboard/CLAUDE.md` |

## How they connect

- Dashboard routes all backend calls through `dashboard/src/proxy.ts` → `dashboard/src/app/api/proxy/`
- Never call `http://localhost:8001` directly from dashboard components
- Two separate auth systems:
  - Dashboard: NextAuth sessions + `DASHBOARD_JWT_SECRET`
  - Backend tools: API keys via `x-api-key` header (RAG endpoints use separate JWT via `JWTAuthMiddleware`)

## Quick start

### Backend
```bash
cd DevForge_Backend
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8001
```

### Dashboard
```bash
cd dashboard
npm install
npm run dev    # starts on port 3000
```

### Full stack with RAG (Docker)
```bash
cd DevForge_Backend
cp .env.docker .env
docker compose --profile rag up -d --build
```

## Testing

```bash
# Backend — all tests
cd DevForge_Backend && pytest tests/ -v

# Backend — single test
pytest tests/test_rag.py::test_semantic_search -v -s

# Dashboard — no test suite yet (Next.js default)
```

## Backend architecture at a glance

Three middleware layers applied to every request (in order):

1. `DashboardAuthMiddleware` — validates `Authorization: Bearer <dashboard_jwt>` for `/api/users/*`, `/api/admin/*`
2. `APIKeyAuthMiddleware` — validates `x-api-key` for `/api/gateway`, `/mcp`
3. `JWTAuthMiddleware` — validates tenant JWTs for RAG endpoints

Request flow for tool execution: `POST /api/gateway` or `POST /mcp` → `src/api/routers.py` → `src/agents/supervisor.py` (intent classification via LangGraph) → individual agent (datagen / github / prompt_refiner / cheatsheet / rag)

Vector storage is configurable via `VECTOR_BACKEND` env var: `chroma`, `postgres` (pgvector), or `qdrant`. The abstraction lives in `src/storage/base_store.py`.

## Key configuration

Backend config is managed by Pydantic Settings (`src/core/config.py`). All vars come from `.env` (local) or `.env.docker` (Docker). Critical vars:

| Variable | Purpose | Default |
|----------|---------|---------|
| `OLLAMA_HOST` | LLM inference endpoint | required |
| `VECTOR_BACKEND` | `chroma`, `postgres`, or `qdrant` | `postgres` |
| `REDIS_URL` | Celery broker + query cache | optional |
| `POSTGRES_URL` | pgvector store + DB | optional |
| `DASHBOARD_JWT_SECRET` | Dashboard auth signing | required for dashboard |
| `CORS_ORIGINS` | Comma-separated allowed origins | required |

## Branch rules

- Backend: work on the branch recommended by the user (current: `rag_resolve`)
- Dashboard: `main` branch

## Never do this

- Do not import backend Python code into the dashboard
- Do not run `npm` commands inside `DevForge_Backend/`
- Do not run `pip` commands inside `dashboard/`
- Do not call `http://localhost:8001` directly from dashboard components — use proxy routes

## Skills loaded for this project

- `devforge-workflow` — use for all backend code changes
- `enterprise-audit-planner` — use when given any audit or issue report `.md` file
