This is the most critical part of your project. The integration between your Lobe Chat (Next.js) frontend and your Python (FastAPI) backend is what makes the whole system work, enabling modular feature expansion (e.g., DataGen in Phase 1, RAG/GitHub in Phase 3) while keeping the architecture decoupled and future-ready.
Here is a detailed breakdown of exactly how they are integrated, refined to align with the updated backend structure (e.g., dynamic manifest serving from /api/manifests, centralized gateway dispatching, and env-configured ports/origins).
The Core Concept: Two Separate Servers
You are running two independent servers that communicate over the network (locally or deployed). This setup leverages Lobe Chat's MCP plugin system for tool discovery and execution, with your FastAPI backend acting as the primary handler for agents/tools.
Frontend (Lobe Chat): A Next.js server running at http://localhost:3000 (or similar; configurable via Lobe Chat's env).
Its job is to be the beautiful "Control Panel" and "Chat Client."
It manages the UI, chat history, user settings, and Zustand stores (e.g., src/store/plugin for manifests).
It acts as the "customer" in a restaurant—sending tool calls based on LLM decisions.
Backend (Your Python App): A FastAPI server running at http://localhost:8000 (or similar; configurable via .env PORT).
Its job is to be the powerful "Engine Room" or "Kitchen."
It hosts all your custom logic: LangGraph agents (in src/agents/), tools (in src/tools/), configs (in src/core/), and API routers (in src/api/).
It acts as the "kitchen" that fulfills orders via dispatched endpoints.
The "integration" is the process of telling the "customer" (Lobe Chat) what's on the "menu" (tools via manifest) and giving it the "phone number" (gateway URL) to the "kitchen" (your FastAPI server). This uses HTTP for communication, with CORS enabled in FastAPI to allow requests from Lobe Chat's origin.
Part 1: The "Handshake" (One-Time Setup)
This is how your Lobe Chat frontend discovers your Python backend. It's semi-manual but dynamic: Instead of uploading a static JSON file, you host the manifest on your backend (in manifests/devforge.json, served via API). This allows easy updates (e.g., adding new tools in future phases) without re-adding the plugin in Lobe Chat.
The manifests/devforge.json file (served dynamically) is the "Menu" and the "Phone Number" all in one.
Here is the setup process:
You run your Python FastAPI server: uvicorn src.main:app --port 8000 (or via docker-compose in Phase 5).
You run your Lobe Chat Next.js server: npm run dev (forked repo for any custom mods, like UI for CSV previews).
You open Lobe Chat and go to Settings > Plugin Store.
You click "Add Custom Plugin" and provide the URL to your backend's manifest: http://127.0.0.1:8000/api/manifests/devforge.json (use 127.0.0.1 for local to avoid CORS issues; update to deployed URL later).
What happens inside Lobe Chat? Lobe Chat's frontend fetches this URL, reads the JSON, and saves it to its internal state (Zustand store in src/store/plugin). It now knows two critical things from your manifest:
The "Menu" (api array): It knows you are offering tools like generate_data (with parameters query and format). This is passed to the LLM (e.g., Ollama via AgentRuntime) during chat flows.
The "Phone Number" (gateway key): It knows that for any tool call, it must send an HTTP POST request to http://127.0.0.1:8000/api/gateway (central dispatcher in src/api/routers.py).
Part 2: The Execution Flow (Runtime Integration)
Once handshaked, here's the step-by-step flow for a user query (e.g., "Generate 100 user records in CSV"):

