CORS enabled for http://localhost:3000

Version 0.7.0 – Updated 23 Nov 2025 (Phase 7 Complete)

**Current Status:**
- ✅ Phases 1-7 Complete (Phase 5 Deployment Deferred)
- ✅ 6 Tools Implemented: DataGen, RAG, GitHub, Reranker, Prompt Refiner, Cheat Sheets
- ✅ 100+ Tests Passing
- ✅ Manifest Version: v0.7.0

Testing with pytest in tests/

Logging via Python logging module (JSON in production)

.env.example
PORT=8000
OLLAMA_HOST=http://localhost:11434
DEFAULT_MODEL=qwen3:4b
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=info
# Optional
GITHUB_TOKEN=
DATABASE_URL=postgresql://user:pass@localhost:5432/devforge
# RAG Configuration
VECTOR_BACKEND=chroma
RAG_EMBED_MODEL=nomic-embed-text
# Qdrant Cloud (optional)
QDRANT_URL=
QDRANT_API_KEY=

8. Sample Manifest (devforge.json) - v0.7.0
{
  "identifier": "devforge",
  "name": "DevForge",
  "meta": {
    "author": "You",
    "version": "0.7.0",
    "description": "Local developer tools (data generation, RAG, GitHub automation, and Cheat Sheets)"
  },
  "api": [
    {
      "name": "generate_data",
      "description": "Generate mock CSV/JSON data using Faker and Pandas.",
      "parameters": {
        "type": "object",
        "properties": {
          "rows": { "type": "integer", "minimum": 1, "maximum": 10000, "default": 10 },
          "format": { "type": "string", "enum": ["json", "csv"], "default": "json" },
          "fields": { "type": "array", "items": { "type": "string" } }
        },
        "required": ["rows"]
      }
    },
    {
      "name": "retrieve_docs",
      "description": "Search documents using RAG (ChromaDB / Qdrant). Ingest documents and query them semantically."
    },
    {
      "name": "github_operation",
      "description": "Perform GitHub actions such as listing repositories, creating issues, committing files, and opening pull requests."
    },
    {
      "name": "rerank_docs",
      "description": "Rerank retrieved documents by relevance using cross-encoder"
    },
    {
      "name": "refine_prompt",
      "description": "Refine and optimize a prompt for specific domains (image, code, rag, llm)"
    },
    {
      "name": "generate_cheatsheet",
      "description": "Generate a dynamic cheat sheet for a programming language based on skill level."
    }
  ]
}

9. Local Testing
uvicorn src.main:app --reload --port 8000
curl http://localhost:8000/api/manifests/devforge.json
curl -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{"tool":"generate_data","args":{"rows":10,"format":"json"}}'

10. Success Criteria

✅ **Phase 1:** End-to-end chat with DataGen works in < 5s (using local Ollama models)
✅ **Phase 1:** Manifest loads successfully via URL (no manual upload)
✅ **Phase 3:** At least 2 additional tools (RAG + GitHub) implemented
✅ **Phase 4:** Document reranking integrated into RAG workflow
✅ **Phase 6:** Prompt refinement with domain-specific handlers
✅ **Phase 7:** Dynamic cheat sheet generation with language detection

**Completed Phases:**
- Phase 1 | ✅ Complete | Foundation (DataGen) | v0.1.0
- Phase 2 | ✅ Complete | Multi-Model Routing | v0.2.0
- Phase 3 | ✅ Complete | RAG + GitHub | v0.3.1
- Phase 4 | ✅ Complete | Document Reranking | v0.4.0
- Phase 5 | ⏳ Deferred | Deployment (Docker + Render)
- Phase 6 | ✅ Complete | Prompt Refinement | v0.6.0
- Phase 7 | ✅ Complete | Dynamic Cheat Sheets | v0.7.0

**Next Phase:** Phase 8 (Enhanced DevOps) or Phase 5 (Deployment)