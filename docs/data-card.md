# Data Card

## Sources (public)
| doc_id | Title | Lang | Publisher | Status |
|---|---|---|---|---|
| ai-charter-en / -ar | UAE Charter for the Development and Use of AI (2024) | EN / AR | UAE AI Office (ai.gov.ae) | Indexed |
| ai-policy-en / -ar | The UAE's International Stance on AI Policy (2024) | EN / AR | UAE AI Office | Indexed |
| pdpl-en / -ar | Federal Decree-Law No. 45 of 2021 (PDPL) | EN / AR | uaelegislation.gov.ae | **Pending** – site blocks automated download (Cloudflare); manual download required |
| ai-ethics-en / -ar | UAE AI Ethics: Principles & Guidelines (2022) | EN / AR | ai.gov.ae (UAE AI Office) | Indexed (44 EN + 58 AR chunks) |

Metadata and source URLs: `data/manifest.json`. Raw PDFs are **not** redistributed in the repo (`data/raw` is git-ignored); they are fetched from the official URLs. Users should consult the publishers' terms; the AI Ethics guidelines are published under CC BY 4.0. Arabic is the authoritative language for UAE federal legislation; English texts may be translations.

## Personal data
None in the corpus. User questions may contain PII; they are masked before logging (see `pdpl-data-residency.md`).

## Processing pipeline
1. **Document Intelligence `prebuilt-layout`** → Markdown with headings and page breaks.
   - F0 limits handled in `ingestion/docintel.py`: max 2 pages and 4 MB per request → PDFs split into ≤2-page slices; oversize slices recompressed, and vector-heavy pages rasterized to JPEG (scale 2.5, q85).
   - Results cached in `data/processed/*.layout.json` to protect the 500 pages/month quota.
2. **Chunking** (`ingestion/chunker.py`): heading-path and page tracking, paragraphs packed to ≤ **450 tokens** (o200k), never across top-level sections, oversize paragraphs split on sentence boundaries incl. Arabic `؟` `۔`, **50-token** overlap, deterministic IDs.
3. **Indexing**: Arabic text normalized (alef/yaa forms, tatweel, diacritics) for search only; original text kept for display.

Current index: 147 chunks (charter EN 13, charter AR 9, policy EN 11, policy AR 12, ethics EN 44, ethics AR 58).

## Quality issues
- OCR artifacts: "Al" for "AI"; some Arabic entity names garbled (e.g. AI71/G42 on policy page 3).
- Last page of each document is a cover/back page with little content.
