"""Azure AI Content Safety (harm categories + Prompt Shields) and Azure AI Language (PII).

- Input:  Prompt Shields (jailbreak / prompt-injection) + harm-category analysis.
- Output: harm-category analysis of the generated answer, and Prompt Shields over the retrieved
          documents (indirect prompt injection hidden inside sources).
- PII:    regex (UAE identifiers) + Azure AI Language PII redaction, applied before logging.
Auth is keyless (Entra ID token). Fail-closed is configurable: in production a guardrail outage
blocks requests rather than silently letting them through.
"""

import asyncio
import logging
from typing import Any

import httpx

from gov_copilot.config import Settings
from gov_copilot.credentials import async_credential
from gov_copilot.guardrails import Guardrails, GuardResult, NoopGuardrails
from gov_copilot.pii import regex_mask

log = logging.getLogger("gov_copilot.guardrails")
SCOPE = "https://cognitiveservices.azure.com/.default"
CS_API = "2024-09-01"
LANG_API = "2024-11-01"
PII_LANGS = {"en", "ar"}
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 4
BACKOFF_S = 0.5


class AzureGuardrails:
    def __init__(self, s: Settings) -> None:
        self.s = s
        self.cred = async_credential()
        self.http = httpx.AsyncClient(timeout=15)

    async def _post(self, endpoint: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST with retry + exponential backoff on throttling (F0 tiers rate-limit)."""
        token = (await self.cred.get_token(SCOPE)).token
        for attempt in range(MAX_RETRIES + 1):
            r = await self.http.post(
                f"{endpoint.rstrip('/')}{path}",
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code in RETRY_STATUS and attempt < MAX_RETRIES:
                retry_after = float(r.headers.get("retry-after", 0) or 0)
                await asyncio.sleep(max(retry_after, BACKOFF_S * 2**attempt))
                continue
            r.raise_for_status()
            data: dict[str, Any] = r.json()
            return data
        raise RuntimeError("unreachable")

    async def _harm(self, text: str) -> GuardResult:
        data = await self._post(
            self.s.content_safety_endpoint,
            f"/contentsafety/text:analyze?api-version={CS_API}",
            {"text": text[:10000], "outputType": "FourSeverityLevels"},
        )
        cats = {c["category"]: int(c["severity"]) for c in data.get("categoriesAnalysis", [])}
        flagged = [k for k, v in cats.items() if v >= self.s.content_safety_severity_threshold]
        return GuardResult(
            allowed=not flagged,
            reason=f"harmful content: {', '.join(flagged)}" if flagged else None,
            categories=cats,
        )

    async def _shield(self, prompt: str, documents: list[str]) -> GuardResult:
        data = await self._post(
            self.s.content_safety_endpoint,
            f"/contentsafety/text:shieldPrompt?api-version={CS_API}",
            {"userPrompt": prompt[:10000], "documents": [d[:10000] for d in documents[:5]]},
        )
        if data.get("userPromptAnalysis", {}).get("attackDetected"):
            return GuardResult(allowed=False, reason="prompt attack (jailbreak) detected")
        if any(d.get("attackDetected") for d in data.get("documentsAnalysis", [])):
            return GuardResult(allowed=False, reason="indirect prompt injection in sources")
        return GuardResult()

    async def _safe(self, coro: Any, what: str) -> GuardResult:
        try:
            result: GuardResult = await coro
            return result
        except Exception as e:
            log.warning("guardrail %s unavailable: %s", what, type(e).__name__)
            if self.s.guardrails_fail_closed:
                return GuardResult(allowed=False, reason=f"{what} unavailable (fail-closed)")
            return GuardResult()

    async def check_input(self, text: str) -> GuardResult:
        shield = await self._safe(self._shield(text, []), "prompt_shields")
        if not shield.allowed:
            return shield
        return await self._safe(self._harm(text), "content_safety")

    async def check_output(self, text: str, sources: list[str]) -> GuardResult:
        harm = await self._safe(self._harm(text), "content_safety")
        if not harm.allowed:
            return harm
        return await self._safe(self._shield("", sources), "prompt_shields_documents")

    async def mask_pii(self, text: str, language: str) -> str:
        text = regex_mask(text)
        if language not in PII_LANGS or not self.s.language_endpoint:
            return text
        try:
            data = await self._post(
                self.s.language_endpoint,
                f"/language/:analyze-text?api-version={LANG_API}",
                {
                    "kind": "PiiEntityRecognition",
                    "analysisInput": {
                        "documents": [{"id": "1", "language": language, "text": text}]
                    },
                    "parameters": {"redactionPolicy": {"policyKind": "entityMask"}},
                },
            )
            docs = data.get("results", {}).get("documents", [])
            return str(docs[0]["redactedText"]) if docs else text
        except Exception as e:
            log.warning("PII service unavailable, regex-only masking: %s", type(e).__name__)
            return text


def make_guardrails(s: Settings) -> Guardrails:
    if s.content_safety_endpoint:
        return AzureGuardrails(s)
    return NoopGuardrails()
