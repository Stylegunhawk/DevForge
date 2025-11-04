**Phase 3 Implementation: COMPLETE**



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

## GitHub Agent Usage (Phase 3.3)

### Basic Usage

```python
from src.agents.github.agent import github_agent_invoke

# List repositories
result = await github_agent_invoke("List my GitHub repositories")
print(result)
# {
#   "success": True,
#   "tool": "github_operation",
#   "data": {
#     "operation": "list_repos",
#     "repositories": [...]
#   },
#   "execution_time": 1.23
# }

# Create an issue
result = await github_agent_invoke(
    "Create an issue in my-repo titled 'Fix login bug' with description 'Users cannot log in'"
)
# {
#   "success": True,
#   "tool": "github_operation",
#   "data": {
#     "operation": "create_issue",
#     "issue_url": "https://github.com/user/my-repo/issues/123",
#     "issue_number": 123
#   }
# }

# Create a pull request
result = await github_agent_invoke(
    "Create a PR from branch feature-auth to main with title 'Add authentication'"
)
```

### Via Gateway API

```python
import requests

# Example: List repositories
response = requests.post(
    "http://localhost:8000/api/gateway",
    json={
        "name": "github_operation",
        "arguments": {
            "query": "List my GitHub repositories"
        }
    }
)
print(response.json())
```

### Via Supervisor

```python
from src.agents.supervisor import supervisor_invoke

# Supervisor will classify intent as "github" and route accordingly
result = await supervisor_invoke("List my GitHub repositories")
# {
#   "success": True,
#   "intent": "github",
#   "result": {
#     "success": True,
#     "tool": "github_operation",
#     "data": {...}
#   }
# }
```

### Supported Operations

- **List Repositories**: "List my repos", "Show all repositories"
- **Create Repository**: "Create a new repo called my-project"
- **Create Issue**: "Create an issue in my-repo titled 'Bug fix'"
- **Commit File**: "Commit file.txt to my-repo with message 'Update config'"
- **Create Pull Request**: "Open a PR from feature-branch to main"

### Example User Queries

1. **"List my GitHub repositories"**
   - Parsed as: `operation="list_repos"`
   - Returns: List of repository objects with name, description, URL

2. **"Create an issue in my-repo titled 'Fix login bug'"**
   - Parsed as: `operation="create_issue", repo="my-repo", title="Fix login bug"`
   - Returns: Issue URL and number

### Error Handling

```python
result = await github_agent_invoke("Invalid operation")
if not result["success"]:
    print(f"Error: {result.get('error')}")
    # Error: Operation not supported or missing required parameters
```