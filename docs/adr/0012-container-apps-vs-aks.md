# ADR-0012: Azure Container Apps for this workload; Helm/AKS as the portable path

- **Status:** Accepted
- **Date:** 2026-11-24
- **Related:** [ADR-0008](0008-container-apps.md) (Container Apps hosting), [deploy/k8s/README.md](../../deploy/k8s/README.md)

## Context
The workload is a single stateless HTTP API container plus a static SPA. It has bursty, low and
often zero traffic, calls managed Azure AI services over HTTPS, and must cost about $0 when
idle. Government and enterprise clients often run a shared AKS platform, so the solution must
also be deployable there without re-engineering.

## Decision
- **Run on Azure Container Apps** (consumption plan, scale to zero, revision-based traffic
  splitting for rollback, managed identity, Key Vault secret references).
- **Ship a production-grade Helm chart** for AKS or any Kubernetes. CI validates it on an
  ephemeral **kind** cluster in GitHub Actions. **No AKS cluster is provisioned.**

## Why Container Apps here
| Factor | Container Apps | AKS |
|---|---|---|
| Idle cost | $0 (scale to zero, monthly free grant) | Nodes always billed; smallest practical system pool is about $70–150/month, plus a load balancer and public IP |
| Ops burden | No cluster upgrades, node patching or CNI management | Cluster lifecycle, node image upgrades, add-ons, policy, capacity planning |
| Features needed | HTTPS ingress, autoscale, revisions and traffic split, managed identity, KV references, Log Analytics | All available, but each one is assembled and operated by us |
| Team size | One engineer | Usually a platform team |

## When AKS is the right choice
Choose AKS, using this chart as the starting point, when one or more of these hold:
1. **A shared multi-tenant platform** already exists, with central governance (Azure Policy and
   Gatekeeper, quotas, namespaces per team) that workloads must land on.
2. **Custom networking**: a service mesh (Istio/Linkerd) with mTLS between services, egress
   gateways or firewalls with fine-grained FQDN rules, or hub-and-spoke integration beyond what
   Container Apps VNet integration offers.
3. **GPU node pools** or self-hosted models (vLLM or Triton serving open-weight LLMs, rerankers, or
   the M8 classifier at scale), or specialised hardware.
4. **An existing platform team** with GitOps (Flux/Argo CD), observability and security tooling
   already standardised on Kubernetes.
5. **Many services** (roughly 10+ microservices), where shared node capacity, sidecars, CRDs and operators
   amortise the cluster's fixed cost.
6. Requirements for **daemonsets, privileged agents or custom operators** that Container Apps
   doesn't allow.

## Migration path (Container Apps → AKS)
1. Create AKS with `--enable-oidc-issuer --enable-workload-identity` and the
   `azure-keyvault-secrets-provider` add-on, ideally private and with Azure CNI Overlay.
2. Reuse the **same user-assigned managed identity**. Add a federated credential for
   `system:serviceaccount:<ns>:gov-policy-copilot`, so role assignments stay unchanged.
3. `helm upgrade --install` using the same GHCR image digest that CD promoted (see `deploy/k8s/README.md`).
4. Front it with an ingress controller (or Application Gateway for Containers) and Entra-protected DNS.
5. Shift traffic with DNS or Front Door weights, keeping Container Apps as the rollback target until stable.
6. Move the review queue off SQLite to Cosmos DB first: it is ephemeral on both platforms (see README limitations).

## Consequences
- Lowest possible run cost and ops load today. The chart and kind CI prove Kubernetes readiness
  without paying for a cluster.
- Two deployment descriptors (Bicep `app.bicep` and the Helm chart) must stay in sync, notably the
  env vars. CI renders the chart on every change to `deploy/**` or the `Dockerfile`, but it
  doesn't diff it against Bicep. That's a known gap.
- kind runs kindnet. NetworkPolicy enforcement is verified there, but AKS with Azure CNI plus Cilium or
  Calico should be re-verified in a real cluster.
