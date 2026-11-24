from gov_copilot.agent.orchestrator import cited_numbers, completion_kwargs
from gov_copilot.agent.review_queue import ReviewQueue, ReviewStatus
from gov_copilot.agent.tools import format_sources
from gov_copilot.models import RetrievedChunk


def test_cited_numbers() -> None:
    assert cited_numbers("A [1]. B [2][3]. C [1].") == [1, 2, 3]
    assert cited_numbers("no cites") == []


def test_completion_kwargs_reasoning_vs_chat() -> None:
    assert "reasoning_effort" in completion_kwargs("gpt-5-mini")
    assert "temperature" in completion_kwargs("openai/gpt-4o-mini")


def test_format_sources_numbers_from_one() -> None:
    c = RetrievedChunk(
        id="1",
        doc_id="d",
        title="T",
        language="en",
        page=3,
        chunk_index=0,
        content="x",
        source_url="u",
    )
    assert format_sources([c]).startswith("[1] T - page 3")


async def test_review_queue_lifecycle() -> None:
    q = ReviewQueue(":memory:")
    item = await q.add(
        request_id="r",
        question_masked="q",
        draft_answer="a",
        reason="low",
        groundedness=0.3,
        citations=[],
    )
    assert [i.id for i in await q.list(ReviewStatus.PENDING)] == [item.id]
    done = await q.decide(item.id, approve=True, reviewer="rev")
    assert done is not None and done.status is ReviewStatus.APPROVED and done.final_answer == "a"
    assert await q.list(ReviewStatus.PENDING) == []
    assert await q.decide("missing", approve=False, reviewer="x") is None
