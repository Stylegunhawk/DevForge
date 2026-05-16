# DevForge Backend - Tools Documentation Index

**Version:** 0.8.0
**Last Updated:** 2026-05-08
**Gateway tools:** 4 (registered in `SUPPORTED_TOOLS`)
**Internal RAG capabilities:** 2 (different access path)

---

## Overview

This directory contains documentation for every DevForge tool. Each `.md` file uses a standard structure designed for LLM consumption and human readability.

> **Doc accuracy:** Every per-tool doc has a corresponding doc-vs-code review under [`_reviews/`](./_reviews/). The reviews list which claims are verified against current source, which diverged, and which are unverifiable. **Read the review before trusting a per-tool doc** — drift is significant in places.

---

## Documentation Format

Each tool doc follows this structure:

1. Header — name, version, status
2. Overview — description and key features
3. Folder structure — file/folder organization
4. Parameters — input/output specs
5. API usage — `curl` examples
6. Use cases — real-world scenarios
7. Implementation — tech stack and architecture
8. Error handling — common errors
9. Testing — test commands and counts
10. Best practices and troubleshooting

---

## Gateway Tools (4)

These are the tools registered in `SUPPORTED_TOOLS` (`src/api/routers/__init__.py:45-54`) and callable via `POST /api/gateway` or `POST /mcp` (`tools/call`). Both endpoints require `x-api-key`.

### 1. `generate_data` — Mock Data Generation
**Doc:** [`generate_data.md`](./generate_data.md) · **Review:** [`_reviews/generate_data_review.md`](./_reviews/generate_data_review.md)

Generates realistic mock CSV/JSON data. Two modes:
- **V1 (simple):** Faker-based, `rows` + `format` + optional `fields`.
- **V2 (advanced):** semantic generation with domain templates, FK integrity validation, realism injection. Triggered by `prompt` or `domain`.

Domains: `ecommerce`, `saas`, `iot_devices`. Realism: `basic | medium | high`.

### 2. `github_operation` — GitHub Automation
**Doc:** [`github_operation.md`](./github_operation.md) · **Curl tests:** [`github_operation_curl_tests.md`](./github_operation_curl_tests.md) · **Review:** [`_reviews/github_operation_review.md`](./_reviews/github_operation_review.md)

LangGraph-orchestrated GitOps with intent classification, fuzzy repo matching, LLM commit-message generation, risk gate, policy gate, and audit logging. Operations supported (per `agent.py:163-179`): `list_repos`, `create_repo`, `delete_repo`, `create_issue`, `commit_file`, `create_pull_request`, `browse_files`, `read_file`, `search_code`, `list_branches`, `create_branch`, `delete_branch`, plus internal `generate_changelog` / `analyze_ci_failure` / `scaffold_repo` (reachable via this tool, **not** as standalone gateway names).

> Token: pass per-request via `arguments.context.github_token`. Server-level `GITHUB_TOKEN` is optional fallback.

### 3. `refine_prompt` — Prompt Optimization
**Doc:** [`refine_prompt.md`](./refine_prompt.md) · **Review:** [`_reviews/refine_prompt_review.md`](./_reviews/refine_prompt_review.md)

Domain-aware LLM prompt enhancement. Five domains: `general`, `image`, `code`, `rag`, `llm`. Three skill levels: `beginner | intermediate | expert`. Uses evidence-weighted stack detection (dependency 0.9, code 0.8, conversation 0.4) for code-domain prompts.

### 4. `generate_cheatsheet` — Cheat Sheet Generation
**Doc:** [`generate_cheatsheet.md`](./generate_cheatsheet.md) · **Review:** [`_reviews/generate_cheatsheet_review.md`](./_reviews/generate_cheatsheet_review.md)

Rule-based (no LLM) markdown cheat sheets. Pipeline: parse → detect libraries (14 supported) → score complexity → select sections → assemble markdown.

> ⚠️ **Known limitation:** only Python has full templates. Requesting `language: "rust"` (etc.) currently returns Python content under a relabelled header. See the review.

---

## Internal RAG Capabilities (2)

