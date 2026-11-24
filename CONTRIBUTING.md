# Contributing

## Workflow
1. Open or pick an issue. Use the bug or feature template.
2. Branch from `main`: `feat/<short-name>`, `fix/<short-name>`, `docs/…`, `infra/…`, `eval/…`, `prompt/<vN>-<topic>`.
3. Commit with [Conventional Commits](https://www.conventionalcommits.org): `feat(agent): …`, `fix(retrieval): …`, `docs(adr): …`, `infra(bicep): …`, `eval: …`, `chore: …`.
4. Open a PR using the template. CI (`.github/workflows/ci.yml`) must be green. A CODEOWNER must approve.
5. Merging to `main` triggers `cd.yml`: build → **eval gate** → deploy a new Container Apps revision → smoke test with automatic rollback.

## Local checks (run before every push)
```bash
uv sync --group dev
uv run ruff check . && uv run ruff format --check .
uv run mypy                     # strict mode, src/ only
uv run pytest tests/unit        # no Azure access needed
az bicep build --file infra/main.bicep --stdout > /dev/null   # if you touched infra/
```
Run the app locally on port 8410: `uv run uvicorn gov_copilot.api.main:app --host 127.0.0.1 --port 8410` (needs `az login` and `.env.azure`, see README).

## Changing prompts, models or retrieval safely
Prompts are versioned and immutable once released.
1. Copy the current version, e.g. `prompts/v2/` → `prompts/v3/`. **Never edit a released version in place.** Older versions are the rollback path.
2. Point `prompt_version` (config default or `PROMPT_VERSION` env var) at the new version.
3. Run the full evaluation: `uv run python eval/run_eval.py --gate`. Paste the metrics table into the PR and compare it to `eval/results/baseline-*.json`.
4. If behaviour changes (scope, refusal policy, citation rules, model or reranker), add an ADR in `docs/adr/` and update `docs/evaluation-report.md` and `docs/model-card.md`.
5. Changing a threshold in `eval/thresholds.json` needs written justification in the PR and in the evaluation report. Don't lower a threshold just to get a failing change through.

The same applies to model deployments (`infra/modules/ai-services.bicep`), chunking parameters, `retrieval_top_k`, `rerank_top_n`, and the reranker.

## Adding a document to the corpus
1. Use **public, official** sources only. Add an entry to `data/manifest.json` with `doc_id`, `file`, `language`, `title`, `publisher`, `year` and `source_url`. Add both EN and AR versions when they exist.
2. Put the PDF in `data/raw/`. This folder is git-ignored; raw documents are never committed.
3. Run `uv run python scripts/ingest.py`. Document Intelligence results are cached in `data/processed/` to save the F0 page quota.
4. Re-run the eval gate. Add golden questions to `eval/golden.jsonl` for the new document, and update `docs/data-card.md`.

## Secrets policy
- **Never commit secrets.** `.env`, `.env.*` (except `.env.example`) and `data/*.db` are git-ignored. Check `git status` before committing.
- Azure services use **Entra ID and managed identity**. Local auth is disabled on the Cognitive Services accounts, so don't add API keys.
- CI authenticates to Azure via **OIDC federation**. GitHub holds only non-secret IDs as repository variables.
- Runtime secrets live in **Key Vault** and are referenced by the Container App through its managed identity.
- If a secret leaks: revoke or rotate it immediately, then follow `docs/runbook.md` (incident response). Rewriting git history isn't enough.

## Data and privacy
Never log raw user input. Use the masked question (`Guardrails.mask_pii`). Test data must be synthetic, with no real Emirates IDs, phone numbers or names.
