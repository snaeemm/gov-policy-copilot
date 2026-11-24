"""Data-quality (DQ) gates for ingestion.

Every chunk is checked before it is embedded or uploaded. Checks return issues with a severity:
- error:   blocks ingestion (the pipeline exits non-zero and nothing is uploaded)
- warning: reported in the DQ report but does not block

Checks
- metadata:       required fields present and valid (doc_id, title, source_url, language, page >= 1)
- classification: a data-classification label is set and allowed for this (public) index
- length:         empty (error) or very short (warning) chunks
- language:       detected language disagrees with the document's declared language
- duplicates:     exact duplicates (error) and near-duplicates (warning, shingled Jaccard)
- ocr:            garbage/replacement characters, symbol-heavy text, overlong tokens, known OCR
                  artefacts such as "Al" read instead of "AI"
"""

import hashlib
import re
from collections import Counter
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, Field

from gov_copilot.ingestion.chunker import count_tokens
from gov_copilot.ingestion.text import detect_language, normalize_arabic
from gov_copilot.models import Chunk, SourceDocument

Severity = Literal["error", "warning"]
ALLOWED_CLASSIFICATIONS = {"public"}  # this index is public-data only

_LETTER = re.compile(r"[A-Za-z؀-ۿ]")
_ARABIC = re.compile(r"[؀-ۿ]")
_LATIN = re.compile(r"[A-Za-z]")
_GARBAGE = re.compile(r"[�\u0000-\u0008\u000B\u000C\u000E-\u001F]")
_SYMBOL = re.compile(r"[^\w\s.,;:!?'\"()\[\]\-–—/%&@#*+=<>|«»،؛؟؀-ۿ]")
# Known OCR confusion: capital-I read as lowercase-l in "AI" (e.g. "Al systems", "Al-driven").
_AL_FOR_AI = re.compile(
    r"\bAl(?=[\s\-]+(?:system|model|technolog|solution|ethic|driven|based|tool|charter|polic|governance|applications?)\w*)",
    re.I,
)
_TOKEN = re.compile(r"\S+")
# URL-like tokens (bibliography links, often without a scheme) are long by nature, not OCR noise.
_URLISH = re.compile(r"://|www\.|^[\w-]+(\.[\w-]+)+/|/[\w-]+/")


class DQThresholds(BaseModel):
    min_tokens_warning: int = 20
    min_chars_error: int = 1
    near_duplicate_jaccard: float = 0.9
    shingle_size: int = 5
    max_garbage_ratio: float = 0.01
    max_symbol_ratio: float = 0.15
    max_token_chars: int = 60
    language_check_min_letters: int = 40
    language_minority_tolerance: float = 0.35


class DQIssue(BaseModel):
    check: str
    severity: Severity
    doc_id: str
    chunk_id: str | None = None
    message: str


class DQReport(BaseModel):
    passed: bool
    total_chunks: int
    errors: int
    warnings: int
    by_check: dict[str, dict[str, int]] = Field(default_factory=dict)
    by_doc: dict[str, dict[str, int]] = Field(default_factory=dict)
    issues: list[DQIssue] = Field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            "# Data-quality report",
            "",
            f"**Result:** {'PASS' if self.passed else 'FAIL'} - {self.total_chunks} chunks, "
            f"{self.errors} errors, {self.warnings} warnings",
            "",
            "| Check | Errors | Warnings |",
            "|---|---|---|",
        ]
        for check, c in sorted(self.by_check.items()):
            lines.append(f"| {check} | {c.get('error', 0)} | {c.get('warning', 0)} |")
        lines += ["", "| Document | Chunks | Errors | Warnings |", "|---|---|---|---|"]
        for doc, c in sorted(self.by_doc.items()):
            lines.append(
                f"| {doc} | {c.get('chunks', 0)} | {c.get('error', 0)} | {c.get('warning', 0)} |"
            )
        if self.issues:
            lines += ["", "## Issues (first 50)", ""]
            for i in self.issues[:50]:
                where = f"{i.doc_id}/{i.chunk_id}" if i.chunk_id else i.doc_id
                lines.append(f"- **{i.severity}** `{i.check}` {where}: {i.message}")
        return "\n".join(lines) + "\n"


