# ADR-0006: Swappable LLM provider (Azure OpenAI primary, GitHub Models fallback)

Status: Accepted

**Context.** Azure OpenAI access/quota can be blocked on trial subscriptions.

**Decision.** `make_client()` returns an OpenAI-compatible async client for `LLM_PROVIDER=azure_openai` (Entra token or key) or `github_models` (PAT). Model names come from config; `completion_kwargs()` adapts parameters for reasoning models (`max_completion_tokens`, `reasoning_effort`) vs classic chat models. File: `src/gov_copilot/llm/clients.py`.

**Consequences.** Switching provider is one env var. GitHub Models is for development only (rate-limited, not a production service, not UAE-hosted). Note: GitHub Models calls could not be verified from the author's corporate network (DNS/proxy); verified Azure path only.
