"""Guardrails interface (implemented with Azure AI Content Safety + Azure AI Language in M4)."""

from typing import Protocol

from pydantic import BaseModel


class GuardResult(BaseModel):
    allowed: bool = True
    reason: str | None = None
    categories: dict[str, int] = {}


class Guardrails(Protocol):
    async def check_input(self, text: str) -> GuardResult: ...
    async def check_output(self, text: str, sources: list[str]) -> GuardResult: ...
    async def mask_pii(self, text: str, language: str) -> str: ...


class NoopGuardrails:
    async def check_input(self, text: str) -> GuardResult:
        return GuardResult()

    async def check_output(self, text: str, sources: list[str]) -> GuardResult:
        return GuardResult()

    async def mask_pii(self, text: str, language: str) -> str:
        return text
