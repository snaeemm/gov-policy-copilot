# Delivery Plan & Milestones

| # | Milestone | Exit criteria |
|---|-----------|---------------|
| M1 | Skeleton & CI | uv project, typed config (provider-swappable), `/healthz`, ruff + mypy + pytest in GitHub Actions, green |
| M2 | Ingestion & index | Doc Intelligence layout → Arabic-aware chunker → embeddings → AI Search index (ar.microsoft + en.microsoft analyzers, HNSW vector), hybrid query (BM25+vector, RRF), pluggable reranker (none / bge cross-encoder / Azure semantic) |
| M3 | RAG agent & API | Semantic Kernel agent: plan → `search_policies` → answer → `verify_citation` / groundedness → respond or `escalate_to_human`. FastAPI async + SSE streaming, Entra ID JWT, RBAC (viewer/reviewer/admin), rate limiting. Bilingual RTL chat UI |
| M4 | Responsible AI & security | Content Safety (text + Prompt Shields) on input/output, PII masking via AI Language before logging, review queue for low-confidence answers |
| M5 | Eval gate | ~50 EN+AR golden Q&A, red-team set, metrics (recall@k, groundedness, relevance, citation accuracy, p50/p95, cost/query), CI gate blocks deploy below thresholds |
| M6 | Azure deploy & observability | Bicep for all resources (+ private endpoints behind flag, $5 budget), Container Apps, managed identity, Key Vault, OIDC deploy, OpenTelemetry → App Insights, KQL workbooks |
| M7 | Docs & governance | Architecture diagram, ADRs, model/data cards, RAI assessment vs UAE AI Charter, PDPL/residency, STRIDE threat model, risk register, runbook, eval report, Fabric/Purview note, README |

Cost policy: free tiers everywhere (Search Free, Doc Intelligence F0, Content Safety F0, Language F0, Container Apps consumption scale-to-zero, App Insights pay-as-you-go under free 5 GB). Azure OpenAI is pay-per-token (gpt-4o-mini + text-embedding-3-small ≈ cents for this corpus).
