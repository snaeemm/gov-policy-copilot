"""Typed application settings. Env vars locally; Key Vault references in Azure Container Apps."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(StrEnum):
    AZURE_OPENAI = "azure_openai"
    GITHUB_MODELS = "github_models"
    FOUNDRY = "foundry"  # Microsoft Foundry model catalog (GPT, Phi, Llama) - chat only


class RerankerKind(StrEnum):
    NONE = "none"
    CROSS_ENCODER = "cross_encoder"
    AZURE_SEMANTIC = "azure_semantic"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env.azure", ".env"), extra="ignore")

    app_env: str = "local"
    prompt_version: str = "v2"

    llm_provider: LLMProvider = LLMProvider.AZURE_OPENAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: SecretStr | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str = "gpt-5-mini"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    github_models_endpoint: str = "https://models.github.ai/inference"
    github_token: SecretStr | None = None
    github_models_chat_model: str = "openai/gpt-4o-mini"
    github_models_embedding_model: str = "openai/text-embedding-3-small"
    embedding_dimensions: int = 1536
    # Microsoft Foundry (AI Services resource + project). Embeddings stay on Azure OpenAI so the
    # search index never needs re-embedding when the chat model changes.
    foundry_endpoint: str = ""  # https://<aif>.openai.azure.com/ (OpenAI-compatible inference)
    foundry_project_endpoint: str = ""  # https://<aif>.services.ai.azure.com/api/projects/<proj>
    foundry_chat_deployment: str = "gpt-5-mini"
    llm_max_retries: int = Field(default=6, ge=0, le=30)

    azure_search_endpoint: str = ""
    azure_search_api_key: SecretStr | None = None
    azure_search_index: str = "gov-policies"
    docintel_endpoint: str = ""
    content_safety_endpoint: str = ""
    language_endpoint: str = ""

    reranker: RerankerKind = RerankerKind.NONE  # cross_encoder needs the `rerank` extra
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    retrieval_top_k: int = Field(default=20, ge=1, le=50)
    rerank_top_n: int = Field(default=8, ge=1, le=20)
    groundedness_threshold: float = Field(default=0.7, ge=0, le=1)
    content_safety_severity_threshold: int = Field(default=2, ge=0, le=6)
    guardrails_fail_closed: bool = True

    # USD per 1M tokens (list prices; used for cost-per-query telemetry)
    price_input_per_m: float = 0.25
    price_output_per_m: float = 2.00
    price_embedding_per_m: float = 0.02
    review_db_path: str = "data/reviews.db"

    # Fine-tuned query classifier (M8) - cheap pre-filter before the LLM
    classifier_enabled: bool = False
    classifier_model_path: str = "ml/artifacts/gov-policy-query-classifier"
    classifier_hf_repo: str = ""
    classifier_oos_threshold: float = Field(default=0.9, ge=0, le=1)

    auth_enabled: bool = False
    entra_tenant_id: str = ""
    entra_api_audience: str = "api://gov-policy-copilot"
    entra_spa_client_id: str = ""
    rate_limit: str = "20/minute"

    applicationinsights_connection_string: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
