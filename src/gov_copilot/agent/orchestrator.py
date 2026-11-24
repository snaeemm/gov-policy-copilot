"""Gov Policy Copilot agent: plan -> retrieve -> answer -> self-check -> respond or escalate."""

import json
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI
from opentelemetry import trace
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

from gov_copilot.agent.prompts import load_prompt
from gov_copilot.agent.review_queue import ReviewQueue
from gov_copilot.agent.schemas import (
    BLOCKED,
    ESCALATED,
    NOT_FOUND,
    OUT_OF_SCOPE,
    AgentResult,
    Citation,
    Outcome,
    Plan,
    Usage,
    Verification,
)
from gov_copilot.agent.tools import PolicyTools, format_sources
from gov_copilot.config import Settings
from gov_copilot.guardrails import Guardrails, NoopGuardrails
from gov_copilot.ingestion.chunker import count_tokens
from gov_copilot.ingestion.text import detect_language
from gov_copilot.llm.clients import chat_model
from gov_copilot.models import Language, RetrievedChunk
from gov_copilot.retrieval.retriever import HybridRetriever

log = logging.getLogger("gov_copilot.agent")
tracer = trace.get_tracer("gov_copilot.agent")
_CITE = re.compile(r"\[(\d+)\]")
PLUGIN = "policy"

Event = dict[str, Any]


def completion_kwargs(model: str) -> dict[str, Any]:
    """Reasoning models (gpt-5*, o*) take different parameters than classic chat models."""
    name = model.split("/")[-1]
    if name.startswith(("gpt-5", "o1", "o3", "o4")):
        return {"max_completion_tokens": 2500, "reasoning_effort": "minimal"}
    return {"max_tokens": 700, "temperature": 0}


def cited_numbers(answer: str) -> list[int]:
    return sorted({int(n) for n in _CITE.findall(answer)})


