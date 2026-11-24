"""Typed application settings. Env vars locally; Key Vault references in Azure Container Apps."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(StrEnum):
    AZURE_OPENAI = "azure_openai"
    GITHUB_MODELS = "github_models"


class RerankerKind(StrEnum):
    NONE = "none"
    CROSS_ENCODER = "cross_encoder"
    AZURE_SEMANTIC = "azure_semantic"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    prompt_version: str = "v1"

    llm_provider: LLMProvider = LLMProvider.AZURE_OPENAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: SecretStr | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str = "gpt-4o-mini"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    github_models_endpoint: str = "https://models.github.ai/inference"
    github_token: SecretStr | None = None
    github_models_chat_model: str = "openai/gpt-4o-mini"
    github_models_embedding_model: str = "openai/text-embedding-3-small"
    embedding_dimensions: int = 1536

    azure_search_endpoint: str = ""
    azure_search_api_key: SecretStr | None = None
    azure_search_index: str = "gov-policies"
    docintel_endpoint: str = ""
    content_safety_endpoint: str = ""
    language_endpoint: str = ""

    reranker: RerankerKind = RerankerKind.CROSS_ENCODER
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    retrieval_top_k: int = Field(default=20, ge=1, le=50)
    rerank_top_n: int = Field(default=5, ge=1, le=20)
    groundedness_threshold: float = Field(default=0.7, ge=0, le=1)

    auth_enabled: bool = False
    entra_tenant_id: str = ""
    entra_api_audience: str = "api://gov-policy-copilot"
    rate_limit: str = "20/minute"

    applicationinsights_connection_string: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
