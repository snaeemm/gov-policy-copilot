"""Fine-tune distilbert-base-multilingual-cased as a bilingual (AR/EN) query router.

Tracks params/metrics/artifacts with MLflow. When --azureml is passed (or AZUREML_MLFLOW_URI is
set) tracking goes to the Azure ML workspace and the ONNX model is registered in its model
registry as `gov-policy-query-classifier`. Otherwise tracking is local (./mlruns).

Usage:
  uv run --extra ml python ml/train_classifier.py --azureml
"""

import argparse
import json
import os
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import torch
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "classifier"
ART = ROOT / "ml" / "artifacts"
RESULTS = ROOT / "eval" / "results" / "classifier"
LABELS = ["charter", "international_policy", "ethics", "data_protection", "out_of_scope"]
L2I = {lab: i for i, lab in enumerate(LABELS)}
BASE = "distilbert-base-multilingual-cased"
MODEL_NAME = "gov-policy-query-classifier"


def load(name: str) -> list[dict[str, Any]]:
    return [
        json.loads(x)
        for x in (DATA / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
        if x
    ]


def oversample(rows: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    """Balance label x language strata up to the largest stratum (simple, transparent)."""
    rng = random.Random(seed)
    strata: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows:
        strata.setdefault((r["label"], r["language"]), []).append(r)
    target = max(len(v) for v in strata.values())
    out: list[dict[str, Any]] = []
    for items in strata.values():
        out += items + [rng.choice(items) for _ in range(target - len(items))]
    rng.shuffle(out)
    return out


class QDataset(Dataset[dict[str, torch.Tensor]]):
    def __init__(self, rows: list[dict[str, Any]], tok: Any, max_len: int) -> None:
        enc = tok(
            [r["text"] for r in rows], truncation=True, max_length=max_len, padding="max_length"
        )
        self.ids = torch.tensor(enc["input_ids"])
        self.mask = torch.tensor(enc["attention_mask"])
        self.y = torch.tensor([L2I[r["label"]] for r in rows])

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, i: int) -> dict[str, torch.Tensor]:
        return {"input_ids": self.ids[i], "attention_mask": self.mask[i], "labels": self.y[i]}


@torch.no_grad()
def predict(model: Any, ds: QDataset, bs: int = 64) -> np.ndarray:
    model.eval()
    out = []
    for b in DataLoader(ds, batch_size=bs):
        out.append(model(input_ids=b["input_ids"], attention_mask=b["attention_mask"]).logits)
    return torch.cat(out).softmax(-1).numpy()


def metrics(rows: list[dict[str, Any]], probs: np.ndarray, prefix: str) -> dict[str, float]:
    y = np.array([L2I[r["label"]] for r in rows])
    p = probs.argmax(-1)
    oos = L2I["out_of_scope"]
    m = {
        f"{prefix}accuracy": float(accuracy_score(y, p)),
        f"{prefix}macro_f1": float(
            f1_score(y, p, average="macro", labels=range(len(LABELS)), zero_division=0)
        ),
        f"{prefix}in_scope_accuracy": float(accuracy_score(y != oos, p != oos)),
        f"{prefix}n": float(len(rows)),
    }
    return m


def confusion_png(rows: list[dict[str, Any]], probs: np.ndarray, path: Path) -> list[list[int]]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    y = [L2I[r["label"]] for r in rows]
    cm = confusion_matrix(y, probs.argmax(-1), labels=range(len(LABELS)))
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    ax.imshow(cm, cmap="Greens")
    ax.set_xticks(range(len(LABELS)), LABELS, rotation=35, ha="right")
    ax.set_yticks(range(len(LABELS)), LABELS)
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    for i in range(len(LABELS)):
        for j in range(len(LABELS)):
            ax.text(j, i, int(cm[i, j]), ha="center", va="center", color="black")
    ax.set_title("Query classifier - test set confusion matrix")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return [[int(v) for v in row] for row in cm]


def export_onnx(model: Any, tok: Any, out_dir: Path, max_len: int) -> Path:
    model.eval()
    dummy = tok(
        ["export"], return_tensors="pt", padding="max_length", max_length=max_len, truncation=True
    )
    path = out_dir / "model.onnx"

    class Wrapper(torch.nn.Module):
        def __init__(self, m: Any) -> None:
            super().__init__()
            self.m = m

        def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
            return self.m(input_ids=input_ids, attention_mask=attention_mask).logits

    torch.onnx.export(
        Wrapper(model),
        (dummy["input_ids"], dummy["attention_mask"]),
        str(path),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "seq"},
            "attention_mask": {0: "batch", 1: "seq"},
            "logits": {0: "batch"},
        },
        opset_version=17,
        dynamo=False,
    )
    return path


