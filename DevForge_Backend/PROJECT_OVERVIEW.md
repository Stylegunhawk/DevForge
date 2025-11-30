CORS enabled for http://localhost:3000

Version 1.6 – Updated 23 Nov 2025 (Phase 7 Complete)

Testing with pytest in tests/

Logging via Python logging module (JSON in production)

.env.example
PORT=8000
OLLAMA_HOST=http://localhost:11434
DEFAULT_MODEL=gemma-1b
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=info
# Optional
GITHUB_TOKEN=
DATABASE_URL=postgresql://user:pass@localhost:5432/devforge

8. Sample Manifest (devforge.json)
{
  "name": "devforge",
  "version": "0.1.0",
  "description": "DevForge plugin manifest — DataGen tool",
  "gateway": "http://localhost:8000/api/gateway",
  "schema_version": "v1",
  "tools": [
    {
      "name": "generate_data",
      "description": "Generate mock CSV/JSON data using Faker and Pandas",
      "endpoint": "/api/datagen",
      "input_schema": {
        "type": "object",
        "properties": {
          "rows": { "type": "integer", "default": 100 },
          "format": { "type": "string", "enum": ["csv", "json"], "default": "json" },
          "fields": { "type": "array", "items": { "type": "object" } }
        },
        "required": ["rows"]
      }
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

End-to-end chat with DataGen works in < 5 s (using local Ollama models)

Manifest loads successfully via URL (no manual upload)

At least 2 additional tools (RAG + GitHub) by Phase 3
Phase 7 | ✅ Complete | 19-20 | Dynamic Cheat Sheets | v0.7.0

Docker image deployable on Render