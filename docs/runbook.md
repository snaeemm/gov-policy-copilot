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
