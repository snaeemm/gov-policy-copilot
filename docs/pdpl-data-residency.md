# PDPL & Data Residency

> Engineering notes, not legal advice. Federal Decree-Law No. 45 of 2021 (PDPL) applies to processing of personal data in the UAE; government entities and some sectors/free zones have separate regimes. A real deployment needs review by the entity's DPO.

## What personal data the system can touch
The **corpus contains none**. Personal data can only enter through **user questions** and **user identity** (Entra token claims).

| Principle | Implementation |
|---|---|
| Data minimisation | Only `oid` and display name are read from the token; no profile storage. Questions are not stored except PII-masked in logs and in escalated review items |
| Masking before logging | `mask_pii()` runs first in every request: UAE regex (Emirates ID, +971/05 phones, AE IBAN, email, card) then Azure AI Language PII (EN and AR). Only masked text reaches logs and the review queue |
| Purpose limitation | Questions are used only to answer and, if escalated, for human review |
| No training | Azure OpenAI does not train on customer prompts; no fine-tuning in this project |
| Retention | Log Analytics retention 30 days; review queue is ephemeral (container `/tmp`) |
| Security | Keyless access, RBAC, TLS-only ingress, Key Vault, optional private endpoints |
| Data subject rights | Not implemented (no persistent user data store). Production: deletion by `oid` across logs/review store |

## Residency by service (all resources in UAE North)
| Service | Data at rest | Processing location |
|---|---|---|
| AI Search (index) | UAE North | UAE North |
| Document Intelligence | transient | UAE North |
| Azure OpenAI embeddings (Standard) | none stored | UAE North |
| **Azure OpenAI gpt-5-mini (GlobalStandard)** | none stored (abuse-monitoring storage may apply) | **any Azure region** ⚠️ |
| Content Safety, AI Language | transient | UAE North |
| Key Vault, Log Analytics, App Insights | UAE North | UAE North |
| Container Apps | UAE North | UAE North |
| GitHub (code, CI logs, GHCR image) | GitHub (US/EU) | contains no user data |

⚠️ To keep all processing in-country for non-public data: regional/provisioned deployment in UAE North, request abuse-monitoring exemption where eligible, enable private endpoints (`enablePrivateEndpoints=true`).
