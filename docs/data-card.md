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

## Data-quality gates

Ingestion (`scripts/ingest.py`) runs data-quality checks on **all** chunks before anything is embedded or uploaded. Implementation: `src/gov_copilot/ingestion/quality.py`; tests: `tests/unit/test_quality.py`. Any **error** fails the run (exit code 1) and leaves the index untouched. **Warnings** are reported but allowed by default; `--no-allow-dq-warnings` makes them fatal too. `--dq-only` runs the checks offline on the cached Document Intelligence output. Reports are written to `data/processed/dq-report.json` and `dq-report.md`.

| Check | Error (blocks) | Warning (reported) |
|---|---|---|
| metadata | missing doc_id, title, source_url or file; non-https source; chunk/doc mismatch; page < 1 | – |
| classification | label missing, mismatched, or not `public` (this index is public-data only) | – |
| length | empty chunk; document produced no chunks | chunk < 20 tokens |
| language | dominant script ≠ declared language with < 5% expected script | 5–35% expected script (mixed text tolerated above 35%; < 40 letters not judged) |
| duplicates | exact duplicate after normalisation (Arabic normalisation, case, whitespace) | near-duplicate within a document (5-word shingles, Jaccard ≥ 0.9) |
| ocr | > 1% replacement or control characters | > 15% symbols; tokens > 60 chars (URLs excluded); known artefact "Al" read for "AI" |

Every document carries a `classification` label (`public` / `internal` / `confidential`) in `data/manifest.json`. It is stored as a filterable field in the search index, so a mixed-sensitivity corpus could be filtered per user role later.

**Latest run (6 documents, 147 chunks): PASS, 0 errors, 34 warnings.**

| Check | Errors | Warnings | Notes |
|---|---|---|---|
| ocr | 0 | 28 | Mostly "Al" for "AI" in the English Charter and Ethics PDFs (a known OCR confusion) |
| length | 0 | 5 | Cover/title-page chunks |
| language | 0 | 1 | Arabic Ethics guide chunk dominated by English bibliography references |
