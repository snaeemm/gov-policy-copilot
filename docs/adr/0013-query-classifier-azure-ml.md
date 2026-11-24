# ADR-0013: Fine-tuned multilingual query classifier, tracked in Azure ML, served in-container

- Status: Accepted (2026-11-24)
- Related: ADR-0004 (deterministic orchestration), ADR-0010 (eval gate), ADR-0008 (Container Apps)

## Context
Every question currently costs at least one LLM call (the planner) before we know whether it is
in scope. We also want a policy-area route (charter / international policy / ethics / data
protection) for analytics and drift monitoring, and the role requires hands-on fine-tuning and
Azure Machine Learning experience. Budget target is ~$0.

## Decision
- Fine-tune **`distilbert-base-multilingual-cased`** (135M params, Arabic + English) as a 5-way
  classifier: `charter | international_policy | ethics | data_protection | out_of_scope`.
- **Train on free GitHub-hosted CPU runners** (`.github/workflows/train.yml`) or locally, and use an
  **Azure ML workspace only for MLflow tracking and the model registry**
  (`infra/modules/ml.bicep`; no compute clusters, no managed endpoints, no ACR).
- Export to **ONNX** and serve with **onnxruntime + tokenizers inside the existing Container App**
  (no torch in the image, no extra endpoint). The model is pulled from Hugging Face Hub at start-up
  (`CLASSIFIER_HF_REPO`) or a mounted path, behind `CLASSIFIER_ENABLED` (default off).
- Runtime policy: only `out_of_scope` with confidence ≥ `CLASSIFIER_OOS_THRESHOLD` (0.9)
  short-circuits (no LLM call). Everything else continues through the LLM planner, retrieval,
  grounding and Content Safety - the classifier is an optimisation and a routing signal, never a
  safety control. Its label is returned in the API/UI and logged (`classifier_label`) for drift KQL.

## Alternatives considered
| Option | Why not (here) |
|---|---|
| Azure OpenAI fine-tuning (e.g. gpt-4.1-mini FT) | Training charged per token plus **hourly hosting for the fine-tuned deployment** (tens of dollars/month even idle); higher latency (~0.5-2 s vs ~10-30 ms); overkill for a 5-way routing task. |
| Zero-shot routing with gpt-5-mini | Works (the planner already does it) but costs tokens and ~1-3 s on every request; no offline-testable artefact. |
| Azure ML managed online endpoint | Always-on compute (~$50+/month minimum). In-container ONNX is free and fast enough on 0.5 vCPU. |
| Azure ML serverless/cluster training | Small per-run cost and trial quota frequently 0; GitHub runners are free and still log/register into Azure ML via MLflow, which is the part that matters for governance (lineage, versions, metrics). |

## Consequences
- + Zero LLM cost and ~10-30 ms for confidently off-topic traffic; policy-area labels for analytics.
- + Model lineage (params, metrics, confusion matrix, git SHA) and versions live in Azure ML;
  public model card on Hugging Face links back to the repo.
- − Synthetic training data (LLM-generated from the public corpus) → monitor label-mix drift
  (`observability/kql/drift_classifier_labels.kql`) and retrain via `train.yml` when the corpus
  changes. Data residency: the model runs in UAE North inside the container; training data is
  derived from public documents only.
- − One more artefact to version: classifier version must be recorded alongside prompt/model
  versions when evaluating.
