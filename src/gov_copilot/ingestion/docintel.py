"""Azure Document Intelligence `prebuilt-layout` -> Markdown, with a local cache.

Free tier (F0) analyzes only the first 2 pages of each request, so we split PDFs into
2-page slices, analyze each, and stitch the Markdown back together with page breaks.
Results are cached in data/processed/ so re-runs don't consume the 500 pages/month quota.
"""

import asyncio
import io
import json
from pathlib import Path

from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentContentFormat
from azure.identity.aio import DefaultAzureCredential
from pypdf import PdfReader, PdfWriter

PAGES_PER_REQUEST = 2  # F0 limit


MAX_BYTES = 4 * 1024 * 1024  # F0 request size limit


def _shrink(writer: PdfWriter, quality: int) -> None:
    """Re-encode embedded images as JPEG at lower quality and downscale very large ones."""
    for page in writer.pages:
        for img in page.images:
            pil = img.image
            if pil is None:
                continue
            if max(pil.size) > 2000:
                pil.thumbnail((2000, 2000))
            if pil.mode not in ("RGB", "L"):
                pil = pil.convert("RGB")
            img.replace(pil, quality=quality)
    writer.compress_identical_objects()


def _to_bytes(writer: PdfWriter) -> bytes:
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def split_pdf(data: bytes, pages_per_slice: int = PAGES_PER_REQUEST) -> list[bytes]:
    """Split into slices that respect both the F0 page limit and the 4 MB size limit."""
    reader = PdfReader(io.BytesIO(data))
    slices: list[bytes] = []
    for start in range(0, len(reader.pages), pages_per_slice):
        w = PdfWriter()
        for p in reader.pages[start : start + pages_per_slice]:
            w.add_page(p)
        out = _to_bytes(w)
        if len(out) > MAX_BYTES and pages_per_slice > 1:
            slices.extend(split_pdf(out, 1))
            continue
        for quality in (70, 50, 30):
            if len(out) <= MAX_BYTES:
                break
            _shrink(w, quality)
            out = _to_bytes(w)
        if len(out) > MAX_BYTES:
            # Vector-heavy pages don't shrink: rasterize each page to JPEG instead.
            slices.extend(_rasterize(out))
            continue
        slices.append(out)
    return slices


def _rasterize(pdf: bytes, scale: float = 2.5, quality: int = 85) -> list[bytes]:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf)
    images: list[bytes] = []
    for page in doc:
        pil = page.render(scale=scale).to_pil().convert("RGB")
        buf = io.BytesIO()
        pil.save(buf, format="JPEG", quality=quality, optimize=True)
        images.append(buf.getvalue())
    return images


def _join(parts: list[str]) -> str:
    return "\n<!-- PageBreak -->\n".join(p.strip() for p in parts)


async def analyze_to_markdown(pdf_path: Path, endpoint: str, cache_dir: Path) -> str:
    cache = cache_dir / f"{pdf_path.stem}.layout.json"
    if await asyncio.to_thread(cache.exists):
        return str(json.loads(await asyncio.to_thread(cache.read_text))["markdown"])
    slices = await asyncio.to_thread(lambda: split_pdf(pdf_path.read_bytes()))
    pages_md: list[str] = []
    async with DocumentIntelligenceClient(endpoint, DefaultAzureCredential()) as client:
        for data in slices:
            poller = await client.begin_analyze_document(
                "prebuilt-layout",
                AnalyzeDocumentRequest(bytes_source=data),
                output_content_format=DocumentContentFormat.MARKDOWN,
            )
            result = await poller.result()
            # Re-split each slice on its own page breaks so page numbers stay correct.
            pages_md.extend(result.content.split("<!-- PageBreak -->"))
    markdown = _join(pages_md)
    payload = json.dumps({"markdown": markdown}, ensure_ascii=False)
    await asyncio.to_thread(cache_dir.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(cache.write_text, payload)
    return markdown
