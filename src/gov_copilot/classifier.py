"""Fine-tuned bilingual query classifier (ONNX Runtime, no torch at serving time).

Routes a question to one of: charter | international_policy | ethics | data_protection |
out_of_scope. Used as a cheap pre-filter before the LLM: confidently out-of-scope questions are
answered without any LLM call. Trained in ml/train_classifier.py, tracked/registered in Azure ML,
published to Hugging Face Hub for download at container start.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np
from pydantic import BaseModel

from gov_copilot.config import Settings

log = logging.getLogger("gov_copilot.classifier")
OUT_OF_SCOPE = "out_of_scope"


class Classification(BaseModel):
    label: str
    confidence: float
    in_scope: bool


class Classifier(Protocol):
    def predict(self, text: str) -> Classification: ...


class OnnxQueryClassifier:
    def __init__(self, model_dir: Path) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        meta = json.loads((model_dir / "labels.json").read_text())
        self.labels: list[str] = meta["labels"]
        self.max_len: int = int(meta.get("max_len", 64))
        self.tok = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tok.enable_truncation(self.max_len)
        self.tok.enable_padding(length=self.max_len)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        self.sess = ort.InferenceSession(
            str(model_dir / "model.onnx"), opts, providers=["CPUExecutionProvider"]
        )

    def predict(self, text: str) -> Classification:
        enc = self.tok.encode(text)
        feeds = {
            "input_ids": np.array([enc.ids], dtype=np.int64),
            "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
        }
        logits = self.sess.run(["logits"], feeds)[0][0]
        exp = np.exp(logits - logits.max())
        probs = exp / exp.sum()
        i = int(probs.argmax())
        label = self.labels[i]
        return Classification(
            label=label, confidence=round(float(probs[i]), 4), in_scope=label != OUT_OF_SCOPE
        )


def _resolve_model_dir(model_path: str, hf_repo: str) -> Path | None:
    path = Path(model_path)
    if (path / "model.onnx").exists():
        return path
    if hf_repo:
        from huggingface_hub import snapshot_download

        local = snapshot_download(
            repo_id=hf_repo,
            allow_patterns=["model.onnx", "tokenizer.json", "labels.json"],
            local_dir=str(path),
        )
        return Path(local)
    return None


@lru_cache
def load_classifier(model_path: str, hf_repo: str) -> OnnxQueryClassifier | None:
    try:
        d = _resolve_model_dir(model_path, hf_repo)
        if d is None:
            log.warning("classifier enabled but no model at %s and no HF repo", model_path)
            return None
        return OnnxQueryClassifier(d)
    except Exception as e:
        log.warning("classifier unavailable: %s", type(e).__name__)
        return None


def make_classifier(s: Settings) -> Classifier | None:
    if not s.classifier_enabled:
        return None
    return load_classifier(s.classifier_model_path, s.classifier_hf_repo)
