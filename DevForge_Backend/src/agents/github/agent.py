# src/agents/github/agent.py
"""
GitHub operations agent with v0.8 intelligence enhancements.
Integrates: repo discovery, commit generation, log parsing, confidence policy, workflows.
"""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import TypedDict, Literal, Optional, Dict, Any

from langgraph.graph import StateGraph, END

from src.core.model_router import ModelRouter
from src.core.audit import Timeline, EventType, generate_audit_id, get_audit_logger
from src.core.confidence import check_confidence
from src.core.session import get_session_manager
from src.core.config import settings
from src.core.features import FeatureFlags, Feature
from src.tools.github import tools as github_tools

# Import intelligence components
from src.agents.github.intelligence.repo_discovery import RepoDiscovery
from src.agents.github.intelligence.commit_generator import CommitGenerator
from src.agents.github.intelligence.log_parser import LogParser

logger = logging.getLogger(__name__)


class GitHubState(TypedDict):
    """Enhanced state for GitHub agent workflow."""
    query: str
    operation: Optional[str]
    parameters: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    error: Optional[str]

    # v0.8 additions
    context: Optional[Dict[str, Any]]  # Additional context (session_id, diff, error_log, etc)
    github_token: Optional[str]        # Transient: per-connection token, NEVER logged or audited
    audit_id: Optional[str]            # Audit tracking
    timeline: Optional[Any]            # Timeline object
    intent_confidence: Optional[float] # LLM confidence for intent
    repo_confidence: Optional[float]   # Fuzzy match confidence
    commit_confidence: Optional[float] # Commit message confidence


@dataclass
class IntelligenceBundle:
    """Per-token bundle of intelligence components.

    Each MCP connection gets an isolated bundle to prevent cross-user data leaks.
    Repo cache lives inside RepoDiscovery and is keyed by token_hash.
    """
    repo_discovery: Any
    commit_generator: Any
    log_parser: Any
    github_tools_instance: Any


# Per-token bundle cache: {sha256(token): IntelligenceBundle}
# Max 128 entries to prevent memory growth from many ephemeral connections.
_bundle_cache: OrderedDict[str, "IntelligenceBundle"] = OrderedDict()
_BUNDLE_CACHE_MAX = 128


def _get_token_hash(token: Optional[str]) -> str:
    """Return SHA256 hex digest of the token, or sentinel for env-token."""
    raw = token or settings.GITHUB_TOKEN or ""
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_intelligence_bundle(token: Optional[str] = None) -> IntelligenceBundle:
    """Get or create an IntelligenceBundle for the given token.

    Uses SHA256 hash of the token as cache key to avoid storing raw tokens
    in memory. Evicts oldest entry when cache reaches _BUNDLE_CACHE_MAX.
    """
    token_hash = _get_token_hash(token)

    if token_hash in _bundle_cache:
        # Move to end (LRU behavior: mark as recently used)
        _bundle_cache.move_to_end(token_hash)
        return _bundle_cache[token_hash]

    # Evict oldest entry if at capacity (FIFO portion of LRU)
    if len(_bundle_cache) >= _BUNDLE_CACHE_MAX:
        # Pop from left (least recently used)
        _bundle_cache.popitem(last=False)
        logger.info("IntelligenceBundle cache evicted oldest entry")

    gh_tools = github_tools.GitHubTools(token=token)
    repo_disc = RepoDiscovery(gh_tools)
    commit_gen = CommitGenerator()
    log_pars = LogParser()

    _bundle_cache[token_hash] = IntelligenceBundle(
        repo_discovery=repo_disc,
        commit_generator=commit_gen,
        log_parser=log_pars,
        github_tools_instance=gh_tools,
    )
    logger.info("Created new IntelligenceBundle for token_hash=%s", token_hash[:8])

    return _bundle_cache[token_hash]


