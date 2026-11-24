"""LLM provider factory. Azure OpenAI (keyless Entra ID by default) or GitHub Models fallback.

Both expose the same OpenAI-compatible async client, so callers don't care which is active.
"""

from typing import Any

from azure.identity import get_bearer_token_provider
from openai import AsyncAzureOpenAI, AsyncOpenAI

from gov_copilot.config import LLMProvider, Settings, get_settings
from gov_copilot.credentials import credential

COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"
AZURE_CHAT_API_VERSION = "2025-04-01-preview"


def _credential() -> Any:
    return credential()


def make_client(settings: Settings | None = None) -> AsyncOpenAI:
    s = settings or get_settings()
    if s.llm_provider is LLMProvider.GITHUB_MODELS:
        if not s.github_token:
            raise RuntimeError("GITHUB_TOKEN is required for the github_models provider")
        return AsyncOpenAI(
            base_url=s.github_models_endpoint, api_key=s.github_token.get_secret_value()
        )
    if s.azure_openai_api_key:
        return AsyncAzureOpenAI(
            azure_endpoint=s.azure_openai_endpoint,
            api_key=s.azure_openai_api_key.get_secret_value(),
            api_version=AZURE_CHAT_API_VERSION,
        )
    return AsyncAzureOpenAI(
        azure_endpoint=s.azure_openai_endpoint,
        azure_ad_token_provider=get_bearer_token_provider(_credential(), COGNITIVE_SCOPE),
        api_version=AZURE_CHAT_API_VERSION,
    )


def chat_model(s: Settings | None = None) -> str:
    s = s or get_settings()
    if s.llm_provider is LLMProvider.GITHUB_MODELS:
        return s.github_models_chat_model
    return s.azure_openai_chat_deployment


def embedding_model(s: Settings | None = None) -> str:
    s = s or get_settings()
    if s.llm_provider is LLMProvider.GITHUB_MODELS:
        return s.github_models_embedding_model
    return s.azure_openai_embedding_deployment


async def embed(texts: list[str], client: AsyncOpenAI | None = None) -> list[list[float]]:
    c = client or make_client()
    out: list[list[float]] = []
    for i in range(0, len(texts), 64):
        resp = await c.embeddings.create(model=embedding_model(), input=texts[i : i + 64])
        out.extend(d.embedding for d in resp.data)
    return out
