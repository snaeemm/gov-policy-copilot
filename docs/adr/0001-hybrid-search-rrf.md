# ADR-0001: Hybrid retrieval (BM25 + vector) fused with RRF

Status: Accepted · 2026-11-24

**Context.** Policy questions mix exact terms (article numbers, acronyms like "ACCESS", entity names) with paraphrased intent. Pure vector search misses exact tokens; pure BM25 misses paraphrase and cross-lingual matches.

**Decision.** Azure AI Search hybrid query: `search_text` over `content_en`, `content_ar`, `title` plus a `VectorizedQuery` (k=20) on `content_vector`. Azure fuses both lists with Reciprocal Rank Fusion. Retriever: `src/gov_copilot/retrieval/retriever.py`.

**Consequences.** + Recall@5 = 1.0 on the golden set. + No extra infra; works on the Free tier. − RRF scores (~0.03) are rank-based, not calibrated probabilities, so they cannot be used as a confidence threshold — groundedness is checked separately (ADR-0004).

**Alternatives.** Vector-only (weaker on acronyms/ordinals); BM25-only (no cross-lingual); custom fusion in app code (unnecessary — native RRF).