User Input in Lobe Chat: Typed in the UI (src/features/ChatInput), captured and sent to Lobe Chat's BFF API route (src/app/(backend)/webapi/chat/[provider]/route.ts).
LLM Orchestration in Lobe Chat: AgentRuntime (src/libs/agent-runtime/) builds the prompt + chat history + enabled plugin APIs (from Zustand store). It calls the LLM (e.g., Ollama at OLLAMA_HOST from your .env).
Tool Call Decision: The LLM (e.g., Gemma-3:1B) recognizes the need for a tool (based on the manifest's api description) and returns a tool_call object (e.g., {name: "generate_data", arguments: {"query": "100 user records", "format": "csv"}}).
Gateway Call to Backend: Lobe Chat intercepts the tool_call, looks up the gateway URL from the store, and POSTs to your FastAPI /api/gateway with the body {name: "generate_data", arguments: "{"query": "100 user records", "format": "csv"}"}.
Backend Processing: FastAPI receives the request (validated via Pydantic in src/core/schemas.py). The gateway router (src/api/routers.py) dispatches based on name:

For "generate_data": Invokes the LangGraph workflow (src/agents/datagen/agent.py), which parses the query, calls tools (src/tools/datagen/tools.py with Pandas/Faker), and formats output (JSON or CSV). Returns the result (e.g., {"data": "CSV string or JSON list"}).

For "retrieve_docs": Invokes the RAG agent (src/agents/rag/agent.py), which ingests documents if provided, performs semantic search, reranks results (Phase 4), and generates contextually-aware responses. Returns result with documents and response.

For "github_operation": Extracts query from arguments and invokes the GitHub agent (src/agents/github/agent.py), which parses the natural language query, determines the operation (list repos, create issue, etc.), and executes via PyGithub. Returns operation result.

For "rerank_docs": Invokes the reranker (src/agents/reranker.py), which uses Cross-Encoder models to re-score documents by relevance. Returns reranked document list.

For "refine_prompt": Invokes the prompt refiner agent (src/agents/prompt_refiner/agent.py), which enhances prompts for specific domains (image, code, rag, llm) with context awareness. Returns refined prompt.

For "generate_cheatsheet": Invokes the cheat sheet agent (src/agents/cheatsheet/agent.py), which generates dynamic cheat sheets based on language and skill level. Returns markdown-formatted cheat sheet.


Response Back to Lobe Chat: The result is fed back to the LLM as a "tool response." The LLM generates a final user-friendly message (e.g., "Here's your generated data: [preview]"), which streams to the UI via SSE (fetchSSE in src/services/chat.ts), updating the Zustand chat store.

Part 3: Enhancements for Future Scopes

**Multi-Tool Support (Phases 1-7 - COMPLETE):**
The manifest (v0.7.0) now includes six tools: `generate_data`, `retrieve_docs`, `github_operation`, `rerank_docs`, `refine_prompt`, and `generate_cheatsheet`. The gateway (`src/api/routers.py`) dispatches to the appropriate agent based on tool name, with special handling for GitHub operations (extracts `query` from arguments).

**Multi-Model Routing (Phase 2 & 3 - COMPLETE):**
The supervisor agent (`src/agents/supervisor.py`) classifies user intents and routes to specialized agents:
- "datagen" → DataGen agent (qwen3:4b)
- "rag" → RAG agent (gpt-oss:20b / gpt-oss:120b-cloud)
- "github" → GitHub agent (qwen3-coder:480b-cloud)

**Additional Features (Phases 4, 6, 7 - COMPLETE):**
- Phase 4: Document reranking integrated into RAG workflow
- Phase 6: Prompt refinement with domain-specific handlers
- Phase 7: Dynamic cheat sheet generation with language detection

Security/Production: Use API keys in .env for auth (add middleware in main.py). For deployment (Phase 5 - DEFERRED), use Docker Compose to run both servers together; update gateway/manifest URLs to https://your-domain.com.
Testing: After setup, test E2E: Add plugin via URL > Enable in an assistant > Prompt in chat. Monitor FastAPI logs for POSTs; use tools like Postman to simulate gateway calls.
Troubleshooting: If CORS errors, verify middleware in main.py. If manifest fetch fails, ensure backend is running first. For hybrid JS/Python (stretch), expose JS agents as separate MCP gateways.

## Part 4: Phase Verification

### Phase 1 Verification (Nov 2, 2025)

**Confirmed Working:**
- ✅ Manifest served at `/api/manifests/devforge.json`
- ✅ Gateway dispatches `generate_data` tool correctly
- ✅ JSON/CSV generation with custom fields
- ✅ All 36 tests passing
- ✅ CORS configured for `localhost:3000`
- ✅ Performance: < 5s for 100 rows

### Phase 3 Verification (Nov 4, 2025)

**Confirmed Working:**
- ✅ All Phase 3 tools functional: `generate_data`, `retrieve_docs`, `github_operation`
- ✅ RAG agent with ChromaDB and Qdrant Cloud support
- ✅ GitHub agent with PyGithub integration
- ✅ Supervisor routing for all three agent types
- ✅ Comprehensive test coverage (100+ tests total)
- ✅ Manifest updated to v0.3.0 with all three tools
- ✅ Performance: RAG retrieval < 2s, GitHub operations < 3s

### Phase 4 Verification (Nov 21, 2025)

**Confirmed Working:**
- ✅ Reranker agent functional with Cross-Encoder models
- ✅ RAG workflow automatically reranks retrieved documents
- ✅ `rerank_docs` tool added to manifest (v0.4.0)
- ✅ Unit tests passing for reranking logic
- ✅ Improved retrieval quality with reranking

### Phase 6 Verification (Nov 22, 2025)

**Confirmed Working:**
- ✅ Prompt refiner agent functional with domain handlers
- ✅ Context-aware prompt enhancement (uses file_context)
- ✅ Support for domains: image, code, rag, llm, general
- ✅ Skill-level adaptation (beginner, intermediate, expert)
- ✅ `refine_prompt` tool added to manifest (v0.6.0)
- ✅ Unit tests passing

### Phase 7 Verification (Nov 23, 2025)

**Confirmed Working:**
- ✅ Cheat sheet generator functional
- ✅ Language detection from code context
- ✅ Skill-level based content generation
- ✅ Support for multiple languages (Python, JavaScript, TypeScript, etc.)
- ✅ `generate_cheatsheet` tool added to manifest (v0.7.0)
- ✅ Unit tests passing

**Current Status (v0.7.0):**
- ✅ All 6 tools functional and tested
- ✅ Comprehensive test coverage (100+ tests)
- ✅ Manifest version: v0.7.0
- ✅ All phases 1-7 complete (Phase 5 deployment deferred)

This refined integration ensures seamless modularity, aligning with your DevForge phases—start with DataGen, expand iteratively. If issues arise (e.g., Ollama integration), debug via Lobe Chat's console or FastAPI's /docs Swagger UI.