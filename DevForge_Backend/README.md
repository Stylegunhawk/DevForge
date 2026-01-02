# DevForge Backend

FastAPI backend for DevForge AI-powered developer tools. Provides MCP integration with Lobe Chat for modular tool execution.

## Quick Start

### 1. Environment Setup

Copy the example environment file and configure:

```bash
cp .env.example .env
# Edit .env with your settings (PORT, OLLAMA_HOST, etc.)
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
# Or install in development mode:
pip install -e .
```

### 3. Run the Server

```bash
uvicorn src.main:app --reload --port 8000
```

Or use the PORT from your .env:

```bash
uvicorn src.main:app --reload --port ${PORT}
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

**Expected Output:**
```json
{"status":"ok","uptime":123.45}
```

### Root
```bash
curl http://localhost:8000/
```

**Expected Output:**
```json
{
  "message": "DevForge backend running",
  "version": "0.1.0",
  "docs": "/docs",
  "health": "/health"
}
```

### Manifest (for Lobe Chat)
```bash
curl http://localhost:8000/api/manifests/devforge.json
```

**Expected Output:**
```json
{
  "name": "devforge",
  "version": "0.1.0",
  "description": "DevForge AI-powered developer tools",
  "schema_version": "v1",
  "gateway": "http://localhost:8000/api/gateway",
  "tools": [
    {
      "name": "generate_data",
      "description": "Generate realistic mock CSV/JSON data...",
      "parameters": { ... }
    }
  ]
}
```

### Gateway (Tool Execution)

#### Generate JSON Data
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{"name":"generate_data","arguments":"{\"rows\":5,\"format\":\"json\"}"}'
```

**Expected Output:**
```json
{
  "success": true,
  "tool": "generate_data",
  "format": "json",
  "data": "[{\"name\":\"John Doe\",\"email\":\"john@example.com\",...}, ...]",
  "error": null,
  "execution_time": 0.0234
}
```

#### Generate CSV Data
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{"name":"generate_data","arguments":"{\"rows\":5,\"format\":\"csv\"}"}'
```

**Expected Output:**
```json
{
  "success": true,
  "tool": "generate_data",
  "format": "csv",
  "data": "name,email,address,...\nJohn Doe,john@example.com,...",
  "error": null,
  "execution_time": 0.0187
}
```

#### Generate with Custom Fields
```bash
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{"name":"generate_data","arguments":"{\"rows\":3,\"format\":\"json\",\"fields\":[\"email\",\"phone\"]}"}'
```

**Expected Output:**
```json
{
  "success": true,
  "tool": "generate_data",
  "format": "json",
  "data": "[{\"email\":\"user@example.com\",\"phone\":\"+1234567890\"}, ...]",
  "error": null,
  "execution_time": 0.0156
}
```

## Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test Suites
```bash
# Unit tests for DataGen tools
pytest tests/test_datagen.py -v

# API integration tests
pytest tests/test_api.py -v

