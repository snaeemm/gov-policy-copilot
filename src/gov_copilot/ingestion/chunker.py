"""Layout-aware, Arabic-aware chunker.

Input: Markdown produced by Azure Document Intelligence `prebuilt-layout` (headings as `#`,
page breaks as `<!-- PageBreak -->`). Strategy:
1. Track page numbers and the current heading path (section).
2. Split into paragraphs; pack paragraphs into chunks of <= max_tokens, never crossing a
   top-level section boundary.
3. Oversized paragraphs are split on sentence boundaries (incl. Arabic `؟` and `۔`).
4. Add a small token overlap from the previous chunk for context continuity.
"""

import hashlib
import re
from dataclasses import dataclass, field

import tiktoken

from gov_copilot.ingestion.text import clean_whitespace, split_sentences
from gov_copilot.models import Chunk, SourceDocument

_ENC = tiktoken.get_encoding("o200k_base")
_PAGE_BREAK = re.compile(r"<!--\s*PageBreak\s*-->")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def count_tokens(text: str) -> int:
    return len(_ENC.encode(text))


@dataclass
class _Block:
    text: str
    page: int
    section: str


@dataclass
class _Acc:
    blocks: list[_Block] = field(default_factory=list)
    tokens: int = 0


def _blocks_from_markdown(markdown: str) -> list[_Block]:
    blocks: list[_Block] = []
    headings: list[str] = []
    for page_no, page_md in enumerate(_PAGE_BREAK.split(markdown), start=1):
        page_md = _COMMENT.sub("", page_md)
        for para in re.split(r"\n\s*\n", page_md):
            para = clean_whitespace(para)
            if not para:
                continue
            m = _HEADING.match(para)
            if m:
                level, title = len(m.group(1)), m.group(2).strip()
                headings = [*headings[: level - 1], title]
                continue
            blocks.append(_Block(para, page_no, " > ".join(headings)))
    return blocks


def _split_long(block: _Block, max_tokens: int) -> list[_Block]:
    if count_tokens(block.text) <= max_tokens:
        return [block]
    out: list[_Block] = []
    buf = ""
    for sent in split_sentences(block.text):
        candidate = f"{buf} {sent}".strip()
        if buf and count_tokens(candidate) > max_tokens:
            out.append(_Block(buf, block.page, block.section))
            buf = sent
        else:
            buf = candidate
    if buf:
        out.append(_Block(buf, block.page, block.section))
    # Hard-split anything still too long (e.g. no punctuation).
    final: list[_Block] = []
    for b in out:
        toks = _ENC.encode(b.text)
        for i in range(0, len(toks), max_tokens):
            final.append(_Block(_ENC.decode(toks[i : i + max_tokens]), b.page, b.section))
    return final


def _top_section(section: str) -> str:
    return section.split(" > ")[0]


def chunk_markdown(
    markdown: str,
    doc: SourceDocument,
    max_tokens: int = 450,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    blocks: list[_Block] = []
    for b in _blocks_from_markdown(markdown):
        blocks.extend(_split_long(b, max_tokens))

    groups: list[list[_Block]] = []
    acc = _Acc()
    for b in blocks:
        t = count_tokens(b.text)
        boundary = acc.blocks and _top_section(acc.blocks[-1].section) != _top_section(b.section)
        if acc.blocks and (acc.tokens + t > max_tokens or boundary):
            groups.append(acc.blocks)
            acc = _Acc()
        acc.blocks.append(b)
        acc.tokens += t
    if acc.blocks:
        groups.append(acc.blocks)

    chunks: list[Chunk] = []
    prev_tail = ""
    for i, group in enumerate(groups):
        body = "\n\n".join(b.text for b in group)
        content = f"{prev_tail}\n\n{body}".strip() if prev_tail else body
        toks = _ENC.encode(body)
        prev_tail = _ENC.decode(toks[-overlap_tokens:]) if overlap_tokens else ""
        cid = hashlib.sha1(f"{doc.doc_id}:{i}:{body}".encode()).hexdigest()[:16]  # noqa: S324
        chunks.append(
            Chunk(
                id=f"{doc.doc_id}-{i:04d}-{cid}",
                doc_id=doc.doc_id,
                title=doc.title,
                language=doc.language,
                section=group[0].section,
                page=group[0].page,
                chunk_index=i,
                content=content,
                source_url=doc.source_url,
            )
        )
    return chunks
