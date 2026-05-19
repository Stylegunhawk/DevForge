# rerank_docs - Document Reranking (Internal Stage)

**Tool Name:** `rerank_docs` (internal — not a standalone gateway tool)
**Version:** 1.1.0 (Phase 4)
**Status:** Implemented
**Last Updated:** 2026-05-19
**Last Verified:** 2026-05-19 — reranker behavior unchanged; version bump aligns with RAG v1.1.0 provenance rollout

---

## Overview

The reranker re-scores candidate chunks returned by vector search using a Cross-Encoder model. It is **invoked internally** as a stage of `retrieve_docs` (the RAG agent) and is **not** registered in `SUPPORTED_TOOLS`. There is no public `name=rerank_docs` route on `/api/gateway` or `/mcp`; callers cannot pass their own `documents` array. The reranker only operates on the internal list of `ChunkResult` objects produced by the upstream vector search step.

**Phase 4 features:**
- Cross-Encoder reranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`)
- Sigmoid score normalization to `[0, 1]`
- Code-aware boosting (function 1.2x, class 1.15x, import 1.0x, text 0.95x)
- Threshold filtering with a fallback ladder (`RERANK_SCORE_THRESHOLD=0.3`)
- Two-stage recall: 30 vector candidates → reranker → top-K
- CPU-only model load (portable, ~100–150ms for 30 candidates)

---

## How It Works

### Pipeline (inside `retrieve_docs`)

```
Query
  → Vector search (top 30 candidates, VECTOR_SEARCH_CANDIDATES=30)
  → Cross-Encoder.predict(query, chunk.content[:2048])  # raw logits
  → Sigmoid normalization → rerank_score in [0, 1]
  → apply_code_boost (BOOST_FUNCTION/CLASS/IMPORT/TEXT)
  → Sort by boosted score, keep top_k * 2
  → Threshold filter (rerank_score >= RERANK_SCORE_THRESHOLD = 0.3)
  → Fallback ladder (see below)
  → Return final top-K
```

### Fallback ladder

After threshold filtering against `RERANK_SCORE_THRESHOLD = 0.3`:

| Chunks passing threshold | Behaviour |
|--------------------------|-----------|
| ≥ 3 | Return the chunks that passed |
| 1–2 | Pad back up to `top_k` from the boosted-but-below-threshold pool |
| 0 | Bypass threshold entirely; return the top-K boosted chunks as-is |

This keeps the agent from returning empty context on weak queries while still preferring high-confidence chunks when they exist.

### Code-aware boosting

After sigmoid normalization, scores are multiplied by a per-chunk-type factor:

| Chunk type (`metadata.chunk_type`) | Boost env var | Default factor |
|------------------------------------|---------------|----------------|
| `function` | `BOOST_FUNCTION` | `1.2` |
| `class` | `BOOST_CLASS` | `1.15` |
| `import` | `BOOST_IMPORT` | `1.0` |
| `text` / markdown / other | `BOOST_TEXT` | `0.95` |

This prioritises executable code entities for code-style queries while gently de-prioritising prose.

### `top_k * 2` over-fetch and re-sort

The RAG agent calls the reranker with `top_k * 2` so that boosting + threshold filtering still has headroom to drop weak chunks before the final cut to `top_k`. The final sort is performed on the boosted score, not the raw logit.

---

## Cross-Encoder Model

**Model:** `cross-encoder/ms-marco-MiniLM-L-6-v2`

- 6-layer MiniLM (~22.7M parameters)
- CPU-only load (`device='cpu'`)
- Token cap `max_length=512`; chunk content is pre-truncated to 2048 chars before being passed in
- Sigmoid maps unbounded logits (~`[-10, 10]`) to a stable `[0, 1]` range so thresholds remain interpretable

**Sigmoid normalization:** `1 / (1 + exp(-raw_score))`
- `0.5` → neutral (logit ≈ 0)
- `0.7+` → relevant (logit > 1)
- `0.3` → "somewhat relevant" threshold

---

## Configuration

Environment variables consumed by the live reranker (see `src/core/config.py`):

```
RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
RERANK_SCORE_THRESHOLD=0.3
VECTOR_SEARCH_CANDIDATES=30

