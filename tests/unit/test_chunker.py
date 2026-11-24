from gov_copilot.ingestion.chunker import chunk_markdown, count_tokens
from gov_copilot.models import SourceDocument

DOC = SourceDocument(
    doc_id="t", file="t.pdf", language="en", title="Test", publisher="p", year=2024, source_url="u"
)

MD = """# Part One

First paragraph about privacy.

Second paragraph about consent.
<!-- PageBreak -->
# Part Two

## Article 5

Third paragraph about transparency.
"""


def test_tracks_pages_and_sections() -> None:
    chunks = chunk_markdown(MD, DOC, max_tokens=400, overlap_tokens=0)
    assert len(chunks) == 2  # split at top-level section boundary
    assert chunks[0].section == "Part One" and chunks[0].page == 1
    assert chunks[1].section == "Part Two > Article 5" and chunks[1].page == 2
    assert "transparency" in chunks[1].content


def test_respects_max_tokens_and_ids_unique() -> None:
    long_para = " ".join(f"Sentence number {i} about data protection." for i in range(400))
    chunks = chunk_markdown(f"# H\n\n{long_para}", DOC, max_tokens=120, overlap_tokens=10)
    assert len(chunks) > 5
    assert all(count_tokens(c.content) <= 120 + 10 + 5 for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)


def test_arabic_long_paragraph_splits_on_arabic_punctuation() -> None:
    ar_doc = DOC.model_copy(update={"language": "ar"})
    para = " ".join("هل يجب حماية البيانات الشخصية؟ نعم يجب ذلك." for _ in range(150))
    chunks = chunk_markdown(f"# عنوان\n\n{para}", ar_doc, max_tokens=100, overlap_tokens=0)
    assert len(chunks) > 3
    assert all(c.language == "ar" for c in chunks)
    assert chunks[0].content.rstrip().endswith(("؟", "."))
