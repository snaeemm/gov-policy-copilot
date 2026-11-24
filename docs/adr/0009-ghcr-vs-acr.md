# ADR-0009: GitHub Container Registry instead of Azure Container Registry

Status: Accepted (cost-driven)

**Decision.** CI pushes images to `ghcr.io/snaeemm/gov-policy-copilot:<sha>` using the workflow `GITHUB_TOKEN`.

**Consequences.** + $0 (ACR Basic ≈ $5/month would consume the entire budget). − Image pull depends on GHCR availability; no ACR features (Defender scanning, geo-replication, private endpoint). − Container Apps pulls anonymously, so the package must be public.

**Production alternative.** ACR Premium with private endpoint, managed-identity pull, content trust and Defender for Containers.
