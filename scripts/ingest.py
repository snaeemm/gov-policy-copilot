"""Ingest PDFs: Document Intelligence -> chunk -> data-quality gate -> embed -> Azure AI Search.

Usage:
  uv run python scripts/ingest.py [--recreate]          full ingest (DQ gate runs first)
  uv run python scripts/ingest.py --dq-only             offline DQ check on cached layout JSON
  uv run python scripts/ingest.py --no-allow-dq-warnings  also fail on DQ warnings

The DQ gate runs on ALL documents before anything is embedded or uploaded. On any error the
script exits non-zero and the index is left untouched. Reports: data/processed/dq-report.{json,md}
"""

import argparse
import asyncio
import contextlib
import json
import sys
from pathlib import Path

from gov_copilot.ingestion.chunker import chunk_markdown
from gov_copilot.ingestion.quality import DQReport, run_checks
from gov_copilot.models import Chunk, SourceDocument

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data/processed"


def load_docs() -> list[SourceDocument]:
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    return [SourceDocument(**d) for d in manifest["documents"]]


def write_report(report: DQReport) -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (PROCESSED / "dq-report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (PROCESSED / "dq-report.md").write_text(report.to_markdown(), encoding="utf-8")


def gate(report: DQReport, allow_warnings: bool) -> bool:
    write_report(report)
    print(
        f"DQ: {'PASS' if report.passed else 'FAIL'} - {report.total_chunks} chunks, "
        f"{report.errors} errors, {report.warnings} warnings "
        f"(report: data/processed/dq-report.md)"
    )
    for check, counts in sorted(report.by_check.items()):
        print(f"  {check:<15} errors={counts.get('error', 0)} warnings={counts.get('warning', 0)}")
    if not report.passed:
        return False
    return allow_warnings or report.warnings == 0


async def collect(
    docs: list[SourceDocument], offline: bool
) -> list[tuple[SourceDocument, list[Chunk]]]:
    out: list[tuple[SourceDocument, list[Chunk]]] = []
    for doc in docs:
        cache = PROCESSED / f"{Path(doc.file).stem}.layout.json"
        pdf = ROOT / "data/raw" / doc.file
        if offline:
            if not cache.exists():
                print(f"skip {doc.doc_id}: no cached layout")
                continue
            md = json.loads(cache.read_text(encoding="utf-8"))["markdown"]
        else:
            if not pdf.exists():
                print(f"skip {doc.doc_id}: {doc.file} not downloaded")
                continue
            from gov_copilot.config import get_settings
            from gov_copilot.ingestion.docintel import analyze_to_markdown

            md = await analyze_to_markdown(pdf, get_settings().docintel_endpoint, PROCESSED)
        out.append((doc, chunk_markdown(md, doc)))
    return out


async def upload(docs_chunks: list[tuple[SourceDocument, list[Chunk]]], recreate: bool) -> None:
    from azure.identity.aio import DefaultAzureCredential
    from azure.search.documents.indexes.aio import SearchIndexClient

    from gov_copilot.config import get_settings
    from gov_copilot.llm.clients import embed
    from gov_copilot.retrieval.index import build_index, to_search_doc
    from gov_copilot.retrieval.retriever import search_client

    s = get_settings()
    async with SearchIndexClient(s.azure_search_endpoint, DefaultAzureCredential()) as ic:
        if recreate:
            with contextlib.suppress(Exception):  # index may not exist yet
                await ic.delete_index(s.azure_search_index)
        await ic.create_or_update_index(build_index(s.azure_search_index, s.embedding_dimensions))

    total = 0
    for doc, chunks in docs_chunks:
        vectors = await embed([f"{c.title}\n{c.section}\n{c.content}" for c in chunks])
        async with search_client(s) as sc:
            await sc.upload_documents(
                [to_search_doc(c, v) for c, v in zip(chunks, vectors, strict=True)]
            )
        total += len(chunks)
        print(f"{doc.doc_id}: {len(chunks)} chunks")
    print(f"done: {total} chunks indexed into '{s.azure_search_index}'")


async def main(recreate: bool, dq_only: bool, allow_warnings: bool) -> int:
    docs_chunks = await collect(load_docs(), offline=dq_only)
    if not gate(run_checks(docs_chunks), allow_warnings):
        print("DATA-QUALITY GATE FAILED - nothing was uploaded", file=sys.stderr)
        return 1
    if dq_only:
        return 0
    await upload(docs_chunks, recreate)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--recreate", action="store_true", help="drop and recreate the index")
    ap.add_argument("--dq-only", action="store_true", help="offline DQ check on cached layout")
    ap.add_argument(
        "--allow-dq-warnings",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="allow DQ warnings (errors always fail)",
    )
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.recreate, a.dq_only, a.allow_dq_warnings)))
