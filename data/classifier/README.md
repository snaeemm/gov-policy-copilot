# Classifier dataset: bilingual query routing (EN/AR)

Training data for `gov-policy-query-classifier` ([ADR-0013](../../docs/adr/0013-query-classifier-azure-ml.md)).
Built by `scripts/build_classifier_dataset.py` (seed 42). Files: `train.jsonl`, `val.jsonl`, `test.jsonl`
(fields: `id, text, label, language, source`), `stats.json`.

## Labels
`charter` · `international_policy` · `ethics` · `data_protection` · `out_of_scope` (in-scope = label ≠ out_of_scope)

## Counts (EN / AR)
| label | train | val | test |
|---|---|---|---|
| charter | 42 / 42 | 9 / 9 | 24 / 22 |
| international_policy | 49 / 49 | 10 / 10 | 20 / 22 |
| ethics | 206 / 206 | 44 / 44 | 44 / 44 |
| data_protection | 31 / 31 | 7 / 7 | 7 / 7 |
| out_of_scope | 53 / 53 | 11 / 11 | 22 / 16 |
| **total** | 762 | 162 | 228 |

Sources (all splits): corpus: 846, synthetic_oos: 150, synthetic_topic: 90, redteam: 16, golden: 50.

## Provenance
| source | how | label |
|---|---|---|
| `corpus:<doc_id>` | Azure OpenAI gpt-5-mini wrote 3 EN + 3 AR realistic questions per indexed chunk (>120 chars) of the public documents (cross-lingual by design) | from the document |
| `synthetic_topic` | gpt-5-mini wrote PDPL-style questions from topic areas (consent, data subject rights, breach notification, cross-border transfer, DPO, penalties) - the PDPL text itself is not indexed | data_protection |
| `synthetic_oos` | gpt-5-mini wrote off-topic questions (cooking, sports, coding, travel, finance, UAE non-policy trivia, casual "AI"/"UAE" mentions) | out_of_scope |
| `golden` | `eval/golden.jsonl` questions, label from first expected document | doc label |
| `redteam` | `eval/redteam.jsonl` items of type jailbreak / prompt_injection / out_of_scope / harmful (legal_advice and pii_extraction excluded as ambiguous for routing) | out_of_scope |

Generation prompts are in the script (`CHUNK_PROMPT`, `TOPIC_PROMPT`, `OOS_PROMPT`). LLM cost of the build: ~$0.07.

## Splitting and leakage control
- Normalised-text dedupe (Arabic normalisation, punctuation/case stripped).
- Stratified 70/15/15 split by label × language for generated rows.
- **Golden and red-team questions appear only in `test`** and are removed from the generated pool if duplicated.

## Licence and terms
Questions are derived from public UAE government publications (UAE AI Office: Charter, International AI policy stance, AI Ethics Principles & Guidelines - the latter published under CC BY 4.0). Generated questions are released with this repo (MIT). No personal data.

## Limitations
- Synthetic, LLM-generated phrasing; real traffic distribution differs - monitor `classifier_label` mix drift.
- Class imbalance (ethics document is the largest); training oversamples label × language strata.
- `data_protection` learned from topic prompts, not statute text.
