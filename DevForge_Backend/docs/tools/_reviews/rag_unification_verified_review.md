# rag_unification_verified — Doc vs Code Review

**Reviewed:** 2026-05-08
**Branch:** rag_resolve
**Doc(s):** `docs/tools/rag_unification_verified.md`
**Code:** `src/agents/rag/`, `src/tools/rag/`, `src/storage/`, `src/api/routers/`
**Verdict:** Stale verification report — every cited line number has drifted; the *behavioral* unification claims are mostly still true, but one is materially wrong (the retrieval kernel does NOT converge on `tools.retrieve_docs`).

## Summary
The doc's high-level conclusion — ingestion converges on `tools.ingest_documents`, single chunking authority lives in `tools.chunk_document`, no shadow chunker logic outside the documented locations — still matches code. But every `file:line` citation is stale: `agent.py` has grown to 1,394 lines and the cited symbols all moved. More importantly, one structural claim is wrong: the doc states `_vector_search` calls `src.tools.rag.tools.retrieve_docs`; in reality `_vector_search` calls `self.vector_store.search` directly, and `tools.retrieve_docs` delegates *back* into the agent — the dependency runs the opposite direction. Part 6 ("After AST bug resolve curl test") packages runtime observations as "verified" but they cannot be statically checked.

## Cited line numbers — accuracy

| # | Doc citation | Doc claim | Reality at that line | Match? | Actual location |
|---|---|---|---|---|---|
| 1 | `agent.py:697` | `RAGAgent.ingest_document` | `if redis_client:` inside ingest_document body | NO | `agent.py:596` |
| 2 | `tools.py:338` | `ingest_documents` does file read/chunk/upsert | empty line in legacy fallback of `chunk_document` | NO | `tools.py:365` |
| 3 | `rag.py:108` | `semantic_search_for_chat` calls `agent.retrieve_with_reranking()` | `results.append(file_meta)` in `upload_files` | NO | `rag.py:213` (call at `rag.py:226`) |
| 4 | `agent.py:108` | `retrieve_node` calls `agent.retrieve_with_reranking()` | call site `agent = get_rag_agent(...)` inside retrieve_node | PARTIAL | def at `agent.py:93`; call at `agent.py:110` |
| 5 | `agent.py:775` | `retrieve_with_reranking` definition | `results["caches_cleared"].append("bm25_index")` in `delete_file_cascade` | NO | `agent.py:837` |
| 6 | `agent.py:754` | `_vector_search` def + "calls `tools.retrieve_docs`" | `results["vector_deleted"] = ...` in `delete_file_cascade` | NO + behavior wrong | `agent.py:796`; calls `self.vector_store.search` (`agent.py:818, 827`) |

**Score: 0 of 6 line citations exact; 1 of 6 within ±2 lines.**

## Verified claims (logic, not line numbers)
- Ingestion entry → Celery task → agent → tool: `upload_files` (`rag.py:46`) → `async_ingest_documents.delay(...)` (`rag.py:102-107`) → `async_ingest_documents` (`rag_tasks.py:14`) → `agent.ingest_document(...)` (`rag_tasks.py:55`) → `RAGAgent.ingest_document` (`agent.py:596`) → `src.tools.rag.tools.ingest_documents` (`agent.py:620-632`). **Verified.**
- Single chunking authority: `chunk_document` (`tools.py:262`) is the only place that imports/instantiates `CodeChunker`/`TextChunker` (`tools.py:281-288`). **Verified.**
- No shadow chunker logic: `grep -rn "CodeChunker|TextChunker|RecursiveCharacterTextSplitter" src/` shows hits only in `src/tools/rag/tools.py` and `src/agents/rag/chunking/*`. **Verified.**
- Both retrieval entry points reach `retrieve_with_reranking`: `semantic_search_for_chat` (`rag.py:213` → call at `rag.py:226`) and `retrieve_node` (`agent.py:93` → call at `agent.py:110`, attached to `rag_agent_invoke` at `agent.py:254`). **Verified — converge on `RAGAgent.retrieve_with_reranking` (`agent.py:837`).**
- `retrieve_with_reranking` orchestrates cache/expansion/hybrid/graph/rerank, calls `_vector_search` at `agent.py:970, 996, 999, 1002`. **Verified.**
- `_vector_search` (`agent.py:796`) calls `self.vector_store.search(...)` directly (`agent.py:818, 827`). **Verified — does NOT call `tools.retrieve_docs`.**
- `is_graph_expansion` flag exists (`agent.py:141, 1043, 1097, 1117, 1349`). **Verified.**
- `ChangelogGenerator` / `_fetch_commits` referenced in Part 6 are real (`src/tools/changelog.py:20, 93`).

