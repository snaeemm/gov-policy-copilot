"""Ingest PDFs: Document Intelligence -> chunk -> embed -> upsert into Azure AI Search.

Usage: uv run python scripts/ingest.py [--recreate]
"""

import argparse
import asyncio
import contextlib
import json
from pathlib import Path

from azure.identity.aio import DefaultAzureCredential
from azure.search.documents.indexes.aio import SearchIndexClient

from gov_copilot.config import get_settings
from gov_copilot.ingestion.chunker import chunk_markdown
from gov_copilot.ingestion.docintel import analyze_to_markdown
from gov_copilot.llm.clients import embed
from gov_copilot.models import SourceDocument
from gov_copilot.retrieval.index import build_index, to_search_doc
from gov_copilot.retrieval.retriever import search_client

ROOT = Path(__file__).resolve().parents[1]


async def main(recreate: bool) -> None:
    s = get_settings()
    manifest = json.loads((ROOT / "data/manifest.json").read_text())
    docs = [SourceDocument(**d) for d in manifest["documents"]]

    async with SearchIndexClient(s.azure_search_endpoint, DefaultAzureCredential()) as ic:
        if recreate:
            with contextlib.suppress(Exception):  # index may not exist yet
                await ic.delete_index(s.azure_search_index)
        await ic.create_or_update_index(build_index(s.azure_search_index, s.embedding_dimensions))

    total = 0
    for doc in docs:
        pdf = ROOT / "data/raw" / doc.file
        if not pdf.exists():
            print(f"skip {doc.doc_id}: {doc.file} not downloaded")
            continue
        md = await analyze_to_markdown(pdf, s.docintel_endpoint, ROOT / "data/processed")
        chunks = chunk_markdown(md, doc)
        vectors = await embed([f"{c.title}\n{c.section}\n{c.content}" for c in chunks])
        async with search_client(s) as sc:
            await sc.upload_documents(
                [to_search_doc(c, v) for c, v in zip(chunks, vectors, strict=True)]
            )
        total += len(chunks)
        print(f"{doc.doc_id}: {len(chunks)} chunks")
    print(f"done: {total} chunks indexed into '{s.azure_search_index}'")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--recreate", action="store_true")
    asyncio.run(main(ap.parse_args().recreate))
