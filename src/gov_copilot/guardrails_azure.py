"""Guardrails factory. Azure implementations are added in M4; until then Noop."""

from gov_copilot.config import Settings
from gov_copilot.guardrails import Guardrails, NoopGuardrails


def make_guardrails(s: Settings) -> Guardrails:
    return NoopGuardrails()
