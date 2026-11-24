# Architecture

Reference implementation on **public** UAE government documents. Region: **UAE North** for every resource (see ADR-0007 for the one model-inference caveat).

## System view

```mermaid
flowchart LR
  subgraph Ingestion["Ingestion (offline, scripts/ingest.py)"]
    PDF[Public PDFs<br/>data/raw] --> DI[Azure AI Document Intelligence<br/>prebuilt-layout F0]
    DI --> MD[Markdown cache<br/>data/processed]
    MD --> CH[Arabic-aware chunker<br/>450 tok / 50 overlap]
    CH --> EMB[Azure OpenAI<br/>text-embedding-3-small]
    EMB --> IDX[(Azure AI Search Free<br/>content_en: en.microsoft<br/>content_ar: ar.microsoft<br/>HNSW vector)]
  end

  subgraph Runtime["Runtime (Azure Container Apps, scale-to-zero)"]
    UI[Bilingual RTL SPA<br/>MSAL.js] -->|Bearer JWT| API[FastAPI<br/>JWT + RBAC + rate limit + SSE]
    API --> CSI[Content Safety<br/>Prompt Shields + harm]
    API --> AG[Semantic Kernel agent<br/>plan → search → answer → verify]
    AG -->|hybrid BM25+vector RRF| IDX
    AG --> LLM[Azure OpenAI gpt-5-mini]
    AG --> CSO[Content Safety on output<br/>+ indirect injection in sources]
    AG -->|low confidence| RQ[(Review queue<br/>SQLite, ephemeral)]
    API --> PII[AI Language PII + UAE regex<br/>mask before logging]
  end

  subgraph Platform
    MI[User-assigned managed identity] -.RBAC.-> LLM & IDX & CSI & PII
    KV[Key Vault] -.secret ref.-> API
    API -->|OpenTelemetry| AI[Application Insights<br/>+ Log Analytics]
    BUD[$5 budget alert]
  end

  subgraph CICD["GitHub Actions"]
    CI[ruff · mypy · pytest · bicep build] --> IMG[Build → GHCR]
    IMG --> GATE[Eval gate<br/>golden + red-team]
    GATE -->|OIDC, no secrets| DEP[Container Apps revision<br/>smoke test + auto rollback]
  end
  Entra[Microsoft Entra ID<br/>app roles] -.tokens.-> UI
```

## Components

| Concern | Azure / OSS service | Tier | Where |
|---|---|---|---|
| Document parsing | Azure AI Document Intelligence `prebuilt-layout` | F0 | `src/gov_copilot/ingestion/docintel.py` |
| Chunking | Custom, heading/page aware, Arabic sentence split | – | `src/gov_copilot/ingestion/chunker.py` |
| Embeddings | Azure OpenAI `text-embedding-3-small` (1536-d) | Standard (regional) | `src/gov_copilot/llm/clients.py` |
| Index + hybrid search | Azure AI Search, RRF fusion | Free | `src/gov_copilot/retrieval/` |
| Re-ranking | none / multilingual cross-encoder / Azure semantic ranker | config | `retrieval/rerankers.py` |
| Orchestration | Semantic Kernel plugin + deterministic workflow | – | `src/gov_copilot/agent/` |
| Generation + judge | Azure OpenAI `gpt-5-mini` | GlobalStandard | `agent/orchestrator.py` |
| Safety | Azure AI Content Safety (text analyze + Prompt Shields) | F0 | `guardrails_azure.py` |
| PII | Azure AI Language PII + UAE regex | F0 | `pii.py`, `guardrails_azure.py` |
| API | FastAPI, SSE, slowapi, PyJWT | – | `src/gov_copilot/api/` |
| Identity | Entra ID app roles; managed identity; GitHub OIDC | – | `api/auth.py`, `infra/scripts/setup-entra.sh` |
| Hosting | Azure Container Apps (consumption, min 0 replicas) | free grant | `infra/modules/app.bicep` |
| Secrets | Azure Key Vault (RBAC), Container Apps Key Vault references | Standard | `infra/modules/app.bicep` |
| Telemetry | OpenTelemetry → Application Insights / Log Analytics | 0.15 GB/day cap | `observability.py`, `observability/` |
| IaC | Bicep (subscription scope) | – | `infra/` |
| Private networking | VNet + private endpoints + DNS (flag, off) | – | `infra/modules/private-endpoints.bicep` |

## Request sequence

```mermaid
sequenceDiagram
  autonumber
  participant U as User (SPA)
  participant A as FastAPI
  participant G as Guardrails
  participant K as SK agent
  participant S as AI Search
  participant O as Azure OpenAI
  participant Q as Review queue
  U->>A: POST /api/chat/stream (Bearer JWT)
  A->>A: validate JWT (issuer, audience, exp, roles) + rate limit
  A->>K: stream(question)
  K->>G: mask PII (for logs) · Prompt Shields + harm on input
  alt blocked
    K-->>U: final(blocked)
  end
  K->>O: plan (language, scope, EN+AR queries)
  K->>S: search_policies (hybrid BM25 + vector, RRF) ×N queries
  K->>O: answer with numbered sources (streamed tokens → UI)
  K->>O: verify_citation (LLM judge: groundedness, citation validity)
  K->>G: harm on output + Prompt Shields on source documents
  alt groundedness < 0.7 or invalid citations or guardrail hit
    K->>Q: escalate_to_human
    K-->>U: final(escalated) – streamed draft replaced
  else
    K-->>U: final(answered, citations, verification, cost)
  end
  K->>A: log copilot_request (masked question, model, prompt version, tokens, cost)
```

Note: tokens are streamed *before* verification completes; the UI replaces the draft if the final event is `escalated`/`blocked` (ADR-0011).
