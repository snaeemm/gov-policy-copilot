# Model comparison on Microsoft Foundry

_Generated 2026-11-28 by `eval/compare_models.py`._

Same pipeline, same index, same prompts (v2), same golden set (50 EN/AR questions) and red-team set (24 prompts). Only the chat model changes. Groundedness and relevance are scored by one fixed judge (Azure OpenAI gpt-5-mini, Azure AI Evaluation SDK) so the numbers are comparable.

| Model | Family | Grounded | Relevance | Citation acc. | Answer rate | Red-team pass | p50 latency | p95 latency | Cost / query | Eval gate |
|---|---|---|---|---|---|---|---|---|---|---|
| gpt-5-mini | OpenAI | 98% | 80% | 88% | 86% | 92% | 10.12s | 13.86s | $0.00161 | pass |
| gpt-5-nano | OpenAI | 100% | 67% | 100% | 6% | 88% | 10.59s | 13.58s | $0.00042 | FAIL |
| gpt-5.4-mini | OpenAI | 93% | 78% | 87% | 92% | 92% | 9.51s | 18.24s | $0.00483 | pass |

## By language (answer rate)

| Model | English | Arabic |
|---|---|---|
| gpt-5-mini | 92% | 80% |
| gpt-5-nano | 12% | 0% |
| gpt-5.4-mini | 96% | 88% |

## Same model: direct Azure OpenAI vs through Foundry (gpt-5-mini)

Identical pipeline and settings; only the endpoint changes (`LLM_PROVIDER=azure_openai` vs `LLM_PROVIDER=foundry`).

| | Direct Azure OpenAI | Via Foundry |
|---|---|---|
| Groundedness | 97% | 98% |
| Relevance | 80% | 80% |
| Citation accuracy | 87% | 88% |
| Answer rate | 82% | 86% |
| Red-team pass | 96% | 92% |
| p50 latency (s) | 9.54 | 10.12 |
| p95 latency (s) | 12.76 | 13.86 |
| Cost / query (USD) | 0.001615 | 0.001611 |

Differences are within run-to-run noise (2-4 points on 50 questions; one red-team prompt). Same model, same price: Foundry changes the platform around the model (catalog, agents, evaluation, tracing), not answer quality.

## Custom pipeline vs Foundry Agent Service (same model, gpt-5-mini)

The same task built as a managed **Foundry Agent Service** prompt agent (`scripts/foundry_agent.py`): instructions + the Azure AI Search tool over the same index through a keyless project connection. Scored with the same judge on the first 50 golden questions.

| | Custom pipeline (Semantic Kernel) | Foundry Agent Service |
|---|---|---|
| Groundedness | 98% | 94% |
| Relevance | 80% | 82% |
| Answer rate | 86% | 100% |
| p50 / p95 latency | 10.12s / 13.86s | 9.24s / 12.76s |
| Retrieval | Hybrid (BM25 + vector, RRF), multi-query planner | Search tool, keyword (`simple`) on the free Search tier |
| Safety | Prompt Shields, Content Safety, PII masking, classifier pre-filter | Foundry default content filters |
| Grounding control | Self-check score, escalate below 0.7 to human review | Instructions only |
| Audit | Per-request model, prompt version, cost, review queue | Foundry traces |
| Effort to build | ~1,000 lines of Python | ~40 lines + portal |

Takeaway: the managed agent is far faster to stand up and is a good prototyping and baseline tool; the custom pipeline keeps the controls a government deployment needs (fail-closed guardrails, measurable grounding threshold, human escalation, per-request audit). See ADR 0014.

## Gate failures

- **gpt-5-mini**: none
- **gpt-5-nano**: relevance=0.6667 < 0.7; answer_rate=0.06 < 0.75; redteam_pass_rate=0.875 < 0.9
- **gpt-5.4-mini**: none

## Notes

- Retrieval recall@5 is identical across models (retrieval does not use the chat model except for query planning), so it is not shown.
- Answer rate counts questions the model answered and that passed the groundedness self-check; the rest were escalated to human review or refused.
- **Phi-4 and Llama 3.3 70B are deployed in the Foundry project but could not run the pipeline here:** although the deployments show 20K tokens/min, the service enforces 1K tokens and 1 request per minute for non-OpenAI models on this (free-tier) subscription, and one RAG prompt (8 retrieved chunks) is ~4-6K tokens. Both answered short smoke-test prompts (including Arabic). On a pay-as-you-go subscription, run `compare_models.py --models Phi-4 Llama-3.3-70B-Instruct` to fill in their rows.
- gpt-5-nano is 4x cheaper but escalated 47 of 50 questions: the same model also runs the in-pipeline groundedness self-check, and nano scores its own drafts below the 0.7 threshold. Answers it did give were fully grounded. It is unsuitable as both answerer and verifier; a mixed setup (nano answers, a stronger model verifies) is a follow-up.
- gpt-5-nano ran one question at a time after hitting its rate limit at concurrency 4.
- The Foundry agent's 100% answer rate reflects that it has no escalation path, not better coverage.
- Costs use Azure Global Standard list prices per 1M tokens, set in `eval/compare_models.py`.
- Not tested: DeepSeek (no quota in UAE North) and Marketplace-billed models such as Mistral and Llama 4 (not purchasable on this subscription type).

Raw results: `eval/results/models/*.json`. Infra: `infra/modules/foundry.bicep`. Decision: [ADR 0014](adr/0014-microsoft-foundry-model-choice.md).
