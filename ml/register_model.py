"""Quantize the ONNX classifier, log it to the MLflow run and register it in Azure ML.

MLflow 3's `log_model` uses the "logged models" REST API, which the Azure ML MLflow backend does
not implement (404). We therefore log the model folder as run artifacts and register it with
the Azure ML SDK, pointing at the run's artifact path so lineage (run -> model version) is kept.

Usage: uv run --extra ml python ml/register_model.py [--run-id RUN_ID]
"""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "ml" / "artifacts" / "gov-policy-query-classifier"
METRICS = ROOT / "eval" / "results" / "classifier" / "metrics.json"
MODEL_NAME = "gov-policy-query-classifier"


def quantize(art: Path) -> Path:
    """Dynamic int8 quantization (~4x smaller, CPU-friendly). Keeps fp32 as model.fp32.onnx."""
    from onnxruntime.quantization import QuantType, quantize_dynamic

    fp32 = art / "model.fp32.onnx"
    if not fp32.exists():
        shutil.move(art / "model.onnx", fp32)
    quantize_dynamic(str(fp32), str(art / "model.onnx"), weight_type=QuantType.QInt8)
    return art / "model.onnx"


def eval_quantized(art: Path) -> dict[str, float]:
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from gov_copilot.classifier import OnnxQueryClassifier

    clf = OnnxQueryClassifier(art)
    rows = [
        json.loads(x) for x in (ROOT / "data/classifier/test.jsonl").read_text().splitlines() if x
    ]
    out: dict[str, float] = {}
    for scope in ("all", "en", "ar"):
        sub = [r for r in rows if scope == "all" or r["language"] == scope]
        preds = [clf.predict(r["text"]) for r in sub]
        out[f"int8_{scope}_accuracy"] = sum(
            p.label == r["label"] for p, r in zip(preds, sub, strict=True)
        ) / len(sub)
        out[f"int8_{scope}_in_scope_accuracy"] = sum(
            p.in_scope == (r["label"] != "out_of_scope") for p, r in zip(preds, sub, strict=True)
        ) / len(sub)
    return out


def ml_client():  # type: ignore[no-untyped-def]
    from azure.ai.ml import MLClient
    from azure.identity import DefaultAzureCredential

    sub = (
        os.environ.get("AZURE_SUBSCRIPTION_ID")
        or subprocess.run(
            ["az", "account", "show", "--query", "id", "-o", "tsv"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    return MLClient(
        DefaultAzureCredential(),
        sub,
        os.environ.get("AZUREML_RESOURCE_GROUP", "rg-govcopilot-dev"),
        os.environ.get("AZUREML_WORKSPACE", "mlw-govcopilot-dev"),
    )


def register(run_id: str, metrics: dict) -> str:  # type: ignore[type-arg]
    import mlflow
    from azure.ai.ml.constants import AssetTypes
    from azure.ai.ml.entities import Model

    from ml.train_classifier import azureml_tracking_uri

    mlflow.set_tracking_uri(azureml_tracking_uri())
    staging = ART.parent / "_register"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    for f in ("model.onnx", "tokenizer.json", "labels.json"):
        shutil.copy(ART / f, staging / f)
    # Use the client API: it works on runs that are already terminated (no re-open/close).
    client = mlflow.MlflowClient()
    try:
        client.log_artifacts(run_id, str(staging), artifact_path="model")
    except Exception as e:  # idempotent re-runs: Azure ML artifacts are immutable
        if "already exists" not in str(e):
            raise
    for k, v in metrics.items():
        if k.startswith("int8_"):
            client.log_metric(run_id, k, float(v))
    client.set_tag(run_id, "registered_model", MODEL_NAME)
    shutil.rmtree(staging, ignore_errors=True)

    m = metrics
    model = Model(
        name=MODEL_NAME,
        path=f"azureml://jobs/{run_id}/outputs/artifacts/paths/model/",
        type=AssetTypes.CUSTOM_MODEL,
        description="Bilingual (AR/EN) query router, distilbert-base-multilingual-cased fine-tune, ONNX int8.",
        tags={
            "framework": "onnxruntime",
            "base_model": "distilbert-base-multilingual-cased",
            "labels": "charter,international_policy,ethics,data_protection,out_of_scope",
            "test_accuracy_en": f"{m.get('en_accuracy', 0):.3f}",
            "test_accuracy_ar": f"{m.get('ar_accuracy', 0):.3f}",
            "test_macro_f1_en": f"{m.get('en_macro_f1', 0):.3f}",
            "test_macro_f1_ar": f"{m.get('ar_macro_f1', 0):.3f}",
            "int8_accuracy": f"{m.get('int8_all_accuracy', 0):.3f}",
            "repo": "https://github.com/snaeemm/gov-policy-copilot",
            "mlflow_run_id": run_id,
        },
    )
    registered = ml_client().models.create_or_update(model)
    return str(registered.version)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--skip-register", action="store_true")
    a = ap.parse_args()
    summary = json.loads(METRICS.read_text())
    run_id = a.run_id or summary["run_id"]
    quantize(ART)
    q = eval_quantized(ART)
    summary["quantized"] = {k: round(v, 4) for k, v in q.items()}
    summary["onnx_size_mb"] = {
        "fp32": round((ART / "model.fp32.onnx").stat().st_size / 1e6, 1),
        "int8": round((ART / "model.onnx").stat().st_size / 1e6, 1),
    }
    flat = {f"{lang}_{k}": v for lang, mm in summary["metrics"].items() for k, v in mm.items()}
    if not a.skip_register:
        version = register(run_id, {**flat, **q})
        summary["registered_model"] = {
            "name": MODEL_NAME,
            "version": version,
            "workspace": "mlw-govcopilot-dev",
        }
        print(f"registered {MODEL_NAME} v{version}")
    METRICS.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(
        json.dumps(
            {"quantized": summary["quantized"], "size_mb": summary["onnx_size_mb"]}, indent=1
        )
    )


if __name__ == "__main__":
    main()
