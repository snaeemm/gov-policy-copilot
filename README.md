# Gov Policy Copilot

**Bilingual (Arabic / English) RAG assistant that answers questions about public UAE government AI & data policy documents, with citations, groundedness checks, safety filters and human escalation. Built end to end on Microsoft Azure (UAE North).**

[![ci](https://github.com/snaeemm/gov-policy-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/snaeemm/gov-policy-copilot/actions/workflows/ci.yml)
[![cd](https://github.com/snaeemm/gov-policy-copilot/actions/workflows/cd.yml/badge.svg)](https://github.com/snaeemm/gov-policy-copilot/actions/workflows/cd.yml)

> ⚠️ **Reference implementation on public data**, built as an engineering portfolio project. It is **not** an official system of any UAE government entity and does not provide legal advice.

**Live:** https://ca-govcopilot-dev.yellowsky-4e1b1c86.uaenorth.azurecontainerapps.io. Sign-in uses Microsoft Entra ID on a personal tenant, so only invited users can sign in. The app scales to zero, so the first request after idle takes about 15 s.

## Screenshots
> TODO: add `docs/images/chat-en.png`, `docs/images/chat-ar-rtl.png`, `docs/images/citations.png`, `docs/images/review-queue.png`, `docs/images/eval-gate.png`.

## Architecture
```mermaid
flowchart LR
  PDF[Public PDFs] --> DI[Document Intelligence] --> CH[Arabic-aware chunker] --> EMB[AOAI embeddings] --> S[(AI Search<br/>hybrid BM25+vector RRF)]
  U[Bilingual RTL UI] -->|Entra JWT| API[FastAPI + RBAC + rate limit]
  API --> CS[Content Safety<br/>Prompt Shields]
  API --> AG[Semantic Kernel agent<br/>plan → retrieve → answer → verify]
  AG --> S
  AG --> LLM[Azure OpenAI gpt-5-mini]
  AG -->|low confidence| HQ[(Human review queue)]
  API --> PII[AI Language PII masking] --> OT[OpenTelemetry → App Insights]
  GH[GitHub Actions<br/>lint · types · tests · eval gate] -->|OIDC| ACA[Container Apps]
```
Details: [docs/architecture.md](docs/architecture.md)

## Features
- **Bilingual retrieval:** Arabic and English analyzers plus multilingual vectors, so a question in either language finds sources in both.
- **Cited, verified answers:** every sentence carries a `[n]` citation with page number. An LLM judge checks groundedness, and low scores escalate to a human reviewer.
- **Safety:** Azure AI Content Safety (harm categories and Prompt Shields) checks input, output and retrieved documents, and fails closed.
- **Privacy:** UAE-specific PII masking (Emirates ID, +971 phones, IBAN) plus Azure AI Language, applied before anything is logged.
- **API:** Entra ID login with app roles (Viewer / Reviewer / Admin), per-user rate limiting, SSE streaming.
- **Versioning and telemetry:** prompts are versioned; model, prompt version, tokens and cost are logged per request.
- **Evaluation gate in CI/CD:** a quality drop blocks deployment.
- **Infrastructure:** all in Bicep, keyless (managed identity, Key Vault, OIDC), with a $5 budget alert and private endpoints behind a flag.

## How this maps to enterprise requirements
| # | Requirement | Implementation | Status |
|---|---|---|---|
| 1 | Ingestion and search | Document Intelligence (F0, 2-page/4 MB slicing) → Arabic-aware chunker → AOAI embeddings → AI Search (`ar.microsoft` + `en.microsoft`, HNSW), hybrid RRF, pluggable reranker | ✅ (reranker `none` in Azure) |
| 2 | Orchestration | Semantic Kernel tools `search_policies`, `verify_citation`, `escalate_to_human`; plan → retrieve → answer → self-check → respond or escalate | ✅ |
| 3 | API | FastAPI async, pydantic, SSE; Entra JWT; RBAC; slowapi rate limiting | ✅ |
| 4 | Responsible AI | Content Safety and Prompt Shields (input, output, documents), PII masking, groundedness check, HITL queue | ✅ (queue ephemeral) |
| 5 | Frontend | Bilingual RTL chat with citations, step progress, reviewer console | ✅ |
| 6 | Infra | Docker, Container Apps, Bicep for all services, managed identity, Key Vault, App Insights, budget, private endpoints (flag) | ✅ |
| 7 | CI/CD | ruff, mypy, pytest, Bicep build → GHCR image → eval gate → OIDC deploy → smoke test with automatic rollback | ✅ |
| 8 | Evaluation and LLMOps | 50 EN/AR golden + 24 red-team; recall@5, groundedness, relevance (Azure AI Evaluation SDK), citation accuracy, latency, cost; versioned prompts; rollback | ✅ |
| 9 | Observability | OpenTelemetry → App Insights, KQL queries, workbook | ✅ |
| 10 | Data governance | Fabric gold-layer contract and Purview design | ◐ designed, not deployed ([why](docs/governance-fabric-purview.md)) |
| 11 | Documentation | ADRs, model and data cards, RAI vs UAE AI Charter, PDPL, STRIDE, risk register, runbook, eval report | ✅ |

## Evaluation (prompt v2, gpt-5-mini)
| Metric | Result | Gate |
|---|---|---|
| Retrieval recall@5 | 1.00 | ≥ 0.80 |
| Groundedness | 0.96 | ≥ 0.80 |
| Relevance | 0.76 | ≥ 0.70 |
| Citation accuracy | 1.00 | ≥ 0.80 |
| Answer rate (EN / AR) | 0.96 (1.00 / 0.92) | ≥ 0.75 |
| Red-team pass rate | 1.00 (24/24) | ≥ 0.90 |
| Latency p50 / p95 | 10.4 s / 14.3 s | p95 ≤ 45 s |
| Cost per query | $0.0016 | ≤ $0.01 |

The first run (prompt v1) **failed the gate** at a 0.72 answer rate. The root causes were F0 throttling, a narrow planner scope, and over-cautious handling of numbered lists. All three were fixed in v2, documented in [docs/evaluation-report.md](docs/evaluation-report.md).

## Quickstart (local)
```bash
uv sync --group dev                 # Python 3.12
az login                            # keyless: your user needs the data-plane roles granted in Bicep
cp .env.example .env                # optional (e.g. GITHUB_TOKEN for the GitHub Models fallback)
# put non-secret endpoints from the Bicep outputs in .env.azure (git-ignored), and set RERANKER=none
uv run python scripts/ingest.py --recreate                          # Doc Intelligence → chunks → index
uv run uvicorn gov_copilot.api.main:app --host 127.0.0.1 --port 8410 # http://127.0.0.1:8410
uv run pytest tests/unit && uv run ruff check . && uv run mypy        # quality
uv sync --extra eval && uv run python eval/run_eval.py --gate          # evaluation gate
```
Infrastructure: `az deployment sub create -l uaenorth --parameters infra/main.dev.bicepparam ...` (see [runbook](docs/runbook.md)).

## Repository layout
```
src/gov_copilot/   ingestion/ retrieval/ agent/ api/ llm/ guardrails*.py pii.py observability.py
prompts/v1, v2     versioned prompts
frontend/          bilingual SPA (no build step)
eval/              golden + red-team sets, runner, thresholds, baseline results
infra/             Bicep (main + modules), Entra setup script
observability/     KQL queries + workbook
docs/              architecture, ADRs, cards, RAI, PDPL, threat model, risks, runbook, eval report
.github/workflows/ ci.yml, cd.yml
```

## Documentation
[Architecture](docs/architecture.md) · [ADRs](docs/adr/) · [Model card](docs/model-card.md) · [Data card](docs/data-card.md) · [Responsible AI (UAE AI Charter)](docs/responsible-ai.md) · [PDPL & residency](docs/pdpl-data-residency.md) · [Threat model](docs/threat-model.md) · [Risk register](docs/risk-register.md) · [Runbook](docs/runbook.md) · [Evaluation report](docs/evaluation-report.md) · [Fabric & Purview](docs/governance-fabric-purview.md) · [Observability](observability/README.md) · [Changelog](CHANGELOG.md)

## Cost
| Item | Tier | Approx. monthly |
|---|---|---|
| AI Search | Free | $0 |
| Document Intelligence, Content Safety, Language | F0 | $0 |
| Container Apps | Consumption, scale-to-zero | $0 (free grant) |
| Log Analytics / App Insights | Capped 0.15 GB/day | $0 |
| Key Vault | Standard | < $0.10 |
| Azure OpenAI | Pay per token | ≈ $0.0016 per question |
| Container registry | GHCR (public) | $0 |
A $5/month budget alert is defined in Bicep.

## Known limitations
- The corpus is small: the AI Charter and the UAE International AI Policy, each in EN and AR. The PDPL and AI Ethics documents are listed in the manifest but need a manual download, because the source sites block automated download.
- gpt-5-mini runs as GlobalStandard, so inference may happen outside the UAE (ADR-0007).
- The review queue is SQLite inside the container, so it's lost on restart; production would use Cosmos DB.
- The same model family generates and judges answers.

## License
MIT. Source documents belong to their publishers and are not redistributed here.
