# DevForge — Monorepo

## Project layout
This repo has two independent projects:

| Folder | Stack | Purpose |
|--------|-------|---------|
| `DevForge_Backend/` | Python, FastAPI, LangGraph, Celery | AI backend — MCP server, RAG pipeline, agent tools |
| `dashboard/` | Next.js 14, TypeScript, shadcn/ui | User dashboard — API key management, usage analytics |

## How they connect
- Dashboard calls `DevForge_Backend` via API proxy at `src/proxy.ts`
- Backend runs on port `8001`, dashboard on port `3000`
- Auth: dashboard uses NextAuth, backend uses JWT + API keys (two separate systems)

## Active development branch
- Backend: always work on user recommended branch
- Dashboard: `main` branch is fine

## Never do this
- Do not import backend Python code into the dashboard
- Do not run `npm` commands inside `DevForge_Backend/`
- Do not run `pip` commands inside `dashboard/`

## Skills loaded for this project
- `devforge-workflow` — use for all backend changes
- `enterprise-audit-planner` — use when given any audit or issue report .md file