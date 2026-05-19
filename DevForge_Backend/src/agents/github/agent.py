# src/agents/github/agent.py
"""
GitHub operations agent with v0.8 intelligence enhancements.
Integrates: repo discovery, commit generation, log parsing, confidence policy, workflows.
"""

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import TypedDict, Literal, Optional, Dict, Any, NotRequired
from github import GithubException
from pydantic import ValidationError

from src.agents.github.schemas import validate_op_params

from langgraph.graph import StateGraph, END

from src.core.model_router import ModelRouter
from src.core.audit import Timeline, EventType, generate_audit_id, get_audit_logger, get_escalation_logger
from src.core.confidence import check_confidence
from src.core.session import get_session_manager
from src.core.config import settings
from src.core.features import FeatureFlags, Feature
from src.core.risk import RiskGate, RiskViolation
from src.core.policy import PolicyGate, PolicyViolation
from src.tools.github import tools as github_tools

# Import intelligence components
from src.agents.github.intelligence.repo_discovery import RepoDiscovery
from src.agents.github.intelligence.commit_generator import CommitGenerator
from src.agents.github.intelligence.log_parser import LogParser

# Import specialized tools
from src.tools.scaffold import scaffold_repository_invoke
from src.tools.changelog import generate_changelog_invoke
from src.tools.ci_diagnostics import analyze_ci_failure_invoke

from src.workers.tasks.usage_tasks import log_llm_usage

logger = logging.getLogger(__name__)

# Regex that matches an exact "owner/repo" string (one slash, non-empty on both sides).
# Used by enhance_with_intelligence to skip fuzzy repo lookup on structured calls.
_EXACT_REPO_RE = re.compile(r"^[^/]+/[^/]+$")


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
    tenant_id: Optional[str]           # Phase 2: per-tenant tracking
    integration_name: Optional[str]    # Phase 2: integration identifier
    user_id: Optional[str]             # NEW: Phase 4 analytics support

    # NEW: structured-call support — defaults to "natural_language" if absent
    entry_method: NotRequired[Literal["natural_language", "structured"]]


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
# Lock guards check-and-construct so concurrent cold-cache requests for the
# same token don't both build a bundle and race on dict mutation.
_bundle_cache: OrderedDict[str, "IntelligenceBundle"] = OrderedDict()
_BUNDLE_CACHE_MAX = 128
_bundle_cache_lock = asyncio.Lock()


def _get_token_hash(token: Optional[str]) -> str:
    """Return SHA256 hex digest of the token, or sentinel for empty token."""
    if not token:
        return "no_token_provided"
    return hashlib.sha256(token.encode()).hexdigest()


