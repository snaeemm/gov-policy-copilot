# Gold layer contract

The copilot indexes **only** gold-layer documents. Locally the gold manifest is `data/manifest.json`; in Fabric it would be the Delta table `gold_documents` (see `docs/governance-fabric-purview.md`).

## `gold_documents` schema
| Field | Type | Required | Notes |
|---|---|---|---|
| doc_id | string | ✓ | Stable ID, e.g. `ai-charter-en` (current manifest field) |
| file | string | ✓ | Bronze file name (current manifest field) |
| language | `en` \| `ar` | ✓ | current manifest field |
| title | string | ✓ | current manifest field |
| publisher | string | ✓ | current manifest field |
| year | int | ✓ | current manifest field |
| source_url | string | ✓ | Official URL (current manifest field) |
| sha256 | string | planned | Hash of the bronze PDF |
| approval_status | `pending` \| `approved` \| `retired` | planned | Only `approved` is indexed |
| approved_by / approved_at | string / timestamp | planned | Steward identity (Entra `oid`) |
| sensitivity_label | string | planned | Must be `Public` for this system |
| gold_version | int | planned | Incremented on re-processing |

## `gold_chunks` schema
Mirrors `gov_copilot.models.Chunk`: `id, doc_id, title, language, section, page, chunk_index, content, source_url` (+ `gold_version`).
