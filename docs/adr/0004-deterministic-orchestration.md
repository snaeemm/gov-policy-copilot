# ADR-0004: Deterministic Semantic Kernel workflow instead of autonomous tool calling

Status: Accepted

**Context.** Government use requires predictable, auditable behaviour: every answer must be grounded, checked, and logged; failure modes must be explicit.

**Decision.** Tools are Semantic Kernel kernel functions (`search_policies`, `verify_citation`, `escalate_to_human`, `agent/tools.py`) invoked via `kernel.invoke` in a fixed order: **plan → retrieve → answer → verify → respond or escalate** (`agent/orchestrator.py`). The LLM decides *queries and wording*, not *control flow*. Escalation triggers: groundedness < 0.7, missing/out-of-range citations, or output guardrail hit.

**Consequences.** + Every request produces the same trace shape (OpenTelemetry spans per step). + Easy to test and reason about. − Less flexible than an autonomous agent for open-ended tasks; ~3 LLM calls/query (p50 ≈ 10 s).

**Alternatives.** SK automatic function calling (`FunctionChoiceBehavior.Auto`) — rejected for now; the plugin is already compatible should autonomy be wanted later.
