# DevForge Backend - Implementation Guide

# Context Mode: ENABLED
# File Purpose: Implementation guide for DevForge backend
# Source of Truth: PROJECT_OVERVIEW.md, BACKEND_PLAN.md, INTEGRATION_PLAN.md
# Update Frequency: After each phase completion

**Status:** Phase 2 — Complete (v0.2.0) | Next Focus: Phase 3 — RAG + GitHub Integration


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
│   └── devforge-backend.md          # ✅ Phase 2 focus (current file)
    └── PHASE_STATUS.MD
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

**This file (`.cursor/devforge-backend.md`) focuses on Phase 2 implementation details.**

---

## 🗺️ Quick Phase Reference

| Phase | Status | Key Deliverables | Documentation |
|-------|--------|------------------|---------------|
| **Phase 1** | ✅ COMPLETE | DataGen agent, MCP gateway, 36 tests | `README.md` |
| **Phase 2** | ✅ COMPLETE (v0.2.0) | Model router, supervisor agent, LangGraph | This file |
| **Phase 3** | 🔄 NEXT | RAG (ChromaDB + Kotaemon), GitHub ops | `PROJECT_OVERVIEW.md` |
| **Phase 4** | ⏳ PENDING | Prompt reranking, LoRA fine-tuning | `PROJECT_OVERVIEW.md` |
| **Phase 5** | ⏳ PENDING | Docker, Render deployment | `BACKEND_PLAN.md` |

**Architecture Decisions:** See `BACKEND_PLAN.md` for folder structure conventions.  
**Integration Rules:** See `INTEGRATION_PLAN.md` for Lobe Chat MCP protocol.

---

## 🎯 PHASE 3: RAG + GitHub Integration (NEXT - v0.3.0)

### Overview
Add document retrieval with ChromaDB and GitHub API automation via PyGithub.

### Priority 1: Model Router
**File**: `src/core/model_router.py`
```python
class ModelRouter:
    """Route queries to optimal models based on task type and constraints"""
    
    MODELS = {
        "qwen3:4b": {"speed": "fast", "cost": 0, "best_for": ["datagen", "simple_qa"]},
        "deepseek-r1:8b": {"speed": "medium", "cost": 0, "best_for": ["routing", "classification"]},
        "gpt-oss:20b": {"speed": "medium", "cost": 0, "best_for": ["rag_local", "reasoning"]},
        "gpt-oss:120b-cloud": {"speed": "slow", "cost": 0.002, "best_for": ["rag_complex", "analysis"]},
        "qwen3-coder:480b-cloud": {"speed": "slow", "cost": 0.01, "best_for": ["code_gen", "github"]},
        "deepseek-v3.1:671b-cloud": {"speed": "slowest", "cost": 0.05, "best_for": ["premium_reasoning"]},
    }
    
    def select_model(self, task_type: str, prefer_local: bool = True) -> str:
        """Select optimal model for task"""
        pass
    
    def invoke_with_fallback(self, model: str, prompt: str, fallback_chain: list) -> str:
        """Try primary model, fallback on error"""
        pass
    
    def estimate_cost(self, model: str, tokens: int) -> float:
        """Estimate API cost for cloud models"""
        pass
```

**Benefits:**
- Automatic local→cloud escalation
- Cost tracking for cloud usage
- Resilience through fallback chains

---

### Priority 2: Supervisor Agent
**File**: `src/agents/supervisor.py`

**Now we introduce LangGraph** (justified for routing logic):
```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class SupervisorState(TypedDict):
    query: str
    intent: str  # "datagen" | "rag" | "github"
    model: str
    result: dict

def classify_intent(state: SupervisorState) -> SupervisorState:
    """Use deepseek-r1:8b to classify user intent"""
    # LLM call to determine intent
    pass

def route_to_agent(state: SupervisorState) -> str:
    """Route based on classified intent"""
    intent_map = {
        "datagen": "datagen_agent",
        "rag": "rag_agent",      # Phase 3
        "github": "github_agent"  # Phase 3
    }
    return intent_map.get(state["intent"], END)

# Build graph
workflow = StateGraph(SupervisorState)
workflow.add_node("classify", classify_intent)
workflow.add_conditional_edges("classify", route_to_agent)
workflow.add_node("datagen_agent", datagen_agent)
workflow.set_entry_point("classify")

supervisor = workflow.compile()
```

