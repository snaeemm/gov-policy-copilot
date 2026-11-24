# ADR-0010: Evaluation gate blocks deployment

Status: Accepted

**Decision.** `eval/run_eval.py --gate` runs the golden set (50 EN/AR) and red-team set (24) through the real agent, scores groundedness and relevance with the **Azure AI Evaluation SDK** (gpt-5-mini judge), plus recall@5, citation accuracy, answer rate, latency and cost. Thresholds in `eval/thresholds.json`; any breach exits non-zero and the `deploy` job (needs `eval-gate`) does not run. Pushes run a 12-item smoke subset (cost/time); manual dispatch and a weekly schedule run the full suite.

| Metric | Gate |
|---|---|
| retrieval_recall_at_5 | ≥ 0.80 |
| groundedness | ≥ 0.80 |
| relevance | ≥ 0.70 |
| citation_accuracy | ≥ 0.80 |
| answer_rate | ≥ 0.75 |
| redteam_pass_rate | ≥ 0.90 |
| latency_p95_s | ≤ 45 |
| cost_per_query_usd | ≤ 0.01 |

**Evidence it works.** First run (prompt v1) failed on answer_rate 0.72; fixes shipped as prompt v2 → 0.96 (see `docs/evaluation-report.md`).

**Consequences.** − LLM-as-judge bias (same model family generates and judges). − Push-time smoke subset is a weaker gate than the full suite.
