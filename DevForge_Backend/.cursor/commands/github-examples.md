---
description: Run GitHub list repos test or call github_operation tool examples
globs:
alwaysApply: false
---

# GitHub Operations Examples

## Run GitHub List Repos Test

```bash
# Run the GitHub agent test for listing repositories
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
pytest tests/test_github.py::TestGitHubAgentWorkflow::test_list_repositories -v
```

## Call GitHub Operation Tool Example

### Via Python Script

```python
import asyncio
from src.agents.github.agent import github_agent_invoke

async def main():
    # Example 1: List repositories
    result = await github_agent_invoke("List my GitHub repositories")
    print(result)
    
    # Example 2: Create an issue
    result = await github_agent_invoke(
        "Create an issue in my-repo titled 'Fix login bug'"
    )
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

### Via Gateway API (curl)

```bash
# List repositories
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "List my GitHub repositories"
    }
  }'

# Create an issue
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "Create an issue in my-repo titled '\''Fix login bug'\''"
    }
  }'
```

### Via Supervisor

```python
from src.agents.supervisor import supervisor_invoke

# Supervisor will automatically route to GitHub agent
result = await supervisor_invoke("List my GitHub repositories")
```

## Common Use Cases

1. **List Repositories**: "List my GitHub repositories"
2. **Create Issue**: "Create an issue in my-repo titled 'Fix login bug'"
3. **Create Repository**: "Create a new repository called my-project"
4. **Create Pull Request**: "Create a PR from feature-branch to main"
