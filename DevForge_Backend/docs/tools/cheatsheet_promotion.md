# Cheatsheet Template Promotion

To maintain low latency (<200ms) and zero cost for common patterns, we use a **Template Promotion** workflow. This converts high-frequency LLM enrichments into permanent static templates.

## Metrics & Telemetry

The API response now includes promotion signals in `data.enrichment`:

```json
"enrichment": {
  "enabled": true,
  "confidence": 0.95,
  "promotable": true, // TRUE if enriched > 3 times
  "enriched_sections": ["LangChain Basics"]
}
```

## Workflow

1.  **Monitor Candidates**: 
    *   **Dashboard**: `GET /api/admin/promotions` to see sorted counts.
    *   **Logs**: Look for `PROMOTION CANDIDATE` logs.
2.  **Review Enrichment**: Check the generated content for quality.
3.  **Promote**:
    *   Copy the high-quality enrichment text.
    *   Paste it into the relevant section in `src/agents/cheatsheet/enhanced_templates.py`.
    *   (Optional) Remove the library from `FAST_EVOLVING_LIBS` in `config.py` if fully covered.

## Tracker Logic
See `src/agents/cheatsheet/promotion_tracker.py` for the in-memory counting logic.

## Language-Specific Notes

**Template Path Languages** (Python, JavaScript, TypeScript):
- Enrichments can be promoted to static templates
- Tracked via `promotion_tracker.py`

**LLM Path Languages** (Ruby, SQL, Rust, Go):
- Full cheatsheets are generated via LLM (not enrichments)
- No promotion workflow needed (content is always LLM-generated)
- Quality is validated via `validators.py` (60% language dominance rule)
