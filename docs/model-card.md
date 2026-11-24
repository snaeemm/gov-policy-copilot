# Model Card – Gov Policy Copilot

| Field | Value |
|---|---|
| System type | Retrieval-augmented generation (RAG) assistant with self-verification and human escalation |
| Intended use | Answer questions about **public** UAE government AI/data policy documents, in Arabic or English, with citations |
| Out of scope | Legal advice, decisions about individuals, non-public data, topics outside the indexed corpus |
| Users | Demo / evaluation audience (portfolio). Not an official government service |
| Chat + judge model | Azure OpenAI `gpt-5-mini` 2025-08-07, GlobalStandard, `reasoning_effort=minimal`, no auto-upgrade |
| Embedding model | Azure OpenAI `text-embedding-3-small` v1, 1536-d, regional Standard (UAE North) |
| Prompts | Versioned in `prompts/v1`, `prompts/v2` (active: v2). Version logged per request |
| Fine-tuning | None. No user data is used for training |
| Decoding | Reasoning model defaults; JSON mode for planner and judge |

## Behaviour and safeguards
- Answers only from retrieved sources; every sentence must cite `[n]`.
- Refuses out-of-scope questions; returns a fixed "not found" message when sources lack the answer.
- LLM-judge groundedness < 0.7 or invalid citations → escalated to the human review queue.
- Azure AI Content Safety (harm categories, Prompt Shields for direct and indirect injection) on input, output and retrieved sources; fail-closed.

## Performance (eval baseline, prompt v2, 2026-11-24)
| Metric | Value |
|---|---|
| Retrieval recall@5 | 1.00 |
| Groundedness (Azure AI Evaluation, normalized) | 0.958 |
| Relevance (normalized) | 0.760 |
| Citation accuracy | 1.00 |
| Answer rate (EN / AR) | 0.96 (1.00 / 0.92) |
| Red-team pass rate | 1.00 (24/24) |
| Latency p50 / p95 | 10.4 s / 14.3 s |
| Cost / query | $0.0016 |

## Known limitations
- Small corpus (6 documents, 147 chunks); the PDPL is not yet indexed (manual download required).
- OCR artifacts in source text (e.g. "Al" for "AI").
- Same model family generates and judges answers (judge bias).
- GlobalStandard inference may leave the UAE (ADR-0007).
- Relevance scores penalize short, precise answers.

## Query classifier (secondary model, M8)
| | |
|---|---|
| Model | `gov-policy-query-classifier` v1 (Azure ML registry), fine-tuned from `distilbert-base-multilingual-cased` (Apache-2.0) |
| Task | 5-way routing: charter / international_policy / ethics / data_protection / out_of_scope |
| Languages | Arabic, English |
| Training | 4 epochs, lr 4e-5, max_len 64, CPU (local / GitHub Actions), MLflow-tracked in Azure ML |
| Serving | ONNX int8 (135.8 MB) via onnxruntime inside the Container App; `CLASSIFIER_ENABLED` flag (code default off; on in the production image) |
| Metrics (test) | accuracy EN 0.812 / AR 0.811; macro-F1 EN 0.810 / AR 0.800; in-scope accuracy 0.961 |
| Use in system | Confident out-of-scope (≥ 0.9) answered without an LLM call; label shown in UI/API and logged for drift monitoring |
| Not for | Safety filtering, legal classification, decisions about people |
| Limitations | Synthetic training questions; Charter vs International Policy confusion; jailbreaks phrased as policy questions look in-scope (handled by Content Safety) |
| Details | [ADR-0013](adr/0013-query-classifier-azure-ml.md), [evaluation report](evaluation-report.md#query-classifier-m8), [dataset card](../data/classifier/README.md) |
