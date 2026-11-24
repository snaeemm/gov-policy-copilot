# Runbook

Resource group `rg-govcopilot-dev` (UAE North) · Container App `ca-govcopilot-dev` · Subscription: personal free trial.

## Deploy
- **Application**: push to `main` → `cd.yml` runs CI → builds `ghcr.io/snaeemm/gov-policy-copilot:<sha>` → eval gate → new Container Apps revision (`--revision-suffix r<sha>`) → `/healthz` smoke test. Manual: *Actions → cd → Run workflow* (full eval by default).
- **Infrastructure** (platform step, run by an admin; CI has Contributor on the RG only):
  ```bash
  az deployment sub what-if -l uaenorth -n govcopilot-dev --parameters infra/main.dev.bicepparam \
    --parameters developerPrincipalId=$(az ad signed-in-user show --query id -o tsv)
  az deployment sub create  -l uaenorth -n govcopilot-dev --parameters infra/main.dev.bicepparam \
    --parameters developerPrincipalId=$(az ad signed-in-user show --query id -o tsv)
  ```
  ⚠️ Re-running the full Bicep resets the container image to the placeholder unless `containerImage=<current image>` is passed.
- **Entra objects**: `infra/scripts/setup-entra.sh <app-url> snaeemm/gov-policy-copilot` (idempotent).

## Rollback
| What | How |
|---|---|
| App revision | `az containerapp revision list -n ca-govcopilot-dev -g rg-govcopilot-dev -o table` then `az containerapp ingress traffic set -n ca-govcopilot-dev -g rg-govcopilot-dev --revision-weight <previous-revision>=100`. The CD smoke test does this automatically on failure |
| Prompt version | `az containerapp update -n ca-govcopilot-dev -g rg-govcopilot-dev --set-env-vars PROMPT_VERSION=v1` (all versions ship in the image under `prompts/`) |
| Model | Change deployment/version in `infra/modules/ai-services.bicep` (or set `AZURE_OPENAI_CHAT_DEPLOYMENT`), run the full eval, then deploy. Never switch without a passing gate |
| Code | `git revert` + push (gate runs again) |

## Re-index
```bash
az login   # needs Search Index Data Contributor + Cognitive Services User + OpenAI User
uv run python scripts/ingest.py --recreate
```
Document Intelligence results are cached in `data/processed/`; delete a file to force re-analysis (counts against F0's 500 pages/month).

## Access
- Grant a user access: Entra admin center → Enterprise applications → `gov-policy-copilot-api` → Users and groups → assign `Viewer` / `Reviewer` / `Admin`. The user must exist in the tenant (invite as guest).
- No secrets to rotate: services are keyless; GitHub uses OIDC. The only Key Vault secret is the App Insights connection string.

## Incident response
1. Check health: `curl https://<app>/healthz`, Container Apps → Revisions, App Insights failures (`observability/kql/failures.kql`).
2. Harmful or wrong answers reported: confirm in traces (`copilot_request`, masked question), roll back prompt/model, add the case to `eval/golden.jsonl` or `eval/redteam.jsonl`.
3. Suspected credential misuse: remove role assignments / federated credential (`az ad app federated-credential delete`), review Activity Log.
4. Spend alert: check `observability/kql/cost_per_day.kql`; scale `maxReplicas` to 0 (`az containerapp update --max-replicas 0`) to stop serving.

## Cost controls
- Budget `budget-govcopilot-dev`: $5/month, emails at 50/80/100% actual and 100% forecast.
- Scale-to-zero; Log Analytics daily cap 0.15 GB; F0 tiers; eval smoke subset on push.
- Typical cost: ~$0.0016/question; full eval run ≈ $0.15–0.30.

## Common failures
| Symptom | Cause | Fix |
|---|---|---|
| `InsufficientQuota` on deploy | Trial quota per model | Choose model with quota: `az cognitiveservices usage list -l uaenorth` |
| `ServiceModelDeprecating` | Model retired for new deployments | Pick a GA model (`az cognitiveservices model list -l uaenorth`) |
| Answers "blocked" in bursts | F0 Content Safety throttling (429) + fail-closed | Retries are built in; lower concurrency or use S0 |
| `InvalidContentLength` in ingestion | DocIntel F0 4 MB limit | Already handled by slicing/rasterization; check `split_pdf` |
| PDF download returns HTML | Cloudflare bot protection on uaelegislation.gov.ae | Download manually in a browser into `data/raw/` with names from `data/manifest.json` |
| 401 from API | Token audience/role missing | Check user has an app role; SPA requests scope `api://<api-app-id>/access_as_user` |
| Cold start ~15 s | Scale-to-zero | Expected; `--min-replicas 1` for demos |

## Drift & alerts

### Weekly drift check (`.github/workflows/drift.yml`)
- Runs Mondays 04:00 UTC (and on demand via *Run workflow*). It logs in to Azure with OIDC, runs a
  small eval sample (`--limit 8`: 8 golden + 8 red-team prompts, about $0.03), then
  `eval/compare_baseline.py` compares the metrics with `eval/results/baseline-v2-6docs.json`
  using the tolerances in `eval/drift.json`.
- On regression it opens a GitHub issue labelled `drift`, or comments on the open one, with the
  drift report. Artifacts: `latest.json` and `drift-report.md`.
- It does not deploy anything; the `cd` workflow no longer runs on a schedule.

### Triage a drift issue
1. Read the report. Small samples are noisy, so first re-run `cd` with *full_eval = true* or
   locally run `uv run python eval/run_eval.py && uv run python eval/compare_baseline.py`.
2. If the regression holds, check for recent changes: prompt version (`PROMPT_VERSION`), model
   deployment version, index contents (re-ingestion), and guardrail behaviour (blocked outcomes,
   for example from F0 throttling).
3. Check query-distribution drift in Log Analytics with `observability/kql/drift_language_mix.kql`,
   `drift_out_of_scope_rate.kql` and `drift_classifier_labels.kql` (week-over-week, percentage points).
4. Fix forward, or roll back the prompt or the revision (see Rollback), then close the issue with
   the run link.

### Update the baseline
After an intentional change (new documents, new prompt version) that passes the full eval gate:
`cp eval/results/latest.json eval/results/baseline-<version>.json`, point `DEFAULT_BASELINE` in
`eval/compare_baseline.py` at it, and record the rationale in `docs/evaluation-report.md` (PR review).

### Azure Monitor alerts (off by default)
`infra/modules/alerts.bicep` defines an email action group plus five log-search alert rules:
out-of-scope spike, blocked spike, escalation rate, p95 latency and daily model cost.
- **Cost:** about $0.50/month per rule at a 15-minute frequency, so about $2.50/month for all
  five. Email notifications are free.
- **Enable:** deploy `infra/main.bicep` with `deployAlerts=true`. Pass the current
  `containerImage` as well, otherwise the app is reset to the placeholder image.
- **Disable:** redeploy with `deployAlerts=false` (the alert rules stay until deleted), or run
  `az monitor scheduled-query delete -g rg-govcopilot-dev -n <rule>`.
