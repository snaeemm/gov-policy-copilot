# Responsible AI Assessment – mapped to the UAE Charter for the Development and Use of AI (2024)

Scope: this reference implementation (public documents, demo users). Status: ✅ implemented · ◐ partial · ✗ gap.

| # | Charter principle | Controls in this system | Evidence | Status / gaps |
|---|---|---|---|---|
| 1 | Strengthening human–machine ties | Assistant supports, not replaces, human judgment; reviewer console to approve/edit/reject escalated answers | `api/main.py` (`/api/reviews`), `frontend/app.js` | ✅ |
| 2 | Safety | Content Safety harm analysis on input and output; Prompt Shields; fail-closed on guardrail outage; red-team suite in CI | `guardrails_azure.py`, `eval/redteam.jsonl` | ✅ |
| 3 | Algorithmic bias | Bilingual parity measured (EN vs AR answer rate 1.00 vs 0.92); Arabic-specific analyzer and normalization | `eval/results/baseline-v2.json`, ADR-0002 | ◐ Arabic still trails; no demographic bias testing (not applicable to corpus Q&A) |
| 4 | Data privacy | PII masked (UAE regex + AI Language) before logging/storage; no training on user data; keyless access | `pii.py`, `orchestrator.py` (`masked_q`) | ◐ raw question still sent to a GlobalStandard model (ADR-0007) |
| 5 | Transparency | Every sentence cited with page; groundedness score, model and prompt version shown in UI; disclaimer | `frontend/app.js` (`renderAnswer`), `index.html` | ✅ |
| 6 | Human oversight | Low-confidence answers escalated to a human review queue; reviewer/admin roles | `agent/review_queue.py`, `api/auth.py` | ◐ queue is ephemeral (SQLite in container) |
| 7 | Governance and accountability | Prompt/model versions logged per request; ADRs; risk register; eval gate in CI; Entra RBAC | `docs/adr/`, `docs/risk-register.md`, `.github/workflows/cd.yml` | ✅ |
| 8 | Technological excellence | Hybrid retrieval, automated evaluation (Azure AI Evaluation SDK), typed code, tests, IaC | `retrieval/`, `eval/`, `tests/`, `infra/` | ✅ |
| 9 | Human commitment | System is scoped to public policy information, refuses legal advice, routes uncertain cases to people | `prompts/v2/answer.md`, red-team `legal_advice` | ✅ |
| 10 | Peaceful coexistence with AI | Clear disclosure that answers are AI-generated and not an official service | `frontend/index.html` disclaimer | ✅ |
| 11 | Promoting AI awareness for an inclusive future | Bilingual UI with RTL support; plain-language answers | `frontend/` | ◐ no accessibility audit (WCAG) yet |
| 12 | Commitment to treaties and applicable laws | PDPL-aware design (minimisation, masking, residency doc); no legal advice | `docs/pdpl-data-residency.md` | ◐ formal legal review not performed |

## Residual risks
See `risk-register.md`. Highest: judge bias in groundedness scores, GlobalStandard inference location, ephemeral review queue, small corpus.
