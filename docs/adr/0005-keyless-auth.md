# ADR-0005: Keyless authentication (Entra ID, managed identity, RBAC)

Status: Accepted

**Decision.** All Cognitive Services accounts set `disableLocalAuth: true`. The Container App runs as a user-assigned managed identity with least-privilege data-plane roles (Cognitive Services OpenAI User, Cognitive Services User, Search Index Data Reader, Key Vault Secrets User). Code uses `DefaultAzureCredential` (az login locally, managed identity in Azure). CI uses GitHub OIDC federated credentials — no client secret exists. Key Vault holds the App Insights connection string, referenced by the Container App via its identity. Files: `infra/modules/ai-services.bicep`, `infra/modules/app.bicep`, `infra/scripts/setup-entra.sh`.

**Consequences.** + No secret to leak or rotate. + Access is auditable in the Azure activity log. − Role propagation delays (minutes) after deployment. − AI Search still allows keys (`aadOrApiKey`) for tooling convenience; production would set it to RBAC-only.
