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

For "generate_data": Invokes the LangGraph workflow (src/agents/datagen/agent.py), which parses the query, calls tools (src/tools/datagen/tools.py with Pandas/Faker), and formats output (JSON or CSV).
Returns the result (e.g., {"data": "CSV string or JSON list"}).


Response Back to Lobe Chat: The result is fed back to the LLM as a "tool response." The LLM generates a final user-friendly message (e.g., "Here's your generated data: [preview]"), which streams to the UI via SSE (fetchSSE in src/services/chat.ts), updating the Zustand chat store.

Part 3: Enhancements for Future Scopes

Multi-Tool Support: Add more entries to the manifest's api array (e.g., "retrieve_rag" in Phase 3). The gateway will handle dispatching to new agents/tools (e.g., elif req.name == "retrieve_rag" in routers.py).
Multi-Model Routing: In Phase 2, expand src/agents/supervisor.py to classify queries (e.g., via Ollama) and route to specialized agents (e.g., qwen3-coder for coding).
Security/Production: Use API keys in .env for auth (add middleware in main.py). For deployment (Phase 5), use Docker Compose to run both servers together; update gateway/manifest URLs to https://your-domain.com.
Testing: After setup, test E2E: Add plugin via URL > Enable in an assistant > Prompt in chat. Monitor FastAPI logs for POSTs; use tools like Postman to simulate gateway calls.
Troubleshooting: If CORS errors, verify middleware in main.py. If manifest fetch fails, ensure backend is running first. For hybrid JS/Python (stretch), expose JS agents as separate MCP gateways.

## Part 4: Phase 1 Verification (Nov 2, 2025)

**Confirmed Working:**
- ✅ Manifest served at `/api/manifests/devforge.json`
- ✅ Gateway dispatches `generate_data` tool correctly
- ✅ JSON/CSV generation with custom fields
- ✅ All 36 tests passing
- ✅ CORS configured for `localhost:3000`
- ✅ Performance: < 5s for 100 rows

**Ready for Phase 2:** Supervisor agent can now be added to gateway router.

This refined integration ensures seamless modularity, aligning with your DevForge phases—start with DataGen, expand iteratively. If issues arise (e.g., Ollama integration), debug via Lobe Chat's console or FastAPI's /docs Swagger UI.