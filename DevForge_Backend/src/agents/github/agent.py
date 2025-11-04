# src/agents/github/agent.py
"""
GitHub operations agent using LangGraph.
Phase 3.3 implementation.
"""

import logging
import json
from typing import TypedDict, Literal, Optional, Dict, Any

from langgraph.graph import StateGraph, END

from src.core.model_router import ModelRouter
from src.tools.github import tools as github_tools

logger = logging.getLogger(__name__)


class GitHubState(TypedDict):
    """State for GitHub agent workflow."""
    query: str
    operation: Optional[str]  # 'list_repos', 'create_repo', 'create_issue', 'commit_file', 'create_pr'
    parameters: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    error: Optional[str]


async def parse_github_request(state: GitHubState) -> GitHubState:
    """Parse user query to determine GitHub operation and parameters.
    
    Uses LLM to classify the intent and extract parameters.
    
    Args:
        state: Current state with user query
        
    Returns:
        Updated state with operation and parameters
    """
    query = state["query"]
    logger.info(f"Parsing GitHub request: {query[:100]}...")
    
    try:
        # Use model router to get appropriate model for classification
        router = ModelRouter()
        model = await router.select_model_by_task("github")
        
        # Define classification prompt
        classification_prompt = f"""Analyze this GitHub-related request and extract the operation and parameters.

User Request: {query}

Available Operations:
- list_repos: List user repositories
- create_repo: Create a new repository
- create_issue: Create an issue in a repository
- commit_file: Commit/update a file in a repository
- create_pull_request: Create a pull request

Respond with ONLY a JSON object in this exact format (no markdown, no explanation):
{{
  "operation": "operation_name",
  "parameters": {{
    "param1": "value1",
    "param2": "value2"
  }}
}}

For list_repos, parameters can include: visibility, sort, limit
For create_repo, parameters must include: name, and can include: description, private
For create_issue, parameters must include: repo_name, title, and can include: body, labels, assignees
For commit_file, parameters must include: repo_name, file_path, content, commit_message, and can include: branch
For create_pull_request, parameters must include: repo_name, title, head, and can include: base, body, draft

Extract all relevant parameters from the user request."""

        # Call LLM for classification
        response = await router.invoke_with_fallback(
            model=model,
            prompt=classification_prompt,
            fallback_chain=["gpt-oss:120b-cloud"]
        )
        
        # Parse LLM response
        # Clean up response (remove markdown code blocks if present)
        response_text = response.strip()
        if response_text.startswith("```"):
            # Remove markdown code blocks
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        
        parsed = json.loads(response_text)
        operation = parsed.get("operation")
        parameters = parsed.get("parameters", {})
        
        logger.info(
            f"Parsed GitHub operation: {operation}",
            extra={"operation": operation, "parameters": parameters}
        )
        
        return {
            **state,
            "operation": operation,
            "parameters": parameters,
        }
        
    except Exception as e:
        logger.error(
            f"Failed to parse GitHub request: {e}",
            extra={"error": str(e), "query": query[:100]},
            exc_info=True
        )
        return {
            **state,
            "error": f"Failed to parse GitHub request: {str(e)}",
        }


async def execute_github_operation(state: GitHubState) -> GitHubState:
    """Execute the determined GitHub operation.
    
    Args:
        state: Current state with operation and parameters
        
    Returns:
        Updated state with result or error
    """
    operation = state.get("operation")
    parameters = state.get("parameters", {})
    
    if not operation:
        return {
            **state,
            "error": "No operation determined",
        }
    
    logger.info(
        f"Executing GitHub operation: {operation}",
        extra={"operation": operation, "parameters": parameters}
    )
    
    try:
        # Execute operation based on type
        if operation == "list_repos":
            result = github_tools.list_repos(**parameters)
            
        elif operation == "create_repo":
            result = github_tools.create_repo(**parameters)
            
        elif operation == "create_issue":
            result = github_tools.create_issue(**parameters)
            
        elif operation == "commit_file":
            result = github_tools.commit_file(**parameters)
            
        elif operation == "create_pull_request":
            result = github_tools.create_pull_request(**parameters)
            
        else:
            raise ValueError(f"Unknown GitHub operation: {operation}")
        
        logger.info(
            f"GitHub operation completed successfully",
            extra={"operation": operation, "result_type": type(result).__name__}
        )
        
        return {
            **state,
            "result": {
                "success": True,
                "operation": operation,
                "data": result,
            },
        }
        
    except Exception as e:
        logger.error(
            f"GitHub operation failed: {e}",
            extra={"operation": operation, "parameters": parameters, "error": str(e)},
            exc_info=True
        )
        return {
            **state,
            "error": f"GitHub operation failed: {str(e)}",
            "result": {
                "success": False,
                "operation": operation,
                "error": str(e),
            },
        }


def should_execute(state: GitHubState) -> Literal["execute", "error"]:
    """Determine if operation should be executed or return error.
    
    Args:
        state: Current state
        
    Returns:
        Next node to execute
    """
    if state.get("error"):
        return "error"
    if not state.get("operation"):
        return "error"
    return "execute"


async def handle_error(state: GitHubState) -> GitHubState:
    """Handle errors in the workflow.
    
    Args:
        state: Current state with error
        
    Returns:
        Updated state with error result
    """
    error = state.get("error", "Unknown error occurred")
    logger.error(f"GitHub agent error: {error}")
    
    return {
        **state,
        "result": {
            "success": False,
            "error": error,
        },
    }


# Build LangGraph workflow
workflow = StateGraph(GitHubState)

# Add nodes
workflow.add_node("parse", parse_github_request)
workflow.add_node("execute", execute_github_operation)
workflow.add_node("error", handle_error)

# Add edges
workflow.set_entry_point("parse")
workflow.add_conditional_edges(
    "parse",
    should_execute,
    {
        "execute": "execute",
        "error": "error",
    }
)
workflow.add_edge("execute", END)
workflow.add_edge("error", END)

# Compile graph
github_graph = workflow.compile()


# Convenience function for invocation
async def github_agent_invoke(query: str) -> Dict[str, Any]:
    """Invoke GitHub agent with a user query.
    
    Args:
        query: User query describing GitHub operation
        
    Returns:
        Result dictionary with success status and data/error
    """
    logger.info(f"Invoking GitHub agent with query: {query[:100]}...")
    
    initial_state: GitHubState = {
        "query": query,
        "operation": None,
        "parameters": None,
        "result": None,
        "error": None,
    }
    
    try:
        final_state = await github_graph.ainvoke(initial_state)
        result = final_state.get("result", {
            "success": False,
            "error": "No result produced",
        })
        
        logger.info(
            f"GitHub agent completed",
            extra={"success": result.get("success"), "operation": final_state.get("operation")}
        )
        
        return result
        
    except Exception as e:
        logger.error(
            f"GitHub agent invocation failed: {e}",
            extra={"error": str(e), "query": query[:100]},
            exc_info=True
        )
        return {
            "success": False,
            "error": f"GitHub agent failed: {str(e)}",
        }