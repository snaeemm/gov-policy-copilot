from gov_copilot.ingestion.text import detect_language, normalize_arabic, split_sentences


def test_detect_language() -> None:
    assert detect_language("حماية البيانات الشخصية") == "ar"
    assert detect_language("Protection of personal data") == "en"
    assert detect_language("Article 5 المادة الخامسة من القانون") == "ar"


def test_normalize_arabic_strips_tatweel_diacritics_and_unifies_alef() -> None:
    assert normalize_arabic("الذكــاء") == "الذكاء"
    assert normalize_arabic("مُحَمَّد") == "محمد"
    assert normalize_arabic("أحمد إسلام آمن") == "احمد اسلام امن"
    assert normalize_arabic("على") == "علي"


def test_split_sentences_handles_arabic_question_mark() -> None:
    parts = split_sentences("ما هو القانون؟ هذا هو القانون. And English too.")
    assert len(parts) == 3
