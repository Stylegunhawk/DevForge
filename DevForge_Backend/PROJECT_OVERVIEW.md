DevForge – Project Overview

Web-Based Developer Chatbot Companion
BTech Computer Science Major Project
Version 1.2 – Updated 02 Nov 2025 (Refined)

1. Executive Summary

DevForge is a modular, open-source, self-hosted developer chatbot designed as a daily coding companion.
It combines Lobe Chat (Next.js UI) with a Python FastAPI backend to deliver:

Feature	Description	Status
RAG	Query codebases, docs, and PDFs via vector store (ChromaDB/Qdrant)	✅ v0.3.1
GitHub Ops	List repos, create issues, commit files, open PRs using PyGitHub	✅ v0.3.1
CSV/JSON Mock Data	On-demand dataset generation with schema (Faker + Pandas)	✅ v0.1.0
CI/CD Hooks	Trigger Vercel / Netlify builds	⏳ Phase 4
Prompt Reranking	Refine LLM outputs	⏳ Phase 4
Fine-Tuning Pipeline	Optional LoRA training on OSS models	⏳ Phase 4

Differentiator: MCP-based multi-tool architecture — each capability is a discrete FastAPI endpoint registered through a single manifest.


Phase | Weeks | Goal | Status
------|-------|------|-------
1 | 1-3 | Core FastAPI + DataGen agent + MCP integration | ✅ COMPLETE
2 | 4-6 | Supervisor router + multi-model fallback | 🔜 NEXT
3 | 7-10 | RAG (Kotaemon + Chroma) + GitHub tool | ⏳ PENDING
4 | 11-14 | Prompt reranking + LoRA fine-tuning | ⏳ PENDING
5 | 15-16 | Dockerize, deploy, docs, demo video | ⏳ PENDING

2. Architecture Overview
┌─────────────────────┐          HTTP (MCP)          ┌─────────────────────┐
│  Lobe Chat (Next.js)│ ◄──────────────────────────► │  FastAPI Backend    │
│  localhost:3000     │   manifest + /api/gateway   │  localhost:8000     │
└─────────────────────┘                             └─────────────────────┘
▲                                                   ▲
│                                                   │
Zustand (plugins)                                 LangGraph agents


Frontend (Lobe Chat) – Handles UI, chat history, plugin store.

Backend (FastAPI) – Located at src/main.py.

MCP Handshake – GET /api/manifests/devforge.json

Gateway – POST /api/gateway dispatches to LangGraph agents

Agents – src/agents/*/agent.py (LangGraph graphs)

Tools – src/tools/*/*.py (Python utility functions)

3. Core Tech Stack
Layer	Technology	Purpose
UI	Lobe Chat (Next.js)	Pre-built chat interface, MCP plugins, streaming
API	FastAPI + Uvicorn	Async I/O, auto-docs, Pydantic validation
Orchestration	LangGraph (Python)	Graph-based agent routing
LLM	Ollama (local) – example quantized models such as gemma-1b, qwen-lite, llama3-small	Lightweight local models for privacy & speed
Vector Store	ChromaDB	Simple file-based RAG store
Data Gen	Pandas + Faker	Create mock CSV/JSON data
GitHub	PyGitHub	Token-based repo operations
Deployment	Docker Compose → Render (free tier)	Easy self-hosting
4. Feature Roadmap

| Phase | Status | Weeks | Goal | Version |
|-------|--------|-------|------|---------|
| Phase 1 | ✅ Complete | 1-3 | Core FastAPI + DataGen agent + MCP integration | v0.1.0 |
| Phase 2 | ✅ Complete | 4-6 | Supervisor router + multi-model fallback | v0.2.0 |
| Phase 3 | ✅ Complete | 7-10 | RAG (ChromaDB + Qdrant) + GitHub Operations | v0.3.1 |
| Phase 4 | ⏳ Pending | 11-14 | Prompt reranking + LoRA fine-tuning | v0.4.0 |
| Phase 5 | ⏳ Pending | 15-16 | Dockerize, deploy, docs, demo video | v0.5.0 |

### Phase 2 Retrospective (v0.2.0 - Nov 2, 2025)