async def _get_intelligence_bundle(token: Optional[str] = None) -> IntelligenceBundle:
    """Get or create an IntelligenceBundle for the given token.

    Uses SHA256 hash of the token as cache key to avoid storing raw tokens
    in memory. Evicts oldest entry when cache reaches _BUNDLE_CACHE_MAX.
    Async + lock-guarded to prevent duplicate construction under concurrent
    cold-cache hits.
    """
    if not token:
        raise ValueError(
            "GitHub token required. Please provide a valid GitHub Personal Access Token from the frontend."
        )

    token_hash = _get_token_hash(token)

    async with _bundle_cache_lock:
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
    _entry_method = state.get("entry_method", "natural_language")
    _parse_desc = f"Parsing: {query[:60] if query else state.get('operation', '')}"
    timeline.add_event(EventType.OPERATION_START, _parse_desc, entry_method=_entry_method)
    
    logger.info(f"[{audit_id}] Parsing GitHub request: {query[:100]}...")

    # NEW: structured-call early return — skip LLM classification entirely
    if state.get("entry_method") == "structured":
        # operation and parameters were pre-populated by github_agent_invoke
        state["intent_confidence"] = 1.0
        state["audit_id"] = audit_id
        state["timeline"] = timeline
        # Emit a step_complete event recording the LLM skip
        timeline.add_event(
            EventType.STEP_COMPLETE,
            "Skipped LLM intent classification — structured call",
            step="llm_classify",
            skipped=True,
            reason="structured_call",
            entry_method="structured",
        )
        return state

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
- close_issue: Close an existing issue by number in a repository
- update_issue: Update an issue's title, body, state, labels, or assignees
- add_comment: Add a comment to an existing issue
- list_commits: List commits in a repository for a specific branch
- get_commit: Get details of a specific commit by SHA
- commit_file: Commit/update a file in a repository (can auto-generate message if diff provided)
- create_pull_request: Create a pull request
- scaffold_repo: create repository from template, scaffold new project with CI/CD
- generate_changelog: generate changelog or release notes between git tags/commits
- analyze_ci_failure: analyze CI/CD pipeline failure, debug GitHub Actions workflow
- browse_files: list files in repo or directory (returns file tree)
- read_file: read contents of a specific file
- search_code: search code across repository
- list_branches: list all branches in a repository
- create_branch: create a new branch in a repository
- delete_branch: delete a branch from a repository (HIGH risk — will be blocked without confirmation)
- delete_repo: permanently delete an entire repository (CRITICAL risk — requires confirmation + reason)
- list_releases: List GitHub releases for a repository
- create_release: Create a new GitHub release with a tag
- trigger_workflow: Trigger a GitHub Actions workflow dispatch event
- create_webhook: Create a webhook for a repository to receive GitHub events
- list_webhooks: List all webhooks configured for a repository
- delete_webhook: Delete a webhook from a repository

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
For close_issue, parameters must include: repo_name, issue_number
For update_issue, parameters must include: repo_name, issue_number, and can include: title, body, state, labels, assignees
For add_comment, parameters must include: repo_name, issue_number, body
For list_commits, parameters must include: repo_name, and can include: branch, limit, author, since, until
For get_commit, parameters must include: repo_name, sha
- For commit_file, parameters must include: repo_name, commit_message, and can include: file_path, content, branch. (Intelligence will try to find the file if file_path or content the user is thinking of is an uploaded file).
For create_pull_request, parameters must include: repo_name, title, head, and can include: base, body, draft
For scaffold_repo, parameters must include: name, template, and can include: description, private, force
For generate_changelog, parameters must include: repo_name, and can include: from_tag, to_tag, format
For analyze_ci_failure, parameters must include: repo_name, run_id, and can include: pr_number
For browse_files, parameters must include: repo_name, and can include: path (default: "/")
For read_file, parameters must include: repo_name, file_path
For search_code, parameters must include: query, and can include: repo_name
For list_branches, parameters must include: repo_name
For create_branch, parameters must include: repo_name, branch_name, and can include: from_branch (default: "main")
For delete_branch, parameters must include: repo_name, branch_name
For delete_repo, parameters must include: repo_name in EXACT 'owner/repo' format. Never infer or abbreviate the repo name.
For list_releases, parameters must include: repo_name, and can include: limit
For create_release, parameters must include: repo_name, tag_name, name, and can include: body, draft, prerelease, target_commitish
For trigger_workflow, parameters must include: repo_name, workflow_id, and can include: ref, inputs
For create_webhook, parameters must include: repo_name, url, and can include: events, content_type, active, secret
For list_webhooks, parameters must include: repo_name
For delete_webhook, parameters must include: repo_name, hook_id

