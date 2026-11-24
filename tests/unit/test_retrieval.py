import io

from pypdf import PdfWriter

from gov_copilot.config import RerankerKind, Settings
from gov_copilot.ingestion.docintel import split_pdf
from gov_copilot.models import Chunk, RetrievedChunk
from gov_copilot.retrieval.index import build_index, to_search_doc
from gov_copilot.retrieval.rerankers import (
    CrossEncoderReranker,
    NoopReranker,
    ScoreReranker,
    make_reranker,
)


def _chunk(lang: str = "ar", content: str = "الذكــاء الاصطناعي") -> Chunk:
    return Chunk(
        id="x",
        doc_id="d",
        title="t",
        language=lang,
        page=1,
        chunk_index=0,  # type: ignore[arg-type]
        content=content,
        source_url="u",
    )


def test_index_has_language_analyzers_and_vector() -> None:
    idx = build_index("i", 1536)
    by_name = {f.name: f for f in idx.fields}
    assert by_name["content_ar"].analyzer_name == "ar.microsoft"
    assert by_name["content_en"].analyzer_name == "en.microsoft"
    assert by_name["content_vector"].vector_search_dimensions == 1536


def test_to_search_doc_routes_and_normalizes_arabic() -> None:
    d = to_search_doc(_chunk(), [0.1])
    assert d["content_ar"] == "الذكاء الاصطناعي"
    assert d["content_en"] == ""
    assert d["content"] == "الذكــاء الاصطناعي"  # original preserved for display


def test_make_reranker() -> None:
    assert isinstance(make_reranker(Settings(reranker=RerankerKind.NONE)), NoopReranker)
    assert isinstance(make_reranker(Settings(reranker=RerankerKind.AZURE_SEMANTIC)), ScoreReranker)
    assert isinstance(
        make_reranker(Settings(reranker=RerankerKind.CROSS_ENCODER)), CrossEncoderReranker
    )


async def test_score_reranker_orders_by_rerank_score() -> None:
    a = RetrievedChunk(**_chunk().model_dump(), rerank_score=0.1)
    b = RetrievedChunk(**_chunk().model_dump(), rerank_score=0.9)
    out = await ScoreReranker().rerank("q", [a, b], top_n=1)
    assert out == [b]


def test_split_pdf_respects_two_page_limit() -> None:
    w = PdfWriter()
    for _ in range(5):
        w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    assert len(split_pdf(buf.getvalue())) == 3
