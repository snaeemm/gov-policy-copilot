# Observability

Telemetry: `src/gov_copilot/observability.py` calls `configure_azure_monitor()` when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set (in Azure it comes from Key Vault via the Container App's managed identity). FastAPI requests, outbound HTTP dependencies, the custom spans `copilot.request`, `step.plan`, `step.answer`, `tool.*`, and the `gov_copilot` loggers are exported.

Per request, the agent logs `copilot_request` (PII-masked question) with: `request_id, user (Entra oid), outcome, model, prompt_version, latency_ms, prompt_tokens, completion_tokens, cost_usd, groundedness`. Span attributes: `copilot.request_id`, `copilot.prompt_version`, `gen_ai.request.model`, `copilot.groundedness`, `copilot.outcome`, `copilot.cost_usd`, `copilot.blocked_reason`.

## Queries (`kql/`)
| File | Question it answers |
|---|---|
| `_copilot_requests.kql` | Base projection of copilot request logs (reuse as a function) |
| `outcomes_over_time.kql` | How many answered / escalated / blocked / not found per hour? |
| `latency_p50_p95.kql` | Are we within latency SLO, per prompt version? |
| `http_requests.kql` | Volume, failure rate, p95 per route |
| `failures.kql` | Recent failed requests and exceptions |
| `escalation_rate.kql` | Human-review load and mean groundedness per day |
| `blocked_by_reason.kql` | Jailbreak / injection / harm blocks |
| `cost_per_day.kql` | LLM spend and tokens per day and model |
| `openai_dependencies.kql` | Health and latency of Azure OpenAI, AI Search, Content Safety calls |

Run them in Application Insights → Logs. Table names are the App Insights schema (`traces`, `requests`, `dependencies`); in the Log Analytics workspace use `AppTraces`, `AppRequests`, `AppDependencies` and `Properties` instead of `customDimensions`.

## Workbook
`workbook.json` – import via Application Insights → Workbooks → New → Advanced editor → paste → Apply → Save.

Ingestion is capped at 0.15 GB/day on the workspace to stay within the free allowance.
