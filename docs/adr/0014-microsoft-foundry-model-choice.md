# ADR-0014: Microsoft Foundry for model comparison and an Agent Service baseline

- Status: Accepted (2026-11-28)
- Related: ADR-0004 (deterministic orchestration), ADR-0006 (LLM provider abstraction),
  ADR-0007 (model and residency), ADR-0010 (eval gate)

## Context
The copilot was built on one model (Azure OpenAI gpt-5-mini) and chosen without a measured
comparison. Enterprise teams increasingly standardise on **Microsoft Foundry** (formerly Azure AI
Foundry): one resource and project that exposes OpenAI, Microsoft (Phi), Meta (Llama), Mistral,
DeepSeek and other models behind the same keyless API, plus Foundry Agent Service, evaluations
and tracing. We want to (1) pick the chat model from evidence, not habit, and (2) check whether a
managed Foundry agent could replace the custom Semantic Kernel pipeline.

## Decision
- **Provision a Foundry resource (`kind: AIServices`, `allowProjectManagement`) and a project** in
  UAE North with Bicep (`infra/modules/foundry.bicep`, `deployFoundry` in `main.bicep`). Local auth
  is disabled; the app identity, CI identity and developer get **Azure AI User** only.
- **Deploy a comparison catalog** as pay-per-token Global Standard deployments (no idle cost):
  gpt-5-mini, gpt-5-nano, gpt-5.4-mini, Phi-4, Llama-3.3-70B-Instruct.
- **Add a `foundry` LLM provider** (`LLM_PROVIDER=foundry`, `FOUNDRY_CHAT_DEPLOYMENT=<model>`).
  Only the chat model moves; **embeddings stay on the Azure OpenAI deployment that built the
  index**, so switching models never requires re-indexing.
- **Compare models with the existing eval harness** (`eval/compare_models.py`): same index,
  prompts, golden + red-team sets and the **same fixed judge**, so only the chat model varies.
  Results in [model-comparison.md](../model-comparison.md).
- **Build the same task as a Foundry Agent Service prompt agent** (`scripts/foundry_agent.py`)
  using the Azure AI Search tool over the same index through a keyless project connection, and
  score it with the same judge.
- **Production stays on gpt-5-mini through the custom pipeline** unless the comparison shows a
  model that passes the eval gate at lower cost; the gate decides, not preference.

## Alternatives considered
| Option | Why not (here) |
|---|---|
| Keep separate Azure OpenAI only | No access to non-OpenAI models or Agent Service; comparisons would need extra accounts and keys. |
| Replace the pipeline with Foundry Agent Service | Fast to build, but loses fail-closed Prompt Shields/Content Safety, PII masking before the LLM, a measurable groundedness threshold with human escalation, and per-request audit records (see comparison). Kept as a baseline. |
| Hub-based (classic) AI Foundry project + ML workspace | Older model; needs a hub, storage and Key Vault. The new project-on-AIServices model is simpler and keyless. |
| Serverless Marketplace models (Mistral, Llama 4) | Marketplace billing cannot be purchased on this subscription type; DeepSeek has no quota in UAE North. Documented, not hidden. |

## Consequences
- + Model choice is now an evidence-based, repeatable decision (one command re-runs it).
- + Switching the production model is a config change gated by the same evaluation.
- + Agent Service baseline shows clearly what the custom orchestration buys.
- − Global Standard deployments may process prompts outside UAE North (same as gpt-5-mini today;
  see ADR-0007 and the PDPL note). Index, documents and logs stay in UAE North.
- − Non-OpenAI models on this subscription are capped at 1K tokens/min by the service, so their
  full-pipeline rows are pending a pay-as-you-go subscription.