def azureml_tracking_uri() -> str:
    if uri := os.environ.get("AZUREML_MLFLOW_URI"):
        return uri
    sub = subprocess.run(
        ["az", "account", "show", "--query", "id", "-o", "tsv"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    rg = os.environ.get("AZUREML_RESOURCE_GROUP", "rg-govcopilot-dev")
    ws = os.environ.get("AZUREML_WORKSPACE", "mlw-govcopilot-dev")
    return (
        f"azureml://uaenorth.api.azureml.ms/mlflow/v1.0/subscriptions/{sub}/resourceGroups/{rg}"
        f"/providers/Microsoft.MachineLearningServices/workspaces/{ws}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--azureml", action="store_true", help="Track + register in Azure ML")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--lr", type=float, default=4e-5)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--max-len", type=int, default=64)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    random.seed(a.seed)
    np.random.seed(a.seed)
    torch.manual_seed(a.seed)
    torch.set_num_threads(max(1, os.cpu_count() or 1))

    if a.azureml or os.environ.get("AZUREML_MLFLOW_URI"):
        mlflow.set_tracking_uri(azureml_tracking_uri())
    else:
        mlflow.set_tracking_uri(f"file://{ROOT / 'mlruns'}")
    mlflow.set_experiment("gov-policy-query-classifier")

    train, val, test = load("train"), load("val"), load("test")
    train_bal = oversample(train, a.seed)
    tok = AutoTokenizer.from_pretrained(BASE)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE, num_labels=len(LABELS), id2label=dict(enumerate(LABELS)), label2id=L2I
    )
    ds_train, ds_val, ds_test = (QDataset(x, tok, a.max_len) for x in (train_bal, val, test))

    with mlflow.start_run(run_name=f"distilbert-mbert-e{a.epochs}") as run:
        mlflow.log_params(
            {
                "base_model": BASE,
                "epochs": a.epochs,
                "lr": a.lr,
                "batch_size": a.batch_size,
                "max_len": a.max_len,
                "seed": a.seed,
                "n_train_raw": len(train),
                "n_train_balanced": len(train_bal),
                "n_val": len(val),
                "n_test": len(test),
                "labels": ",".join(LABELS),
                "git_sha": os.environ.get(
                    "GITHUB_SHA",
                    subprocess.run(
                        ["git", "rev-parse", "--short", "HEAD"],
                        capture_output=True,
                        text=True,
                        cwd=ROOT,
                    ).stdout.strip(),
                ),
            }
        )
        mlflow.set_tags(
            {
                "task": "query-routing",
                "languages": "ar,en",
                "trainer": "github-actions-or-local-cpu",
            }
        )

        opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
        loader = DataLoader(ds_train, batch_size=a.batch_size, shuffle=True)
        steps = len(loader) * a.epochs
        sched = get_linear_schedule_with_warmup(opt, int(0.1 * steps), steps)
        best_f1, best_state = -1.0, None
        for epoch in range(a.epochs):
            model.train()
            total = 0.0
            for b in loader:
                loss = model(**b).loss
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                sched.step()
                opt.zero_grad()
                total += float(loss)
            vm = metrics(val, predict(model, ds_val), "val_")
            mlflow.log_metrics({"train_loss": total / len(loader), **vm}, step=epoch)
            print(
                f"epoch {epoch + 1}: loss={total / len(loader):.4f} val_acc={vm['val_accuracy']:.3f} val_f1={vm['val_macro_f1']:.3f}",
                flush=True,
            )
            if vm["val_macro_f1"] > best_f1:
                best_f1 = vm["val_macro_f1"]
                best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        assert best_state is not None
        model.load_state_dict(best_state)

        probs = predict(model, ds_test)
        report: dict[str, Any] = {"overall": metrics(test, probs, "")}
        for lang in ("en", "ar"):
            idx = [i for i, r in enumerate(test) if r["language"] == lang]
            report[lang] = metrics([test[i] for i in idx], probs[idx], "")
        for src in ("golden", "redteam"):
            idx = [i for i, r in enumerate(test) if r["source"] == src]
            if idx:
                report[f"heldout_{src}"] = metrics([test[i] for i in idx], probs[idx], "")
        for scope, m in report.items():
            mlflow.log_metrics({f"test_{scope}_{k}": v for k, v in m.items()})

        RESULTS.mkdir(parents=True, exist_ok=True)
        cm = confusion_png(test, probs, RESULTS / "confusion_matrix.png")
        errors = [
            {
                "text": r["text"],
                "language": r["language"],
                "true": r["label"],
                "pred": LABELS[int(p.argmax())],
                "confidence": round(float(p.max()), 3),
                "source": r["source"],
            }
            for r, p in zip(test, probs, strict=True)
            if LABELS[int(p.argmax())] != r["label"]
        ]
        summary = {
            "run_id": run.info.run_id,
            "base_model": BASE,
            "labels": LABELS,
            "metrics": report,
            "confusion_matrix": cm,
            "label_counts_test": dict(Counter(r["label"] for r in test)),
            "errors": errors,
        }
        (RESULTS / "metrics.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        mlflow.log_artifact(str(RESULTS / "confusion_matrix.png"))
        mlflow.log_artifact(str(RESULTS / "metrics.json"))

        # Save HF + ONNX artifacts
        out = ART / MODEL_NAME
        out.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(out / "hf")
        tok.save_pretrained(out / "hf")
        onnx_path = export_onnx(model, tok, out, a.max_len)
        tok.backend_tokenizer.save(str(out / "tokenizer.json"))
        (out / "labels.json").write_text(json.dumps({"labels": LABELS, "max_len": a.max_len}))

        _ = onnx_path
        print(json.dumps({k: v for k, v in report.items()}, indent=1))

    # Quantize to int8, evaluate the quantized model, log to the run and register in Azure ML.
    # (MLflow 3 log_model/register_model hit an API the Azure ML backend lacks - see register_model.py)
    from ml.register_model import main as register_main

    sys.argv = [sys.argv[0], "--run-id", run.info.run_id] + (
        [] if mlflow.get_tracking_uri().startswith("azureml") else ["--skip-register"]
    )
    register_main()


if __name__ == "__main__":
    main()
