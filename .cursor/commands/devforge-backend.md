# DevForge Backend - Implementation Guide

# Context Mode: ENABLED
# File Purpose: Implementation guide for DevForge backend
# Source of Truth: PROJECT_OVERVIEW.md, BACKEND_PLAN.md, INTEGRATION_PLAN.md, PHASE_STATUS.md
# Update Frequency: After each phase completion

**Status:** Phase 7 — Complete (v0.7.0) | Next Focus: Phase 8 (Enhanced DevOps) or Phase 5 (Deployment)


## ✅ PHASE 1: COMPLETE (Updated: Nov 2, 2025)

**Delivered Features:**
- ✅ FastAPI server with health/root/manifest endpoints
- ✅ DataGen agent (CSV/JSON generation with Faker + Pandas)
- ✅ MCP gateway endpoint (`/api/gateway`)
- ✅ 36 comprehensive tests (100% pass rate)
- ✅ CORS configured for Lobe Chat (`localhost:3000`)
- ✅ Performance tracking with execution time logging
- ✅ Manifest served dynamically at `/api/manifests/devforge.json`

**Implementation Decisions:**
- Used **simple async functions** (LangGraph deferred to Phase 2)
- Gateway uses `name`/`arguments` schema (Lobe Chat compatible)
- Model router **NOT implemented** (deferred to Phase 2)
- Using `qwen3:4b` for DataGen operations

**Verification:** All items in README.md Phase 1 Verification Checklist completed ✓


---
DevForge/
├── .cursor/
│   └── devforge-backend.md          # ✅ Current status: Phase 7 complete (v0.7.0)
    └── PHASE_STATUS.md
    └── devforge-lobe-chat.md
├── DevForge_Backend/
│   
├── lobe-chat

DevForge_Backend/
├
│
├──                               # 📚 Full project context
│── PROJECT_OVERVIEW.md           # High-level roadmap (all phases)
│── BACKEND_PLAN.md               # Architecture details
│── INTEGRATION_PLAN.md           # Lobe Chat integration
│── MANIFEST_EXAMPLE.json         # Reference schemas
│── CODE_SNIPPETS.md              # Implementation examples
│
├── README.md                          # Phase 1 completion (what's done)
└── PHASE_STATUS.md                    # NEW: Quick phase tracker
---

## Full Project Context

**For complete project understanding, Cursor should reference:**

