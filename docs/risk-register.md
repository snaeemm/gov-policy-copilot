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
| R14 | Query classifier misroutes an in-scope question as out-of-scope | 2 | 3 | Short-circuit only at confidence ≥ 0.9; otherwise LLM planner decides; `CLASSIFIER_ENABLED` kill switch; per-language metrics tracked; label mix in drift KQL | Mitigated |
| R15 | Model supply chain (classifier downloaded from Hugging Face Hub) | 2 | 4 | Pin repo revision/commit hash; prefer Azure ML registry or baked-in artifact in production; ONNX only (no pickle) | Open |
| R16 | Quality drift undetected between weekly drift runs | 3 | 3 | Every deploy runs the eval gate; App Insights outcome KQL; alert rules available (`deployAlerts`) | Mitigated |
| R17 | Data-quality false positives block ingestion | 2 | 2 | Warnings vs errors split; thresholds tuned on real corpus (0 errors / 34 warnings); `--dq-only` dry run | Mitigated |
| R18 | Private networking not enabled in the live environment | 4 | 3 | Bicep module tested and evidenced; production needs `publicNetworkAccess: Disabled`, VNet-integrated ACA, AI Search Basic+ | Accepted (demo) |