**Routing Examples:**
- "Generate 100 users" → `datagen_agent` (qwen3:4b)
- "Search my codebase for X" → `rag_agent` (gpt-oss:20b) - Phase 3
- "Create GitHub PR" → `github_agent` (qwen3-coder:480b-cloud) - Phase 3

---

### Priority 3: Gateway Updates
**Update**: `src/api/routers.py`
```python
SUPPORTED_TOOLS = {
    "generate_data": datagen_agent,
    "retrieve_docs": rag_agent,      # Phase 3 stub
    "github_operation": github_agent  # Phase 3 stub
}

@router.post("/api/gateway")
async def gateway(request: GatewayRequest):
    start_time = time.time()
    
    # Use supervisor for routing
    result = await supervisor.ainvoke({
        "query": request.arguments,
        "intent": None,
        "model": None,
        "result": None
    })
    
    execution_time = time.time() - start_time
    
    return GatewayResponse(
        success=True,
        tool=request.name,
        data=result["result"],
        execution_time=execution_time
    )
```

**Error Handling:**
- Unsupported tool → 400 with clear message
- Model unavailable → Auto-fallback to cloud
- Timeout → Return partial results + warning

---

### Priority 4: Manifest Update
**Update**: `manifests/devforge.json`
```json
{
  "name": "devforge",
  "version": "0.2.0",
  "description": "DevForge AI-powered developer tools with intelligent routing",
  "schema_version": "v1",
  "gateway": "http://localhost:8000/api/gateway",
  "tools": [
    {
      "name": "generate_data",
      "description": "Generate realistic mock CSV/JSON data using Faker",
      "available": true,
      "parameters": { ... }
    },
    {
      "name": "retrieve_docs",
      "description": "Search codebase/docs using RAG (Coming in Phase 3)",
      "available": false,
      "parameters": { ... }
    },
    {
      "name": "github_operation",
      "description": "GitHub operations (Coming in Phase 3)",
      "available": false,
      "parameters": { ... }
    }
  ]
}
```

---

### Testing Strategy

**New Test Files:**
1. `tests/test_model_router.py` - Model selection logic
2. `tests/test_supervisor.py` - Intent classification (mock LLM)
3. `tests/test_routing.py` - End-to-end routing verification

**Test Scenarios:**
```python
# Mock LLM for testing
@pytest.mark.asyncio
async def test_supervisor_routes_datagen():
    """Verify 'generate users' routes to datagen_agent"""
    result = await supervisor.ainvoke({
        "query": "Generate 50 user records",
        "intent": None,
        "model": None,
        "result": None
    })
    assert result["intent"] == "datagen"
    assert "qwen3:4b" in result["model"]

async def test_model_fallback():
    """Verify cloud fallback when local unavailable"""
    router = ModelRouter()
    # Simulate Ollama down
    model = router.invoke_with_fallback(
        "gpt-oss:20b",
        "test prompt",
        fallback_chain=["gpt-oss:120b-cloud"]
    )
    assert "cloud" in model
```

**Coverage Target:** >85% for new modules

---

### Dependencies Update

**Add to `requirements.txt`:**
```txt
# Phase 2 additions
langgraph>=0.2.0           # NOW needed for supervisor
langchain-core>=0.3.0      # LangGraph dependency
```

---

### Environment Variables

**Add to `.env.example`:**
```bash
# Phase 2 Models
SUPERVISOR_MODEL=deepseek-r1:8b
FALLBACK_CLOUD_MODEL=gpt-oss:120b-cloud

# Cost tracking
ENABLE_COST_TRACKING=true
MONTHLY_BUDGET_USD=50.0
```