**Achievements:**
- ✅ Multi-Model Router operational with async fallback logic
- ✅ Supervisor Agent successfully integrated with LangGraph
- ✅ MCP Gateway supports intelligent routing
- ✅ Coverage: > 90% across core modules
- ✅ 58/58 tests passing (36 Phase 1 + 22 Phase 2)
- ✅ Released as v0.2.0 on Nov 2, 2025

**Key Technical Wins:**
- Task-based model selection (`select_model_by_task()`)
- Health checking for model availability
- Cost tracking for cloud model usage
- LangGraph state management for supervisor workflow

### Phase 3 Retrospective (v0.3.1 - Nov 4, 2025)

**Achievements:**
- ✅ RAG Agent with dual vector store support (ChromaDB local + Qdrant Cloud)
- ✅ Document ingestion and semantic search for PDF, MD, TXT, DOCX
- ✅ GitHub Operations agent with PyGithub integration
- ✅ Supervisor routing extended to support "rag" and "github" intents
- ✅ 33+ RAG tests + comprehensive GitHub operation tests
- ✅ Released as v0.3.1 on Nov 4, 2025

**Key Technical Wins:**
- Async file I/O with aiofiles for document processing
- LLM-based query parsing for GitHub operations
- Configurable vector backends with graceful fallback
- Natural language interface for GitHub operations

**Example User Queries:**
- "List my GitHub repositories"
- "Create an issue in my-repo titled 'Fix login bug'"
- "Search documents about authentication"
- "Generate 100 user records in CSV format"

5. Integration Flow (MCP)

Handshake – Lobe Chat fetches http://localhost:8000/api/manifests/devforge.json

Tool Call – LLM returns tool_call(name="generate_data", args={...})

Gateway – Lobe Chat POSTs to /api/gateway → FastAPI dispatches to datagen_graph.invoke(...)

Response – JSON or CSV is returned → LLM formats final message → UI streams result.

Security Note: Gateway endpoints should validate origin and block internal/private IP ranges to prevent SSRF.
Set CORS_ORIGINS=http://localhost:3000 in .env for local testing.

6. Example Files (for AI Reference)

BACKEND_PLAN.md – Folder structure & code snippets

INTEGRATION_PLAN.md – Detailed handshake and execution steps

MANIFEST_EXAMPLE.json – Sample manifest file for Phase 1

CODE_SNIPPETS.md – Starter FastAPI and LangGraph examples

7. Development Guidelines
Use latest version of tools whenever Possible

Python 3.11+ with venv isolation use Latest model agnostic langchain 

Pin package versions in requirements.txt

CORS enabled for http://localhost:3000

Environment variables in .env (see example below)

Testing with pytest in tests/

Logging via Python logging module (JSON in production)

.env.example
PORT=8000
OLLAMA_HOST=http://localhost:11434
DEFAULT_MODEL=gemma-1b
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=info
# Optional
GITHUB_TOKEN=
DATABASE_URL=postgresql://user:pass@localhost:5432/devforge

8. Sample Manifest (devforge.json)
{
  "name": "devforge",
  "version": "0.1.0",
  "description": "DevForge plugin manifest — DataGen tool",
  "gateway": "http://localhost:8000/api/gateway",
  "schema_version": "v1",
  "tools": [
    {
      "name": "generate_data",
      "description": "Generate mock CSV/JSON data using Faker and Pandas",
      "endpoint": "/api/datagen",
      "input_schema": {
        "type": "object",
        "properties": {
          "rows": { "type": "integer", "default": 100 },
          "format": { "type": "string", "enum": ["csv", "json"], "default": "json" },
          "fields": { "type": "array", "items": { "type": "object" } }
        },
        "required": ["rows"]
      }
    }
  ]
}

9. Local Testing
uvicorn src.main:app --reload --port 8000
curl http://localhost:8000/api/manifests/devforge.json
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{"tool":"generate_data","args":{"rows":10,"format":"json"}}'

10. Success Criteria

End-to-end chat with DataGen works in < 5 s (using local Ollama models)

Manifest loads successfully via URL (no manual upload)

At least 2 additional tools (RAG + GitHub) by Phase 3

Docker image deployable on Render