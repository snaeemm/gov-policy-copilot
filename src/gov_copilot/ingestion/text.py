"""Arabic-aware text utilities."""

import re

_ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_TATWEEL = "ـ"
_DIACRITICS_RE = re.compile(r"[ً-ٰٟۖ-ۭ]")
# Sentence boundaries: Latin . ! ? and Arabic question mark / full stop, followed by space.
_SENTENCE_RE = re.compile(r"(?<=[.!?؟۔])\s+")


def detect_language(text: str) -> str:
    """Return 'ar' if Arabic letters dominate Latin letters, else 'en'."""
    ar = len(_ARABIC_RE.findall(text))
    en = len(_LATIN_RE.findall(text))
    return "ar" if ar > en else "en"


def normalize_arabic(text: str) -> str:
    """Light normalization: strip tatweel and diacritics, unify alef/yaa/taa-marbuta forms.

    Applied to the indexed/searchable text only, never to the text shown to users.
    """
    text = text.replace(_TATWEEL, "")
    text = _DIACRITICS_RE.sub("", text)
    text = re.sub("[إأآٱ]", "ا", text)
    text = text.replace("ى", "ي")
    return text


def clean_whitespace(text: str) -> str:
    text = text.replace("\u00a0", " ")  # no-break space
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_RE.split(text) if s.strip()]