async def parse_github_request(state: GitHubState) -> GitHubState:
    """Parse user query with v0.8 intelligence enhancements.
    
    Args:
        state: Current state with user query
        
    Returns:
        Updated state with operation, parameters, and confidence scores
    """
    query = state["query"]
    context = state.get("context", {})
    
    # Initialize audit tracking
    audit_id = generate_audit_id()
    timeline = Timeline(audit_id, "github_operation")
    timeline.add_event(EventType.OPERATION_START, f"Parsing: {query[:50]}")
    
    logger.info(f"[{audit_id}] Parsing GitHub request: {query[:100]}...")
    
    try:
        # Use model router to get appropriate model
        router = ModelRouter()
        model = router.select_model_by_task("github", prefer_local=False)
        
        # Enhanced classification prompt
        classification_prompt = f"""Analyze this GitHub-related request and extract the operation and parameters.

User Request: {query}

Available Operations:
- list_repos: List user repositories
- create_repo: Create a new repository
- create_issue: Create an issue in a repository (can parse from error_log if provided)
- commit_file: Commit/update a file in a repository (can auto-generate message if diff provided)
- create_pull_request: Create a pull request

Respond with ONLY a JSON object in this exact format (no markdown, no explanation):
{{
  "operation": "operation_name",
  "parameters": {{
    "param1": "value1"
  }},
  "confidence": 0.95
}}

For list_repos, parameters can include: visibility, sort, limit
For create_repo, parameters must include: name, and can include: description, private
For create_issue, parameters must include: repo_name, title, and can include: body, labels, assignees
For commit_file, parameters must include: repo_name, file_path, content, commit_message, and can include: branch
For create_pull_request, parameters must include: repo_name, title, head, and can include: base, body, draft

Important: Include a confidence score (0.0 to 1.0) indicating how confident you are in the classification.
Extract all relevant parameters from the user request."""

        # Call LLM for classification
        timeline.start_step("llm_classify", "Classifying user intent with LLM")
        
        start_time = time.time()
        response = await router.invoke_with_fallback(
            model_name=model,
            prompt=classification_prompt,
            fallback_models=["deepseek-v3.1:671b-cloud"]
        )
        duration = time.time() - start_time
        logger.info(
            f"LLM Classification complete in {duration:.2f}s",
            extra={
                "step": "llm_classify",
                "duration_ms": int(duration * 1000),
                "model": model
            }
        )
        
        timeline.complete_step("llm_classify")
        
        # Parse LLM response
        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        
        parsed = json.loads(response_text)
        operation = parsed.get("operation")
        parameters = parsed.get("parameters", {})
        intent_confidence = parsed.get("confidence", 0.8)  # Default if not provided
        
        logger.info(
            f"[{audit_id}] Parsed operation: {operation} (confidence: {intent_confidence})",
            extra={"operation": operation, "confidence": intent_confidence}
        )
        
        # Check confidence policy for intent
        confidence_check = check_confidence(
            operation="intent_classification",
            confidence=intent_confidence,
            context={"intent": parsed, "query": query}
        )
        
        if confidence_check:
            # Low confidence - return for user confirmation
            timeline.add_event(EventType.OPERATION_COMPLETE, "Low confidence - needs confirmation")
            return {
                **state,
                "audit_id": audit_id,
                "intent_confidence": intent_confidence,
                "result": confidence_check,
                "timeline": timeline
            }
        
        return {
            **state,
            "operation": operation,
            "parameters": parameters,
            "audit_id": audit_id,
            "timeline": timeline,
            "intent_confidence": intent_confidence,
        }
        
    except Exception as e:
        logger.error(
            f"[{audit_id}] Failed to parse GitHub request: {e}",
            extra={"error": str(e)},
            exc_info=True
        )
        timeline.add_event(EventType.OPERATION_FAILED, f"Parse failed: {e}")
        
        return {
            **state,
            "error": f"Failed to parse GitHub request: {str(e)}",
            "audit_id": audit_id,
            "timeline": timeline,
        }


