# Kubernetes packaging (Helm)

The production deployment of this project is **Azure Container Apps** (see
[ADR-0008](../../docs/adr/0008-container-apps.md) and
[ADR-0012](../../docs/adr/0012-container-apps-vs-aks.md)). This Helm chart is a portable package
for teams that run on **AKS** or another Kubernetes platform. CI validates it on every change.
**No AKS cluster is created by this repo.**

Chart: [`deploy/helm/gov-policy-copilot`](../helm/gov-policy-copilot)

## What the chart contains
| Resource | Purpose |
|---|---|
| Deployment | Non-root (uid 10001), read-only root filesystem, `emptyDir` `/tmp`, dropped capabilities, seccomp `RuntimeDefault`; startup, liveness and readiness probes on `/healthz`; requests and limits; rolling update with `maxUnavailable: 0` |
| Service | ClusterIP on port 80 → 8000 |
| HorizontalPodAutoscaler | `autoscaling/v2`, CPU 70 %, 2–6 replicas (scale-down stabilization 5 min) |
| PodDisruptionBudget | `minAvailable: 1` |
| NetworkPolicy | Ingress only from the ingress controller (plus explicit extras). Egress only to DNS and TCP 443 (Azure OpenAI, AI Search, Content Safety, Language, Entra ID, Key Vault) |
| ServiceAccount | AKS **Workload Identity** annotations (`azure.workload.identity/client-id`). Same keyless model as the Container App's managed identity |
| SecretProviderClass | **Azure Key Vault CSI driver**: syncs `appinsights-connection-string` into a Kubernetes Secret consumed via `envFrom`. Default on |
| ExternalSecret | Alternative: External Secrets Operator + `ClusterSecretStore` for Key Vault. Default off |
| ConfigMap | Non-secret settings, mirroring `infra/main.bicep` `envVars` |
| Ingress | Optional (`ingress.enabled`) |

No secret values ever appear in values files. Secrets are referenced by Key Vault object name only.

## Install on AKS
Prerequisites: an AKS cluster with `--enable-oidc-issuer --enable-workload-identity` and the
`azure-keyvault-secrets-provider` add-on, plus an ingress controller. You also need a federated
credential on the app's user-assigned managed identity for
`system:serviceaccount:<namespace>:gov-policy-copilot`.

```bash
helm upgrade --install gpc deploy/helm/gov-policy-copilot -n copilot --create-namespace \
  --set image.tag=<git-sha> \
  --set serviceAccount.workloadIdentity.clientId=<uami-client-id> \
  --set serviceAccount.workloadIdentity.tenantId=<tenant-id> \
  --set secrets.csi.keyVaultName=<kv-name> --set secrets.csi.tenantId=<tenant-id> \
  --set config.AZURE_OPENAI_ENDPOINT=https://<aoai>.openai.azure.com/ \
  --set config.AZURE_SEARCH_ENDPOINT=https://<search>.search.windows.net \
  --set config.CONTENT_SAFETY_ENDPOINT=https://<cs>.cognitiveservices.azure.com/ \
  --set config.LANGUAGE_ENDPOINT=https://<lang>.cognitiveservices.azure.com/ \
  --set config.ENTRA_TENANT_ID=<tenant-id> --set config.ENTRA_API_AUDIENCE=api://<api-app-id> \
  --set config.ENTRA_SPA_CLIENT_ID=<spa-app-id> \
  --set ingress.enabled=true --set ingress.host=copilot.example.ae
```

The identity needs the same data-plane roles the Container App identity has (see
`infra/modules/app.bicep`): Cognitive Services OpenAI User, Cognitive Services User (Content
Safety, Language), Search Index Data Reader, and Key Vault Secrets User.

## CI: `.github/workflows/k8s.yml` ($0)
Runs on PRs and pushes that touch `deploy/**` or the `Dockerfile`, entirely inside the GitHub runner:
1. `helm lint`, using both the CI and the AKS-style values.
2. `kubeconform -strict` against Kubernetes 1.30 schemas, for three variants: AKS + CSI, AKS + ExternalSecret + Ingress, and CI. CRDs without public schemas are skipped.
3. Builds the image, creates a **kind** cluster, loads the image, then runs `helm install --wait` with [`values-ci.yaml`](../helm/gov-policy-copilot/values-ci.yaml). That file sets auth off, no Azure endpoints, no CSI, and keeps the NetworkPolicy **on**.
4. Smoke tests: `/healthz` and `/` via port-forward, and checks that the HPA and NetworkPolicy exist.
5. NetworkPolicy behaviour: a pod labelled `role=smoke-test` **can** reach the service, and an unlabelled pod is **blocked**.
6. Asserts the security context: non-root and read-only root filesystem.

## Local validation
```bash
helm lint deploy/helm/gov-policy-copilot -f deploy/helm/gov-policy-copilot/values-ci.yaml
helm template gpc deploy/helm/gov-policy-copilot -f deploy/helm/gov-policy-copilot/values-ci.yaml \
  | kubeconform -strict -summary
kind create cluster --name gpc && docker build -t gov-policy-copilot:ci . \
  && kind load docker-image gov-policy-copilot:ci --name gpc \
  && helm install gpc deploy/helm/gov-policy-copilot -f deploy/helm/gov-policy-copilot/values-ci.yaml --wait
kind delete cluster --name gpc
```