Important: Include a confidence score (0.0 to 1.0) indicating how confident you are in the classification.
Extract all relevant parameters from the user request."""

        # Call LLM for classification
        timeline.start_step("llm_classify", "Classifying user intent with LLM")
        
        start_time = time.time()
        try:
            # Phase 2: Use invoke_with_usage with auto-logging
            usage_result = await asyncio.wait_for(
                router.invoke_with_usage(
                    model_name=model,
                    prompt=classification_prompt,
                    fallback_models=["deepseek-v3.1:671b-cloud"],
                    tenant_id=state.get("tenant_id"),
                    integration_name=state.get("integration_name"),
                    task_type="github_intent_classification",
                    user_id=state.get("user_id")  # NEW: Pass user_id to ModelRouter
                ),
                timeout=30.0
            )
            response_text = usage_result.content
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
        response_text = response_text.strip()
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
    query = state.get("query")
    _entry_method = state.get("entry_method", "natural_language")

    logger.debug(f"[{audit_id}] Starting enhancement. Operation: {operation}")
    logger.debug(f"[{audit_id}] Current parameters: {parameters}")
    logger.debug(f"[{audit_id}] Context keys: {list(context.keys())}")
    if "available_files" in context:
        logger.debug(f"[{audit_id}] available_files in context: {[f.get('filename') for f in context['available_files']]}")
    else:
        logger.debug(f"[{audit_id}] available_files NOT in context")
    token = state.get("github_token")  # transient field — never log this

    # === Disambiguation session restore (Slice 2) ===
    _dis_session_id = context.get("session_id")
    _dis_selected_repo = context.get("selected_repo")
    if _dis_session_id and _dis_selected_repo:
        try:
            _session_mgr = get_session_manager()
            _session = await _session_mgr.get(_dis_session_id, state.get("tenant_id") or "unknown")
            if _session and _session.get("kind") == "disambiguation":
                _params = {**(_session.get("params_pending") or {}), "repo_name": _dis_selected_repo}
                await _session_mgr.delete(_dis_session_id, state.get("tenant_id") or "unknown")
                return {
                    **state,
                    "parameters": _params,
                    "entry_method": _session.get("entry_method", state.get("entry_method", "natural_language")),
                }
        except Exception as _restore_err:
            logger.warning(f"[{audit_id}] Disambiguation session restore failed: {_restore_err}")
        # Fall through to fresh disambiguation if restore fails

    try:
        bundle = await _get_intelligence_bundle(token)
    except ValueError as e:
        # Invalid / missing PAT — surface as a clean error instead of letting
        # the outer except-Exception swallow it silently and leave the user
        # wondering why intelligence enhancements were skipped.
        logger.warning(f"[{audit_id}] enhance: intelligence bundle unavailable: {e}")
        if timeline:
            timeline.fail_step("enhance", str(e), entry_method=_entry_method)
        return {**state, "error": str(e), "timeline": timeline}
    repo_discovery = bundle.repo_discovery
    commit_generator = bundle.commit_generator
    log_parser = bundle.log_parser

    best_match = None
    try:
        # === Structured-call repo key normalization ===
        # If the caller used the shorthand "repo" key (structured-call convention),
        # promote it to "repo_name" so the rest of the pipeline sees the canonical key.
        # We do this BEFORE the fuzzy block so the skip-guard logic below works correctly.
        if state.get("entry_method") == "structured" and "repo" in parameters:
            repo_shorthand = parameters.pop("repo")
            # Only set repo_name if it hasn't already been provided explicitly
            if not parameters.get("repo_name"):
                parameters["repo_name"] = repo_shorthand

        # 1. Fuzzy repo matching (if repo_name provided but might be ambiguous)
        # delete_repo is intentionally excluded: it requires an exact name match, never fuzzy.
        if (operation != "delete_repo" and FeatureFlags.is_enabled(Feature.FUZZY_SEARCH)):
            repo_name = parameters.get("repo_name")

            # === Fuzzy skip guard ===
            # When entry_method is "structured" AND the repo is already in exact
            # "owner/repo" form, there is nothing for fuzzy search to resolve.
            # Skip it entirely and record the skip in the audit timeline.
            skip_fuzzy = (
                state.get("entry_method") == "structured"
                and isinstance(repo_name, str)
                and bool(_EXACT_REPO_RE.match(repo_name))
            )

            if skip_fuzzy:
                logger.info(
                    f"[{audit_id}] Skipping fuzzy repo lookup — structured call with exact repo: {repo_name}"
                )
                if timeline:
                    timeline.add_event(
                        EventType.STEP_COMPLETE,
                        "Skipped fuzzy repo lookup — exact owner/repo provided",
                        step="fuzzy_repo",
                        skipped=True,
                        reason="exact_repo",
                        entry_method="structured",
                    )
                # repo_name is already the canonical form; nothing more to do here.
            else:
                # Agentic Discovery Fallback: If repo_name missing from parameters, search full query text
                if not repo_name:
                    best_match = await repo_discovery.discover_from_text(query)
                    if best_match:
                        logger.info(f"[{audit_id}] Proactive repo discovery: {best_match.full_name}")
                        parameters["repo_name"] = best_match.full_name
                        state["repo_confidence"] = best_match.confidence
                        repo_name = best_match.full_name

                if repo_name:
                    timeline.start_step("repo_discovery", "Fuzzy matching repository name")

                    # Try fuzzy search (if we already found a high-confidence match above, this will confirm it)
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
                elif repo_name:
                    # Ambiguous - need clarification (only when repo_name was actually provided)
                    matches = await repo_discovery.fuzzy_search(repo_name, max_results=3)
                    if matches and matches[0].confidence < 0.85:
                        timeline.add_event(EventType.OPERATION_COMPLETE, "Repo ambiguous - needs clarification")
                        session_id = f"sess_{uuid.uuid4().hex[:16]}"
                        tenant_id = state.get("tenant_id") or "unknown"
                        try:
                            session_mgr = get_session_manager()
                            await session_mgr.get_or_create(
                                session_id=session_id,
                                tenant_id=tenant_id,
                                initial={
                                    "kind": "disambiguation",
                                    "operation": state.get("operation"),
                                    "candidates": [{"repo": m.full_name, "confidence": m.confidence} for m in matches],
                                    "params_pending": state.get("parameters") or {},
                                    "entry_method": state.get("entry_method", "natural_language"),
                                },
                            )
                        except Exception as _sess_err:
                            logger.warning(f"[{audit_id}] Failed to save disambiguation session: {_sess_err}")
                            session_id = None
                        base_result = repo_discovery.format_disambiguation_response(matches)
                        if session_id:
                            base_result["session_id"] = session_id
                        return {
                            **state,
                            "result": base_result,
                            "timeline": timeline
                        }
                    timeline.complete_step("repo_discovery", "Using original repo name")
        
        # 2. Auto-generate commit message (if message not present)
        # === Commit message generation ===
        diff = (state.get("context") or {}).get("diff")
        explicit_msg = parameters.get("commit_message")
        skip_commit_gen = (
            state.get("entry_method") == "structured" and bool(explicit_msg)
        )
        if (operation == "commit_file" and
                not explicit_msg and
                FeatureFlags.is_enabled(Feature.COMMIT_GENERATION)):

            if diff:
                timeline.start_step("commit_gen", "Generating commit message from diff")
                commit_msg = await commit_generator.generate(
                    repo=parameters.get("repo_name", "unknown"),
                    diff=diff,
                    tenant_id=state.get("tenant_id"),
                    integration_name=state.get("integration_name"),
                    user_id=state.get("user_id")  # NEW: Pass user_id to commit_generator
                )
            else:
                # Proactive fallback: generate from query/file params
                timeline.start_step("commit_gen", "Proactively generating commit message")
                commit_msg = await commit_generator.generate_proactive(
                    repo=parameters.get("repo_name", "unknown"),
                    query=query,
                    file_path=parameters.get("file_path"),
                    is_new=not parameters.get("file_url"), # Heuristic: if no file_url, it's likely a creation
                    tenant_id=state.get("tenant_id"),
                    integration_name=state.get("integration_name"),
                    user_id=state.get("user_id")  # NEW: Pass user_id to commit_generator
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

        elif operation == "commit_file" and diff and skip_commit_gen:
            # Structured call with explicit commit_message — skip commit generator
            # and record the skip in the audit timeline (mirrors Task 5/6 skip pattern).
            logger.info(
                f"[{audit_id}] Skipping commit_generator — structured call with explicit commit_message"
            )
            if timeline is not None:
                timeline.add_event(
                    EventType.STEP_COMPLETE,
                    "Skipped commit_generator — explicit commit_message provided",
                    step="commit_generator",
                    skipped=True,
                    reason="explicit_message",
                    entry_method="structured",
                )
        
        # 3. Parse error log to issue (if error_log provided)
        # === Log parsing for issue creation ===
        error_log = (state.get("context") or {}).get("error_log")
        explicit_title = (state.get("parameters") or {}).get("title")
        skip_log_parser = (
            state.get("entry_method") == "structured" and bool(explicit_title)
        )
        if (operation == "create_issue" and
                error_log and
                not skip_log_parser and
                FeatureFlags.is_enabled(Feature.LOG_PARSING)):

            timeline.start_step("log_parse", "Parsing error log")

            parsed_issue = await log_parser.parse(
                log=error_log,
                language=context.get("language")
            )

            # Override/enhance parameters with parsed data
            parameters["title"] = parsed_issue.title
            parameters["body"] = parsed_issue.body
            parameters["labels"] = parsed_issue.labels

            logger.info(f"[{audit_id}] Parsed error log to issue: {parsed_issue.title}")
            timeline.complete_step("log_parse", f"Created issue: {parsed_issue.title[:50]}")

        elif operation == "create_issue" and error_log and skip_log_parser:
            # Structured call with explicit title — skip log parser and record in audit timeline
            logger.info(
                f"[{audit_id}] Skipping log_parser — structured call with explicit title"
            )
            if timeline is not None:
                timeline.add_event(
                    EventType.STEP_COMPLETE,
                    "Skipped log_parser — explicit title provided",
                    step="log_parser",
                    skipped=True,
                    reason="explicit_title",
                    entry_method="structured",
                )
        
        # 4. Commit file context injection (before validation)
        if (operation == "commit_file" and 
            "file_url" not in parameters and 
            "content" not in parameters):
            
            available_files = context.get("available_files", [])
            file_path = parameters.get("file_path", "").lower()
            logger.debug(f"[{audit_id}] commit_file injection started. file_path: '{file_path}', available_files count: {len(available_files)}")

            # Clean path to handle Unicode ellipsis, underscores, hyphens, and parentheses
            file_path = file_path.replace("…", " ").replace("...", " ").replace("_", " ").replace("-", " ").replace("(", " ").replace(")", " ")
            
            # Fuzzy match or single-file fallback
            matches = []
            
            # Case 1: file_path provided - use fuzzy matching
            if file_path:
                words = [w for w in file_path.split() if len(w) >= 3]
                logger.debug(f"[{audit_id}] Split file_path words: {words}")
                
                for f in available_files:
                    fname = f["filename"].lower()
                    if any(word in fname for word in words):
                        matches.append(f)
                
                logger.debug(f"[{audit_id}] Fuzzy matches found: {[m['filename'] for m in matches]}")
            
            # Case 2: No specific file mentioned or fuzzy match failed - if only one file exist, pick it!
            if not matches and len(available_files) == 1:
                logger.debug(f"[{audit_id}] Single file fallback: {available_files[0]['filename']}")
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
    parameters = state.get("parameters", {})
    context = state.get("context", {})
    audit_id = state.get("audit_id")
    timeline = state.get("timeline")
    _entry_method = state.get("entry_method", "natural_language")

    if not operation:
        return state

    try:
        if timeline:
            timeline.start_step("risk_gate", f"Risk check for {operation}",
                                entry_method=_entry_method)

        # Extract risk confirmation from context. Accept both prefixed (risk_confirmed,
        # risk_reason) and bare (confirmed, reason) key forms — mirrors the dual-key
        # support documented in src/core/risk.py:128.
        risk_context = {}
        risk_confirmed = context.get("risk_confirmed", context.get("confirmed"))
        if risk_confirmed is not None:
            risk_context["confirmed"] = risk_confirmed
        risk_reason = context.get("risk_reason", context.get("reason"))
        if risk_reason is not None:
            risk_context["reason"] = risk_reason

        # Check risk requirements with contextual awareness
        # Parameters are passed so branch-level overrides (e.g., commit to main → HIGH) apply
        violation = RiskGate.check_contextual(operation, parameters, risk_context)

        if violation:
            error_msg = f"Risk gate blocked: {violation.message}"
            logger.warning(f"[{audit_id}] {error_msg}")

            if timeline:
                timeline.fail_step("risk_gate", error_msg, entry_method=_entry_method)

            # Escalation audit: record every HIGH/CRITICAL block via the dedicated
            # logger so security ops can review attempts to bypass the gate.
            try:
                escalation = get_escalation_logger()
                token_hash = _get_token_hash(state.get("github_token"))
                rl = violation.risk_level.value.upper()
                if rl == "CRITICAL":
                    await escalation.record_critical(
                        audit_id=audit_id or "",
                        operation=operation,
                        parameters=parameters,
                        outcome="blocked",
                        token_hash=token_hash,
                        confirmed=bool(risk_context.get("confirmed")),
                        reason=str(risk_context.get("reason") or ""),
                    )
                elif rl == "HIGH":
                    await escalation.record_blocked_high(
                        audit_id=audit_id or "",
                        operation=operation,
                        parameters=parameters,
                        token_hash=token_hash,
                        confirmed=bool(risk_context.get("confirmed")),
                    )
            except Exception as _esc_err:
                # Escalation logging must never break the user-facing response.
                logger.error(f"[{audit_id}] Escalation logger failed: {_esc_err}")

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

        # Risk passed: stash the resolved level on state so execute_github_operation
        # can decide whether to emit a CRITICAL escalation record when the op succeeds.
        passed_level = RiskGate.resolve_effective_risk(operation, parameters)
        if timeline:
            timeline.complete_step("risk_gate", f"Risk check passed ({passed_level.value})",
                                   entry_method=_entry_method)

        logger.info(f"[{audit_id}] Risk gate passed for {operation}")
        return {**state, "resolved_risk_level": passed_level.value}

    except Exception as e:
        error_msg = f"Risk gate error: {str(e)}"
        logger.error(f"[{audit_id}] {error_msg}")

        if timeline:
            timeline.fail_step("risk_gate", error_msg, entry_method=_entry_method)

        return {
            **state,
            "error": error_msg,
            "timeline": timeline
        }


async def policy_gate_check(state: GitHubState) -> GitHubState:
    """Enforce environment/protection-mode policy BEFORE the risk gate.

    Phase 4: Runs after validate, before risk_gate.
    Answers: 'Is this operation allowed at all in the current environment?'
    """
    operation = state.get("operation")
    parameters = state.get("parameters", {})
    context = state.get("context", {})
    audit_id = state.get("audit_id")
    timeline = state.get("timeline")
    _entry_method = state.get("entry_method", "natural_language")

    if not operation:
        return state

    try:
        if timeline:
            timeline.start_step("policy_gate", f"Policy check for {operation}",
                                entry_method=_entry_method)

        violation = PolicyGate.check(operation, parameters, context)

        if violation:
            error_msg = violation.message
            logger.warning(
                f"[{audit_id}] Policy gate blocked: {operation} — {violation.policy}"
            )
            if timeline:
                timeline.fail_step("policy_gate", error_msg, entry_method=_entry_method)

            return {
                **state,
                "error": error_msg,
                "timeline": timeline,
                "result": {
                    **violation.to_dict(),
                    "audit_id": audit_id,
                    "timeline": timeline.to_dict() if timeline else None,
                },
            }

        if timeline:
            timeline.complete_step("policy_gate", "Policy check passed",
                                   entry_method=_entry_method)

        logger.info(f"[{audit_id}] Policy gate passed for {operation}")
        return state

    except Exception as e:
        error_msg = f"Policy gate error: {str(e)}"
        logger.error(f"[{audit_id}] {error_msg}")
        if timeline:
            timeline.fail_step("policy_gate", error_msg, entry_method=_entry_method)
        return {
            **state,
            "error": error_msg,
            "timeline": timeline,
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
    _entry_method = state.get("entry_method", "natural_language")

    if not operation:
        return state

    try:
        if timeline:
            timeline.start_step("validation", f"Validating parameters for {operation}",
                                entry_method=_entry_method)

        # Phase 4: Strict Pydantic validation
        validated = validate_op_params(operation, parameters)

        if timeline:
            timeline.complete_step("validation", "Validation passed",
                                   entry_method=_entry_method)
        return {
            **state,
            "parameters": validated,
            "timeline": timeline
        }
    except ValidationError as e:
        friendly_error = _friendly_validation_message(str(e), operation)

        logger.warning(f"[{audit_id}] Validation failed: {friendly_error}")
        if timeline:
            timeline.fail_step("validation", friendly_error, entry_method=_entry_method)

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
    _entry_method = state.get("entry_method", "natural_language")

    # Get the bundle for this token so we use the correct authenticated client
    try:
        bundle = await _get_intelligence_bundle(token)
    except ValueError as e:
        logger.warning(f"[{audit_id}] execute: intelligence bundle unavailable: {e}")
        if timeline:
            timeline.fail_step("execute", str(e), entry_method=_entry_method)
        return {**state, "error": str(e), "timeline": timeline}
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
        timeline.start_step(f"execute_{operation}", f"Executing {operation}",
                            entry_method=_entry_method)

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

            elif operation == "list_branches":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.list_branches(**parameters)
                )

            elif operation == "create_branch":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.create_branch(**parameters)
                )

            elif operation == "delete_branch":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.delete_branch(**parameters)
                )

            elif operation == "delete_repo":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.delete_repo(**parameters)
                )

            elif operation == "merge_pr":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.merge_pr(**parameters)
                )

            elif operation == "list_pull_requests":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.list_pull_requests(**parameters)
                )

            elif operation == "get_pr":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.get_pr(**parameters)
                )

            elif operation == "close_issue":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.close_issue(**parameters)
                )

            elif operation == "update_issue":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.update_issue(**parameters)
                )

            elif operation == "add_comment":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.add_comment(**parameters)
                )

            elif operation == "list_commits":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.list_commits(**parameters)
                )

            elif operation == "get_commit":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.get_commit(**parameters)
                )

            elif operation == "list_releases":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.list_releases(**parameters)
                )

            elif operation == "create_release":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.create_release(**parameters)
                )

            elif operation == "trigger_workflow":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.trigger_workflow(**parameters)
                )

            elif operation == "create_webhook":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.create_webhook(**parameters)
                )

            elif operation == "list_webhooks":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.list_webhooks(**parameters)
                )

            elif operation == "delete_webhook":
                return await loop.run_in_executor(
                    None, lambda: gh_tools.delete_webhook(**parameters)
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
            timeline.complete_step(f"execute_{operation}", f"Completed successfully",
                                   entry_method=_entry_method)
            timeline.add_event(EventType.OPERATION_COMPLETE, f"{operation} completed",
                               entry_method=_entry_method)
        
        executed_at = time.time()
        logger.info(
            f"[{audit_id}] GitHub operation completed successfully",
            extra={"operation": operation}
        )

        # Escalation audit: CRITICAL ops that executed successfully must be
        # logged so security ops can review every destructive action that ran.
        # The risk level was resolved upstream by risk_gate_check and stashed
        # in state["resolved_risk_level"].
        if (state.get("resolved_risk_level") or "").upper() == "CRITICAL":
            try:
                context = state.get("context") or {}
                escalation = get_escalation_logger()
                await escalation.record_critical(
                    audit_id=audit_id or "",
                    operation=operation,
                    parameters=parameters,
                    outcome="executed",
                    token_hash=_get_token_hash(state.get("github_token")),
                    confirmed=bool(context.get("risk_confirmed", context.get("confirmed"))),
                    reason=str(context.get("risk_reason", context.get("reason")) or ""),
                )
            except Exception as _esc_err:
                logger.error(f"[{audit_id}] CRITICAL escalation logger failed: {_esc_err}")

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
            timeline.fail_step(f"execute_{operation}", "GitHub API Timeout",
                               entry_method=_entry_method)
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
            timeline.fail_step(f"execute_{operation}", friendly_msg,
                               entry_method=_entry_method)

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
            timeline.fail_step(f"execute_{operation}", str(e), entry_method=_entry_method)
            timeline.add_event(EventType.OPERATION_FAILED, f"{operation} failed: {e}",
                               entry_method=_entry_method)
        
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



def _friendly_validation_message(error: str, operation: str) -> str:
    """Parse a raw Pydantic validation error and return a user-friendly message.

    Args:
        error: Raw error string from the validation step
        operation: The operation that was being attempted

    Returns:
        Human-readable string with an example
    """
    error_lower = error.lower()

    # Field-specific friendly messages with examples
    field_messages = {
        "repo_name": (
            "Please specify the repository in 'owner/repo' format.\n"
            "  Example: 'create issue Login bug in owner/my-repo'"
        ),
        "branch_name": (
            "Please specify the branch name.\n"
            "  Example: 'delete branch feature-x from owner/my-repo'"
        ),
        "title": (
            "Please specify a title.\n"
            "  Example: 'create issue Login bug in owner/my-repo'"
        ),
        "name": (
            "Please specify the repository name.\n"
            "  Example: 'create repo my-new-project'"
        ),
        "head": (
            "Please specify the source branch (head) for the pull request.\n"
            "  Example: 'create PR from feature-x to main in owner/my-repo'"
        ),
        "file_path": (
            "Please specify the file path.\n"
            "  Example: 'commit src/app.py to owner/my-repo'"
        ),
        "commit_message": (
            "Please specify a commit message.\n"
            "  Example: 'commit README.md with message \"Update docs\" to owner/my-repo'"
        ),
        "run_id": (
            "Please specify the CI run ID.\n"
            "  Example: 'analyze CI failure run 1234567890 in owner/my-repo'"
        ),
        "query": (
            "Please specify what to search for.\n"
            "  Example: 'search for def authenticate in owner/my-repo'"
        ),
        "template": (
            "Please specify the scaffold template.\n"
            "  Example: 'scaffold my-project with python-fastapi template'"
        ),
        "from_branch": (
            "Please specify the source branch to branch from.\n"
            "  Example: 'create branch feature-y from main in owner/my-repo'"
        ),
    }

    # Check for delete_repo exact-format errors
    if "owner/repo" in error_lower or ("repo_name" in error_lower and "delete_repo" in operation):
        return (
            "For 'delete_repo', you must provide the exact repository name in 'owner/repo' format.\n"
            "  Example: 'delete repo owner/my-repo'"
        )

    # Check content/file_url mutual requirement
    if "content" in error_lower and "file_url" in error_lower:
        return (
            "Please provide either file content or a file URL to commit.\n"
            "  Example: 'commit README.md with content \"Hello World\" to owner/my-repo'"
        )

    # Field-level matching
    for field, message in field_messages.items():
        if field in error_lower:
            return message

    # Generic validation fallback
    return (
        f"Some required information is missing for '{operation}'. "
        "Please rephrase your request with all required details.\n"
        f"  Original error: {error}"
    )


async def handle_error(state: GitHubState) -> GitHubState:
    """Handle errors or early returns in the workflow.

    Converts raw Pydantic / validation errors into friendly user-facing messages.

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
    operation = state.get("operation", "")

    logger.error(f"[{audit_id}] GitHub agent error: {error}")

    if timeline:
        timeline.add_event(
            EventType.OPERATION_FAILED,
            error,
            entry_method=state.get("entry_method"),
        )

    # Convert validation errors into friendly messages
    friendly_error = error
    error_lower = error.lower()
    if "field required" in error_lower or "validation failed" in error_lower:
        friendly_error = _friendly_validation_message(error, operation)
        logger.info(f"[{audit_id}] Converted validation error to friendly message")

        # Agentic Error Recovery: Add broad repository suggestions if missing
        if "repo_name" in error_lower or "repository" in friendly_error.lower():
            try:
                # Fetch recent repositories from cache
                github_token = state.get("github_token")
                bundle = await _get_intelligence_bundle(github_token)
                repo_discovery = bundle.repo_discovery
                suggestions = await repo_discovery.get_recent_suggestions(limit=3)
                
                if suggestions:
                    suggestion_text = "\n\nI couldn't identify the repository. Did you mean one of these?\n" + "\n".join([f"- {s}" for s in suggestions])
                    friendly_error += suggestion_text
                    logger.info(f"[{audit_id}] Added proactive repo suggestions to error message")
            except Exception as e:
                logger.warning(f"[{audit_id}] Failed to fetch proactive suggestions: {e}")

    return {
        **state,
        "result": {
            "success": False,
            "error": friendly_error,
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
workflow.add_node("policy_gate", policy_gate_check)   # Phase 4: runs before risk_gate
workflow.add_node("risk_gate", risk_gate_check)
workflow.add_node("execute", execute_github_operation)
workflow.add_node("error", handle_error)

# Add edges: parse → enhance → validate → policy_gate → risk_gate → execute
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
    lambda state: "policy_gate" if not state.get("error") else "error",
    {
        "policy_gate": "policy_gate",
        "error": "error",
    }
)
workflow.add_conditional_edges(
    "policy_gate",
    lambda state: "risk_gate" if not state.get("error") and not state.get("result") else "error",
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
    query: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    github_token: Optional[str] = None,
    tenant_id: str = "unknown",
    integration_name: str = "github",
    user_id: str = None,  # NEW: Phase 4 analytics support
    # NEW: structured-call kwargs
    operation: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Main entry point for github_operation tool.

    Two valid call shapes:
      1. Natural-language: pass `query="..."`. The supervisor LLM extracts operation+params.
      2. Structured:       pass `operation="..."` and `parameters={...}`. The LLM step is skipped.

    Exactly one of `query` and `operation` must be provided (non-empty).

    Args:
        query: User query describing GitHub operation (natural-language path)
        context: Optional context (session_id, diff, error_log, files, etc.)
                 Must NOT contain 'github_token' — strip it at the router layer.
        github_token: Optional per-connection GitHub PAT. Treated as transient;
                      never logged, audited, or serialized into response.
        operation: Pre-resolved operation name (structured-call path)
        parameters: Pre-resolved parameters dict (structured-call path)

    Returns:
        Result dictionary with success status, data/error, and audit info
    """
    # Exactly-one-of validation (assertion fires AssertionError; the MCP handler
    # catches this earlier via the GithubOperationArgs Pydantic validator in Task 9)
    has_query = bool(query)
    has_operation = bool(operation)
    if has_query == has_operation:
        # Either both set or both empty — caller contract violation.
        # Raise ValueError (not AssertionError) so MCP/gateway handlers translate
        # this into a clean 400/-32602 instead of surfacing a 500 traceback.
        raise ValueError(
            "github_agent_invoke: exactly one of (query, operation) must be provided. "
            f"Got query={query!r}, operation={operation!r}"
        )

    # Determine entry method
    entry_method = "structured" if has_operation else "natural_language"

    logger.info(f"Invoking GitHub agent with query: {(query or '')[:100]}...")

    # Defensive guard: if caller forgot to strip the token from context, pop it here
    safe_context = dict(context or {})
    if "github_token" in safe_context:
        logger.warning("github_token found inside context dict — stripping at agent boundary")
        github_token = github_token or safe_context.pop("github_token")

    initial_state: GitHubState = {
        "query": query or "",
        "operation": operation,           # NEW: pre-populated on structured calls (None for NL)
        "parameters": parameters,         # NEW: pre-populated on structured calls (None for NL)
        "result": None,
        "error": None,
        "context": safe_context,
        "github_token": github_token,   # transient — stays in state, never serialized out
        "audit_id": None,
        "timeline": None,
        "intent_confidence": None,
        "repo_confidence": None,
        "commit_confidence": None,
        "tenant_id": tenant_id,
        "integration_name": integration_name,
        "user_id": user_id,  # NEW: Phase 4 analytics support
        "entry_method": entry_method,     # NEW
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