"""Supervisor agent with LangGraph-based intent classification and routing.

Routes user queries to appropriate agents based on LLM-based intent classification.
Phase 2: Supports DataGen routing. RAG and GitHub routing are stubs for Phase 3.
"""

import logging
from typing import Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from src.core.model_router import ModelRouter, model_router

logger = logging.getLogger(__name__)


class SupervisorState(TypedDict):
    """State for supervisor agent graph."""

    query: str  # User input
    intent: Optional[str]  # Classified intent: "datagen" | "rag" | "github" | "unknown"
    model_used: Optional[str]  # Model used for classification
    agent_result: Optional[dict]  # Result from delegated agent
    error: Optional[str]  # Error message if any


async def classify_intent(state: SupervisorState) -> SupervisorState:
    """Classify user intent using deepseek-r1:8b.

    Intents:
    - "datagen": User wants to generate mock data
    - "rag": User wants to search/query documents (Phase 3)
    - "github": User wants GitHub operations (Phase 3)
    - "unknown": Cannot determine intent

    Args:
        state: Current supervisor state with query

    Returns:
        Updated state with intent and model_used
    """
    query = state.get("query", "")
    logger.info(
        f"Classifying intent for query: {query[:100]}...",
        extra={"query_length": len(query)},
    )

    try:
        # Select routing model (deepseek-r1:8b)
        model_name = model_router.select_model_by_task("routing")

        # Create classification prompt
        classification_prompt = f"""Classify the user's intent. Reply with ONLY one word: datagen, rag, github, or unknown.

User query: {query}

Intent:"""

        chat_model = model_router.get_chat_model(model_name)
        response = await chat_model.ainvoke([{"role": "user", "content": classification_prompt}])

        # Extract intent from response
        intent = response.content.strip().lower() if hasattr(response, "content") else str(response).strip().lower()

        # Clean and validate intent
        intent = intent.replace(".", "").replace(",", "").strip()

        # Validate intent is one of expected values
        valid_intents = ["datagen", "rag", "github", "unknown"]
        if intent not in valid_intents:
            logger.warning(f"Invalid intent '{intent}' returned, defaulting to 'unknown'")
            intent = "unknown"

        logger.info(
            f"Classified intent: {intent} for query: {query[:50]}...",
            extra={"intent": intent, "model": model_name, "query_preview": query[:50]},
        )

        return {
            **state,
            "intent": intent,
            "model_used": model_name,
        }

    except Exception as e:
        logger.error(
            f"Intent classification failed: {e}",
            extra={"error": str(e), "query": query[:50]},
            exc_info=True,
        )
        return {
            **state,
            "intent": "unknown",
            "error": f"Classification failed: {str(e)}",
        }


def route_to_agent(state: SupervisorState) -> Literal["datagen_node", "rag_node", "github_node", "unknown_node"]:
    """Determine which agent to route to based on classified intent.

    Args:
        state: Supervisor state with classified intent

    Returns:
        Node name to route to: "datagen_node", "rag_node", "github_node", or "unknown_node"
    """
    intent = state.get("intent", "unknown")

    route_map = {
        "datagen": "datagen_node",
        "rag": "rag_node",  # Phase 3
        "github": "github_agent",  # Phase 3
        "unknown": "unknown_node",
    }

    target_node = route_map.get(intent, "unknown_node")

    logger.info(
        f"Routing to {target_node} based on intent: {intent}",
        extra={"intent": intent, "target_node": target_node},
    )

    return target_node


async def datagen_node(state: SupervisorState) -> SupervisorState:
    """Execute DataGen agent.

    Args:
        state: Supervisor state with query

    Returns:
        Updated state with agent_result
    """
    from src.agents.datagen.agent import datagen_agent

    query = state.get("query", "")
    logger.info(f"Executing DataGen agent for query: {query[:50]}...")

    try:
        # Parse arguments from query (simplified - extract numbers and keywords)
        # Default values
        args = {
            "rows": 100,
            "format": "json",
            "fields": None,
        }

        # Simple extraction: look for numbers in query
        import re

        numbers = re.findall(r"\d+", query)
        if numbers:
            args["rows"] = int(numbers[0])

        # Check for format keywords
        if "csv" in query.lower():
            args["format"] = "csv"

        # Check for field mentions (simplified)
        if "email" in query.lower() or "phone" in query.lower():
            fields = []
            if "email" in query.lower():
                fields.append("email")
            if "phone" in query.lower():
                fields.append("phone")
            if fields:
                args["fields"] = fields

        result = await datagen_agent(args)

        logger.info(
            f"DataGen agent completed successfully",
            extra={"rows": args["rows"], "format": args["format"]},
        )

        return {
            **state,
            "agent_result": result,
        }

    except Exception as e:
        logger.error(
            f"DataGen agent failed: {e}",
            extra={"error": str(e), "query": query[:50]},
            exc_info=True,
        )
        return {
            **state,
            "error": f"DataGen execution failed: {str(e)}",
            "agent_result": {
                "success": False,
                "error": str(e),
            },
        }


