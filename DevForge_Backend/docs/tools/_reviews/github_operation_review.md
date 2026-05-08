# github_operation — Doc vs Code Review

**Reviewed:** 2026-05-08
**Branch:** rag_resolve
**Doc(s):** docs/tools/github_operation.md, docs/tools/github_operation_curl_tests.md, docs/tools/README.md
**Code:** src/agents/github/, src/tools/github/, src/api/routers/__init__.py, manifests/devforge.json
**Verdict:** Diverged

## Summary
The architectural skeleton (LangGraph nodes, intelligence components, risk/policy gates, audit timeline) and the per-operation parameter schemas are accurate. However, the curl test suite is materially broken: it fabricates HTTP 400/405 responses the gateway never produces, calls Phase 2 tools (`generate_changelog`, `analyze_ci_failure`, `scaffold_repository`) as if they were registered gateway tools when they are explicitly commented out in `SUPPORTED_TOOLS`, hits the wrong port (8000 vs 8001), and omits the required `x-api-key` header. The main doc also advertises a `merge_pr` method that does not exist in `src/tools/github/tools.py`, mis-states the LangGraph edge order in one of two diagrams, and ships several env-var names (`GITOPS_ENABLE_CONFIDENCE_GATING`, `GITOPS_COMMIT_CONFIDENCE_THRESHOLD`) that are not in `src/core/config.py`. Version drift is also present: doc 0.8.5, manifest 0.8.0, README index 0.7.0, Dockerfile 0.9.0.

