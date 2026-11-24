# Delivery Plan & Milestones

| # | Milestone | Exit criteria | Status |
|---|-----------|---------------|--------|
| M1 | Skeleton & CI | uv project, typed config (provider-swappable), `/healthz`, ruff + mypy + pytest in GitHub Actions | ✅ Done |
| M2 | Ingestion & index | Doc Intelligence layout → Arabic-aware chunker → embeddings → AI Search (ar/en analyzers, HNSW), hybrid RRF, pluggable reranker | ✅ Done (6 of 8 documents; PDPL pending manual download) |
| M3 | RAG agent & API | SK agent plan → retrieve → answer → verify → escalate; FastAPI + SSE, Entra JWT, RBAC, rate limiting; bilingual RTL UI | ✅ Done |
| M4 | Responsible AI & security | Content Safety + Prompt Shields (input, output, documents), PII masking before logging, review queue | ✅ Done |
| M5 | Eval gate | 50 EN/AR golden + 24 red-team, Azure AI Evaluation SDK, thresholds, CI gate | ✅ Done (v1 failed, v2 passing) |
| M6 | Azure deploy & observability | Bicep for all services, Container Apps, managed identity, Key Vault, OIDC deploy, OpenTelemetry → App Insights, KQL | ✅ Done |
| M7 | Docs & governance | Architecture, ADRs, cards, RAI vs UAE AI Charter, PDPL, STRIDE, risks, runbook, eval report, Fabric/Purview design, README | ✅ Done (Fabric/Purview designed, not deployed) |
| M8 | Azure ML fine-tuning | Bilingual query classifier, Azure ML MLflow + registry, ONNX in-container router | ✅ Done (live flag off; HF publish pending token) |
| M9 | Kubernetes | Helm chart + kind CI smoke test, ADR vs AKS | ✅ Done |
| M10 | Drift detection | Weekly sampled eval vs baseline → GitHub issue; drift KQL; alert rules (off) | ✅ Done |
| M11 | Data-quality gates | DQ checks fail ingestion before embedding; DQ report | ✅ Done |
| M12 | Private networking + Fabric | PE test deployed/verified/torn down; Fabric lakehouse | ◐ PE done; Fabric documented design |
| M13 | Standards & KT | CONTRIBUTING, templates, standards, onboarding, KT plan | ✅ Done |

## Cost policy
Everything uses free tiers where possible:
- AI Search Free
- Document Intelligence, Content Safety and Language on F0
- Container Apps consumption with scale-to-zero
- Log Analytics capped at 0.15 GB/day
- GHCR instead of ACR

Azure OpenAI is pay per token, about $0.0016 per question. A $5/month budget alert is defined in Bicep.

## Open items
- Index the PDPL after a manual browser download (AI Ethics indexed 2026-11-24).
- Make the review queue durable (Cosmos DB).
- Add screenshots to `docs/images/`.
- Use a different judge model, and build a human-labelled evaluation subset.
