"""PII masking applied before anything is logged or stored.

Two layers:
1. Deterministic regex for UAE-specific identifiers (Emirates ID, +971 phones, AE IBAN, emails) -
   works for Arabic and English text and never depends on a network call.
2. Azure AI Language PII detection (names, addresses, etc.) for supported languages.
"""

import re

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMIRATES_ID", re.compile(r"\b784[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d\b")),
    ("IBAN", re.compile(r"\bAE\d{2}\s?(?:\d{4}\s?){4}\d{3}\b", re.I)),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    (
        "PHONE",
        re.compile(
            r"(?:\+|00)971[\s-]?\d{1,2}[\s-]?\d{3}[\s-]?\d{4}\b|\b05\d[\s-]?\d{3}[\s-]?\d{4}\b"
        ),
    ),
    ("CARD", re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b")),
]


def regex_mask(text: str) -> str:
    for label, pattern in _PATTERNS:
        text = pattern.sub(f"[{label}]", text)
    return text
