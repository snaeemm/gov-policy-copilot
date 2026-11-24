"""Publish the fine-tuned query classifier to Hugging Face Hub with a model card.

Reads HF_TOKEN and HF_USERNAME from the environment (or .env). Never prints the token.
Usage: uv run --extra ml python ml/publish_hf.py
"""

import json
import os
import sys
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "ml" / "artifacts" / "gov-policy-query-classifier"
METRICS = ROOT / "eval" / "results" / "classifier" / "metrics.json"
REPO_NAME = "gov-policy-query-classifier"


def env(name: str) -> str:
    if v := os.environ.get(name):
        return v
    for f in (".env", ".env.azure"):
        p = ROOT / f
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith(f"{name}="):
                    return line.split("=", 1)[1].split("#")[0].strip()
    return ""


def card(m: dict) -> str:  # type: ignore[type-arg]
    rows = "\n".join(
        f"| {k} | {v['n']:.0f} | {v['accuracy']:.3f} | {v['macro_f1']:.3f} | {v['in_scope_accuracy']:.3f} |"
        for k, v in m["metrics"].items()
    )
    return f"""---
language:
- ar
- en
license: apache-2.0
base_model: distilbert-base-multilingual-cased
pipeline_tag: text-classification
tags:
- uae
- government
- query-routing
- onnx
- azure-machine-learning
metrics:
- accuracy
- f1
---

# gov-policy-query-classifier

Bilingual (Arabic / English) query router fine-tuned from `distilbert-base-multilingual-cased`.
It is the pre-filter of **[Gov Policy Copilot](https://github.com/snaeemm/gov-policy-copilot)**, a
reference RAG assistant over public UAE government policy documents built on Microsoft Azure.

**Labels:** `charter` (UAE Charter for the Development and Use of AI), `international_policy`
(UAE international stance on AI policy), `ethics` (UAE AI Ethics Principles & Guidelines),
`data_protection` (personal data protection / PDPL topics), `out_of_scope`.

## Intended use
Route questions and cheaply reject clearly off-topic ones before calling an LLM. In the copilot,
only predictions of `out_of_scope` with confidence ≥ 0.9 short-circuit; everything else still goes
through the LLM planner, retrieval, grounding checks and content safety. **Not** a safety filter
and **not** a legal classifier.

## Training
- Data: ~1.1k questions generated with Azure OpenAI gpt-5-mini from the indexed public documents
  (same- and cross-language), synthetic data-protection topic questions, and generic off-topic
  questions. Golden and red-team evaluation questions are held out in the test split only.
  Dataset card: [data/classifier/README.md](https://github.com/snaeemm/gov-policy-copilot/blob/main/data/classifier/README.md)
- 4 epochs, lr 4e-5, max_len 64, CPU; label×language strata oversampled to balance.
- Tracked with MLflow in Azure Machine Learning and registered as `gov-policy-query-classifier`.

## Evaluation (held-out test split)
| scope | n | accuracy | macro-F1 | in-scope accuracy |
|---|---|---|---|---|
{rows}

## Files
`model.onnx` + `tokenizer.json` + `labels.json` for onnxruntime serving (no torch needed);
`hf/` contains the Transformers checkpoint.

## Limitations
- Synthetic, LLM-generated training questions; real user traffic will differ (monitor label mix drift).
- `data_protection` is learned from topic prompts, not the PDPL text itself.
- Small corpus (6 documents); unseen policy areas will tend to map to the nearest label or out_of_scope.
- Reference implementation on public data - not an official UAE government system.
"""


def main() -> int:
    token, user = env("HF_TOKEN"), env("HF_USERNAME")
    if not token or not user:
        print("HF_TOKEN / HF_USERNAME not set - skipping Hugging Face publish")
        return 0
    m = json.loads(METRICS.read_text())
    (ART / "README.md").write_text(card(m), encoding="utf-8")
    api = HfApi(token=token)
    repo = f"{user}/{REPO_NAME}"
    api.create_repo(repo, exist_ok=True, private=False)
    api.upload_folder(
        repo_id=repo, folder_path=str(ART), commit_message="Upload classifier + model card"
    )
    print(f"published https://huggingface.co/{repo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
