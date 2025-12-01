Backend Implementation Plan for DevForge

## Current Status: ✅ Phases 1-7 COMPLETE (Updated: Nov 23, 2025)

**Current Version:** v0.7.0  
**Completed Phases:** 1, 2, 3, 4, 6, 7  
**Deferred:** Phase 5 (Deployment)  
**Next Phase:** Phase 8 (Enhanced DevOps)

**Implemented Features (All Phases):**
- ✅ Phase 1: Core FastAPI server, DataGen agent, MCP gateway (36 tests)
- ✅ Phase 2: Multi-model routing, Supervisor agent (58 tests total)
- ✅ Phase 3: RAG agent, GitHub operations (100+ tests total)
- ✅ Phase 4: Document reranking with Cross-Encoder
- ✅ Phase 6: Prompt refinement agent with domain handlers
- ✅ Phase 7: Dynamic cheat sheet generator

**Next Steps:** Phase 8 (Enhanced DevOps) or Phase 5 (Deployment)

After thoroughly reviewing all the provided information—including the Lobe Chat architecture (decoupled frontend with BFF, MCP plugin system, Zustand state, AgentRuntime orchestration), the DevForge project report (multi-model orchestration, agentic routing via LangGraph/CrewAI, features like RAG/GitHub/CSV gen/prompt reranking/fine-tuning, phased 3-6 month timeline, OSS focus), the integration plan (two servers connected via manifest.json handshake, gateway for tool calls), and the initial backend plan (modular structure with FastAPI/LangGraph)—I've refined the plan to make it more robust, future-ready, and aligned with best practices.
Key Refinements and Rationale

Modularity and Scalability: Enhanced the folder structure to better support adding features (e.g., separate subfolders in agents/ and tools/ for each feature like datagen/, rag/, github/). This follows Python's package conventions for easy imports and avoids monolithic files. Added a configs/ folder for environment-specific settings (e.g., .env for API keys, model endpoints) to handle multi-model fallbacks (Ollama local → OpenRouter/Grok).
Future-Proofing: Included placeholders for stretch goals (e.g., fine-tuning with Llama-Factory, caching with Redis). Added a tests/ folder for unit/integration testing (using pytest), a docker/ folder for containerization (Docker Compose for local dev/prod), and a manifests/ folder to serve multiple plugin manifests dynamically (e.g., for different MCP tools). This aligns with Phase 5 deployment (Docker + Render).
Security and Best Practices: Emphasize env vars for sensitive data (e.g., GitHub tokens, API keys). Added logging (via logging lib) and error handling in APIs. CORS middleware for Lobe Chat integration. Start with minimal dependencies to avoid bloat; add as phases progress (e.g., PyGithub in Phase 3).
Integration with Lobe Chat: The backend will serve manifest.json from /manifests/devforge.json (dynamic endpoint for updates). Gateway endpoint (/api/gateway) will dispatch to agents/tools based on tool name, supporting multi-MCP (e.g., hybrid JS/Python via future LangChain.js calls if needed).
Phased Rollout: Stick to Phase 1 focus (core setup + DataGen agent), but include stubs for Phases 2-4 (e.g., supervisor agent skeleton). Use LangGraph for agents to enable graph-based workflows (e.g., parse query → generate data → format output).
Performance/Feasibility: Optimized for student hardware—use quantized models via Ollama; async FastAPI for low latency. Assumes Python 3.10+; venv for isolation. Total Phase 1 effort: 1-2 days.
Assumptions: Starting with DataGen as the first feature (CSV/mock data with Pandas/Faker). LLM: Ollama (e.g., Gemma-3:1B for lightweight tasks). No internet installs in code (per tools guidelines, but this is setup).

If any aspect needs further adjustment (e.g., based on hardware), we can iterate.
Refined Project Folder Structure
This structure is professional, PEP-compliant, and extensible. It builds on the initial plan but adds depth for future scopes (e.g., submodules, tests, deployment).
text


