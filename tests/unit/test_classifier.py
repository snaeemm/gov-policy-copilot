from collections.abc import AsyncIterator
from typing import Any

import pytest

from gov_copilot.agent.orchestrator import Copilot
from gov_copilot.agent.schemas import Outcome
from gov_copilot.classifier import Classification, make_classifier
from gov_copilot.config import Settings


class FakeClassifier:
    def __init__(self, label: str, confidence: float) -> None:
        self.c = Classification(
            label=label, confidence=confidence, in_scope=label != "out_of_scope"
        )

    def predict(self, text: str) -> Classification:
        return self.c


class ExplodingClient:
    """Any LLM call fails the test: the classifier must short-circuit before the LLM."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"LLM client used: {name}")


class FakeRetriever:
    async def retrieve(self, *a: Any, **k: Any) -> list[Any]:
        return []


def _copilot(clf: FakeClassifier | None, **settings: Any) -> Copilot:
    s = Settings(llm_provider="azure_openai", azure_openai_endpoint="https://x", **settings)
    cp = Copilot.__new__(Copilot)
    # Build without Semantic Kernel/OpenAI wiring: only the fields stream() needs before planning.
    from gov_copilot.guardrails import NoopGuardrails

    cp.s, cp.client, cp.model, cp.kw = s, ExplodingClient(), "fake", {}  # type: ignore[assignment]
    cp.guard, cp.classifier = NoopGuardrails(), clf
    return cp


async def _final(gen: AsyncIterator[dict[str, Any]]) -> dict[str, Any]:
    last: dict[str, Any] = {}
    async for ev in gen:
        last = ev
    return last


async def test_confident_out_of_scope_skips_llm() -> None:
    cp = _copilot(FakeClassifier("out_of_scope", 0.98))
    ev = await _final(cp.stream("best shawarma in Abu Dhabi?"))
    r = ev["result"]
    assert r["outcome"] == Outcome.OUT_OF_SCOPE.value
    assert r["classifier"] == {"label": "out_of_scope", "confidence": 0.98, "in_scope": False}
    assert r["usage"]["prompt_tokens"] == 0


async def test_low_confidence_out_of_scope_falls_through_to_llm() -> None:
    cp = _copilot(FakeClassifier("out_of_scope", 0.55))
    with pytest.raises(AssertionError, match="LLM client used"):
        await _final(cp.stream("question about data?"))


def test_make_classifier_disabled_by_default() -> None:
    assert make_classifier(Settings()) is None


def test_make_classifier_missing_model_is_none(tmp_path: Any) -> None:
    from gov_copilot.classifier import load_classifier

    load_classifier.cache_clear()
    s = Settings(classifier_enabled=True, classifier_model_path=str(tmp_path / "none"))
    assert make_classifier(s) is None