class Copilot:
    def __init__(
        self,
        settings: Settings,
        client: AsyncOpenAI,
        retriever: HybridRetriever,
        review_queue: ReviewQueue,
        guardrails: Guardrails | None = None,
    ) -> None:
        self.s = settings
        self.client = client
        self.model = chat_model(settings)
        self.kw = completion_kwargs(self.model)
        self.guard: Guardrails = guardrails or NoopGuardrails()
        self.tools = PolicyTools(
            retriever, client, self.model, settings.prompt_version, review_queue, self.kw
        )
        self.kernel = Kernel()
        self.kernel.add_service(OpenAIChatCompletion(ai_model_id=self.model, async_client=client))
        self.kernel.add_plugin(self.tools, plugin_name=PLUGIN)

    async def _tool(self, name: str, **kwargs: Any) -> Any:
        with tracer.start_as_current_span(f"tool.{name}"):
            result = await self.kernel.invoke(plugin_name=PLUGIN, function_name=name, **kwargs)
            return result.value if result else None

    def _cost(self, u: Usage) -> float:
        s = self.s
        return round(
            u.prompt_tokens / 1e6 * s.price_input_per_m
            + u.completion_tokens / 1e6 * s.price_output_per_m
            + u.embedding_tokens / 1e6 * s.price_embedding_per_m,
            6,
        )

    async def _plan(self, question: str, usage: Usage) -> Plan:
        fallback_lang: Language = "ar" if detect_language(question) == "ar" else "en"
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": load_prompt("planner", self.s.prompt_version)},
                {"role": "user", "content": question},
            ],
            response_format={"type": "json_object"},
            **self.kw,
        )
        if resp.usage:
            usage.prompt_tokens += resp.usage.prompt_tokens
            usage.completion_tokens += resp.usage.completion_tokens
        try:
            plan = Plan(**json.loads(resp.choices[0].message.content or "{}"))
        except (ValueError, TypeError):
            plan = Plan(language=fallback_lang)
        if not plan.search_queries:
            plan.search_queries = [question]
        return plan

    async def stream(self, question: str, user: str = "anonymous") -> AsyncIterator[Event]:
        """Yield status/token events, then a final event carrying the AgentResult."""
        rid = uuid.uuid4().hex
        t0 = time.perf_counter()
        usage = Usage()
        lang: Language = "ar" if detect_language(question) == "ar" else "en"
        masked_q = await self.guard.mask_pii(question, lang)

        def final(answer: str, outcome: Outcome, **extra: Any) -> Event:
            usage.cost_usd = self._cost(usage)
            result = AgentResult(
                request_id=rid,
                question=masked_q,
                answer=answer,
                language=lang,
                outcome=outcome,
                prompt_version=self.s.prompt_version,
                model=self.model,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                usage=usage,
                **extra,
            )
            # Only PII-masked text is ever logged.
            log.info(
                "copilot_request",
                extra={
                    "request_id": rid,
                    "user": user,
                    "question_masked": masked_q,
                    "outcome": outcome.value,
                    "prompt_version": self.s.prompt_version,
                    "model": self.model,
                    "latency_ms": result.latency_ms,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "cost_usd": usage.cost_usd,
                    "groundedness": result.verification.groundedness
                    if result.verification
                    else None,
                },
            )
            span = trace.get_current_span()
            span.set_attribute("copilot.outcome", outcome.value)
            span.set_attribute("copilot.cost_usd", usage.cost_usd)
            return {"type": "final", "result": result.model_dump()}

        with tracer.start_as_current_span("copilot.request") as span:
            span.set_attribute("copilot.request_id", rid)
            span.set_attribute("copilot.prompt_version", self.s.prompt_version)
            span.set_attribute("gen_ai.request.model", self.model)

            guard_in = await self.guard.check_input(question)
            if not guard_in.allowed:
                span.set_attribute("copilot.blocked_reason", guard_in.reason or "")
                yield final(BLOCKED[lang], Outcome.BLOCKED)
                return

            yield {"type": "status", "step": "planning"}
            with tracer.start_as_current_span("step.plan"):
                plan = await self._plan(question, usage)
            lang = plan.language
            if not plan.in_scope:
                yield final(OUT_OF_SCOPE[lang], Outcome.OUT_OF_SCOPE)
                return

            yield {"type": "status", "step": "retrieving", "queries": plan.search_queries}
            chunks: list[RetrievedChunk] = await self._tool(
                "search_policies", queries=plan.search_queries, top_n=self.s.rerank_top_n
            )
            usage.embedding_tokens += sum(count_tokens(q) for q in plan.search_queries)
            if not chunks:
                yield final(NOT_FOUND[lang], Outcome.NOT_FOUND)
                return
            sources = format_sources(chunks)

            yield {"type": "status", "step": "answering", "sources": len(chunks)}
            system = load_prompt("answer", self.s.prompt_version).format(
                language="Arabic" if lang == "ar" else "English",
                not_found=NOT_FOUND[lang],
                sources=sources,
            )
            answer = ""
            with tracer.start_as_current_span("step.answer"):
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": question},
                    ],
                    stream=True,
                    stream_options={"include_usage": True},
                    **self.kw,
                )
                async for ev in stream:
                    if ev.usage:
                        usage.prompt_tokens += ev.usage.prompt_tokens
                        usage.completion_tokens += ev.usage.completion_tokens
                    if ev.choices and ev.choices[0].delta.content:
                        piece = ev.choices[0].delta.content
                        answer += piece
                        yield {"type": "token", "text": piece}
            answer = answer.strip()

            if answer.startswith(NOT_FOUND[lang][:30]) or not answer:
                yield final(NOT_FOUND[lang], Outcome.NOT_FOUND)
                return

            nums = cited_numbers(answer)
            valid_nums = [n for n in nums if 1 <= n <= len(chunks)]
            citations = [
                Citation(
                    n=n,
                    doc_id=chunks[n - 1].doc_id,
                    title=chunks[n - 1].title,
                    page=chunks[n - 1].page,
                    section=chunks[n - 1].section,
                    source_url=chunks[n - 1].source_url,
                    snippet=chunks[n - 1].content[:300],
                )
                for n in valid_nums
            ]

            yield {"type": "status", "step": "verifying"}
            verification: Verification = await self._tool(
                "verify_citation", answer=answer, sources=sources
            )
            pt, ct = self.tools.last_usage
            usage.prompt_tokens += pt
            usage.completion_tokens += ct
            if not nums or len(valid_nums) != len(nums):
                verification.citations_valid = False
            span.set_attribute("copilot.groundedness", verification.groundedness)

            guard_out = await self.guard.check_output(answer, [c.content for c in chunks])
            reasons = []
            if verification.groundedness < self.s.groundedness_threshold:
                reasons.append(f"groundedness {verification.groundedness:.2f} below threshold")
            if not verification.citations_valid:
                reasons.append("invalid or missing citations")
            if not guard_out.allowed:
                reasons.append(f"output guardrail: {guard_out.reason}")

            if reasons:
                review_id: str = await self._tool(
                    "escalate_to_human",
                    request_id=rid,
                    question_masked=masked_q,
                    draft_answer=answer,
                    reason="; ".join(reasons),
                    groundedness=verification.groundedness,
                    citations=[c.model_dump() for c in citations],
                )
                yield final(
                    ESCALATED[lang],
                    Outcome.ESCALATED,
                    contexts=[c.content for c in chunks],
                    verification=verification,
                    review_id=review_id,
                )
                return

            yield final(
                answer,
                Outcome.ANSWERED,
                citations=citations,
                verification=verification,
                contexts=[c.content for c in chunks],
            )

    async def ask(self, question: str, user: str = "anonymous") -> AgentResult:
        result: AgentResult | None = None
        async for ev in self.stream(question, user):
            if ev["type"] == "final":
                result = AgentResult(**ev["result"])
        assert result is not None
        return result
