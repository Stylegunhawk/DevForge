# src/agents/github/agent.py
"""
GitHub operations agent with v0.8 intelligence enhancements.
Integrates: repo discovery, commit generation, log parsing, confidence policy, workflows.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import TypedDict, Literal, Optional, Dict, Any
from github import GithubException
from pydantic import ValidationError

from src.agents.github.schemas import validate_op_params

from langgraph.graph import StateGraph, END

from src.core.model_router import ModelRouter
from src.core.audit import Timeline, EventType, generate_audit_id, get_audit_logger
from src.core.confidence import check_confidence
from src.core.session import get_session_manager
from src.core.config import settings
from src.core.features import FeatureFlags, Feature
from src.core.risk import RiskGate, RiskViolation
from src.tools.github import tools as github_tools

# Import intelligence components
from src.agents.github.intelligence.repo_discovery import RepoDiscovery
from src.agents.github.intelligence.commit_generator import CommitGenerator
from src.agents.github.intelligence.log_parser import LogParser

# Import specialized tools
from src.tools.scaffold import scaffold_repository_invoke
from src.tools.changelog import generate_changelog_invoke
from src.tools.ci_diagnostics import analyze_ci_failure_invoke

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
    """Return SHA256 hex digest of the token, or sentinel for empty token."""
    if not token:
        return "no_token_provided"
    return hashlib.sha256(token.encode()).hexdigest()


def _get_intelligence_bundle(token: Optional[str] = None) -> IntelligenceBundle:
    """Get or create an IntelligenceBundle for the given token.

    Uses SHA256 hash of the token as cache key to avoid storing raw tokens
    in memory. Evicts oldest entry when cache reaches _BUNDLE_CACHE_MAX.
    """
    if not token:
        raise ValueError(
            "GitHub token required. Please provide a valid GitHub Personal Access Token from the frontend."
        )
    
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
- scaffold_repo: create repository from template, scaffold new project with CI/CD
- generate_changelog: generate changelog or release notes between git tags/commits
- analyze_ci_failure: analyze CI/CD pipeline failure, debug GitHub Actions workflow
- browse_files: list files in repo or directory (returns file tree)
- read_file: read contents of a specific file
- search_code: search code across repository

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
- For commit_file, parameters must include: repo_name, commit_message, and can include: file_path, content, branch. (Intelligence will try to find the file if file_path or content the user is thinking of is an uploaded file).
For create_pull_request, parameters must include: repo_name, title, head, and can include: base, body, draft
For scaffold_repo, parameters must include: name, template, and can include: description, private, force
For generate_changelog, parameters must include: repo_name, and can include: from_tag, to_tag, format
For analyze_ci_failure, parameters must include: repo_name, run_id, and can include: pr_number
For browse_files, parameters must include: repo_name, and can include: path (default: "/")
For read_file, parameters must include: repo_name, file_path
For search_code, parameters must include: query, and can include: repo_name

Important: Include a confidence score (0.0 to 1.0) indicating how confident you are in the classification.
Extract all relevant parameters from the user request."""

        # Call LLM for classification
        timeline.start_step("llm_classify", "Classifying user intent with LLM")
        
        start_time = time.time()
        try:
            # Phase 3: Add 30s timeout for LLM classification
            response = await asyncio.wait_for(
                router.invoke_with_fallback(
                    model_name=model,
                    prompt=classification_prompt,
                    fallback_models=["deepseek-v3.1:671b-cloud"]
                ),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.error(f"[{audit_id}] LLM classification timed out after 30s")
            timeline.fail_step("llm_classify", "LLM Classification Timeout")
            return {
                **state,
                "error": "LLM classification timed out. The system is currently slow, please try again later.",
                "result": {
                    "success": False,
                    "error": "LLM Timeout",
                    "audit_id": audit_id,
                    "timeline": timeline.to_dict() if timeline else None
                }
            }
        
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
    
    logger.info(f"[{audit_id}] [DEBUG] Starting enhancement. Operation: {operation}")
    logger.info(f"[{audit_id}] [DEBUG] Current parameters: {parameters}")
    logger.info(f"[{audit_id}] [DEBUG] Context keys: {list(context.keys())}")
    if "available_files" in context:
        logger.info(f"[{audit_id}] [DEBUG] available_files in context: {[f.get('filename') for f in context['available_files']]}")
    else:
        logger.warning(f"[{audit_id}] [DEBUG] available_files NOT in context")
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
        
        # 4. Commit file context injection (before validation)
        if (operation == "commit_file" and 
            "file_url" not in parameters and 
            "content" not in parameters):
            
            available_files = context.get("available_files", [])
            file_path = parameters.get("file_path", "").lower()
            logger.info(f"[{audit_id}] [DEBUG] commit_file injection started. file_path: '{file_path}', available_files count: {len(available_files)}")

            # Clean path to handle Unicode ellipsis, underscores, hyphens, and parentheses
            file_path = file_path.replace("…", " ").replace("...", " ").replace("_", " ").replace("-", " ").replace("(", " ").replace(")", " ")
            
            # Fuzzy match or single-file fallback
            matches = []
            
            # Case 1: file_path provided - use fuzzy matching
            if file_path:
                words = [w for w in file_path.split() if len(w) >= 3]
                logger.info(f"[{audit_id}] [DEBUG] Split file_path words: {words}")
                
                for f in available_files:
                    fname = f["filename"].lower()
                    if any(word in fname for word in words):
                        matches.append(f)
                
                logger.info(f"[{audit_id}] [DEBUG] Fuzzy matches found: {[m['filename'] for m in matches]}")
            
            # Case 2: No specific file mentioned or fuzzy match failed - if only one file exist, pick it!
            if not matches and len(available_files) == 1:
                logger.info(f"[{audit_id}] [DEBUG] Single file fallback: {available_files[0]['filename']}")
                matches = [available_files[0]]
            
            # Disambiguation: Pick most recent if multiple matches
            matched = None
            if matches:
                # Sort by createdAt if available, otherwise just pick first
                matches.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
                matched = matches[0]
            
            # Fallback: first PDF if no match and multiple files exist
            if not matched and available_files:
                matched = next(
                    (f for f in available_files if "pdf" in f.get("file_type", "").lower()), 
                    available_files[0]
                )
            
            if matched:
                parameters["file_url"] = matched["file_url"]
                logger.info(f"Pre-validation file injection: {matched['filename']} → {matched['file_url']}")
                if timeline:
                    timeline.add_event(EventType.STEP_COMPLETE, f"Injected file_url: {matched['filename']}")
        
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


async def risk_gate_check(state: GitHubState) -> GitHubState:
    """Enforce risk requirements for the operation.
    
    Args:
        state: Current state with operation and context
        
    Returns:
        State with error if risk requirements not met, or passes through
    """
    operation = state.get("operation")
    context = state.get("context", {})
    audit_id = state.get("audit_id")
    timeline = state.get("timeline")
    
    if not operation:
        return state
    
    try:
        if timeline:
            timeline.start_step("risk_gate", f"Risk check for {operation}")
        
        # Extract risk confirmation from context if present
        risk_context = {}
        if "risk_confirmed" in context:
            risk_context["confirmed"] = context["risk_confirmed"]
        if "risk_reason" in context:
            risk_context["reason"] = context["risk_reason"]
        
        # Check risk requirements
        violation = RiskGate.check(operation, risk_context)
        
        if violation:
            error_msg = f"Risk gate blocked: {violation.message}"
            logger.warning(f"[{audit_id}] {error_msg}")
            
            if timeline:
                timeline.fail_step("risk_gate", error_msg)
            
            return {
                **state,
                "error": error_msg,
                "timeline": timeline,
                "risk_violation": {
                    "operation": violation.operation,
                    "risk_level": violation.risk_level.value,
                    "missing_requirements": violation.missing_requirements
                }
            }
        
        if timeline:
            timeline.complete_step("risk_gate", f"Risk check passed ({violation.risk_level.value if violation else 'LOW'})")
        
        logger.info(f"[{audit_id}] Risk gate passed for {operation}")
        return state
        
    except Exception as e:
        error_msg = f"Risk gate error: {str(e)}"
        logger.error(f"[{audit_id}] {error_msg}")
        
        if timeline:
            timeline.fail_step("risk_gate", error_msg)
        
        return {
            **state,
            "error": error_msg,
            "timeline": timeline
        }


def validate_parameters(state: GitHubState) -> GitHubState:
    """Strictly validate operation parameters using Pydantic schemas.
    
    Args:
        state: Current state
        
    Returns:
        Validated state or state with error
    """
    operation = state.get("operation")
    parameters = state.get("parameters", {})
    audit_id = state.get("audit_id")
    timeline = state.get("timeline")
    
    if not operation:
        return state
        
    try:
        if timeline:
            timeline.start_step("validation", f"Validating parameters for {operation}")
        
        # Phase 4: Strict Pydantic validation
        validated = validate_op_params(operation, parameters)
        
        if timeline:
            timeline.complete_step("validation", "Validation passed")
        return {
            **state,
            "parameters": validated,
            "timeline": timeline
        }
    except ValidationError as e:
        error_details = e.errors()[0]
        loc = error_details.get("loc", [])
        field = loc[-1] if loc else "general"
        msg = error_details.get("msg", "invalid value")
        friendly_error = f"Validation failed for {operation}: {field} -> {msg}"
        
        logger.warning(f"[{audit_id}] Validation failed: {friendly_error}")
        if timeline:
            timeline.fail_step("validation", friendly_error)
        
        return {
            **state,
            "error": friendly_error,
            "timeline": timeline
        }
    except Exception as e:
        logger.error(f"[{audit_id}] Unexpected validation error: {e}")
        return {
            **state,
            "error": f"Validation error: {str(e)}",
            "timeline": timeline
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

    if timeline:
        timeline.start_step(f"execute_{operation}", f"Executing {operation}")

    try:
        loop = asyncio.get_event_loop()
        
        # Phase 3: Add 15s timeout for GitHub API operations
        async def run_operation():
            # Execute operation based on type using per-token tools instance
            # All GitHubTools methods are sync - wrap in executor for async safety
            if operation == "list_repos":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.list_repos(**parameters)
                )

            elif operation == "create_repo":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.create_repo(**parameters)
                )

            elif operation == "create_issue":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.create_issue(**parameters)
                )

            elif operation == "commit_file":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.commit_file(**parameters)
                )

            elif operation == "create_pull_request":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.create_pull_request(**parameters)
                )

            elif operation == "browse_files":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.browse_files(**parameters)
                )

            elif operation == "read_file":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.read_file(**parameters)
                )

            elif operation == "search_code":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.search_code(**parameters)
                )
                
            elif operation == "scaffold_repo":
                # Pass the authenticated gh_tools instance
                return await scaffold_repository_invoke(parameters, github_tools=gh_tools)

            elif operation == "generate_changelog":
                return await generate_changelog_invoke(parameters, github_tools=gh_tools)

            elif operation == "analyze_ci_failure":
                return await analyze_ci_failure_invoke(parameters, github_tools=gh_tools)

            else:
                raise ValueError(f"Unknown GitHub operation: {operation}")

        result = await asyncio.wait_for(run_operation(), timeout=15.0)
        
        if timeline:
            timeline.complete_step(f"execute_{operation}", f"Completed successfully")
            timeline.add_event(EventType.OPERATION_COMPLETE, f"{operation} completed")
        
        executed_at = time.time()
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
                "timeline": timeline.to_dict() if timeline else None,
                "intent_confidence": state.get("intent_confidence"),
                "repo_confidence": state.get("repo_confidence"),
                "commit_confidence": state.get("commit_confidence"),
                # Phase 4: Rollback context
                "rollback_context": {
                    "executed_at": executed_at,
                    "repo_name": parameters.get("repo_name"),
                    "operation": operation
                }
            },
        }
        
    except asyncio.TimeoutError:
        logger.error(f"[{audit_id}] GitHub operation {operation} timed out after 15s")
        if timeline:
            timeline.fail_step(f"execute_{operation}", "GitHub API Timeout")
        return {
            **state,
            "error": f"The GitHub operation '{operation}' timed out. The API is responding slowly.",
            "result": {
                "success": False,
                "error": "Timeout Error",
                "audit_id": audit_id,
                "timeline": timeline.to_dict() if timeline else None
            }
        }
    except GithubException as e:
        status = getattr(e, "status", 500)
        error_msg = str(e.data.get("message", e)) if hasattr(e, "data") else str(e)
        
        # Categorize error
        category = "GitHub API Error"
        friendly_msg = f"GitHub operation failed: {error_msg}"
        
        if status == 404:
            category = "Not Found"
            repo_name = parameters.get("repo_name", "unknown")
            friendly_msg = f"Repository or resource not found: '{repo_name}'. Please verify the name and your access permissions."
        elif status == 401:
            category = "Authentication Failed"
            friendly_msg = "Authentication failed. Your GitHub token may be invalid or expired."
        elif status == 403:
            category = "Permission Denied"
            if "rate limit" in error_msg.lower():
                friendly_msg = "GitHub API rate limit exceeded. Please try again later."
            else:
                friendly_msg = "Access forbidden. You don't have permission to perform this action on the repository."
        
        logger.error(f"[{audit_id}] {category} ({status}): {error_msg}")
        if timeline:
            timeline.fail_step(f"execute_{operation}", friendly_msg)
        
        return {
            **state,
            "error": friendly_msg,
            "result": {
                "success": False,
                "error": category,
                "status": status,
                "audit_id": audit_id,
                "timeline": timeline.to_dict() if timeline else None
            }
        }
    except Exception as e:
        if timeline:
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
    finally:
        # Store audit log - ensures persistence on both success and failure
        try:
            audit_logger = get_audit_logger()
            await audit_logger.store_timeline(timeline)
        except Exception as audit_err:
            logger.error(f"[{audit_id}] Failed to store timeline: {audit_err}")


def should_enhance(state: GitHubState) -> Literal["enhance", "validate", "error"]:
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
    
    # Phase 4: Route to validation instead of execute
    return "enhance"


def should_execute(state: GitHubState) -> Literal["execute", "error"]:
    """Determine if operation should be executed after validation.
    
    Args:
        state: Current state
        
    Returns:
        Next node to execute
    """
    if state.get("error"):
        return "error"
    if state.get("result"):
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
workflow.add_node("validate", validate_parameters)
workflow.add_node("risk_gate", risk_gate_check)
workflow.add_node("execute", execute_github_operation)
workflow.add_node("error", handle_error)

# Add edges
workflow.set_entry_point("parse")
workflow.add_conditional_edges(
    "parse",
    should_enhance,
    {
        "enhance": "enhance",
        "validate": "validate",
        "error": "error",
    }
)
workflow.add_edge("enhance", "validate")
workflow.add_conditional_edges(
    "validate",
    lambda state: "risk_gate" if not state.get("error") else "error",
    {
        "risk_gate": "risk_gate",
        "error": "error",
    }
)
workflow.add_conditional_edges(
    "risk_gate",
    lambda state: "execute" if not state.get("error") else "error",
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