## Verified claims
- `github_operation` is registered in `SUPPORTED_TOOLS` mapped to `github_agent_invoke` — `src/api/routers/__init__.py:47`.
- Gateway endpoint `/api/gateway` accepts `{"name": "github_operation", "arguments": {"query": ..., "context": ...}}` — `src/api/routers/__init__.py:639-744`.
- Token is popped out of `context` before any logging — `src/api/routers/__init__.py:725` and again defensively in `github_agent_invoke` — `src/agents/github/agent.py:1192-1196`.
- `GitHubState` fields exist as documented (with extras: `tenant_id`, `integration_name`, `user_id`, `github_token`) — `src/agents/github/agent.py:47-65`.
- `github_agent_invoke` is the main entry point; signature includes `query`, `context`, `github_token` (and undocumented `tenant_id`, `integration_name`, `user_id`) — `src/agents/github/agent.py:1170-1177`.
- LangGraph nodes registered: `parse`, `enhance`, `validate`, `policy_gate`, `risk_gate`, `execute`, `error` — `src/agents/github/agent.py:1117-1124`.
- 30s LLM classify timeout, 15s GitHub API timeout — `src/agents/github/agent.py:224, 815`.
- Bundle cache keyed by SHA256(token) with `_BUNDLE_CACHE_MAX = 128` LRU eviction — `src/agents/github/agent.py:81-131`.
- `RepoDiscovery` matching pipeline: exact (1.0) → substring (0.7-0.9) → Levenshtein (>0.5) — `src/agents/github/intelligence/repo_discovery.py:86-123`.
- `get_best_match` default threshold = 0.85 — `src/agents/github/intelligence/repo_discovery.py:233`.
- Repo cache TTL = `GITOPS_REPO_CACHE_TTL` defaulting to 3600s — `src/core/config.py:167` and `repo_discovery.py:155`.
- `ChangeType` enum has the 10 doc-listed values (FEAT, FIX, DOCS, STYLE, REFACTOR, PERF, TEST, CHORE, CI, BUILD) — `src/agents/github/intelligence/commit_generator.py:19-30`.
- Commit-generator type-inference rules match doc (tests→TEST, .md→DOCS, .yml/.github→CI, package.json/requirements.txt→BUILD, more deletions→REFACTOR, more additions→FEAT) — `commit_generator.py:200-220`.
- Fallback (rule-based) commit confidence = 0.60; LLM-parsed scoped = 0.95, unscoped = 0.90, unparsed = 0.70 — `commit_generator.py:282,300,341`.
- Medium-confidence draft-PR threshold band 0.85 ≤ x < 0.90 — `src/agents/github/agent.py:428-430`.
- `Language` enum: PYTHON, JAVASCRIPT, JAVA, GO, UNKNOWN — `src/agents/github/intelligence/log_parser.py:19-25`.
- `RollbackMatrix.MATRIX` operations + feasibilities exactly match the doc table (`create_branch`/IMMEDIATE, `merge_pr`/COMPENSATING, `delete_repository`/IMPOSSIBLE, etc.) and the 48hr reflog window for `delete_branch` — `src/agents/github/workflows/rollback.py:42-99`.
- Risk levels for the listed ops: `list_repos` LOW, `create_issue` MEDIUM, `create_repo` HIGH, `delete_repo` CRITICAL — `src/core/risk.py:47-77`.
- Contextual escalation: `merge_pr` to main/master → HIGH; production/release/* → CRITICAL; `delete_branch` of main/master/production → CRITICAL — `src/core/risk.py:202-216`.
- Policy gate runs before risk gate — `src/agents/github/agent.py:1121-1153`.
- `GITOPS_PROTECTED_MODE`, `GITOPS_ENV` semantics (production blocks `delete_repo`/`force_push`; staging blocks `delete_repo`, requires confirmed for `force_push`) — `src/core/policy.py:40-186`.
- Token redaction (`[REDACTED]`) and SHA-256-hash-only token logging in escalation records — `src/core/audit.py:243-260, 286-303`.
- `delete_repo` requires exact `owner/repo` format (raises ValueError otherwise, no fuzzy fallback) — `src/tools/github/tools.py:806-811` and `src/agents/github/agent.py:347`.
- `commit_file` requires either `content` or `file_url` (Pydantic model_validator) — `src/agents/github/schemas.py:40-44`.
- `GITHUB_TOKEN`, `GITHUB_USERNAME`, `GITOPS_ENABLE_FUZZY_SEARCH`, `GITOPS_FUZZY_THRESHOLD`, `GITOPS_ENABLE_COMMIT_GEN`, `GITOPS_ENABLE_LOG_PARSING`, `GITOPS_REPO_CACHE_TTL`, `GITOPS_SESSION_TTL` exist in settings — `src/core/config.py:150-169`.
- 4 test files referenced exist: `test_repo_discovery.py`, `test_commit_generator.py`, `test_log_parser.py`, `test_github_integration.py`.

## Discrepancies (doc says X, code does Y)

- **claim:** "`merge_pr()` … `repo_name, pull_number, commit_title, merge_method` … MEDIUM to CRITICAL RISK" listed as a `GitHubTools` method (`github_operation.md:124`).
  **reality:** No `merge_pr` method exists in `src/tools/github/tools.py`. Only methods present: `list_repos`, `create_repo`, `create_issue`, `commit_file`, `create_pull_request`, `browse_files`, `read_file`, `search_code`, `list_branches`, `create_branch`, `delete_branch`, `delete_repo`. The agent's operation dispatch (`agent.py:742-810`) has no `merge_pr` branch, and `validate_op_params` (`schemas.py:131-147`) has no `merge_pr` schema. `merge_pr` only appears in `OperationRiskRegistry.RISK_LEVELS` and `RollbackMatrix.MATRIX` as dead-code metadata.
  **severity:** critical (doc advertises a feature that does not exist; users will get "Unknown GitHub operation" if any LLM produces it)

- **claim:** Curl suite calls `generate_changelog`, `analyze_ci_failure`, `scaffold_repository` as direct gateway tools with `"name": "generate_changelog"` etc. (`github_operation_curl_tests.md:611, 645, 692`). Doc's main file also describes them as "Phase 2 specialized tools" with their own `*_invoke` entry points.
  **reality:** All three are explicitly commented out in `SUPPORTED_TOOLS` — `src/api/routers/__init__.py:50-53` ("Phase 2: Specialized GitHub Tools (Integrated into github_operation)"). Calling the gateway with `name="generate_changelog"` returns `"Tool 'generate_changelog' not found. Available tools: ['generate_data', 'github_operation', 'refine_prompt', 'generate_cheatsheet']"` (HTTP 400 from `routers/__init__.py:646-654`). They are only reachable via the LLM picking those `operation` strings inside `github_operation` and the agent dispatching to `generate_changelog_invoke` / `analyze_ci_failure_invoke` / `scaffold_repository_invoke` (`agent.py:802-810`).
  **severity:** critical (entire "Phase 2 Tools" section of curl suite cannot work as written)

- **claim:** Curl suite uses `http://localhost:8000/api/gateway` everywhere (`github_operation_curl_tests.md:4, 17, 56, …`).
  **reality:** Backend runs on port **8001** per project `CLAUDE.md` and the doc itself: `github_operation.md:480` shows `localhost:8001`. The curl suite mixes 8000 and 8001 (one example uses 8001 — line 87). All `localhost:8000` examples will refuse connection.
  **severity:** important

- **claim:** Curl suite never sends an `x-api-key` header on any request.
  **reality:** `/api/gateway` is gated by `APIKeyAuthMiddleware` per project `CLAUDE.md` (middleware section). Without `x-api-key`, every request is rejected before reaching the route handler; expected responses ("HTTP 200 success") are unreachable.
  **severity:** critical

- **claim:** "Malformed JSON" returns `{"success": false, "data": null, "message": "github_operation execution error: Invalid JSON payload"}` HTTP 400 (`github_operation_curl_tests.md:773-780`).
  **reality:** FastAPI/Pydantic intercepts malformed JSON before the handler runs and returns its own `{"detail": [...]}` 422 response. The doc's exact response shape is fabricated.
  **severity:** important

- **claim:** "Missing Content-Type Header" returns `"Content-Type must be application/json"` HTTP 400 (`github_operation_curl_tests.md:945-953`).
  **reality:** No such enforcement exists in `gateway_endpoint` (`routers/__init__.py:639-905`). FastAPI tolerates the missing header and either parses the body or 422s with a Pydantic error. Fabricated.
  **severity:** important

- **claim:** "Null Arguments" returns `"Arguments cannot be null"` HTTP 400 (`github_operation_curl_tests.md:918-927`).
  **reality:** `args = gateway_req.arguments or {}` (`routers/__init__.py:643`) silently coerces `None` → `{}`. With null `arguments`, `github_operation` then errors with `"github_operation requires 'query' parameter"` (`routers/__init__.py:712-721`), not "Arguments cannot be null". Wrong message.
  **severity:** minor

- **claim:** "Missing Name Field" returns HTTP 400 with `"Tool 'None' not found. Available tools: [...]"` (`github_operation_curl_tests.md:798-807`).
  **reality:** `GatewayRequest` has `name: str` required by Pydantic; missing `name` triggers a 422 validation error before reaching the SUPPORTED_TOOLS check. Even if it reached, the message would list 4 actual tools (`generate_data`, `github_operation`, `refine_prompt`, `generate_cheatsheet`), not the curl suite's `["generate_data", "retrieve_docs", "github_operation", ...]` (`curl_tests.md:831`) — `retrieve_docs` is not a registered tool.
  **severity:** important

- **claim:** Architecture diagram and "Workflow Sequence" show edges `parse → enhance → validate → policy_gate → risk_gate → execute` (`github_operation.md:30, 547-583`).
  **reality:** Code sequence matches `parse → enhance → validate → policy_gate → risk_gate → execute` (`agent.py:1126-1162`), so the architecture-diagram edge order is correct. **However** the doc's "Workflow Sequence" section (lines 555-583) only diagrams `parse → enhance → validate → execute`, omitting `policy_gate` and `risk_gate` entirely. Inconsistent with own architecture diagram and with code.
  **severity:** important

- **claim:** Required env var `GITHUB_TOKEN=ghp_your_token_here` (`github_operation.md:520`).
  **reality:** Per `agent.py:100-103` and `tools.py:74-77`, the token is **required at request time** but is sourced primarily from `context.github_token` (the per-connection PAT) — not from the server-level `GITHUB_TOKEN` env var. `GITHUB_TOKEN` is `Optional[str] = None` in config (`config.py:150`), and `_get_intelligence_bundle` raises `ValueError("GitHub token required. Please provide a valid GitHub Personal Access Token from the frontend.")` when no per-request token is provided. The doc presents env-var token as the canonical path; in practice the gateway expects it inside the request context.
  **severity:** important

- **claim:** "Feature Toggles: GITOPS_ENABLE_CONFIDENCE_GATING=true" and "GITOPS_COMMIT_CONFIDENCE_THRESHOLD=0.90" (`github_operation.md:533, 537`).
  **reality:** Neither name exists in `src/core/config.py`. Code uses `Feature.CONFIDENCE_GATING` from `src/core/features.py:26` (with hard-coded default `True`, no env binding) and the 0.90 commit threshold is hard-coded in `ConfidencePolicy.THRESHOLDS["commit_message"] = 0.90` (`src/core/confidence.py:42`), not env-driven. `GITOPS_FUZZY_THRESHOLD` (`config.py:159`) does exist.
  **severity:** important

- **claim:** Specialized tools listed as "`generate_changelog`", "`analyze_ci_failure`", "`scaffold_repository`" tool names (`github_operation.md:337, 363, 406`).
  **reality:** Inside the github agent, the LLM operation strings are `generate_changelog`, `analyze_ci_failure`, **and `scaffold_repo`** (not `scaffold_repository`) — `agent.py:169, 802` and `schemas.py:140`. The manifest entry uses `scaffold_repository` (`devforge.json:278`) but the dispatch operation is `scaffold_repo`. Doc's tool name doesn't match the operation string the LLM is taught to emit.
  **severity:** important

- **claim:** `Phase 1-3` for risk gate, `Phase 4` for policy gate, `Phase 5` for audit hardening with status "Production Ready (Hardened)" (`github_operation.md:5-6, 91-92`).
  **reality:** Phase numbering is a doc-only convention; no `phase` constant in code. The escalation logger and sanitization (`audit.py:266-339`) and policy gate (`policy.py`) and risk gate (`risk.py`) all exist as described, so the substantive claim is correct, but the phase labels cannot be cross-validated.
  **severity:** minor (consistent within doc, just unverifiable)

- **claim:** Test counts: `test_repo_discovery.py` 18, `test_commit_generator.py` 20, `test_log_parser.py` 18, `test_github_integration.py` 20 (`github_operation.md:625-628`).
  **reality:** Actual `def test_` counts: 13 / 19 / 18 / 18 respectively (68 total vs the doc's implicit 76).
  **severity:** minor

- **claim:** README header `Version: 0.7.0`, doc header `Version: 0.8.5`, manifest `version: 0.8.0`.
  **reality:** Five different version strings: `docs/tools/README.md:3,403` = 0.7.0; `manifests/devforge.json:6` = 0.8.0; `src/main.py:58,168` = 0.8.0; `Dockerfile:56` LABEL = 0.9.0; `github_operation.md:4,647` = 0.8.5.
  **severity:** important

- **claim:** Curl suite "Wrong Tool Name" expected response includes `"retrieve_docs"` in the available-tools list (`github_operation_curl_tests.md:831`).
  **reality:** `retrieve_docs` is not in `SUPPORTED_TOOLS` (`routers/__init__.py:45-54`). Real list is `[generate_data, github_operation, refine_prompt, generate_cheatsheet]`.
  **severity:** minor

- **claim:** Manifest description for `github_operation` lists the v0.8 features but does not mention any of: branches (`list_branches`/`create_branch`/`delete_branch`), file-tree browsing (`browse_files`), `read_file`, `search_code`, `delete_repo`, `scaffold_repo`, `generate_changelog`, `analyze_ci_failure` (`devforge.json:48`).
  **reality:** All those operations are advertised by the LLM classification prompt (`agent.py:163-179`) and have schemas + dispatch wired up. MCP/discovery surface is significantly thinner than the actual capability.
  **severity:** important

- **claim:** Curl test "Fuzzy Repository Matching - Below Threshold" expects HTTP 200 with `{"success": false, "status": "rejected", "message": "Cannot proceed safely…(65%)…"}` (`github_operation_curl_tests.md:430-441`).
  **reality:** The 65% threshold response would only fire from `ConfidencePolicy.format_rejection` when intent confidence < 0.70 (`confidence.py:96-102, 207-219`). That path applies to `intent_classification`, not to repo-fuzzy-match below threshold. When repo confidence is below 0.85, the agent returns `format_disambiguation_response` (`agent.py:378-385`) — a `needs_clarification` payload with `options[]`, NOT the `rejected` shape with the 65% banner.
  **severity:** important

- **claim:** `manifests/devforge.json` advertises `available_files` array as a `context` property (`devforge.json:84-105`) but the gateway schema in `routers/__init__.py:1386-1424` does NOT list `available_files` (it lists `session_id`, `diff`, `error_log`, `files`, `github_token`, `confirmed`, `reason`, `file_url`).
  **reality:** Two different context schemas surfaced for the same tool.
  **severity:** minor (manifest used by auto-discovery; gateway schema used by `tools/list` MCP)

## Unverifiable

- "Lines: 558" for `agent.py` — actual is 1238 lines (so the 558 figure is stale, but this is bookkeeping, not a behavior claim).
- "Lines: 423" for `tools.py` — actual is 952 lines.
- "Lines: 230" for `repo_discovery.py` — actual is 343 lines. (All three "Lines: NNN" headers undercount the current files; new code has been added since the doc was written.)
- LLM model used by `parse_github_request` — `agent.py:156` calls `router.select_model_by_task("github", prefer_local=False)`; the resolved model depends on `ModelRouter` runtime mapping, not directly verifiable from doc claims.
- "Phase X" gating dates and the production-ready claim are doc-only conventions.
- Performance ("30s LLM timeout, 15s GitHub API timeout") is verified but the implicit "fast enough for production" framing isn't benchmarked.

## Stale / drift

- Version sprawl: doc 0.8.5, manifest 0.8.0, `src/main.py` 0.8.0, Dockerfile LABEL 0.9.0, `docs/tools/README.md` 0.7.0.
- README index `Last Updated: December 2, 2025` (`README.md:4,404`) vs github_operation doc `Last Updated: 3 March, 2026` (`github_operation.md:648`).
- Doc per-file line counts (558/423/230/335/487/234/272/455/355) all undercount current files.
- Phase 2 tools are presented as standalone gateway tools across the curl suite but are commented out in `SUPPORTED_TOOLS` since at least the current commit (`routers/__init__.py:50-53`).
- `merge_pr` is registered in `RiskLevels` and `RollbackMatrix` but has no implementation, no schema, no dispatch — orphaned dead config.
- Curl suite Test Coverage section claims 76 tests across 4 files; actual is 68.

## Recommended doc changes

1. Remove the `merge_pr()` row from the GitHubTools method table, or add `merge_pr` to `tools.py`, the schema map, and the agent's operation dispatch — the current state advertises a non-existent method.
2. Rewrite `github_operation_curl_tests.md` Section 4 ("Phase 2 Tools"): either (a) remove it because those names are not gateway-callable, or (b) reframe each as `name: github_operation` with a natural-language query that the LLM can route to the corresponding internal `operation`.
3. Globally replace `localhost:8000` with `localhost:8001` in the curl suite.
4. Add `-H "x-api-key: <key>"` to every curl example in the suite (also note `APIKeyAuthMiddleware` is required).
5. Delete or correct the fabricated error-handling tests: malformed JSON returns 422 with FastAPI shape, not a 400 with custom "Invalid JSON payload"; null arguments returns "github_operation requires 'query' parameter", not "Arguments cannot be null"; no Content-Type enforcement exists.
6. Update "Wrong Tool Name" expected available-tools list to the real four: `generate_data, github_operation, refine_prompt, generate_cheatsheet`. Remove `retrieve_docs` from the example.
7. Fix the "Workflow Sequence" diagram (lines 555-583) to include `policy_gate` and `risk_gate` between `validate` and `execute`, matching the architecture diagram and `agent.py:1126-1162`.
8. Replace the `GITHUB_TOKEN` "Required" framing with "Required at request time, normally supplied via `context.github_token` (per-user PAT)". Note that the server-level env var is optional fallback.
9. Drop `GITOPS_ENABLE_CONFIDENCE_GATING` and `GITOPS_COMMIT_CONFIDENCE_THRESHOLD` from the env table — neither is wired in `config.py`. Keep only the env names actually present (`GITOPS_ENABLE_FUZZY_SEARCH`, `GITOPS_FUZZY_THRESHOLD`, `GITOPS_ENABLE_COMMIT_GEN`, `GITOPS_ENABLE_LOG_PARSING`, `GITOPS_REPO_CACHE_TTL`, `GITOPS_SESSION_TTL`, `GITOPS_PROTECTED_MODE`, `GITOPS_ENV`).
10. Reconcile the scaffold tool name: pick one — either rename the operation in `agent.py` and `schemas.py` from `scaffold_repo` to `scaffold_repository` (matching the manifest) or rename the manifest entry to `scaffold_repo` (matching the dispatch).
11. Reconcile the "Below Threshold" curl example: either change the expected payload to a `needs_clarification` disambiguation response (matching `format_disambiguation_response`), or change the prompt so it triggers low *intent* confidence (which is what `format_rejection` actually fires on).
12. Replace test counts (`18/20/18/20`) with actual counts (`13/19/18/18`) or drop the numbers and link to `pytest --collect-only`.
13. Update the file-line counts in each section header (or delete them — they're not load-bearing and decay quickly).
14. Pick a single project version and propagate to `manifests/devforge.json:6`, `src/main.py:58,168`, `Dockerfile:56`, `docs/tools/README.md:3,403`, and the doc header `github_operation.md:4,647`.
15. Expand the manifest description for `github_operation` to mention branches, file browsing, code search, delete operations, and the Phase 2 internal tools, so MCP/`tools/list` consumers see the real surface.
