# Risk Register

L/I: 1 (low) – 5 (high). Owner: project engineer unless stated.

| ID | Risk | L | I | Mitigation | Status |
|---|---|---|---|---|---|
| R1 | Hallucinated or ungrounded answer | 3 | 5 | Source-only prompt, citations, LLM-judge groundedness + escalation, eval gate | Mitigated |
| R2 | LLM-judge bias (same model family judges itself) | 3 | 3 | Deterministic citation checks; human review sample; plan: different judge model | Open |
| R3 | Prompt injection (direct / indirect) | 3 | 4 | Prompt Shields on input and documents, red-team suite | Mitigated |
| R4 | PII leakage to logs | 2 | 4 | Regex + AI Language masking before logging | Mitigated |
| R5 | Inference outside UAE (GlobalStandard) | 5 | 3 | Public corpus only; documented (ADR-0007); move to regional deployment for non-public data | Accepted |
| R6 | Review queue lost on container restart | 4 | 3 | Documented; plan Cosmos DB / Azure SQL | Open |
| R7 | Free-tier throttling (Content Safety / Language F0) | 4 | 2 | Retry with backoff; fail-closed; S0 in production | Mitigated |
| R8 | Cost overrun | 1 | 3 | $5 budget alerts (50/80/100% + forecast), scale-to-zero, eval cost gate | Mitigated |
| R9 | Model deprecation / quota changes | 4 | 3 | Model in config + Bicep, `NoAutoUpgrade`, eval gate before switching | Mitigated |
| R10 | Outdated or incomplete corpus (PDPL missing) | 5 | 3 | Manifest-driven ingestion; manual download step | Open |
| R11 | Misuse as legal advice | 3 | 4 | Refusal rules, disclaimer, red-team `legal_advice` | Mitigated |
| R12 | Cold start latency (scale-to-zero) | 5 | 1 | Accepted for demo; `minReplicas: 1` in production | Accepted |
| R13 | Users see unverified streamed draft briefly | 3 | 2 | Draft replaced on escalation (ADR-0011); buffered mode for high-risk use | Accepted |