## Discrepancies

- **claim:** "_vector_search (agent.py:754) calls src.tools.rag.tools.retrieve_docs" (PART 4).
  **reality:** `_vector_search` (`agent.py:796`) calls `self.vector_store.search(...)` (`agent.py:818, 827`). The dependency runs the *other way*: `tools.retrieve_docs` (`tools.py:533`) imports `get_rag_agent` and calls `agent.retrieve_with_reranking(...)` (`tools.py:564-572`). The `retrieve_docs` import in `agent.py:21` is unused inside the retrieval pipeline.
  **severity:** important — the "convergence proof" cites a function the agent never calls.

- **claim:** `RAGAgent.ingest_document` at `agent.py:697`.
  **reality:** `def` at `agent.py:596` — off by 101 lines. Behavior claim correct.
  **severity:** minor.

- **claim:** PART 1 ingestion endpoint `POST /v1/rag/file/upload`.
  **reality:** Mounted under `/api/v1/rag/file/upload`. Cosmetic.
  **severity:** minor.

- **claim:** `semantic_search_for_chat` at `rag.py:108`.
  **reality:** `rag.py:108` is in `upload_files`. Function is at `rag.py:213`; retrieval call at `rag.py:226`.
  **severity:** minor.

- **claim (Part 6):** AST chunking / vector retrieval / dependency surfacing "verified" with checkmarks.
  **reality:** These are single-session curl observations packaged as static verifications.
  **severity:** minor — frame issue.

## Unverifiable
- Part 6 log line `AST chunking successful: 15 chunks (imports: 8, entities: 7)` — depends on a specific test corpus.
- Part 6 dedup claim "Multiple uploads → multiple versions in vector store" — no test in `tests/test_rag.py` exercises this.
- Part 6 "Phase 2 of RAG maturity" — opinion, not a code claim.

## Stale / drift
- **6 of 6 cited line numbers are wrong.** Drifts: `agent.py:697 → 596` (~101), `tools.py:338 → 365` (~27), `rag.py:108 → 213` (~105), `agent.py:108 → 93/110` (~2-15), `agent.py:775 → 837` (~62), `agent.py:754 → 796` (~42). Median drift ~50 lines.
- `agent.py` is 1,394 lines now (the doc's largest cited line is 775); `tools.py` is 671; `rag.py` is 427.
- PART 5 ("Shadow Logic Detection") still holds against current `grep`.
- Part 6 mixes doc-style verification with chat-style commentary ("You've crossed the hard part", "Do NOT touch it further").

## Recommended doc changes
1. Replace every line citation with symbol citations (`RAGAgent.ingest_document` instead of `agent.py:697`).
2. Fix PART 4's wrong convergence claim. Correct version: `_vector_search` calls `self.vector_store.search` (the `BaseVectorStore` abstraction). `tools.retrieve_docs` is a shim that delegates *back* to `RAGAgent.retrieve_with_reranking` (`tools.py:533-580`).
3. Or freeze the doc with a commit SHA at the top.
4. Refresh PART 1 endpoint paths to `/api/v1/rag/...`.
5. Split Part 6 out — its tone is incompatible with a verification report.
6. Add a "How to re-verify" block with the exact `grep`/`pytest` commands.