devforge-backend/
├── .env.example              # Template for env vars (e.g., OLLAMA_HOST=http://localhost:11434, GITHUB_TOKEN=xxx)
├── .gitignore                # Ignore venv, __pycache__, etc.
├── docker/                   # For future deployment (Phase 5 - DEFERRED)
│   ├── Dockerfile            # Build image for FastAPI
│   └── docker-compose.yml    # Compose for backend + Ollama/Redis
├── manifests/                # Plugin manifests for Lobe Chat integration
│   └── devforge.json         # Main manifest (served via API)
├── src/                      # Core source code
│   ├── api/                  # API routers (MCP endpoints, e.g., gateway)
│   │   ├── __init__.py
│   │   └── routers.py        # Define routes (e.g., /api/gateway, /manifests)
│   ├── agents/               # LangGraph agents (modular by feature)
│   │   ├── __init__.py
│   │   ├── datagen/          # DataGen agent (Phase 1) ✅
│   │   │   └── agent.py     # LangGraph workflow for data gen
│   │   ├── rag/              # RAG agent (Phase 3.1) ✅
│   │   │   ├── __init__.py
│   │   │   └── agent.py     # LangGraph workflow for document retrieval
│   │   ├── github/           # GitHub Operations agent (Phase 3.3) ✅
│   │   │   ├── __init__.py
│   │   │   └── agent.py     # LangGraph workflow for GitHub operations
│   │   ├── reranker.py       # Document reranking (Phase 4) ✅
│   │   ├── prompt_refiner/   # Prompt refinement (Phase 6) ✅
│   │   │   ├── agent.py
│   │   │   ├── enhancer.py
│   │   │   ├── domain_handlers.py
│   │   │   └── templates.py
│   │   ├── cheatsheet/       # Cheat sheet generator (Phase 7) ✅
│   │   │   ├── agent.py
│   │   │   ├── generator.py
│   │   │   ├── formatter.py
│   │   │   └── language_profiles.py
│   │   └── supervisor.py     # Main router agent (Phase 2) ✅
│   ├── tools/                # Reusable Python functions (called by agents)
│   │   ├── __init__.py
│   │   ├── datagen/          # DataGen tools (Phase 1) ✅
│   │   │   ├── __init__.py
│   │   │   └── tools.py     # generate_mock_data()
│   │   ├── rag/              # RAG tools (Phase 3.1) ✅
│   │   │   ├── __init__.py
│   │   │   └── tools.py     # Document reading, chunking, ingestion, retrieval
│   │   ├── github/           # GitHub tools (Phase 3.3) ✅
│   │   │   ├── __init__.py
│   │   │   └── tools.py     # GitHub API operations (list repos, create issues, etc.)
│   │   └── cheatsheet/       # Cheat sheet tools (Phase 7) ✅
│   │       ├── __init__.py
│   │       └── tools.py     # Language detection, template generation
│   ├── core/                 # Shared utilities
│   │   ├── __init__.py
│   │   ├── config.py         # Load env vars, settings
│   │   ├── schemas.py        # Pydantic models (e.g., ToolRequest)
│   │   └── utils.py          # Helpers (e.g., logging, error handling)
│   └── main.py               # FastAPI app entry point
├── tests/                    # Unit/integration tests (100+ tests)
│   ├── __init__.py
│   ├── test_datagen.py       # DataGen tests (Phase 1) ✅
│   ├── test_api.py           # API integration tests (Phase 1) ✅
│   ├── test_end_to_end.py    # E2E workflow tests (Phase 1) ✅
│   ├── test_rag.py           # RAG tests (Phase 3.1) ✅
│   ├── test_github.py        # GitHub operation tests (Phase 3.3) ✅
│   ├── test_reranker.py      # Reranking tests (Phase 4) ✅
│   ├── test_prompt_refiner.py # Prompt refiner tests (Phase 6) ✅
│   └── test_cheatsheet.py    # Cheat sheet tests (Phase 7) ✅
├── requirements.txt          # Dependencies (refined below)
├── README.md                 # Setup/install instructions, architecture overview
└── setup.sh                  # Optional script: create venv, install deps