# End-to-end integration tests
pytest tests/test_end_to_end.py -v
```

### Test Coverage
Phase 1 includes comprehensive test coverage:
- **Unit Tests**: 13 tests for DataGen tools (CSV/JSON generation, validation, edge cases)
- **Integration Tests**: 13 tests for API endpoints (manifest, gateway, error handling)
- **End-to-End Tests**: 10 tests for complete workflow verification

**Total: 36 tests** covering all Phase 1 functionality.

## Architecture

- **FastAPI**: Async web framework
- **MCP Integration**: Manifest + Gateway pattern for Lobe Chat
- **Modular Agents**: Feature-based agent organization (datagen, rag, github)
- **LangChain**: Model integration (Phase 2+)

## Phase 1 Features (v0.1.0)

- ✅ DataGen agent (CSV/JSON mock data generation)
- ✅ MCP manifest serving
- ✅ Gateway endpoint with tool dispatch
- ✅ CORS configuration
- ✅ Structured logging
- ✅ Performance tracking

### 3. RAG (Retrieval-Augmented Generation)

**Phase 11.2 Complete - Production Ready** ✅

**Advanced Retrieval:**
- 🔍 **Hybrid Search** - BM25 keyword + Vector semantic with RRF fusion (+8-12% accuracy)
- 🚀 **Query Cache** - Exact-match caching (10-50ms vs 250ms, Redis + LRU fallback)
- 🎯 **Cross-Encoder Reranking** - Two-stage retrieval (ms-marco-MiniLM-L-6-v2)
- ⚡ **Code-Aware Boosting** - Prioritize functions, classes over text
- 📊 **Observability** - /rag/metrics and /rag/health endpoints

**Core Features:**
- 📝 **Code-Aware Chunking** - AST-based parsing (Tree-sitter) for Python, JS, TS
- 🔗 **Dependency Graph** - BFS traversal with QID-based linking
- 🧪 **Test-Source Linking** - Automatic test file association
- ⚙️ **Async Processing** - Celery task queue for ingestion
- 🔌 **Vector Store Abstraction** - ChromaDB + pgvector support

**Performance:**
- <50ms cached queries
- <200ms reranking overhead (30 candidates)
- <300MB memory footprint
- 40-60% cache hit rate (production)

## 🧠 Phase 3 Summary (v0.3.1)

Phase 3 introduced RAG (Retrieval-Augmented Generation) and GitHub automation.

**Key Highlights:**
- ✅ **RAG Agent**: Document ingestion (PDF, MD, TXT, DOCX) and semantic search using ChromaDB (local) and Qdrant (cloud).
- ✅ **GitHub Agent**: Automate repository operations (list repos, create issues, PRs) using PyGithub.
- ✅ **Supervisor Integration**: Intelligent routing for "rag" and "github" intents.
- ✅ **Dual Vector Store**: Seamless fallback between local ChromaDB and cloud Qdrant.
- ✅ **Manifest Update**: Bumped to `v0.3.1` with new tools `retrieve_docs` and `github_operation`.

**New Components:**
- `src/agents/rag/` & `src/tools/rag/` - Document processing and retrieval.
- `src/agents/github/` & `src/tools/github/` - GitHub API integration.
- `src/core/model_router.py` - Updated with RAG and GitHub model profiles.

## 🧠 Phase 4 Summary (v0.4.0)

Phase 4 focused on improving RAG retrieval quality through reranking.

**Key Highlights:**
- ✅ **Reranker Agent**: Uses `sentence-transformers` and Cross-Encoder models to re-score retrieved documents.
- ✅ **RAG Integration**: Automatically reranks documents before context generation.
- ✅ **New Tool**: `rerank_docs` added to MCP manifest.

## 🎨 Phase 6 Summary (v0.6.0)

Phase 6 added a **Prompt Refinement Agent** to optimize user prompts for various domains.

**Key Highlights:**
- ✅ **Prompt Refiner Agent**: Enhances prompts for Image, Code, RAG, and LLM tasks.
- ✅ **Context Awareness**: Uses file context to tailor prompts to specific code or documentation.
- ✅ **New Tool**: `refine_prompt` added to MCP manifest.

### Next Phase: Deployment (v0.7.0)

Phase 5 (Deployment) was deferred and is the next logical step.

## Project Structure

```
DevForge_Backend/
├── src/
│   ├── main.py              # FastAPI app entry point
│   ├── api/routers.py       # Gateway + manifest endpoints
│   ├── agents/
│   │   ├── datagen/         # DataGen agent (Phase 1)
│   │   ├── supervisor.py    # Supervisor routing (Phase 2)
│   │   ├── rag/             # RAG agent (Phase 3)
│   │   └── github/          # GitHub agent (Phase 3)
│   ├── tools/
│   │   ├── datagen/         # DataGen tools
│   │   ├── rag/             # RAG tools (Phase 3)
│   │   └── github/          # GitHub tools (Phase 3)
│   └── core/                # Config, schemas, utils, model_router
├── manifests/               # Plugin manifests (v0.3.1)
├── tests/                   # Test suite (58+ tests)
└── requirements.txt        # Dependencies
```

## Development

### Adding New Tools

1. Create tool functions in `src/tools/<feature>/tools.py`
2. Create agent in `src/agents/<feature>/agent.py`
3. Add tool to `SUPPORTED_TOOLS` in `src/api/routers.py`
4. Update `manifests/devforge.json` with tool definition

## Integration with Lobe Chat

1. Start the backend server
2. In Lobe Chat, go to Settings > Plugin Store
3. Add custom plugin with URL: `http://localhost:8000/api/manifests/devforge.json`
4. Enable the plugin in your assistant
5. Start using tools via chat!

## Environment Variables

See `.env.example` for all available configuration options:

- `PORT`: Server port (default: 8000)
- `CORS_ORIGINS`: Comma-separated allowed origins
- `OLLAMA_HOST`: Ollama API endpoint
- `DEFAULT_MODEL`: Primary model (Phase 1)
- See `.env.example` for all model configurations

## Phase 1 Verification Checklist

Before considering Phase 1 complete, verify all items:

### Server Setup
- [ ] Server starts without errors: `uvicorn src.main:app --reload --port 8000`
- [ ] Health endpoint returns 200: `curl http://localhost:8000/health`
- [ ] Root endpoint returns API info: `curl http://localhost:8000/`

### Manifest Integration
- [ ] Manifest loads successfully: `curl http://localhost:8000/api/manifests/devforge.json`
- [ ] Manifest contains `tools` array with `generate_data` tool
- [ ] Manifest gateway URL matches actual server port
- [ ] Manifest uses `parameters` (not `input_schema`) per Lobe Chat standard

### Gateway Functionality
- [ ] POST `/api/gateway` with `generate_data` returns 200
- [ ] Response includes `success: true` for valid requests
- [ ] Response includes `execution_time` field (numeric, > 0)
- [ ] JSON generation works: `{"name":"generate_data","arguments":"{\"rows\":5,\"format\":\"json\"}"}`
- [ ] CSV generation works: `{"name":"generate_data","arguments":"{\"rows\":5,\"format\":\"csv\"}"}`
- [ ] Custom fields work: `{"fields":["email","phone"]}`
- [ ] Unsupported tool returns 400: `{"name":"unknown_tool","arguments":"{}"}`
- [ ] Invalid arguments return 400: `{"rows":0}` or `{"rows":50000}`

