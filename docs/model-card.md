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
- Small corpus (4 documents, ~24 pages); PDPL and AI Ethics documents not yet indexed.
- OCR artifacts in source text (e.g. "Al" for "AI").
- Same model family generates and judges answers (judge bias).
- GlobalStandard inference may leave the UAE (ADR-0007).
- Relevance scores penalize short, precise answers.
