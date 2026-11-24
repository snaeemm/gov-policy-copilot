# Engineer Onboarding (Day 1-5)

## Before day 1: access requests
| Access | Why | Granted by |
|---|---|---|
| GitHub repo (write) | Code, PRs | Repo owner |
| Entra ID user in the tenant, plus app role `Copilot.Viewer` (or `Reviewer`) on `gov-policy-copilot-api` | Sign in to the app | Tenant admin |
| Azure RBAC on `rg-govcopilot-dev`: Reader; data plane: Cognitive Services OpenAI User, Search Index Data Reader, Cognitive Services User | Run locally against dev and run evals | Subscription owner |
| App Insights / Log Analytics Reader | Telemetry and KQL | Subscription owner |

## Day 1: run it locally
1. Install `uv`, the Azure CLI, Docker and the GitHub CLI.
2. `git clone`, then `uv sync --group dev`, then `az login`.
3. Create `.env.azure` with the endpoints from the Bicep outputs (see README). Don't add keys; auth is keyless.
4. Run `uv run pytest tests/unit`, then `uv run uvicorn gov_copilot.api.main:app --host 127.0.0.1 --port 8410`, and open http://127.0.0.1:8410.
5. Ask one English and one Arabic question, and click a citation.

## Day 2: architecture walkthrough (read in this order)
1. `README.md` and `docs/architecture.md`
2. ADRs `docs/adr/0001`-`0011` (why things are the way they are)
3. Query path: `api/main.py` → `agent/orchestrator.py` → `agent/tools.py` → `retrieval/retriever.py` → `guardrails_azure.py`
4. Ingestion path: `scripts/ingest.py` → `ingestion/docintel.py` → `ingestion/chunker.py` → `retrieval/index.py`
5. `infra/main.bicep` and its modules, then `.github/workflows/ci.yml` and `cd.yml`

## Day 3: quality and operations
- Run a small eval: `uv run python eval/run_eval.py --limit 5`, and read `docs/evaluation-report.md`.
- Read `docs/runbook.md`, `docs/threat-model.md` and `docs/responsible-ai.md`.
- Run two queries from `observability/kql/` in Log Analytics.

## Day 4-5: first tasks (good starters)
- Add 5 golden questions for the AI Ethics guide and allow multiple valid source documents per question.
- Add a unit test for an untested branch in `orchestrator.py` (e.g. the empty-retrieval path).
- Improve a UI string or accessibility detail in `frontend/` (RTL, keyboard navigation).
- Pick up an open item from `docs/risk-register.md` with the owner.

Done when you have merged one PR with green CI and walked a reviewer through the request lifecycle.
