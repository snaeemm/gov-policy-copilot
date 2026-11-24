"""Versioned prompts loaded from /prompts/<version>/. The version is logged with every request."""

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


@lru_cache
def load_prompt(name: str, version: str) -> str:
    return (PROMPTS_DIR / version / f"{name}.md").read_text(encoding="utf-8")
