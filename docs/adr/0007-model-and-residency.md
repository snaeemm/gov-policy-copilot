# ADR-0007: gpt-5-mini (GlobalStandard) and data residency

Status: Accepted, with documented residency caveat

**Context.** In UAE North (Nov 2026): `gpt-4o-mini` is deprecated for new deployments; `gpt-5.4-mini` had 0 quota on the trial subscription; `gpt-5-mini` (2025-08-07) is GA with quota, **GlobalStandard only**.

**Decision.** Chat/judge: `gpt-5-mini`, GlobalStandard, `reasoning_effort=minimal`, version auto-upgrade disabled. Embeddings: `text-embedding-3-small`, **regional Standard** (inference in UAE North).

**Consequences.** Resources and stored data (index, logs, Key Vault) are in UAE North, but chat-completion prompts may be processed in any Azure region. Acceptable here because all source documents are public and user questions are PII-masked in logs (the raw question is still sent to the model). For a government deployment handling non-public data: use a Regional Standard / Data Zone or Provisioned deployment available in-region, or a model hosted in UAE North, and record it in this ADR.
