**Phase 1 Implementation: COMPLETE**
This file shows the final structure after Phase 1 completion.
All files under `src/agents/datagen/` and `src/tools/datagen/` are fully implemented.
See `tests/` for 36 passing tests validating functionality.


devforge-backend/
├── .env.example              # Template for env vars (e.g., OLLAMA_HOST=http://localhost:11434, GITHUB_TOKEN=xxx)
├── .gitignore                # Ignore venv, __pycache__, etc.
├── docker/                   # For future deployment (Phase 5)
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
│   │   ├── datagen/          # DataGen agent (Phase 1)
│   │   │   └── agent.py     # LangGraph workflow for data gen
│   │   ├── rag/              # Placeholder for RAG (Phase 3)
│   │   │   └── agent.py     # Stub
│   │   ├── github/           # Placeholder for GitHub ops (Phase 3)
│   │   │   └── agent.py     # Stub
│   │   └── supervisor.py     # Main router agent (Phase 2)
│   ├── tools/                # Reusable Python functions (called by agents)
│   │   ├── __init__.py
│   │   ├── datagen/          # DataGen tools (e.g., Faker/Pandas funcs)
│   │   │   └── tools.py     # e.g., generate_mock_data()
│   │   ├── rag/              # Placeholder (e.g., retrieve_docs())
│   │   │   └── tools.py     # Stub
│   │   └── github/           # Placeholder (e.g., create_pr())
│   │       └── tools.py     # Stub
│   ├── core/                 # Shared utilities
│   │   ├── __init__.py
│   │   ├── config.py         # Load env vars, settings
│   │   ├── schemas.py        # Pydantic models (e.g., ToolRequest)
│   │   └── utils.py          # Helpers (e.g., logging, error handling)
│   └── main.py               # FastAPI app entry point
├── tests/                    # Unit/integration tests (future-ready)
│   ├── __init__.py
│   └── test_datagen.py       # Example test for DataGen
├── requirements.txt          # Dependencies (refined below)
├── README.md                 # Setup/install instructions, architecture overview
└── setup.sh                  # Optional script: create venv, install deps