BOOST_FUNCTION=1.2
BOOST_CLASS=1.15
BOOST_IMPORT=1.0
BOOST_TEXT=0.95

ENABLE_RERANKING=true
```

Note: `RERANK_MIN_SCORE` is **not** a valid setting — the real knob is `RERANK_SCORE_THRESHOLD`.

---

## Integration with RAG

`retrieve_docs` invokes the reranker automatically when `ENABLE_RERANKING=true`:

```python
# Simplified flow inside src/agents/rag/agent.py
candidates = vector_store.search(query, top_k=VECTOR_SEARCH_CANDIDATES)  # 30
reranked = await self.reranker.rerank(query, candidates, top_k=top_k * 2)
boosted = self.reranker.apply_code_boost(reranked)
boosted.sort(key=lambda c: c.rerank_score, reverse=True)

passed = [c for c in boosted if c.rerank_score >= settings.RERANK_SCORE_THRESHOLD]
if len(passed) >= 3:
    final = passed[:top_k]
elif len(passed) >= 1:
    final = (passed + [c for c in boosted if c not in passed])[:top_k]
else:
    final = boosted[:top_k]  # fallback: return best-effort
```

---

## Implementation Details

### Technology Stack
- **sentence-transformers** 2.6 — Cross-encoder framework
- **transformers** 4.38 — Hugging Face library
- **torch** 2.9 (CPU) — Deep learning backend

### Code Location
- Live reranker: `src/agents/rag/reranking/cross_encoder_reranker.py`
- Base interface: `src/agents/rag/reranking/base_reranker.py`
- Tests: `tests/test_reranker.py`

### Class signature (live)

```python
class CrossEncoderReranker(BaseReranker):
    def __init__(self, model_name: Optional[str] = None): ...

    @staticmethod
    def normalize_score(raw_score: float) -> float: ...

    async def rerank(
        self,
        query: str,
        chunks: List[ChunkResult],
        top_k: int = 5,
    ) -> List[ChunkResult]: ...

    def apply_code_boost(
        self,
        chunks: List[ChunkResult],
    ) -> List[ChunkResult]: ...
```

`rerank()` resets `chunk.rerank_score = 0.0` on entry to prevent state leakage across requests, runs `model.predict` inside `asyncio.to_thread` to keep the event loop unblocked, and returns the top-`top_k` chunks sorted by normalized score. `apply_code_boost()` mutates the chunks in place using the `BOOST_*` factors.

---

## Testing

```bash
pytest tests/test_reranker.py -v
```

Covers basic reranking, score reset between calls, top-k selection, empty-input handling, and code-aware boosting.

---

## Limitations

1. **Internal-only.** No public `rerank_docs` endpoint; the reranker only runs as a stage of `retrieve_docs`. Callers cannot supply their own `documents` array.
2. **Document length.** Content is pre-truncated to 2048 chars and the model truncates to 512 tokens internally. Very long chunks lose tail content.
3. **Language.** Tuned on MS MARCO (English); accuracy degrades for non-English queries.
4. **CPU-only.** No GPU code path — latency scales linearly with candidate count.

---

## Related

- `retrieve_docs` — the RAG agent stage that owns the reranker call
- `src/core/config.py` — all `RERANK_*` and `BOOST_*` settings

---

**Last Updated:** 2026-05-19
**Maintainer:** DevForge Team

---

## Changelog

### 2026-05-19 — v1.1.0: Version alignment

- No behavioral changes to the reranker itself.
- Version bumped to align with RAG v1.1.0 rollout (graph expansion provenance fields added upstream in `retrieve_docs`, `rag_integration_flow`, `rag_architecture`).
- Graph-expanded chunks entering the reranker now carry `is_graph_expansion=True` and `expanded_from` in their dict; the reranker treats them identically to vector-retrieved chunks (scores them without special-casing).