def _issue(check: str, sev: Severity, chunk: Chunk | None, doc_id: str, msg: str) -> DQIssue:
    return DQIssue(
        check=check, severity=sev, doc_id=doc_id, chunk_id=chunk.id if chunk else None, message=msg
    )


def check_document_metadata(doc: SourceDocument) -> list[DQIssue]:
    issues: list[DQIssue] = []
    for name in ("doc_id", "title", "source_url", "file"):
        if not str(getattr(doc, name)).strip():
            issues.append(_issue("metadata", "error", None, doc.doc_id or "?", f"missing {name}"))
    if doc.source_url and not doc.source_url.startswith("https://"):
        issues.append(
            _issue("metadata", "error", None, doc.doc_id, "source_url must be an https URL")
        )
    if doc.classification not in ALLOWED_CLASSIFICATIONS:
        issues.append(
            _issue(
                "classification",
                "error",
                None,
                doc.doc_id,
                f"classification '{doc.classification}' not allowed in the public index",
            )
        )
    return issues


def check_chunk_metadata(chunk: Chunk, doc: SourceDocument) -> list[DQIssue]:
    issues: list[DQIssue] = []
    for name in ("id", "doc_id", "title", "source_url"):
        if not str(getattr(chunk, name)).strip():
            issues.append(_issue("metadata", "error", chunk, doc.doc_id, f"missing {name}"))
    if chunk.doc_id != doc.doc_id:
        issues.append(_issue("metadata", "error", chunk, doc.doc_id, "doc_id mismatch"))
    if chunk.language != doc.language:
        issues.append(_issue("metadata", "error", chunk, doc.doc_id, "language label mismatch"))
    if chunk.page < 1:
        issues.append(_issue("metadata", "error", chunk, doc.doc_id, "page must be >= 1"))
    if chunk.classification != doc.classification:
        issues.append(
            _issue("classification", "error", chunk, doc.doc_id, "classification mismatch")
        )
    return issues


def check_length(chunk: Chunk, doc_id: str, t: DQThresholds) -> list[DQIssue]:
    text = chunk.content.strip()
    if len(text) < t.min_chars_error:
        return [_issue("length", "error", chunk, doc_id, "empty chunk")]
    n = count_tokens(text)
    if n < t.min_tokens_warning:
        return [_issue("length", "warning", chunk, doc_id, f"short chunk ({n} tokens)")]
    return []


def check_language(chunk: Chunk, doc: SourceDocument, t: DQThresholds) -> list[DQIssue]:
    """Flag chunks whose dominant script disagrees with the declared document language.

    Short or genuinely mixed chunks (e.g. Arabic text quoting English acronyms) are tolerated.
    """
    ar = len(_ARABIC.findall(chunk.content))
    en = len(_LATIN.findall(chunk.content))
    total = ar + en
    if total < t.language_check_min_letters:
        return []
    detected = detect_language(chunk.content)
    if detected == doc.language:
        return []
    expected_share = (ar if doc.language == "ar" else en) / total
    if expected_share >= t.language_minority_tolerance:
        return []  # mixed-language chunk, expected script still substantial
    sev: Severity = "error" if expected_share < 0.05 else "warning"
    return [
        _issue(
            "language",
            sev,
            chunk,
            doc.doc_id,
            f"detected '{detected}' but document is '{doc.language}' "
            f"({expected_share:.0%} expected script)",
        )
    ]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_arabic(text).lower()).strip()


