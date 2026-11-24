# ADR-0011: Stream tokens, then verify

Status: Accepted, trade-off documented

**Context.** Users expect streaming. Groundedness verification needs the full answer.

**Decision.** Stream status events and answer tokens over SSE; after the answer completes, run `verify_citation` and output guardrails, then send a `final` event. If the outcome is `escalated` or `blocked`, the UI replaces the streamed draft with the escalation/blocked message (`frontend/app.js`, `renderAnswer`).

**Consequences.** + Perceived latency drops (first tokens ~4–6 s). − An unverified draft is visible for a few seconds before replacement. For high-risk deployments, set the UI to buffer until `final` (non-streaming `/api/chat` already does this).