async def rag_node(state: SupervisorState) -> SupervisorState:
    """Execute RAG agent for document search and querying.

    Args:
        state: Supervisor state with query

    Returns:
        Updated state with agent_result
    """
    from src.agents.rag.agent import rag_agent_invoke

    query = state.get("query", "")
    logger.info(f"Executing RAG agent for query: {query[:50]}...")

    try:
        # Call RAG agent with query (no file_paths from supervisor - assumes documents already ingested)
        result = await rag_agent_invoke(query=query)

        logger.info(
            f"RAG agent completed successfully",
            extra={"success": result.get("success"), "documents_count": len(result.get("data", {}).get("documents", []))},
        )

        return {
            **state,
            "agent_result": result,
        }

    except Exception as e:
        logger.error(
            f"RAG agent failed: {e}",
            extra={"error": str(e), "query": query[:50]},
            exc_info=True,
        )
        return {
            **state,
            "error": f"RAG execution failed: {str(e)}",
            "agent_result": {
                "success": False,
                "tool": "retrieve_docs",
                "data": {
                    "response": "",
                    "documents": [],
                    "backend": "chroma",
                },
                "error": str(e),
            },
        }


async def github_node(state: SupervisorState) -> SupervisorState:
    '''Execute GitHub agent for repository operations.
    
    Args:
        state: Supervisor state with query
        
    Returns:
        Updated state with agent_result
    '''
    from src.agents.github.agent import github_agent_invoke
    
    query = state.get("query", "")
    logger.info(f"Executing GitHub agent for query: {query[:50]}...")
    
    try:
        result = await github_agent_invoke(query=query, context=None, github_token=None)
        
        logger.info(
            f"GitHub agent completed successfully",
            extra={"success": result.get("success"), "operation": result.get("operation")}
        )
        
        return {
            **state,
            "agent_result": result,
        }
        
    except Exception as e:
        logger.error(
            f"GitHub agent failed: {e}",
            extra={"error": str(e), "query": query[:50]},
            exc_info=True
        )
        return {
            **state,
            "error": f"GitHub execution failed: {str(e)}",
            "agent_result": {
                "success": False,
                "tool": "github_operation",
                "error": str(e),
            },
        }


async def unknown_node(state: SupervisorState) -> SupervisorState:
    """Handle unknown intents.

    Args:
        state: Supervisor state with query

    Returns:
        Updated state with helpful error message
    """
    query = state.get("query", "")
    logger.warning(f"Unknown intent for query: {query[:50]}...")

    return {
        **state,
        "agent_result": {
            "success": False,
            "message": "I couldn't understand your request. Try one of these:\n"
            "- 'Generate 100 user records'\n"
            "- 'Create 50 rows of CSV data with email and phone'\n"
            "- 'Generate mock data in JSON format'",
        },
    }


def create_supervisor_graph():
    """Create and compile the supervisor workflow graph.

    Returns:
        Compiled LangGraph workflow
    """
    workflow = StateGraph(SupervisorState)

    # Add nodes
    workflow.add_node("classify", classify_intent)
    workflow.add_node("datagen_node", datagen_node)
    workflow.add_node("rag_node", rag_node)
    workflow.add_node("github_node", github_node)
    workflow.add_node("unknown_node", unknown_node)

    # Set entry point
    workflow.set_entry_point("classify")

    # Add conditional routing after classification
    workflow.add_conditional_edges(
        "classify",
        route_to_agent,
        {
            "datagen_node": "datagen_node",
            "rag_node": "rag_node",
            "github_node": "github_node",
            "unknown_node": "unknown_node",
        },
    )

    # All agent nodes lead to END
    workflow.add_edge("datagen_node", END)
    workflow.add_edge("rag_node", END)
    workflow.add_edge("github_node", END)
    workflow.add_edge("unknown_node", END)

    # Compile graph
    compiled_graph = workflow.compile()

    logger.info("Supervisor graph compiled successfully")
    return compiled_graph


# Export compiled supervisor
supervisor = create_supervisor_graph()


async def supervisor_invoke(query: str) -> dict:
    """Convenience function to invoke supervisor with a query.

    Args:
        query: User query string

    Returns:
        Dict with success, intent, model_used, result, and error fields
    """
    initial_state: SupervisorState = {
        "query": query,
        "intent": None,
        "model_used": None,
        "agent_result": None,
        "error": None,
    }

    logger.info(f"Supervisor invoked with query: {query[:100]}...")

    try:
        final_state = await supervisor.ainvoke(initial_state)

        result = {
            "success": final_state.get("error") is None and final_state.get("agent_result", {}).get("success", False) is not False,
            "intent": final_state.get("intent"),
            "model_used": final_state.get("model_used"),
            "result": final_state.get("agent_result"),
            "error": final_state.get("error"),
        }

        logger.info(
            f"Supervisor completed: intent={result['intent']}, success={result['success']}",
            extra={"intent": result["intent"], "success": result["success"]},
        )

        return result

    except Exception as e:
        logger.error(f"Supervisor invocation failed: {e}", extra={"error": str(e)}, exc_info=True)
        return {
            "success": False,
            "intent": None,
            "model_used": None,
            "result": None,
            "error": f"Supervisor execution failed: {str(e)}",
        }

