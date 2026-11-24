# Implementation Details

How each capability of Gov Policy Copilot is implemented, its known limitations, and a demo walkthrough.

## Requirement → implementation map
| Job requirement | What I built | Where |
|---|---|---|
| Azure AI Search, RAG | Bilingual index, hybrid RRF, pluggable reranker | `src/gov_copilot/retrieval/`, ADR-0001..0003 |
| Document processing | Doc Intelligence layout, F0-aware slicing, Arabic chunker | `src/gov_copilot/ingestion/` |
| Azure OpenAI / LLMs | gpt-5-mini + embeddings, provider abstraction | `src/gov_copilot/llm/clients.py`, ADR-0006/0007 |
| Agents / orchestration | Semantic Kernel plugin, plan→retrieve→answer→verify→escalate | `src/gov_copilot/agent/` |
| APIs | FastAPI async, pydantic, SSE streaming | `src/gov_copilot/api/main.py` |
| Security / identity | Entra JWT, app roles, managed identity, Key Vault, OIDC | `api/auth.py`, `infra/` |
| Responsible AI | Content Safety, Prompt Shields, PII masking, HITL | `guardrails_azure.py`, `pii.py`, `docs/responsible-ai.md` |
| MLOps / LLMOps | Versioned prompts, eval gate, weekly drift eval, rollback | `prompts/`, `eval/`, `.github/workflows/cd.yml` |
| IaC / DevOps | Bicep, Container Apps, GitHub Actions | `infra/`, `.github/workflows/` |
| Observability | OpenTelemetry → App Insights, KQL, workbook | `observability/` |
| Governance / compliance | UAE AI Charter mapping, PDPL, STRIDE, risk register, Fabric/Purview design | `docs/` |
| Fine-tuning / Azure ML | Bilingual query classifier, MLflow tracking + model registry in Azure ML, ONNX serving | `ml/`, `data/classifier/`, `src/gov_copilot/classifier.py`, `infra/modules/ml.bicep`, ADR-0013 |
| Kubernetes | Helm chart, kind smoke test in CI, ACA-vs-AKS decision | `deploy/helm/`, `.github/workflows/k8s.yml`, ADR-0012 |
| Drift / monitoring | Weekly sampled eval vs baseline → GitHub issue; drift KQL; alert rules | `.github/workflows/drift.yml`, `eval/compare_baseline.py`, `infra/modules/alerts.bicep` |
| Data quality | DQ gates before embedding, DQ report, classification label | `src/gov_copilot/ingestion/quality.py`, `scripts/ingest.py` |
| Private networking | Private endpoints + privatelink DNS, tested and torn down | `infra/modules/private-endpoints.bicep`, `docs/evidence/` |
| Standards / knowledge transfer | Contributing guide, review checklist, onboarding, handover plan | `CONTRIBUTING.md`, `docs/engineering/` |

## Known limitations
- It's a reference implementation on public data, not a government system. Only invited users of a personal tenant can sign in.
- The corpus is small (8 documents, 196 chunks). The PDPL (EN/AR) was added from its official text as cleaned Markdown, because the legislation portal blocks automated PDF download.
- Model inference is GlobalStandard, and the judge comes from the same model family.
- The review queue is ephemeral, the eval on push is a 12-item subset, and there's no WCAG audit yet.
- Fabric Gold layer is live (Delta tables in a OneLake lakehouse); Purview is design-only.
- The classifier is trained, registered (Azure ML v1) and enabled in the live app; the model artifact is published as a GitHub release.
- The first Azure ML run (v1) is marked FAILED because MLflow 3's `log_model` calls an API Azure ML doesn't support. Fixed by logging artifacts through the MLflow client and registering via the Azure ML SDK; the retrained run completed cleanly and is registered as v2.
- Private endpoints were tested and torn down, not left on: the live environment is public with Entra auth.

## Demo walkthrough
1. Open the live URL and sign in to show Entra.
2. Ask in English, open a citation, and point out the groundedness, model and prompt version.
3. Switch to Arabic (RTL) and ask a cross-lingual question.
4. Try a jailbreak to show it blocked, then an off-topic question to show out-of-scope.
5. As Admin, open the review queue.
6. Show the GitHub Actions run with the eval gate summary.
7. Show an App Insights KQL query for cost per day.
