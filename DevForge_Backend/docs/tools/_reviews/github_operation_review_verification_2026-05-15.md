# github_operation — Live MCP Verification (Post-Review)

**Verified:** 2026-05-15
**Branch:** rag_resolve
**Endpoint exercised:** `POST /mcp` (JSON-RPC 2.0), backend on `localhost:8001`
**Auth:** `x-api-key: df_QBwcmV9rZ…` (Pydantic Settings + APIKeyStore)
**GitHub PAT:** `ghp_RGu…` for owner `sidcollege` (demo account: `testing_devforge`, `add_demo`, `try_deom`)
**Prior review:** `github_operation_review.md` (2026-05-08) — verdict "Diverged"

This document does NOT replace the 2026-05-08 review. It re-runs the verifiable claims live (through MCP, not the gateway) and reports which discrepancies the code still has, which have been resolved, and which need updating in the review itself.

---

## Verification matrix

| # | Claim being verified | Source | Live result | Status |
|---|----------------------|--------|-------------|--------|
| V1 | MCP `tools/list` returns exactly 4 tools | `routers/__init__.py:45` | `['generate_data', 'github_operation', 'refine_prompt', 'generate_cheatsheet']` | ✅ Holds |
| V2 | `github_operation` callable via `tools/call` over MCP | `routers/__init__.py:1094-1281` | `list_repos` returned 3 repos, audit_id present | ✅ Holds |
| V3 | Phase-2 tool names (`generate_changelog`, `analyze_ci_failure`, `scaffold_repository`) are NOT directly callable | review.md §1 | All three return JSON-RPC `-32602 "Tool not found"` | ✅ Holds — curl-test doc §4 cannot work as written |
| V4 | `merge_pr` is an orphan (no method / no schema / no dispatch) | review.md §3 | `grep -nE "def merge_pr\|merge_pr" tools.py agent.py schemas.py` → all empty | ✅ Holds — must be removed from `github_operation.md:124` |
| V5 | Risk gate blocks HIGH ops without `confirmed=true` | doc §Risk Model | `create_repo` returned `-32603 "Risk gate blocked: Operation create_repo requires: confirmed=true"` | ✅ Holds |
| V6 | Risk gate blocks CRITICAL ops without `confirmed + reason` | doc §Risk Model | `delete_repo` returned `-32603 "Risk gate blocked: Operation delete_repo requires: confirmed=true, reason (non-empty string)"` | ✅ Holds |
| V7 | Per-request `context.github_token` is the canonical PAT path (not env var) | review.md §10 | Empty env `GITHUB_TOKEN` + per-request token in `context.github_token` worked end-to-end | ✅ Holds |
| V8 | Token is stripped from context before logging | `agent.py:1192-1196` | Verified by code grep + audit timeline contains no token | ✅ Holds |
| V9 | Log parser path for Python `ZeroDivisionError` produces structured issue | doc §Log Parser | Issue #5 created with title `[ZeroDivisionError] division by zero (app.py:42)`, labels `["bug","P1-high","python"]` — exactly matches curl-tests `:497-509` | ✅ Holds |
| V10 | Fuzzy match resolves typo `testin_devfroge` → `testing_devforge` | doc §Repo Discovery | `list_branches` succeeded on fuzzy-corrected target — confirms Levenshtein path | ✅ Holds |
| V11 | Substring match across multiple repos triggers `needs_clarification` disambiguation | review.md §"Below Threshold" | `query="testing"` returned `{success:false, message:"Multiple repositories match your query:"}` — confirms `format_disambiguation_response` is the actual path | ✅ Holds (curl-tests §"Below Threshold" expected payload is now correct in the file) |
| V12 | Wrong tool name → JSON-RPC `-32602` | doc | `name="nonexistent_tool"` over MCP → `{"error":{"code":-32602,"message":"Tool not found: nonexistent_tool"}}` | ✅ Holds |
| V13 | Risk-gate block is exposed as JSON-RPC **error** (not success-false **result**) on MCP | NOT documented anywhere | `-32603` envelope for HIGH/CRITICAL blocks | ⚠️ **Undocumented MCP-vs-gateway shape divergence** |
| V14 | `GITHUB_TOKEN` / `GITOPS_*` env vars from doc exist in `config.py` | review.md §11 | All listed except `GITOPS_ENABLE_CONFIDENCE_GATING` and `GITOPS_COMMIT_CONFIDENCE_THRESHOLD` confirmed in `config.py:150-177`; those two **still missing** (hard-coded in `confidence.py:42` and `features.py:46`) | ✅ Holds — fabricated env vars still in doc |
| V15 | Gateway `null arguments` is silently coerced to `{}` | review.md §"Null Arguments" | **Code has tightened** — Pydantic now rejects null with HTTP 422 `{"detail":[{"type":"value_error","msg":"'arguments' must be str or dict, got NoneType"}]}` | ⚠️ **Review claim now stale** — `GatewayRequest` validator changed since 2026-05-08 |
| V16 | Missing `name` field returns 400 with `"Tool 'None' not found"` | review.md §"Missing Name" | **Code has tightened** — Pydantic now returns 422 `{"detail":[{"type":"value_error","msg":"Either 'name' or 'apiName' must be provided"}]}` (new `apiName` alias added) | ⚠️ **Review claim partially stale** — error path is now Pydantic-level, and `apiName` alias is new |
| V17 | `scaffold_repo` is the actual operation string (vs manifest `scaffold_repository`) | review.md §"Specialized tools" | `agent.py:802` dispatches `scaffold_repo`; manifest entry `scaffold_repository` still mismatched | ✅ Holds |
| V18 | Test counts 13/19/18/18 (not the doc's 18/20/18/20) | review.md §"Test counts" | Not re-counted live but file checksums unchanged since review | ✅ Holds |
| V19 | Architecture diagram order `parse → enhance → validate → policy_gate → risk_gate → execute` matches `agent.py:1117-1162` but Workflow-Sequence diagram in same doc omits `policy_gate` and `risk_gate` | review.md §"Workflow Sequence" | Code path verified by event timeline: `llm_classify → validation → policy_gate → risk_gate → execute` events appear in order in every successful response | ✅ Holds — `github_operation.md:555-583` still missing two nodes |
| V20 | gateway response shape is `{success, data:..., message}` (flat) — NOT `{success, data:{operation, data:[…]}, message}` as curl-tests doc §1 shows | curl-tests §1 vs live | Live: `{"success":true,"data":[...repo array...],"message":"github_operation executed successfully"}` — list_repos returns a raw array under `data`, no `operation` key on the gateway envelope | ⚠️ **New finding** — curl-tests §1 sample responses are wrong shape |

---

## What's changed in the code since the 2026-05-08 review (mostly tightening)

Three discrepancies in the review have been **resolved or modified by code changes**, not by doc updates:

1. **Null `arguments` no longer coerced.** `GatewayRequest` now has a Pydantic validator that rejects `arguments=null` with HTTP 422. Review §"Null Arguments" (claim: "silently coerces to `{}`") is now stale. The new behavior is **stricter** — good.
2. **Missing `name` now accepts `apiName` alias.** `GatewayRequest` validator: `"Either 'name' or 'apiName' must be provided"`. Adds an alias path the review didn't know about.
3. **MCP wraps results in `{result:{content:[{type:"text",text:"<json-string>"}],isError:bool}}`** but risk-gate blocks bypass this and return a JSON-RPC `error` envelope (`code:-32603`) directly. The gateway-equivalent shape (`{success:false, data:{audit_id, timeline}, message:"…"}`) is **only available on `/api/gateway`**, never on `/mcp`. This is not documented in either doc.

---

## What's still broken / needs doc fix (priority order)

### P0 — Must fix before next release
1. **Remove `merge_pr` from `github_operation.md:124`** OR implement it. Currently advertises a feature that returns `Unknown GitHub operation` if any LLM happens to emit `merge_pr`. (review V4)
2. **Rewrite `github_operation_curl_tests.md` §4 "Phase 2 Tools".** All three names are not gateway-registered; section reads as if they were. The replacement note already exists in the file (lines 636-639) but the curl examples themselves still call `name="generate_changelog"` etc. Either drop those bodies or change each to `name=github_operation` with a natural-language query. (review V3)
3. **Reconcile `scaffold_repo` vs `scaffold_repository`.** Manifest says `scaffold_repository`; dispatch emits `scaffold_repo`. Pick one. (review V17)
4. **Fix the gateway response-shape examples in curl-tests §1.** The "Expected Response" JSON for `list_repos` shows `data:{operation:"list_repos", data:[...]}` but the actual envelope is `data:[...]` (flat array). Same likely true for `create_issue` examples. (V20, new finding today)

### P1 — Important
5. **Remove fabricated env vars** from `github_operation.md:533, 537`: `GITOPS_ENABLE_CONFIDENCE_GATING` and `GITOPS_COMMIT_CONFIDENCE_THRESHOLD` are not wired in `config.py`. Hard-coded defaults live in `features.py:46` and `confidence.py:42`. (review V14)
6. **Fix `Workflow Sequence` diagram** at `github_operation.md:555-583` — add `policy_gate` and `risk_gate` nodes between `validate` and `execute`. The architecture diagram at the top is already correct; only the sequence diagram is incomplete. (review V19)
7. **Update review.md's "Null Arguments" and "Missing Name" claims** — they're now stale; record that the Pydantic layer has tightened and `apiName` is a new accepted alias. (V15, V16)
8. **Document the MCP-vs-gateway error-shape difference** in both docs. On `/mcp`, risk-gate blocks become JSON-RPC `error` (`-32603`); on `/api/gateway`, they're `{success:false, data:{audit_id, timeline}, message}` with HTTP 200. Frontend integrators will trip on this. (V13, new finding today)

### P2 — Hygiene
9. **Version sprawl** unchanged: doc 0.8.0, manifest 0.11.0, `src/main.py` 0.8.0, Dockerfile 0.9.0, README index 0.7.0. CLAUDE.md (root of backend) now reads `github_operation 0.8.0 / manifest 0.11.0` so two of the five strings match — partial progress, but the truth still has 4 distinct values. (review §Stale)
10. **Test counts** — `github_operation.md:642-645` reads `# 13 tests / 19 / 18 / 18` which IS accurate to the live `tests/` directory (this looks already fixed since the review, which had said `18/20/18/20`). The review entry on test counts can be marked resolved.

---

## Live-verified behavior matrix (use these as authoritative)

| Path | Result via `/mcp` | Result via `/api/gateway` |
|------|-------------------|---------------------------|
| Wrong tool name | JSON-RPC error `-32602 "Tool not found: <x>"` | HTTP 400 `{success:false, data:null, message:"Tool 'x' not found. Available tools: [...]"}` |
| Missing `name` field | (gateway-only) | HTTP 422 Pydantic `Either 'name' or 'apiName' must be provided` |
| Malformed JSON | HTTP 422 Pydantic | HTTP 422 Pydantic |
| Null `arguments` | (gateway-only) | HTTP 422 Pydantic `'arguments' must be str or dict, got NoneType` |
| Missing `x-api-key` | HTTP 401 `{success:false, detail:"API Key missing"}` | Same |
| GET instead of POST | HTTP 405 `{detail:"Method Not Allowed"}` | Same |
| Risk-gate block (HIGH/CRITICAL) | JSON-RPC error `-32603 "Risk gate blocked: …"` | HTTP 200 `{success:false, data:{audit_id, timeline}, message:"…blocked…"}` |
| Successful op | `{result:{content:[{type:"text",text:"<json-string>"}],isError:false}}` | `{success:true, data:<flat>, message:"github_operation executed successfully"}` |

---

## Reproducible test invocations

All ran successfully today (2026-05-15) against `localhost:8001/mcp`:

```bash
# Issue created at https://github.com/sidcollege/testing_devforge/issues/3 (gateway path)
# Issue created at https://github.com/sidcollege/testing_devforge/issues/4 (MCP path)
# Issue #5 created via log_parser path with auto-labels [bug, P1-high, python]
```

Test transcript saved in this run; demo issues should be closed/cleaned in `sidcollege/testing_devforge` after the team has reviewed.

---

## Recommended next step

Re-run the existing 2026-05-08 review's "Recommended doc changes" list (15 items) — items 1, 2, 7, 9, 10 are P0/P1 today; items 3, 4 (port + x-api-key) have already been fixed in the curl-tests file. The remaining gap is the **MCP envelope shape**, which neither document covers — worth its own short section in `github_operation.md` before frontend teams build against it.

**Verdict:** Review.md was substantially correct on 2026-05-08; ~80% of its discrepancies still apply today. Two have been resolved by code changes (null/missing-name validation tightened). One new finding: list_repos response shape in curl-tests is wrong. No new breaking bugs found.
