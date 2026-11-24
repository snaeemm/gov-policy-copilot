"""Semantic Kernel plugin exposing the agent's tools.

Tools are SK kernel functions so they are discoverable, traceable and could be offered to an
LLM for autonomous function calling. The orchestrator invokes them in a fixed, auditable order
(plan -> search -> answer -> verify -> respond/escalate) - a deliberate choice for a
government setting where every step must be predictable and logged (see ADR-0004).
"""

import json
from typing import Annotated, Any

from openai import AsyncOpenAI
from semantic_kernel.functions import kernel_function

from gov_copilot.agent.prompts import load_prompt
from gov_copilot.agent.review_queue import ReviewQueue
from gov_copilot.agent.schemas import Verification
from gov_copilot.models import RetrievedChunk
from gov_copilot.retrieval.retriever import HybridRetriever


def format_sources(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"[{i}] {c.title} - page {c.page}{' - ' + c.section if c.section else ''}\n{c.content}"
        for i, c in enumerate(chunks, start=1)
    )


class PolicyTools:
    def __init__(
        self,
        retriever: HybridRetriever,
        client: AsyncOpenAI,
        model: str,
        prompt_version: str,
        review_queue: ReviewQueue,
        completion_kwargs: dict[str, Any],
    ) -> None:
        self.retriever = retriever
        self.client = client
        self.model = model
        self.prompt_version = prompt_version
        self.queue = review_queue
        self.kw = completion_kwargs
        self.last_usage: tuple[int, int] = (0, 0)

    @kernel_function(name="search_policies", description="Hybrid search over UAE policy documents.")
    async def search_policies(
        self,
        queries: Annotated[list[str], "Search queries (EN and/or AR)"],
        top_n: Annotated[int, "Number of passages to return"] = 6,
    ) -> list[RetrievedChunk]:
        seen: dict[str, RetrievedChunk] = {}
        for q in queries:
            for c in await self.retriever.retrieve(q, top_n=top_n):
                best = seen.get(c.id)
                key = c.rerank_score if c.rerank_score is not None else c.score
                if best is None or key > (
                    best.rerank_score if best.rerank_score is not None else best.score
                ):
                    seen[c.id] = c
        ranked = sorted(
            seen.values(),
            key=lambda c: c.rerank_score if c.rerank_score is not None else c.score,
            reverse=True,
        )
        return ranked[:top_n]

    @kernel_function(
        name="verify_citation",
        description="LLM-as-judge: score how well an answer is supported by its cited sources.",
    )
    async def verify_citation(
        self, answer: Annotated[str, "Draft answer"], sources: Annotated[str, "Numbered sources"]
    ) -> Verification:
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": load_prompt("groundedness", self.prompt_version)},
                {"role": "user", "content": f"SOURCES:\n{sources}\n\nANSWER:\n{answer}"},
            ],
            response_format={"type": "json_object"},
            **self.kw,
        )
        if resp.usage:
            self.last_usage = (resp.usage.prompt_tokens, resp.usage.completion_tokens)
        try:
            return Verification(**json.loads(resp.choices[0].message.content or "{}"))
        except (ValueError, TypeError):
            return Verification(groundedness=0.0, citations_valid=False)

    @kernel_function(
        name="escalate_to_human",
        description="Send a low-confidence answer to the human review queue.",
    )
    async def escalate_to_human(
        self,
        request_id: str,
        question_masked: str,
        draft_answer: str,
        reason: str,
        groundedness: float | None,
        citations: list[dict[str, object]],
    ) -> str:
        item = await self.queue.add(
            request_id=request_id,
            question_masked=question_masked,
            draft_answer=draft_answer,
            reason=reason,
            groundedness=groundedness,
            citations=citations,
        )
        return item.id
