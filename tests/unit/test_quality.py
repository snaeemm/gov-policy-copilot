from gov_copilot.ingestion.quality import (
    DQThresholds,
    check_chunk_metadata,
    check_document_metadata,
    check_duplicates,
    check_language,
    check_length,
    check_ocr,
    run_checks,
)
from gov_copilot.models import Chunk, SourceDocument

T = DQThresholds()
EN_DOC = SourceDocument(
    doc_id="d-en",
    file="d.pdf",
    language="en",
    title="Doc",
    publisher="p",
    year=2024,
    source_url="https://example.gov.ae/d.pdf",
)
AR_DOC = EN_DOC.model_copy(update={"doc_id": "d-ar", "language": "ar"})

EN_TEXT = (
    "The Charter emphasises human oversight of artificial intelligence systems so that errors "
    "and biases can be corrected, and it requires transparency about how decisions are made."
)
AR_TEXT = (
    "يؤكد الميثاق على أهمية الرقابة البشرية على أنظمة الذكاء الاصطناعي لضمان تصحيح الأخطاء "
    "والتحيزات، ويشترط الشفافية في كيفية اتخاذ القرارات من قبل هذه الأنظمة."
)


def chunk(content: str, doc: SourceDocument = EN_DOC, i: int = 0, **kw: object) -> Chunk:
    data = {
        "id": f"{doc.doc_id}-{i}",
        "doc_id": doc.doc_id,
        "title": doc.title,
        "language": doc.language,
        "page": 1,
        "chunk_index": i,
        "content": content,
        "source_url": doc.source_url,
        **kw,
    }
    return Chunk.model_validate(data)


def test_length_empty_is_error_short_is_warning() -> None:
    assert check_length(chunk(""), "d", T)[0].severity == "error"
    assert check_length(chunk("Cover page"), "d", T)[0].severity == "warning"
    assert check_length(chunk(EN_TEXT), "d", T) == []
    assert check_length(chunk(AR_TEXT, AR_DOC), "d", T) == []


def test_language_mismatch_and_mixed_tolerance() -> None:
    # English text inside an Arabic document -> error (almost no Arabic script)
    issues = check_language(chunk(EN_TEXT, AR_DOC), AR_DOC, T)
    assert issues and issues[0].severity == "error"
    # Arabic text with an English acronym is fine
    mixed = AR_TEXT + " (AI) ACCESS"
    assert check_language(chunk(mixed, AR_DOC), AR_DOC, T) == []
    # Short chunks are not judged
    assert check_language(chunk("AI", AR_DOC), AR_DOC, T) == []
    assert check_language(chunk(AR_TEXT, AR_DOC), AR_DOC, T) == []


def test_exact_and_near_duplicates() -> None:
    long_text = (
        EN_TEXT + " The UAE seeks to build public trust through clear accountability for every "
        "deployed model, regular audits of training data, protection of personal information, "
        "inclusive access for all members of society, and cooperation with international partners "
        "on safe standards. Government entities should document the purpose of each system, "
        "the categories of data it processes, the expected benefits for residents, the known "
        "limitations of the model, and the escalation path when outputs are disputed. Developers "
        "are encouraged to test systems in both Arabic and English, to measure fairness across "
        "demographic groups, to monitor performance after deployment, and to retire systems that "
        "no longer meet the published principles. Accountability rests with the operator of the "
        "system at all times."
    )
    a = chunk(long_text, i=0)
    b = chunk(long_text, i=1)
    near = chunk(long_text.replace("operator", "owner"), i=2)
    other = chunk("A completely different paragraph about international cooperation.", i=3)
    issues = check_duplicates([a, b, near, other], "d-en", T)
    by_chunk = {i.chunk_id: i.severity for i in issues}
    assert by_chunk[b.id] == "error"  # exact duplicate
    assert by_chunk[near.id] == "warning"  # near-duplicate
    assert other.id not in by_chunk


def test_arabic_duplicates_normalized() -> None:
    a = chunk(AR_TEXT, AR_DOC, i=0)
    b = chunk(AR_TEXT.replace("الذكاء", "الذكــاء"), AR_DOC, i=1)  # tatweel only
    assert check_duplicates([a, b], "d-ar", T)[0].severity == "error"


def test_ocr_heuristics() -> None:
    assert check_ocr(chunk(EN_TEXT), "d", T) == []
    garbage = check_ocr(chunk(EN_TEXT + "�" * 20), "d", T)
    assert any(i.severity == "error" for i in garbage)
    symbols = check_ocr(chunk("@@ ## $$ ^^ ~~ @@ ## $$ ^^ ~~ data"), "d", T)
    assert any("symbol-heavy" in i.message for i in symbols)
    long_tok = check_ocr(chunk(EN_TEXT + " " + "x" * 80), "d", T)
    assert any("overlong" in i.message for i in long_tok)
    url = check_ocr(
        chunk(EN_TEXT + " consumerfinance.gov/policy-compliance/guidance/very-long-path-x"), "d", T
    )
    assert not any("overlong" in i.message for i in url)
    al = check_ocr(chunk("Al systems must be transparent."), "d", T)
    assert al and al[0].severity == "warning" and "Al" in al[0].message


def test_metadata_and_classification() -> None:
    assert check_document_metadata(EN_DOC) == []
    bad = EN_DOC.model_copy(update={"source_url": "http://insecure", "title": " "})
    assert {i.message for i in check_document_metadata(bad)} >= {
        "missing title",
        "source_url must be an https URL",
    }
    conf = EN_DOC.model_copy(update={"classification": "confidential"})
    assert check_document_metadata(conf)[0].check == "classification"
    wrong_lang = chunk(EN_TEXT, language="ar")
    assert any("language label" in i.message for i in check_chunk_metadata(wrong_lang, EN_DOC))
    wrong_cls = chunk(EN_TEXT, classification="internal")
    assert any(i.check == "classification" for i in check_chunk_metadata(wrong_cls, EN_DOC))


def test_run_checks_report_pass_and_fail() -> None:
    ok = run_checks([(EN_DOC, [chunk(EN_TEXT)]), (AR_DOC, [chunk(AR_TEXT, AR_DOC)])])
    assert ok.passed and ok.total_chunks == 2 and ok.errors == 0
    bad = run_checks([(EN_DOC, [chunk(EN_TEXT, i=0), chunk(EN_TEXT, i=1)]), (AR_DOC, [])])
    assert not bad.passed
    assert bad.by_check["duplicates"]["error"] == 1
    assert bad.by_doc["d-ar"]["error"] == 1  # document produced no chunks
    assert "FAIL" in bad.to_markdown()