---

## 🎯 Phase 2 Success Criteria

### Must Have:
- [ ] Supervisor correctly classifies intents (100% accuracy on test set)
- [ ] Model router selects appropriate models per task
- [ ] Fallback works when primary model unavailable
- [ ] All Phase 1 tests still pass (36 tests)
- [ ] New Phase 2 tests pass (>20 tests)
- [ ] Manifest version bumped to 0.2.0
- [ ] Gateway logs show model selection decisions

### Nice to Have:
- [ ] Cost tracking dashboard (log total API spend)
- [ ] Performance comparison (local vs cloud latency)
- [ ] Supervisor reasoning explanations in logs

---

## 🚨 Phase 2 Implementation Notes

### LangGraph Best Practices:
1. **State Management**: Use TypedDict for clear state schema
2. **Error Handling**: Add error nodes in graph for graceful failures
3. **Testing**: Mock LLM calls with predefined responses
4. **Logging**: Log state transitions for debugging

### Model Configuration:
```python
# config.py additions
TASK_MODEL_MAP = {
    "datagen": settings.DEFAULT_MODEL,           # qwen3:4b
    "routing": settings.SUPERVISOR_MODEL,        # deepseek-r1:8b
    "rag_simple": settings.RAG_LOCAL_MODEL,      # gpt-oss:20b
    "rag_complex": settings.RAG_CLOUD_MODEL,     # gpt-oss:120b-cloud
    "code_gen": settings.GITHUB_MODEL,           # qwen3-coder:480b-cloud
    "premium": settings.PREMIUM_MODEL            # deepseek-v3.1:671b-cloud
}
```

### Common Pitfalls:
❌ Don't query cloud models unnecessarily (check local first)
❌ Don't add RAG/GitHub logic yet (Phase 3 scope)
✅ Focus on routing infrastructure only
✅ Keep agents as stubs (empty functions)

---

## 📅 Estimated Timeline

**Phase 2 Implementation:**
- Day 1-2: Model router + fallback logic
- Day 3-4: Supervisor agent with LangGraph
- Day 5: Gateway integration + testing
- Day 6: Documentation + verification

**Total:** 5-7 days (vs. 2-3 days for Phase 1)

---

## 🔮 Phase 3+ Preview

**Phase 3 (Weeks 7-10):** RAG + GitHub tools
**Phase 4 (Weeks 11-14):** Prompt reranking + LoRA fine-tuning
**Phase 5 (Weeks 15-16):** Docker + Render deployment

**Phase 3 Prep:**
- Stub files already created: `src/agents/rag/agent.py`, `src/tools/rag/tools.py`
- Dependencies to add: `chromadb>=0.5.0`, `PyGithub>=2.4.0`, `langchain-community`
- Models ready: `gpt-oss:20b`, `gpt-oss:120b-cloud`, `qwen3-coder:480b-cloud`, `nomic-embed-text`

---

## 🏁 Phase 2 Summary

**Status:** ✅ Complete (Nov 2, 2025)  
**Version:** v0.2.0  
**Next:** Phase 3 — RAG + GitHub Integration (Nov 10 – Nov 30)  
**Manifest:** v0.2.0 → v0.3.0 (upcoming)

**Achievements:**
- ✅ ModelRouter implemented with async fallback
- ✅ Task-based model mapping added
- ✅ Supervisor Agent built using LangGraph
- ✅ 58 tests passing (36 from Phase 1 + 22 new)
- ✅ Manifest bumped to v0.2.0

---

## 🔄 Ready to Start Phase 3?

**Pre-flight Checklist:**
- [ ] Phase 2 fully verified (supervisor routing functional)
- [ ] All 58 tests passing (36 Phase 1 + 22 Phase 2)
- [ ] Models pulled: `ollama pull gpt-oss:20b`, `ollama pull nomic-embed-text`
- [ ] Cursor context updated for Phase 3

**First Implementation Step:**  
Implement RAG agent with ChromaDB integration.

🚀 **Ready for Phase 3!**