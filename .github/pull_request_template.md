## Summary
<!-- What changes and why. Link the issue: Closes #… -->

## Type
- [ ] feat  - [ ] fix  - [ ] prompt / model / retrieval change  - [ ] infra (Bicep / CI)  - [ ] docs  - [ ] chore

## Checklist
- [ ] `ruff check`, `ruff format --check`, `mypy`, and `pytest tests/unit` pass locally
- [ ] Tests added or updated for new behaviour
- [ ] `az bicep build` passes (if `infra/` changed)
- [ ] No secrets, `.env*` files, raw PDFs or `*.db` files committed

### Prompt / model / retrieval changes only
- [ ] New prompt version (`prompts/vN`) - released versions not edited
- [ ] Full eval run: `uv run python eval/run_eval.py --gate`

| metric | baseline | this PR |
|---|---|---|
| retrieval_recall_at_5 | | |
| groundedness | | |
| citation_accuracy | | |
| answer_rate (EN / AR) | | |
| redteam_pass_rate | | |
| latency_p95_s | | |
| cost_per_query_usd | | |

## Security, PII and Responsible AI impact
- [ ] No new path where raw user input or PII is logged or stored
- [ ] Guardrails (Content Safety, Prompt Shields) still cover new inputs and outputs
- [ ] Auth and RBAC unchanged, or changes reviewed (roles: Viewer / Reviewer / Admin)
<!-- Describe any new data flow, external call or permission. -->

## Docs
- [ ] README / runbook / model card / data card / evaluation report updated where relevant
- [ ] ADR added in `docs/adr/` for any architectural or behavioural decision
- [ ] CHANGELOG updated

## Rollback plan
<!-- e.g. "Shift Container Apps traffic to the previous revision" or "set PROMPT_VERSION=v2". -->
