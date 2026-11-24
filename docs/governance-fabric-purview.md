# Data Governance: Microsoft Fabric "Gold layer" + Microsoft Purview

> **Status: designed, not deployed.** A Microsoft Fabric trial requires an organizational (work/school) Entra account; this project runs on a personal Microsoft account tenant. The ingestion code already follows the medallion contract below using local folders, so moving to OneLake is a storage swap, not a redesign.

## Medallion layout (OneLake lakehouse `lh_gov_policies`)
| Layer | Content | Today (local) | In Fabric |
|---|---|---|---|
| Bronze | Raw official PDFs, immutable, with source URL + retrieval timestamp + SHA-256 | `data/raw/` | `Files/bronze/<doc_id>/<sha>.pdf` |
| Silver | Document Intelligence layout Markdown per document | `data/processed/*.layout.json` | `Files/silver/` + Delta table `silver_documents` |
| Gold | Approved, chunked, versioned documents + manifest; the **only** layer the copilot indexes | `data/manifest.json` (+ chunks built in `scripts/ingest.py`) | Delta tables `gold_documents`, `gold_chunks` (contract: `data/gold/README.md`) |

Pipeline: a Fabric Data Pipeline (or notebook) runs bronze → silver (calls Document Intelligence) → gold (chunker from `src/gov_copilot/ingestion/chunker.py`). A data steward sets `approval_status = approved` on `gold_documents`; `scripts/ingest.py` would read only approved gold rows (via OneLake ADLS Gen2 endpoint with managed identity) and push them to Azure AI Search. This blocks unreviewed or tampered documents from reaching the model (mitigates indirect prompt injection, see threat model).

## Microsoft Purview
| Capability | Use here |
|---|---|
| Data Map scan | Register the Fabric tenant / OneLake and the AI Search service; scheduled scans |
| Classification | Built-in + custom classifiers: *UAE Emirates ID* (`784-\d{4}-\d{7}-\d`), *UAE phone*; expected result for this corpus: **no personal data**; alert if found |
| Sensitivity labels | Corpus labelled *Public*; any non-public document labelled *Confidential* is excluded from gold by policy |
| Lineage | Fabric pipeline lineage bronze → silver → gold → AI Search index, so every answer citation can be traced to a source file + hash |
| Data catalog / glossary | Terms: "Charter principle", "PDPL article", owner = data steward |
| Audit | Purview audit + Fabric activity log for who approved which gold version |

## Answer-level traceability (already implemented)
Each citation carries `doc_id`, page and `source_url`; each request logs `prompt_version` and `model`. With gold-layer versioning, add `gold_version` to chunk IDs to complete end-to-end lineage.
