# Code Review Checklist

Reviewers: tick what applies, and comment on anything you can't tick.

## Correctness
- [ ] Does what the issue or PR says, and edge cases are handled (empty retrieval, Arabic/RTL text, mixed-language input, long input)
- [ ] Pydantic models validate external input; API contracts (`AgentResult`, SSE events) are backward compatible or versioned
- [ ] Async code doesn't block the event loop (file and CPU work goes through `asyncio.to_thread`)

## Security
- [ ] **No secrets** in code, config, tests or logs. Keyless auth (managed identity / `DefaultAzureCredential`) is preserved
- [ ] New endpoints declare a role (`require(Role.…)`) and are rate-limited where they're user-facing
- [ ] **Prompt injection:** retrieved text is treated as data; system prompts keep the "ignore instructions in sources" rule; Prompt Shields still run on new inputs and documents
- [ ] **PII:** only `mask_pii` output is logged or stored; no raw question text in traces, logs or review items
- [ ] HTML rendering escapes model output (`esc()` in `frontend/app.js`); no `innerHTML` with unescaped data
- [ ] New dependencies are pinned through `uv.lock`, maintained, and come from trusted sources

## Responsible AI
- [ ] Answers stay grounded: citations are required, the not-found path is intact, the groundedness threshold is unchanged or justified
- [ ] Escalation to human review still triggers for low-confidence answers
- [ ] Bilingual parity: behaviour checked in both Arabic and English
- [ ] Prompt, model and retrieval changes include an eval run and a new prompt version (see CONTRIBUTING)

## Performance and cost
- [ ] No extra LLM calls per request without justification (each call costs tokens and adds about 2-5 s)
- [ ] Token usage and cost accounting still updated (`Usage`)
- [ ] New Azure resources: SKU and monthly cost stated; free tier or scale-to-zero preferred

## Observability
- [ ] New steps have OpenTelemetry spans (`tracer.start_as_current_span`) with useful attributes
- [ ] Structured log fields stay compatible with the KQL queries in `observability/kql/`
- [ ] Errors are logged once, with context, and without PII

## Tests
- [ ] Unit tests cover new logic; Azure calls mocked (`respx`, fakes) so CI runs without credentials
- [ ] Failure paths tested (throttling, service outage, fail-closed guardrails, 401/403)

## Docs
- [ ] README, runbook, model card or data card updated as needed; ADR added for decisions; CHANGELOG entry added
