# Cheatsheet LLM Enrichment

## Overview
The `generate_cheatsheet` tool now supports **Scoped LLM Enrichment** (Phase 6). This feature selectively uses an LLM (**Ollama gpt-oss:20b-cloud**) to add contextual "Debugging Tips" and "Latest API Changes" to template sections for fast-evolving libraries (like LangChain, LangGraph) where static templates might be outdated.

**Note**: Enrichment is part of the Template Path. For unsupported languages (Ruby, SQL, Rust, Go), the system uses the full LLM Path instead of enrichment.

## Architecture

The system uses a **Rule-Based Core with Optional Enrichment**:

1.  **Core Pipeline (<200ms)**: Rules detect libraries, score complexity, and select static templates (Pandas, FastAPI, Python Basics).
2.  **Enrichment Gate**: A smart detector decides if enrichment is needed.
3.  **Scoped Enricher**: If approved, the agent makes a targeted **Async Ollama call** to *append* tips to specific sections. It does NOT rewrite the entire cheat sheet.

## When Enrichment Triggers

Enrichment is strictly gated to control costs and latency. It only triggers if **ALL** conditions are met:

1.  **Feature Flag Enabled**: `ENABLE_LLM_ENRICHMENT=true`
2.  **Target Library Detected**: The code uses a "fast-evolving" library (e.g., `langchain`, `langgraph`, `autogen`, `crewai`, `llama-index`).
3.  **No Full Template**: The library does NOT have a comprehensive static template (unlike `pandas`).
4.  **Context Signal**: EITHER:
    *   User explicitly asks for "latest", "new", or "modern" syntax.
    *   Code contains error/debugging keywords + complex usage patterns.

## Configuration

To enable enrichment, set the following environment variables:

```bash
# .env
ENABLE_LLM_ENRICHMENT=true
OLLAMA_MODEL=gpt-oss:20b-cloud  # Default model
```

## Response Format

Enriched responses include metadata in the `data` field:

```json
{
  "success": true,
  "data": {
    "method": "enriched",  // vs "template"
    "enrichment": {
      "enabled": true,
      "reason": "user_needs_latest",
      "target_libraries": ["langchain"],
      "enriched_sections": ["LangChain Basics"]
    },
    // ... standard fields ...
  }
}
```

## Performance & Safety

*   **Latency**:
    *   Standard requests: **<500ms** (SLO)
    *   Enriched requests: **<5s** (SLO)
*   **Cost Control**: Max 300 output tokens per enrichment call.
*   **Fail-Safe**: If the LLM API fails or times out, the tool gracefully returns the standard static templates without enrichment.

## Template Promotion (Lifecycle)

To manage costs, high-frequency enrichments should be converted into permanent static templates. The system tracks this automatically.

*   **Telemetry**: Look for `"promotable": true` in the API response.
*   **Workflow**: See [Template Promotion Guide](./cheatsheet_promotion.md) for instructions on how to graduate content.

## Language Support

Enrichment works with **Template Path** languages (Python, JavaScript, TypeScript). For unsupported languages (Ruby, SQL, Rust, Go), the system uses the **LLM Path** instead, which generates complete cheatsheets rather than enriching templates.

## Testing

*   **Unit**: `tests/test_enrichment_detector.py`
*   **Integration**: `tests/test_enrichment_integration.py`
*   **Performance**: `tests/test_enrichment_performance.py`