def _shingles(text: str, k: int) -> set[str]:
    words = _norm(text).split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def check_duplicates(chunks: list[Chunk], doc_id: str, t: DQThresholds) -> list[DQIssue]:
    issues: list[DQIssue] = []
    seen: dict[str, str] = {}
    for c in chunks:
        h = hashlib.sha256(_norm(c.content).encode()).hexdigest()
        if h in seen:
            issues.append(_issue("duplicates", "error", c, doc_id, f"exact duplicate of {seen[h]}"))
        else:
            seen[h] = c.id
    shingles = [(c, _shingles(c.content, t.shingle_size)) for c in chunks]
    for i, (a, sa) in enumerate(shingles):
        for b, sb in shingles[i + 1 :]:
            if _norm(a.content) == _norm(b.content):
                continue  # already reported as exact duplicate
            score = jaccard(sa, sb)
            if score >= t.near_duplicate_jaccard:
                issues.append(
                    _issue(
                        "duplicates",
                        "warning",
                        b,
                        doc_id,
                        f"near-duplicate of {a.id} (Jaccard {score:.2f})",
                    )
                )
    return issues


def check_ocr(chunk: Chunk, doc_id: str, t: DQThresholds) -> list[DQIssue]:
    text = chunk.content
    if not text:
        return []
    issues: list[DQIssue] = []
    garbage = len(_GARBAGE.findall(text)) / len(text)
    if garbage > t.max_garbage_ratio:
        issues.append(_issue("ocr", "error", chunk, doc_id, f"garbage characters {garbage:.1%}"))
    letters = len(_LETTER.findall(text))
    symbols = len(_SYMBOL.findall(text))
    if letters and symbols / (letters + symbols) > t.max_symbol_ratio:
        issues.append(
            _issue(
                "ocr",
                "warning",
                chunk,
                doc_id,
                f"symbol-heavy text ({symbols / (letters + symbols):.0%} symbols)",
            )
        )
    long_tokens = [
        tok
        for tok in _TOKEN.findall(text)
        if len(tok) > t.max_token_chars and not _URLISH.search(tok)
    ]
    if long_tokens:
        issues.append(
            _issue(
                "ocr",
                "warning",
                chunk,
                doc_id,
                f"{len(long_tokens)} overlong token(s), e.g. '{long_tokens[0][:30]}...'",
            )
        )
    if _AL_FOR_AI.search(text):
        issues.append(
            _issue("ocr", "warning", chunk, doc_id, "OCR artefact: 'Al' likely means 'AI'")
        )
    return issues


def run_checks(
    docs_chunks: Iterable[tuple[SourceDocument, list[Chunk]]],
    thresholds: DQThresholds | None = None,
) -> DQReport:
    t = thresholds or DQThresholds()
    issues: list[DQIssue] = []
    by_doc: dict[str, Counter[str]] = {}
    total = 0
    for doc, chunks in docs_chunks:
        doc_issues = check_document_metadata(doc)
        if not chunks:
            doc_issues.append(
                _issue("length", "error", None, doc.doc_id, "document produced no chunks")
            )
        for c in chunks:
            doc_issues += check_chunk_metadata(c, doc)
            doc_issues += check_length(c, doc.doc_id, t)
            doc_issues += check_language(c, doc, t)
            doc_issues += check_ocr(c, doc.doc_id, t)
        doc_issues += check_duplicates(chunks, doc.doc_id, t)
        counts: Counter[str] = Counter(i.severity for i in doc_issues)
        counts["chunks"] = len(chunks)
        by_doc[doc.doc_id] = counts
        total += len(chunks)
        issues += doc_issues

    by_check: dict[str, Counter[str]] = {}
    for i in issues:
        by_check.setdefault(i.check, Counter())[i.severity] += 1
    errors = sum(i.severity == "error" for i in issues)
    return DQReport(
        passed=errors == 0,
        total_chunks=total,
        errors=errors,
        warnings=len(issues) - errors,
        by_check={k: dict(v) for k, v in by_check.items()},
        by_doc={k: dict(v) for k, v in by_doc.items()},
        issues=sorted(issues, key=lambda i: (i.severity != "error", i.doc_id, i.check)),
    )
