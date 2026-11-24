# Coding Standards

## Python
- Python 3.12, managed with **uv**. Add dependencies with `uv add`, never `pip install` into the venv by hand.
- **Typing:** `mypy --strict` must pass for `src/`. Annotate every function. Prefer `X | None` over `Optional`. Use `Literal` or `StrEnum` for closed sets (`Outcome`, `Role`, `RerankerKind`). Use `Any` only at SDK boundaries.
- **Formatting and lint:** `ruff format` (line length 100). `ruff check` with rules E, F, I, B, UP, N, S, ASYNC, RUF and SIM. Arabic string literals are allowed (RUF001-003 disabled).
- **Data contracts:** use Pydantic v2 models for anything that crosses a boundary (API, agent results, eval files). No untyped dicts in public functions.

## Async
- I/O is async end to end (FastAPI, `AsyncOpenAI`, async Azure SDK clients, `httpx.AsyncClient`).
- Never block the loop: wrap file I/O, SQLite and model inference (cross-encoder) in `asyncio.to_thread`.
- Bound concurrency against rate-limited services (semaphores); retry 429 and 5xx with exponential backoff that honours `Retry-After`.
- Close clients with `async with`, or reuse long-lived clients created at startup.

## Error handling
- Validate at the edges (Pydantic, FastAPI). Inside the agent, degrade to a safe outcome (`not_found`, `escalated`, `blocked`) rather than raising to the user.
- Guardrails **fail closed** in Azure (`GUARDRAILS_FAIL_CLOSED=true`). A safety-service outage blocks requests; it never skips the check.
- Only catch broad exceptions at integration boundaries, and always log the exception type.

## Logging and PII
- Use the `logging` module under the `gov_copilot.*` namespace. Structured fields go in `extra={...}`; App Insights turns them into `customDimensions`.
- **Only masked text is logged** (`await guard.mask_pii(text, lang)`). Never log raw questions, tokens, headers or connection strings.
- Every request logs: `request_id`, `outcome`, `prompt_version`, `model`, latency, token counts and `cost_usd`.

## Configuration
- All configuration lives in `gov_copilot.config.Settings` (pydantic-settings), read from env vars, `.env.azure` and `.env` locally, and Bicep-defined env vars or Key Vault references in Azure.
- Secrets are typed `SecretStr`. Add new settings to `.env.example` with a comment.
- Behaviour switches are config flags (`LLM_PROVIDER`, `RERANKER`, `AUTH_ENABLED`, `PROMPT_VERSION`), not code branches on environment names.

## Prompts
- Prompts live in `prompts/vN/*.md` and are loaded by name and version. Released versions are immutable.

## Bicep
- `infra/main.bicep` (subscription scope) composes the modules in `infra/modules/`. Parameters go in `*.bicepparam`.
- Names follow `<abbr>-govcopilot-<env>[-<uniqueString>]` (e.g. `aoai-`, `srch-`, `kv-gc-`, `ca-`). Tag everything with `project`, `env` and `costCenter`.
- Keyless by default: set `disableLocalAuth: true` and grant least-privilege role assignments scoped to the single resource.
- Cost-bearing options (private endpoints, higher SKUs) sit behind boolean params that default to off.
- Run `az bicep build` and `what-if` before every deploy.

## Naming
- Modules and functions use `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`.
- Name things after the domain: `search_policies`, `verify_citation`, `escalate_to_human`.

## Tests
- `pytest` with `asyncio_mode=auto`. Unit tests must run **offline**: mock HTTP with `respx` and inject fakes (`FakeCopilot`, `ReviewQueue(":memory:")`).
- Test files are `tests/unit/test_<module>.py`, with one behaviour per test and a descriptive name.
- Quality of LLM behaviour is measured by the eval suite (`eval/`), not by asserting exact model output in unit tests.
