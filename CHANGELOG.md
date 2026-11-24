# Changelog
All notable changes to this project are documented here (Keep a Changelog, SemVer).

## [Unreleased]
### Added
- M1: project skeleton, typed provider-swappable settings, `/healthz`, CI (ruff, mypy, pytest).
- M2: Doc Intelligence layout ingestion (F0-aware slicing + rasterization), Arabic-aware chunker, bilingual AI Search index (ar.microsoft + en.microsoft + HNSW vector), hybrid RRF retrieval, pluggable reranker (none | cross-encoder | Azure semantic).
- M3: Semantic Kernel agent (plan -> search_policies -> answer -> verify_citation -> respond or escalate_to_human), versioned prompts, cost/token accounting, OpenTelemetry spans; FastAPI with SSE streaming, Entra ID JWT + RBAC (Viewer/Reviewer/Admin), per-user rate limiting, SQLite review queue; bilingual RTL chat UI with citations and reviewer console.
- M4: Azure AI Content Safety (harm categories + Prompt Shields for direct and indirect prompt injection) on input, output and retrieved sources; PII masking (UAE regex + Azure AI Language) before logging; fail-closed guardrails; favicon and bilingual page titles.
- M5: Golden set (50 EN/AR) + red-team set (24), Azure AI Evaluation SDK groundedness/relevance, recall@5, citation accuracy, latency p50/p95, cost per query; thresholds + `--gate`. Prompt v2 (scope + numbered-list handling), top-8 retrieval, guardrail retry/backoff - answer rate 72% -> 96%.
- M6 (infra): Container Apps (scale-to-zero), user-assigned managed identity, Key Vault secret references, Log Analytics + App Insights, Entra app registrations (app roles), GitHub OIDC federated credentials, private endpoints module behind a flag.
- M6 (CD): GHCR image, OIDC eval gate + deploy to Container Apps revisions with smoke test and automatic rollback; live at the Azure Container Apps URL behind Entra ID.
- M7: architecture, 11 ADRs, model/data cards, Responsible AI assessment vs UAE AI Charter, PDPL/residency, STRIDE threat model, risk register, runbook, evaluation report, Fabric/Purview governance design, KQL queries + workbook, interview guide, README.
