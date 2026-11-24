# ADR-0008: Azure Container Apps with scale-to-zero

Status: Accepted

**Decision.** Consumption Container Apps environment, 0.5 vCPU / 1 GiB, `minReplicas: 0`, `maxReplicas: 2`, HTTP scaling at 20 concurrent requests, `activeRevisionsMode: Multiple` for revision-based rollback.

**Consequences.** + $0 when idle (monthly free grant). + Revisions give blue/green and instant traffic rollback. − Cold start 10–20 s after idle. − SQLite review queue in `/tmp` is lost on restart (see risk register).

**Alternatives.** AKS (operational overhead, node cost); App Service (no scale-to-zero on paid tiers, B1 ≈ $13/mo); Azure Functions (awkward for SSE streaming).