1. **`../PROJECT_OVERVIEW.md`** - 5-phase roadmap, tech stack, success criteria
2. **`../BACKEND_PLAN.md`** - Folder structure, module design, conventions
3. **`../INTEGRATION_PLAN.md`** - Lobe Chat MCP handshake, execution flow
4. **`../README.md`** - Phase 1 implementation (what's already working)
5. **`../PHASE_STATUS.md`** - Current phase status and next steps

**This file (`.cursor/devforge-backend.md`) provides implementation details and current status for all phases.**

---

## 🗺️ Quick Phase Reference

| Phase | Status | Key Deliverables | Version | Documentation |
|-------|--------|------------------|---------|---------------|
| **Phase 1** | ✅ COMPLETE | DataGen agent, MCP gateway, 36 tests | v0.1.0 | `README.md` |
| **Phase 2** | ✅ COMPLETE | Model router, supervisor agent, LangGraph | v0.2.0 | This file |
| **Phase 3** | ✅ COMPLETE | RAG (ChromaDB + Qdrant), GitHub ops | v0.3.1 | `PROJECT_OVERVIEW.md` |
| **Phase 4** | ✅ COMPLETE | Document reranking with Cross-Encoder | v0.4.0 | `PROJECT_OVERVIEW.md` |
| **Phase 5** | ⏳ DEFERRED | Docker, Render deployment | - | `BACKEND_PLAN.md` |
| **Phase 6** | ✅ COMPLETE | Prompt refinement agent | v0.6.0 | `PROJECT_OVERVIEW.md` |
| **Phase 7** | ✅ COMPLETE | Dynamic cheat sheet generator | v0.7.0 | `PROJECT_OVERVIEW.md` |
| **Phase 8** | 🔄 NEXT | Enhanced DevOps, CI/CD | v0.8.0 | `PHASE_STATUS.md` |

**Architecture Decisions:** See `BACKEND_PLAN.md` for folder structure conventions.  
**Integration Rules:** See `INTEGRATION_PLAN.md` for Lobe Chat MCP protocol.

---

## ✅ PHASE 2: COMPLETE (v0.2.0)

**Delivered Features:**
- ✅ ModelRouter with task-to-model mapping
- ✅ Supervisor Agent with LangGraph
- ✅ Intent classification using `deepseek-r1:8b`
- ✅ Async fallback support with cost tracking
- ✅ 22 new tests (58 total: 36 Phase 1 + 22 Phase 2)
- ✅ Manifest version bumped to v0.2.0

**Key Files:**
- `src/core/model_router.py` - Enhanced with task mapping and health checks
- `src/agents/supervisor.py` - LangGraph-based supervisor workflow

---

## ✅ PHASE 3: RAG + GitHub Integration (COMPLETE - v0.3.1)

### Overview
✅ **COMPLETE** - Document retrieval with ChromaDB/Qdrant and GitHub API automation via PyGithub.

**Delivered Features:**
- ✅ RAG agent with LangGraph workflow
- ✅ Dual vector store support: ChromaDB (local) + Qdrant Cloud (remote)
- ✅ Document ingestion: PDF, MD, TXT, DOCX with async I/O
- ✅ Semantic search with configurable top_k and score threshold
- ✅ GitHub agent with PyGithub integration
- ✅ Support for: list repos, create repo, create issue, commit file, create PR
- ✅ Natural language query parsing using LLM
- ✅ 33+ comprehensive tests for RAG functionality
- ✅ Comprehensive test suite for GitHub operations
- ✅ Manifest updated to v0.3.1

**Key Files:**
- `src/agents/rag/agent.py` - LangGraph RAG workflow
- `src/tools/rag/tools.py` - Document reading, chunking, ingestion, retrieval
- `src/agents/github/agent.py` - LangGraph GitHub workflow
- `src/tools/github/tools.py` - GitHub API operations wrapper

**Models Used:**
- Embeddings: `nomic-embed-text` (primary), `bge-m3` (fallback)
- RAG Local: `gpt-oss:20b`
- RAG Cloud: `gpt-oss:120b-cloud` (fallback)
- GitHub Operations: `qwen3-coder:480b-cloud`

### Implementation Details (Historical Reference)
**Note:** Model Router and Supervisor Agent were implemented in Phase 2. See Phase 2 section above.

**RAG Workflow:**
1. **Ingest Node**: Process and chunk documents if file_paths provided
2. **Retrieve Node**: Semantic search with reranking (Phase 4 integration)
3. **Generate Node**: LLM response based on retrieved context
4. **Error Node**: Graceful error handling

**GitHub Operations:**
- Natural language query parsing
- Support for: list repos, create repo, create issue, commit file, create PR
- PyGithub integration with token authentication

**Gateway Tools (v0.3.1):**
```python
SUPPORTED_TOOLS = {
    "generate_data": datagen_agent,
    "retrieve_docs": rag_agent_invoke,      # ✅ Implemented
    "github_operation": github_agent_invoke   # ✅ Implemented
}
```

**Manifest (v0.3.1):**
- All three tools available and functional
- Gateway URL dynamically configured
- Parameters properly defined

---

## ✅ PHASE 4: Document Reranking (COMPLETE - v0.4.0)

**Delivered Features:**
- ✅ Reranker agent using `sentence-transformers` and Cross-Encoder models
- ✅ Integration with RAG workflow (reranks retrieved docs before generation)
- ✅ `rerank_docs` tool added to manifest
- ✅ Unit tests for reranking logic
- ✅ Cross-Encoder model: `cross-encoder/ms-marco-MiniLM-L-6-v2`

**Key Files:**
- `src/agents/reranker.py` - Reranker implementation
- `src/agents/rag/agent.py` - Updated with reranking step
- `tests/test_reranker.py` - Reranker tests

**Implementation:**
- Uses Cross-Encoder for re-scoring documents by relevance
- Automatically integrated into RAG pipeline
- Improves retrieval quality significantly

---

## ⏳ PHASE 5: Deployment (DEFERRED)

**Status:** Skipped to prioritize Phase 6.

**Planned Features:**
- Docker configuration
- Render deployment guide
- Production environment setup

---

## ✅ PHASE 6: Prompt Refinement Agent (COMPLETE - v0.6.0)

**Delivered Features:**
- ✅ PromptRefinerAgent with domain handlers
- ✅ Domain-specific handlers for Image, Code, RAG, and LLM
- ✅ Context-aware prompt enhancement using file content
- ✅ `refine_prompt` tool added to manifest
- ✅ Unit tests (`tests/test_prompt_refiner.py`)

**Key Files:**
- `src/agents/prompt_refiner/agent.py`
- `src/agents/prompt_refiner/enhancer.py`
- `src/agents/prompt_refiner/domain_handlers.py`
- `src/agents/prompt_refiner/templates.py`

**Supported Domains:**
- `general` - General-purpose refinement
- `image` - Image generation prompts
- `code` - Code generation prompts
- `rag` - RAG query optimization
- `llm` - LLM interaction prompts

**Skill Levels:**
- `beginner` - Simplified, clear instructions
- `intermediate` - Balanced complexity
- `expert` - Advanced, technical prompts

---

## ✅ PHASE 7: Dynamic Cheat Sheets (COMPLETE - v0.7.0)

**Delivered Features:**
- ✅ CheatsheetAgent with language profiles
- ✅ Language detection from code context
- ✅ Skill-level based content generation (Beginner, Intermediate, Expert)
- ✅ `generate_cheatsheet` tool added to manifest
- ✅ Unit tests (`tests/test_cheatsheet.py`)

**Key Files:**
- `src/agents/cheatsheet/agent.py`
- `src/agents/cheatsheet/generator.py`
- `src/agents/cheatsheet/formatter.py`
- `src/agents/cheatsheet/language_profiles.py`

**Features:**
- Auto-detects language from code context
- Generates topics based on skill level
- Quick reference sections
- Markdown-formatted output

**Supported Languages:**
- Python, JavaScript, TypeScript, Java, C++, Go, Rust, and more

---

## 🎯 Current Status Summary

**Current Version:** v0.7.0  
**Completed Phases:** 1, 2, 3, 4, 6, 7  
**Deferred:** Phase 5 (Deployment)  
**Next Phase:** Phase 8 (Enhanced DevOps) or Phase 5 (Deployment)

**Total Tools Implemented:** 6
1. `generate_data` - Mock CSV/JSON data generation
2. `retrieve_docs` - RAG document search and retrieval
3. `github_operation` - GitHub repository operations
4. `rerank_docs` - Document reranking by relevance
5. `refine_prompt` - Prompt optimization
6. `generate_cheatsheet` - Dynamic cheat sheet generation

**Test Coverage:** 100+ tests passing
- Phase 1: 36 tests
- Phase 2: 22 tests (58 total)
- Phase 3: 33+ tests (100+ total)
- Phase 4, 6, 7: Additional test suites

**Manifest Version:** v0.7.0

---

## 🔄 Next Steps

**Option 1: Phase 8 (Enhanced DevOps)**
- CI/CD automation
- Docker/Cloud deployment helpers
- Enhanced monitoring and logging

**Option 2: Phase 5 (Deployment)**
- Dockerize application
- Render deployment guide
- Production environment setup

**Pre-flight Checklist:**
- ✅ All phases 1-7 complete and verified
- ✅ 100+ tests passing
- ✅ Manifest v0.7.0 functional
- ✅ All 6 tools working correctly

🚀 **Ready for Phase 8 or Phase 5!**