"""LLM provider factory: Azure OpenAI, Microsoft Foundry (any catalog model) or GitHub Models.

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


def _azure(endpoint: str, retries: int = 6) -> AsyncAzureOpenAI:
    return AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=get_bearer_token_provider(_credential(), COGNITIVE_SCOPE),
        api_version=AZURE_CHAT_API_VERSION,
        max_retries=retries,  # Foundry pay-per-token deployments return 429s under bursts
    )


def make_client(settings: Settings | None = None) -> AsyncOpenAI:
    s = settings or get_settings()
    if s.llm_provider is LLMProvider.FOUNDRY:
        if not s.foundry_endpoint:
            raise RuntimeError("FOUNDRY_ENDPOINT is required for the foundry provider")
        # Foundry serves OpenAI, Phi, Llama, ... behind the same chat-completions API (keyless).
        return _azure(s.foundry_endpoint, s.llm_max_retries)
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
    return _azure(s.azure_openai_endpoint, s.llm_max_retries)


def embedding_client(settings: Settings | None = None) -> AsyncOpenAI:
    """Embeddings always come from the provider that built the index (never Foundry chat)."""
    s = settings or get_settings()
    if s.llm_provider is LLMProvider.FOUNDRY:
        return make_client(s.model_copy(update={"llm_provider": LLMProvider.AZURE_OPENAI}))
    return make_client(s)


def chat_model(s: Settings | None = None) -> str:
    s = s or get_settings()
    if s.llm_provider is LLMProvider.GITHUB_MODELS:
        return s.github_models_chat_model
    if s.llm_provider is LLMProvider.FOUNDRY:
        return s.foundry_chat_deployment
    return s.azure_openai_chat_deployment


def embedding_model(s: Settings | None = None) -> str:
    s = s or get_settings()
    if s.llm_provider is LLMProvider.GITHUB_MODELS:
        return s.github_models_embedding_model
    return s.azure_openai_embedding_deployment


async def embed(texts: list[str], client: AsyncOpenAI | None = None) -> list[list[float]]:
    c = client or embedding_client()
    out: list[list[float]] = []
    for i in range(0, len(texts), 64):
        resp = await c.embeddings.create(model=embedding_model(), input=texts[i : i + 64])
        out.extend(d.embedding for d in resp.data)
    return out