### Data Quality
- [ ] Generated JSON is valid and parseable
- [ ] Generated CSV has header row
- [ ] Row count matches requested count
- [ ] Default fields are present when no custom fields specified
- [ ] Custom fields are respected when provided

### Performance
- [ ] Small datasets (5-10 rows) complete in < 1 second
- [ ] Medium datasets (100 rows) complete in < 5 seconds
- [ ] Execution time is tracked and reported accurately

### Lobe Chat Integration (Manual Testing)
- [ ] Backend server running on `localhost:8000`
- [ ] Lobe Chat can fetch manifest from `http://localhost:8000/api/manifests/devforge.json`
- [ ] Manifest appears in Lobe Chat plugin store
- [ ] Plugin can be enabled in assistant settings
- [ ] Tool calls work from Lobe Chat UI (e.g., "Generate 10 user records")

### Test Suite
- [ ] All tests pass: `pytest tests/ -v`
- [ ] No linter errors: Code passes PEP-8 checks
- [ ] Imports resolve correctly: No ModuleNotFoundError

### Documentation
- [ ] README.md includes all curl examples
- [ ] README.md includes expected outputs
- [ ] `.env.example` includes all required variables
- [ ] Code includes docstrings for all public functions

### Security & Best Practices
- [ ] CORS configured for Lobe Chat origin
- [ ] No stack traces exposed to clients (errors logged server-side)
- [ ] Environment variables used for sensitive data
- [ ] Input validation on all endpoints
### Phase 3 Verification Checklist (RAG + GitHub)

- [ ] **RAG Agent**:
    - [ ] Document ingestion works (PDF/MD/TXT).
    - [ ] Semantic search returns relevant context.
    - [ ] Fallback to cloud vector store works if local fails.
- [ ] **GitHub Agent**:
    - [ ] Can list repositories (`list my repos`).
    - [ ] Can create issues (`create issue...`).
    - [ ] Token authentication is working.
- [ ] **Supervisor**:
    - [ ] Correctly routes "search..." to RAG agent.
    - [ ] Correctly routes "create repo..." to GitHub agent.
- [ ] **Tests**:
    - [ ] All tests pass: `pytest tests/ -v` (should be >90 tests).

### Phase 4 Verification Checklist (Reranking)
- [ ] **Reranker**:
    - [ ] `Reranker` class initializes with default model.
    - [ ] `rerank()` method correctly sorts documents by relevance.
    - [ ] RAG agent uses reranker when available.
- [ ] **Tests**:
    - [ ] `pytest tests/test_reranker.py` passes.

### Phase 6 Verification Checklist (Prompt Refiner)
- [ ] **Prompt Refiner**:
    - [ ] `PromptRefinerAgent` initializes correctly.
    - [ ] `refine_prompt` tool works via Gateway.
    - [ ] Context-aware refinement functions as expected.
- [ ] **Tests**:
    - [ ] `pytest tests/test_prompt_refiner.py` passes.

### Phase 1 Verification Checklist
- [ ] Server starts without errors.
- [ ] Manifest loads successfully.
- [ ] DataGen tool works via Gateway.
- [ ] CORS configured correctly.

## Integration with Lobe Chat

### Step-by-Step Setup

1. **Start Backend Server**
   ```bash
   uvicorn src.main:app --reload --port 8000
   ```

2. **Verify Manifest is Accessible**
   ```bash
   curl http://localhost:8000/api/manifests/devforge.json
   ```
   Should return valid JSON with `tools` array.

3. **Add Plugin in Lobe Chat**
   - Open Lobe Chat in browser
   - Go to Settings → Plugin Store
   - Click "Add Custom Plugin"
   - Enter URL: `http://localhost:8000/api/manifests/devforge.json`
   - Save

4. **Enable Plugin in Assistant**
   - Create or edit an assistant
   - Enable the "devforge" plugin
   - Save assistant settings

5. **Test Tool Execution**
   - Start a chat with the assistant
   - Try: "Generate 10 user records in JSON format"
   - The LLM should recognize the tool and call it
   - You should see generated data in the response

### Troubleshooting

**Manifest not loading:**
- Verify server is running: `curl http://localhost:8000/health`
- Check CORS settings in `.env`: `CORS_ORIGINS=http://localhost:3000`
- Verify manifest endpoint: `curl http://localhost:8000/api/manifests/devforge.json`

**Tool calls failing:**
- Check server logs for error messages
- Verify tool name matches manifest: `"name": "generate_data"`
- Test gateway directly with curl (see examples above)
- Check Lobe Chat console for errors

**CORS errors:**
- Ensure `CORS_ORIGINS` includes Lobe Chat origin (usually `http://localhost:3000`)
- Restart server after changing `.env` file
- Check browser console for specific CORS error messages

## License

See LICENSE file in project root.