These appear in older docs as "tools" but they are **not gateway-registered**. Calling `POST /api/gateway` with `name: "retrieve_docs"` or `name: "rerank_docs"` returns *Tool not found*.

### `retrieve_docs` — Document Retrieval (RAG)
**Doc:** [`rag/retrieve_docs.md`](./rag/retrieve_docs.md) · **Architecture:** [`rag_architecture.md`](./rag_architecture.md) · **Reviews:** [`_reviews/retrieve_docs_review.md`](./_reviews/retrieve_docs_review.md), [`_reviews/rag_architecture_review.md`](./_reviews/rag_architecture_review.md)

Reachable via:
- `POST /api/v1/rag/chunk/semanticSearchForChat` (tenant JWT required)
- `POST /api/v1/rag/file/upload` for ingestion
- `retrieve_node` inside the LangGraph supervisor (when supervisor routes to RAG)

Pipeline: query intent → expansion → hybrid search (BM25 + vector) → cross-encoder rerank → optional code-graph BFS expansion → top-K. Vector backends: `chroma` or `postgres` (pgvector); production default is **postgres**.

### `rerank_docs` — Cross-Encoder Reranking
**Doc:** [`rag/rerank_docs.md`](./rag/rerank_docs.md) · **Review:** [`_reviews/rerank_docs_review.md`](./_reviews/rerank_docs_review.md)

Internal stage of `retrieve_docs`. Cross-encoder model `cross-encoder/ms-marco-MiniLM-L-6-v2`, sigmoid-normalised, with code-aware boosting (function 1.2, class 1.15). Not exposed as a standalone tool.

---

## Quick Start

### Local development
```bash
cd DevForge_Backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8001
```

### Docker (full RAG stack)
```bash
cp .env.docker .env
docker compose --profile rag up -d --build
```

### Calling a gateway tool
```bash
curl -X POST http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: <YOUR_KEY>" \
  -d '{"name": "generate_data", "arguments": {"rows": 100, "format": "json"}}'
```

---

## Project Structure

```
DevForge_Backend/
├── docs/
│   └── tools/                     # this directory
│       ├── README.md              # this file
│       ├── generate_data.md
│       ├── github_operation.md
│       ├── refine_prompt.md
│       ├── generate_cheatsheet.md
│       ├── rag_architecture.md
│       ├── rag/                   # RAG endpoint docs
│       │   ├── retrieve_docs.md
│       │   ├── rerank_docs.md
│       │   ├── get_files_api.md
│       │   ├── get_file_chunks_api.md
│       │   └── rag_integration_flow.md
│       └── _reviews/              # doc-vs-code audit reviews
│
├── src/
│   ├── agents/                    # business logic
│   │   ├── datagen/
│   │   ├── github/
│   │   ├── prompt_refiner/
│   │   ├── cheatsheet/
│   │   ├── rag/                   # RAG agent + reranking + intent + graph
│   │   └── supervisor.py
│   ├── tools/                     # reusable tool functions
│   │   ├── datagen/
│   │   ├── github/
│   │   ├── rag/
│   │   └── cheatsheet/
│   ├── storage/                   # vector store abstraction
│   │   ├── base_store.py
│   │   ├── chroma_store.py
│   │   └── pgvector_store.py
│   ├── api/
│   │   ├── routers/__init__.py    # gateway, MCP, SUPPORTED_TOOLS
│   │   └── routers/rag.py         # /api/v1/rag/* endpoints
│   └── main.py
│
├── manifests/
│   └── devforge.json              # MCP discovery manifest
│
└── tests/                         # pytest suites
```

---

## Tool Comparison

| Tool | Surface | LLM | Speed | Common use |
|---|---|---|---|---|
| `generate_data` | gateway | optional (V2 only) | fast (V1) / medium (V2) | seed DBs, prototype, load test |
| `github_operation` | gateway | yes | medium | issues, commits, PRs, repo ops |
| `refine_prompt` | gateway | yes | medium | optimise prompts before sending elsewhere |
| `generate_cheatsheet` | gateway | no (rule-based) | fast | quick reference for Python libs |
| `retrieve_docs` | RAG endpoint | optional (cloud LLM for response synthesis) | fast (cached) / medium | semantic search over uploaded files |
| `rerank_docs` | internal stage | no | fast | reorder retrieve_docs candidates |