async def enhance_with_intelligence(state: GitHubState) -> GitHubState:
    """Apply intelligence enhancements (fuzzy repo, commit gen, log parse).
    
    Args:
        state: Current state
        
    Returns:
        Enhanced state with intelligence applied
    """
    operation = state.get("operation")
    parameters = state.get("parameters", {})
    context = state.get("context", {})
    timeline = state.get("timeline")
    audit_id = state.get("audit_id")
    token = state.get("github_token")  # transient field — never log this

    bundle = _get_intelligence_bundle(token)
    repo_discovery = bundle.repo_discovery
    commit_generator = bundle.commit_generator
    log_parser = bundle.log_parser

    try:
        # 1. Fuzzy repo matching (if repo_name provided but might be ambiguous)
        if "repo_name" in parameters and FeatureFlags.is_enabled(Feature.FUZZY_SEARCH):
            timeline.start_step("repo_discovery", "Fuzzy matching repository name")
            
            repo_name = parameters["repo_name"]
            
            # Try fuzzy search
            best_match = await repo_discovery.get_best_match(
                query=repo_name,
                confidence_threshold=0.85
            )
            
            if best_match:
                logger.info(
                    f"[{audit_id}] Fuzzy matched repo: {repo_name} → {best_match.full_name} "
                    f"(confidence: {best_match.confidence})"
                )
                parameters["repo_name"] = best_match.full_name
                state["repo_confidence"] = best_match.confidence
                timeline.complete_step("repo_discovery", f"Matched to {best_match.full_name}")
            else:
                # Ambiguous - need clarification
                matches = await repo_discovery.fuzzy_search(repo_name, max_results=3)
                if matches and matches[0].confidence < 0.85:
                    timeline.add_event(EventType.OPERATION_COMPLETE, "Repo ambiguous - needs clarification")
                    return {
                        **state,
                        "result": repo_discovery.format_disambiguation_response(matches),
                        "timeline": timeline
                    }
                timeline.complete_step("repo_discovery", "Using original repo name")
        
        # 2. Auto-generate commit message (if diff provided and message not present)
        if (operation == "commit_file" and 
            context.get("diff") and 
            not parameters.get("commit_message") and
            FeatureFlags.is_enabled(Feature.COMMIT_GENERATION)):
            
            timeline.start_step("commit_gen", "Generating commit message from diff")
            
            commit_msg = await commit_generator.generate(
                repo=parameters.get("repo_name", "unknown"),
                diff=context["diff"]
            )
            
            parameters["commit_message"] = commit_msg.text
            state["commit_confidence"] = commit_msg.confidence
            
            logger.info(
                f"[{audit_id}] Generated commit: {commit_msg.text} "
                f"(confidence: {commit_msg.confidence})"
            )
            
            timeline.complete_step("commit_gen", f"Generated: {commit_msg.text[:50]}")
            
            # Check if should create draft PR instead (medium confidence)
            if 0.85 <= commit_msg.confidence < 0.90:
                parameters["draft"] = True
                state["_create_draft_reason"] = "Medium commit confidence - creating draft PR"
        
        # 3. Parse error log to issue (if error_log provided)
        if (operation == "create_issue" and 
            context.get("error_log") and
            FeatureFlags.is_enabled(Feature.LOG_PARSING)):
            
            timeline.start_step("log_parse", "Parsing error log")
            
            parsed_issue = await log_parser.parse(
                log=context["error_log"],
                language=context.get("language")
            )
            
            # Override/enhance parameters with parsed data
            parameters["title"] = parsed_issue.title
            parameters["body"] = parsed_issue.body
            parameters["labels"] = parsed_issue.labels
            
            logger.info(f"[{audit_id}] Parsed error log to issue: {parsed_issue.title}")
            timeline.complete_step("log_parse", f"Created issue: {parsed_issue.title[:50]}")
        
        return {
            **state,
            "parameters": parameters,
            "timeline": timeline,
        }
        
    except Exception as e:
        logger.error(f"[{audit_id}] Intelligence enhancement failed: {e}", exc_info=True)
        timeline.add_event(EventType.STEP_FAILED, f"Intelligence failed: {e}")
        
        # Continue without enhancements
        return {
            **state,
            "timeline": timeline,
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
    timeline = state.get("timeline")
    audit_id = state.get("audit_id")
    token = state.get("github_token")  # transient field — never log this

    # Get the bundle for this token so we use the correct authenticated client
    bundle = _get_intelligence_bundle(token)
    gh_tools = bundle.github_tools_instance

    if not operation:
        return {
            **state,
            "error": "No operation determined",
        }

    logger.info(
        f"[{audit_id}] Executing GitHub operation: {operation}",
        extra={"operation": operation}  # parameters intentionally omitted — may contain tokens
    )

    timeline.start_step(f"execute_{operation}", f"Executing {operation}")

    try:
        # Execute operation based on type using per-token tools instance
        if operation == "list_repos":
            result = gh_tools.list_repos(**parameters)

        elif operation == "create_repo":
            result = gh_tools.create_repo(**parameters)

        elif operation == "create_issue":
            result = gh_tools.create_issue(**parameters)

        elif operation == "commit_file":
            result = gh_tools.commit_file(**parameters)

        elif operation == "create_pull_request":
            result = gh_tools.create_pull_request(**parameters)

        else:
            raise ValueError(f"Unknown GitHub operation: {operation}")
        
        timeline.complete_step(f"execute_{operation}", f"Completed successfully")
        timeline.add_event(EventType.OPERATION_COMPLETE, f"{operation} completed")
        
        # Store audit log
        audit_logger = get_audit_logger()
        await audit_logger.store_timeline(timeline)
        
        logger.info(
            f"[{audit_id}] GitHub operation completed successfully",
            extra={"operation": operation}
        )
        
        return {
            **state,
            "result": {
                "success": True,
                "operation": operation,
                "data": result,
                "audit_id": audit_id,
                "timeline": timeline.to_dict(),
                "intent_confidence": state.get("intent_confidence"),
                "repo_confidence": state.get("repo_confidence"),
                "commit_confidence": state.get("commit_confidence"),
            },
        }
        
    except Exception as e:
        timeline.fail_step(f"execute_{operation}", str(e))
        timeline.add_event(EventType.OPERATION_FAILED, f"{operation} failed: {e}")
        
        logger.error(
            f"[{audit_id}] GitHub operation failed: {e}",
            extra={"operation": operation, "error": str(e)},
            exc_info=True
        )
        
        return {
            **state,
            "error": f"GitHub operation failed: {str(e)}",
            "result": {
                "success": False,
                "operation": operation,
                "error": str(e),
                "audit_id": audit_id,
                "timeline": timeline.to_dict() if timeline else None,
            },
        }


def should_enhance(state: GitHubState) -> Literal["enhance", "execute", "error"]:
    """Determine if intelligence enhancement should be applied.
    
    Args:
        state: Current state
        
    Returns:
        Next node to execute
    """
    if state.get("error"):
        return "error"
    if not state.get("operation"):
        return "error"
    
    # Check if result already set (e.g., from confidence check)
    if state.get("result"):
        return "error"  # Will return the result as-is
    
    # Apply enhancements if enabled
    return "enhance"


def should_execute(state: GitHubState) -> Literal["execute", "error"]:
    """Determine if operation should be executed.
    
    Args:
        state: Current state
        
    Returns:
        Next node to execute
    """
    if state.get("error"):
        return "error"
    if state.get("result"):  # Already have result (e.g., needs clarification)
        return "error"
    if not state.get("operation"):
        return "error"
    return "execute"


async def handle_error(state: GitHubState) -> GitHubState:
    """Handle errors or early returns in the workflow.
    
    Args:
        state: Current state with error or result
        
    Returns:
        Updated state with error result
    """
    # If result already set (e.g., needs_clarification), return as-is
    if state.get("result"):
        return state
    
    error = state.get("error", "Unknown error occurred")
    audit_id = state.get("audit_id")
    timeline = state.get("timeline")
    
    logger.error(f"[{audit_id}] GitHub agent error: {error}")
    
    if timeline:
        timeline.add_event(EventType.OPERATION_FAILED, error)
    
    return {
        **state,
        "result": {
            "success": False,
            "error": error,
            "audit_id": audit_id,
            "timeline": timeline.to_dict() if timeline else None,
        },
    }


# Build enhanced LangGraph workflow
workflow = StateGraph(GitHubState)

# Add nodes
workflow.add_node("parse", parse_github_request)
workflow.add_node("enhance", enhance_with_intelligence)
workflow.add_node("execute", execute_github_operation)
workflow.add_node("error", handle_error)

# Add edges
workflow.set_entry_point("parse")
workflow.add_conditional_edges(
    "parse",
    should_enhance,
    {
        "enhance": "enhance",
        "execute": "execute",
        "error": "error",
    }
)
workflow.add_conditional_edges(
    "enhance",
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


# Enhanced convenience function for invocation
async def github_agent_invoke(
    query: str,
    context: Optional[Dict[str, Any]] = None,
    github_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Invoke enhanced GitHub agent with a user query.

    Args:
        query: User query describing GitHub operation
        context: Optional context (session_id, diff, error_log, files, etc.)
                 Must NOT contain 'github_token' — strip it at the router layer.
        github_token: Optional per-connection GitHub PAT. Treated as transient;
                      never logged, audited, or serialized into response.

    Returns:
        Result dictionary with success status, data/error, and audit info
    """
    logger.info(f"Invoking GitHub agent with query: {query[:100]}...")

    # Defensive guard: if caller forgot to strip the token from context, pop it here
    safe_context = dict(context or {})
    if "github_token" in safe_context:
        logger.warning("github_token found inside context dict — stripping at agent boundary")
        github_token = github_token or safe_context.pop("github_token")

    initial_state: GitHubState = {
        "query": query,
        "operation": None,
        "parameters": None,
        "result": None,
        "error": None,
        "context": safe_context,
        "github_token": github_token,   # transient \u2014 stays in state, never serialized out
        "audit_id": None,
        "timeline": None,
        "intent_confidence": None,
        "repo_confidence": None,
        "commit_confidence": None,
    }
    
    try:
        final_state = await github_graph.ainvoke(initial_state)
        result = final_state.get("result", {
            "success": False,
            "error": "No result produced",
        })
        
        logger.info(
            f"GitHub agent completed",
            extra={"success": result.get("success"), "audit_id": final_state.get("audit_id")}
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