# Threat Model (STRIDE)

Assets: index content (public), user questions (may contain PII), review queue, Azure credentials, model spend.

| Component | Threat (STRIDE) | Mitigation – implemented | Planned / gap |
|---|---|---|---|
| SPA → API | **S**poofing a user | Entra ID JWT validated (signature via JWKS, issuer, audience, exp); `appRoleAssignmentRequired` on the API enterprise app | Conditional Access / MFA policy (tenant-level) |
| API | **E**levation of privilege | App roles Viewer < Reviewer < Admin enforced per route (`require(Role)`) | Periodic access reviews |
| API | **D**enial of service / cost exhaustion | Per-user/IP rate limit (`RATE_LIMIT=20/minute`), max question length 1000, max 2 replicas, $5 budget alerts | Azure Front Door + WAF; token budgets per user |
| Prompt | **T**ampering via jailbreak | Prompt Shields on input; system prompt instructs to use sources only | – |
| Retrieved sources | **T**ampering via indirect prompt injection | Prompt Shields on documents; prompt treats sources as data | Signed/approved gold-layer ingestion (see governance doc) |
| LLM output | **I**nformation disclosure / harmful output | Harm analysis on output; groundedness check; escalation | – |
| Logs | **I**nformation disclosure of PII | PII masked before logging; 30-day retention | Customer-managed keys |
| Azure services | **S**poofing / credential theft | No keys (`disableLocalAuth`), managed identity, OIDC for CI | Search: switch to RBAC-only (`disableLocalAuth`) |
| CI/CD | **T**ampering with pipeline | OIDC federated credential scoped to `main` + `production` environment; Contributor on one RG only | Required reviewers on `production` env; image signing; Dependabot |
| Review queue | **R**epudiation | Reviewer `oid` + timestamp recorded per decision | Durable, append-only store (Cosmos DB) |
| Network | **I**nformation disclosure in transit | HTTPS only (`allowInsecure: false`) | Private endpoints (Bicep flag, off for cost) |
| Supply chain | **T**ampering with image/deps | `uv.lock` pinned, non-root container | SBOM, vulnerability scanning (Defender/Trivy) |