---

## API Gateway

**Endpoint:** `POST /api/gateway`
**Auth:** `x-api-key` header (validated by `APIKeyAuthMiddleware`)
**Port:** 8001 (local), 8001 inside Docker (`api` service)

### Request
```json
{
  "name": "tool_name",
  "arguments": {"param1": "value1"}
}
```

### Response (success)
```json
{
  "success": true,
  "data": { "...": "..." },
  "message": "tool_name executed successfully"
}
```

### Response (unknown tool)
```json
{
  "success": false,
  "data": null,
  "message": "Tool 'X' not found. Available tools: ['generate_data', 'github_operation', 'refine_prompt', 'generate_cheatsheet']"
}
```

### MCP equivalent
The same four tools are reachable via JSON-RPC at `POST /mcp` using `tools/list` and `tools/call`.

---

## Testing

```bash
# All tests
pytest tests/ -v

# Per tool
pytest tests/test_datagen.py -v
pytest tests/test_rag.py -v
pytest tests/test_github_integration.py -v
pytest tests/test_reranker.py -v
pytest tests/test_prompt_refiner.py -v
pytest tests/test_cheatsheet.py -v

# Single test with prints
pytest tests/test_rag.py::test_semantic_search -v -s
```

> Some integration tests require Docker services running (Postgres + Redis): `docker compose --profile rag up -d`.

---

## Doc-vs-Code Reviews

Each per-tool doc has a corresponding review under [`_reviews/`](./_reviews/). Reviews follow a strict format: every "Verified" claim cites a `file:line`; every "Discrepancy" quotes the doc and shows what the code actually does.

| Tool / Doc | Review | Verdict |
|---|---|---|
| `generate_data.md` | [`generate_data_review.md`](./_reviews/generate_data_review.md) | Diverged |
| `refine_prompt.md` | [`refine_prompt_review.md`](./_reviews/refine_prompt_review.md) | Mostly accurate |
| `rag/retrieve_docs.md` | [`retrieve_docs_review.md`](./_reviews/retrieve_docs_review.md) | Diverged |
| `rag/rerank_docs.md` | [`rerank_docs_review.md`](./_reviews/rerank_docs_review.md) | Diverged |
| `github_operation.md` | [`github_operation_review.md`](./_reviews/github_operation_review.md) | Diverged |
| `generate_cheatsheet.md` | [`generate_cheatsheet_review.md`](./_reviews/generate_cheatsheet_review.md) | Diverged |
| `rag_architecture.md` | [`rag_architecture_review.md`](./_reviews/rag_architecture_review.md) | Diverged |
| `rag_unification_verified.md` | [`rag_unification_verified_review.md`](./_reviews/rag_unification_verified_review.md) | Stale verification report |

---

## Contributing

Adding a new tool:
1. Implement in `src/tools/<feature>/tools.py`
2. Add an agent in `src/agents/<feature>/agent.py` if it needs orchestration
3. Register in `SUPPORTED_TOOLS` (`src/api/routers/__init__.py:45`) and `TOOL_DESCRIPTIONS`
4. Add a JSON-Schema entry to `_get_tool_schema` in the same file
5. Update `manifests/devforge.json`
6. Add `tests/test_<feature>.py`
7. Write `docs/tools/<feature>.md` following the standard format
8. Add a doc-vs-code review under `_reviews/` (audit your own doc)

---

## Resources

- [`manifests/devforge.json`](../../manifests/devforge.json) — MCP discovery manifest
- [`docs/API.md`](../API.md) — full HTTP API reference
- [`docs/AUTHENTICATION_GUIDE.md`](../AUTHENTICATION_GUIDE.md) — JWT and API-key auth
- [`docs/DOCKER_GUIDE.md`](../DOCKER_GUIDE.md) — Docker compose setup
- [`docs/CELERY_SCALING.md`](../CELERY_SCALING.md) — async worker scaling
- [`DevForge_Backend/CLAUDE.md`](../../CLAUDE.md) — project conventions
