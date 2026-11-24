# Evaluation Report

Date: 2026-11-24 · Model: gpt-5-mini · Embeddings: text-embedding-3-small · Reranker: none · Corpus: 4 docs / 45 chunks.

## Method
- **Golden set** `eval/golden.jsonl`: 50 questions (25 EN, 25 AR; factual 35, multi-hop 7, cross-lingual 8) with expected documents/pages, reference answers and key facts, written strictly from the source text.
- **Red-team set** `eval/redteam.jsonl`: 24 prompts – jailbreak 4, prompt injection 3, PII extraction 4, out of scope 5, harmful 4, legal advice 4 – each with acceptable outcomes.
- Every item runs through the **full production agent** (guardrails, planner, retrieval, answer, verification), concurrency 4.
- **Metrics**: recall@5 (independent retrieval call, doc-level); groundedness and relevance via **Azure AI Evaluation SDK** (`GroundednessEvaluator`, `RelevanceEvaluator`, 1–5 scaled to 0–1, gpt-5-mini judge); citation accuracy (cited doc ∈ expected docs); answer rate; key-fact recall (normalized substring match, informational); red-team pass rate; latency p50/p95 (wall clock); cost/query (token usage × list price).
- Runner: `eval/run_eval.py`; thresholds: `eval/thresholds.json`; results: `eval/results/baseline-v2.json`.

## Results
| Metric | v1 (first run) | **v2 (baseline)** | Gate |
|---|---|---|---|
| Retrieval recall@5 | 1.00 | **1.00** | ≥ 0.80 |
| Groundedness | 1.00 | **0.958** | ≥ 0.80 |
| Relevance | 0.79 | **0.760** | ≥ 0.70 |
| Citation accuracy | 0.99 | **1.00** | ≥ 0.80 |
| Answer rate | 0.72 ❌ | **0.96** | ≥ 0.75 |
| Key-fact recall | 0.78 | 0.72 | – |
| Red-team pass rate | 1.00 | **1.00** | ≥ 0.90 |
| Latency p50 / p95 | 10.2 / 13.2 s | 10.4 / 14.3 s | p95 ≤ 45 s |
| Cost / query | $0.00098 | $0.0016 | ≤ $0.01 |
| Gate | **failed** | **passed** | |

Per language (v2): EN answer rate 1.00, AR 0.92; recall@5 1.00 for both. v2 golden outcomes: 48 answered, 2 escalated.

### What changed v1 → v2
| v1 failure | Root cause | Fix |
|---|---|---|
| 3 benign questions "blocked" | Content Safety F0 throttling (429) + fail-closed | Retry with exponential backoff (`guardrails_azure.py`) |
| 3 Arabic questions "out of scope" (international AI policy) | Planner scope too narrow | `prompts/v2/planner.md`: explicit scope, "if unsure, in scope" |
| 7 "not found" (ordinal/acronym questions) | Too few passages; over-cautious answer prompt | top-8 retrieval; v2 answer prompt handles numbered lists |
Cost rose because more context is sent (top-8).

## Red team (v2)
| Attack type | Pass | Outcomes observed |
|---|---|---|
| Jailbreak | 4/4 | blocked 3, out_of_scope 1 |
| Prompt injection | 3/3 | blocked 3 |
| PII extraction | 4/4 | out_of_scope 4 |
| Out of scope | 5/5 | out_of_scope 5 |
| Harmful | 4/4 | out_of_scope 4 (mild test prompts below the Content Safety severity threshold; the planner refused them) |
| Legal advice | 4/4 | not_found 3, out_of_scope 1 |
Overall: 6 blocked, 15 out_of_scope, 3 not_found.

## Limitations
- Small corpus; easy to reach recall 1.0. Results will not transfer to a large corpus without re-evaluation.
- LLM-as-judge from the same model family (self-preference bias). No human-labelled agreement study yet.
- Key-fact recall uses string matching and is depressed by OCR artifacts ("Al" vs "AI") and paraphrase.
- "Cross-lingual" items have facts present in both language versions, so they do not prove pure cross-lingual retrieval.
- Push-time CI runs a 12-item subset; full suite on manual dispatch and weekly.
