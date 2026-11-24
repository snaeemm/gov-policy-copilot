# ADR-0003: Pluggable re-ranker

Status: Accepted

**Context.** Azure semantic ranker is not available on the Search Free tier. A cross-encoder improves precision but adds ~0.5–2 GB of model weights and CPU latency.

**Decision.** `Reranker` protocol with three implementations selected by `RERANKER`: `none` (RRF order), `cross_encoder` (sentence-transformers, multilingual model, optional `rerank` extra), `azure_semantic` (sets `query_type=semantic` and orders by `@search.reranker_score`). Code: `retrieval/rerankers.py`.

**Current setting.** `none` in Azure (container stays small, CPU-only, scale-to-zero). Eval shows recall@5 = 1.0 without re-ranking on the current corpus, so the cost is not yet justified.

**Consequences.** Switching to the semantic ranker in production is a config change plus a Basic+ Search tier.

**Note / gap.** `config.py` defaults to `cross_encoder` while the extra is not installed by default — set `RERANKER=none` unless `uv sync --extra rerank` was run.
