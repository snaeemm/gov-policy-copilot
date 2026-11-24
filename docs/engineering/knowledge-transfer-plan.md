# Knowledge Transfer and Handover Plan

Handing Gov Policy Copilot over to a client engineering/operations team.

## Stakeholders (RACI)
| Activity | Delivery lead | Client tech lead | Client engineers | Client ops / SRE | Data / RAI owner | Security |
|---|---|---|---|---|---|---|
| KT schedule and sign-off | A/R | A | I | I | C | C |
| Code and architecture handover | R | A | R | I | I | C |
| Infrastructure and CI/CD | R | A | R | R | I | C |
| Evaluation and prompt governance | R | C | R | I | A | I |
| Operations runbook and incidents | R | C | C | A/R | I | C |
| Access and secrets transfer | R | A | I | R | I | A |

## Schedule (5 weeks)
| Week | Phase | Focus | Mode |
|---|---|---|---|
| 1 | Foundations | Architecture, ADRs, local setup, codebase tour | Shadow: client watches |
| 2 | Build and quality | Ingestion, agent, prompts, eval gate, adding documents | Shadow → paired |
| 3 | Platform | Bicep, CI/CD, OIDC, Entra roles, Key Vault, cost controls | Reverse shadow: client drives, we watch |
| 4 | Operations | Monitoring/KQL, incidents, rollback drills, review queue | Reverse shadow |
| 5 | Independence | Client runs a full release and an incident drill alone | Independent, with on-call backup |

## Sessions and artefacts
| # | Session (60-90 min) | Artefacts |
|---|---|---|
| 1 | Solution overview and decisions | `docs/architecture.md`, `docs/adr/` |
| 2 | Local dev, coding standards, PR flow | `docs/engineering/*`, `CONTRIBUTING.md` |
| 3 | Ingestion and the bilingual index | `scripts/ingest.py`, `docs/data-card.md` |
| 4 | Agent, prompts and versioning | `src/gov_copilot/agent/`, `prompts/` |
| 5 | Evaluation and the release gate | `eval/`, `docs/evaluation-report.md` |
| 6 | Responsible AI, PDPL and security | `docs/responsible-ai.md`, `docs/pdpl-data-residency.md`, `docs/threat-model.md` |
| 7 | Infrastructure and CI/CD | `infra/`, `.github/workflows/` |
| 8 | Operations, monitoring and incidents | `docs/runbook.md`, `observability/` |
| 9 | Rollback and prompt rollback drill (hands-on) | Drill log |
| 10 | Risk register review and roadmap | `docs/risk-register.md` |

All sessions are recorded. Q&A goes into a shared FAQ, which is added to the repo.

## Exit criteria (all must be met)
- [ ] Client engineer merged a feature PR end to end (CI → eval gate → deploy) without help
- [ ] Client ran `scripts/ingest.py` to add a document and updated the golden set
- [ ] Client created a new prompt version, ran the eval and documented the result
- [ ] Revision rollback and prompt rollback drills completed within the target time (under 15 minutes)
- [ ] Client on-call handled a simulated incident (guardrail outage / quota exhaustion) using the runbook
- [ ] All access transferred: GitHub admin, Azure Owner, Entra app ownership, budget alert recipients; vendor access removed or reduced
- [ ] Open risks re-owned by client staff in the risk register

## Operational readiness
- Alerts routed to the client's on-call (budget, failures, escalation-rate spike)
- Runbook validated by the client team; contact list updated
- Backups and retention decided for the review queue (move from SQLite to a durable store before production)
- Model and prompt change process agreed (CAB or PR approval and eval evidence)

## Support model after handover
- Weeks 6-9: hypercare. Vendor is second-line, responds within 1 business day; client is first-line.
- Afterwards: advisory only, on request.

## Risks
| Risk | Mitigation |
|---|---|
| Key-person dependency | Pairing rotation; recorded sessions; ADRs explain the "why" |
| Client team lacks GenAI evaluation experience | Dedicated eval session; PR template forces eval evidence |
| Access not fully transferred | Exit checklist with Security sign-off |
| Model or SKU deprecation after handover | Runbook model-swap procedure; eval gate catches regressions |
| Scope creep during KT | Change requests logged separately from the KT plan |
