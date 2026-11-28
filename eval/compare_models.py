"""Side-by-side model comparison on Microsoft Foundry.

Runs the full pipeline (planner -> hybrid retrieval -> answer -> self-check -> guardrails) with each
Foundry model as the chat model, on the same golden + red-team sets. Everything else is held fixed:
same index, same prompts, same embeddings, and the SAME judge (Azure OpenAI gpt-5-mini) for
groundedness/relevance, so the scores are comparable.

Each model runs in its own process (settings are read from env) and writes
eval/results/models/<model>.json; this script then builds docs/model-comparison.md.

Usage:
  uv run --extra eval python eval/compare_models.py                 # all models
  uv run --extra eval python eval/compare_models.py --models Phi-4  # subset
  uv run --extra eval python eval/compare_models.py --report-only   # rebuild report from results
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "models"
DOC = ROOT.parent / "docs" / "model-comparison.md"

# USD per 1M tokens (input, output): Azure Global Standard list prices at time of writing.
# Low-quota models (20K tokens/min on this subscription) run one question at a time.
MODELS: dict[str, dict[str, Any]] = {
    "gpt-5-mini": {"family": "OpenAI", "price": (0.25, 2.00), "concurrency": 4},
    "gpt-5-nano": {"family": "OpenAI", "price": (0.05, 0.40), "concurrency": 1},
    "gpt-5.4-mini": {"family": "OpenAI", "price": (0.75, 4.50), "concurrency": 4},
    "Phi-4": {"family": "Microsoft (open weights)", "price": (0.125, 0.50), "concurrency": 1},
    "Llama-3.3-70B-Instruct": {
        "family": "Meta (open weights)",
        "price": (0.71, 0.71),
        "concurrency": 1,
    },
}


def run_model(name: str, limit: int | None) -> int:
    cfg = MODELS[name]
    env = {
        **os.environ,
        "LLM_PROVIDER": "foundry",
        "FOUNDRY_CHAT_DEPLOYMENT": name,
        "PRICE_INPUT_PER_M": str(cfg["price"][0]),
        "PRICE_OUTPUT_PER_M": str(cfg["price"][1]),
        "EVAL_CONCURRENCY": str(cfg["concurrency"]),
        "LLM_MAX_RETRIES": "20" if cfg["concurrency"] == 1 else "8",
    }
    cmd = [sys.executable, str(ROOT / "run_eval.py"), "--out", str(OUT / f"{name}.json")]
    if limit:
        cmd += ["--limit", str(limit)]
    print(f"\n=== {name} ===", flush=True)
    return subprocess.call(cmd, env=env)


def fmt(v: float, pct: bool = True) -> str:
    return f"{v * 100:.0f}%" if pct else f"{v:g}"


def build_report() -> str:
    rows = []
    for name, cfg in MODELS.items():
        f = OUT / f"{name}.json"
        if f.exists():
            rows.append((name, cfg, json.loads(f.read_text())))
    if not rows:
        raise SystemExit("no results yet")
    lines = [
        "# Model comparison on Microsoft Foundry",
        "",
        f"_Generated {date.today().isoformat()} by `eval/compare_models.py`._",
        "",
        "Same pipeline, same index, same prompts (v"
        + str(rows[0][2].get("prompt_version", "?")).lstrip("v")
        + "), same golden set "
        f"({rows[0][2]['n_golden']} EN/AR questions) and red-team set ({rows[0][2]['n_redteam']} "
        "prompts). Only the chat model changes. Groundedness and relevance are scored by one fixed "
        "judge (Azure OpenAI gpt-5-mini, Azure AI Evaluation SDK) so the numbers are comparable.",
        "",
        "| Model | Family | Grounded | Relevance | Citation acc. | Answer rate | Red-team pass "
        "| p50 latency | p95 latency | Cost / query | Eval gate |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, cfg, r in rows:
        m = r["metrics"]
        lines.append(
            f"| {name} | {cfg['family']} | {fmt(m['groundedness'])} | {fmt(m['relevance'])} "
            f"| {fmt(m['citation_accuracy'])} | {fmt(m['answer_rate'])} "
            f"| {fmt(m['redteam_pass_rate'])} | {m['latency_p50_s']}s | {m['latency_p95_s']}s "
            f"| ${m['cost_per_query_usd']:.5f} | {'pass' if r['gate']['passed'] else 'FAIL'} |"
        )
    lines += [
        "",
        "## By language (answer rate)",
        "",
        "| Model | English | Arabic |",
        "|---|---|---|",
    ]
    for name, _, r in rows:
        bl = r["by_language"]
        lines.append(
            f"| {name} | {fmt(bl['en']['answer_rate'])} | {fmt(bl['ar']['answer_rate'])} |"
        )
    agent = OUT / "foundry-agent.json"
    if agent.exists():
        a = json.loads(agent.read_text())
        am = a["metrics"]
        base = next((r for n, _, r in rows if n == "gpt-5-mini"), None)
        lines += [
            "",
            "## Custom pipeline vs Foundry Agent Service (same model, gpt-5-mini)",
            "",
            "The same task built as a managed **Foundry Agent Service** prompt agent "
            "(`scripts/foundry_agent.py`): instructions + the Azure AI Search tool over the same "
            "index through a keyless project connection. Scored with the same judge on the first "
            f"{a['n_golden']} golden questions.",
            "",
            "| | Custom pipeline (Semantic Kernel) | Foundry Agent Service |",
            "|---|---|---|",
        ]
        if base:
            bm = base["metrics"]
            lines += [
                f"| Groundedness | {fmt(bm['groundedness'])} | {fmt(am['groundedness'])} |",
                f"| Relevance | {fmt(bm['relevance'])} | {fmt(am['relevance'])} |",
                f"| Answer rate | {fmt(bm['answer_rate'])} | {fmt(am['answer_rate'])} |",
                f"| p50 / p95 latency | {bm['latency_p50_s']}s / {bm['latency_p95_s']}s "
                f"| {am['latency_p50_s']}s / {am['latency_p95_s']}s |",
            ]
        lines += [
            "| Retrieval | Hybrid (BM25 + vector, RRF), multi-query planner | Search tool, "
            "keyword (`simple`) on the free Search tier |",
            "| Safety | Prompt Shields, Content Safety, PII masking, classifier pre-filter | "
            "Foundry default content filters |",
            "| Grounding control | Self-check score, escalate below 0.7 to human review | "
            "Instructions only |",
            "| Audit | Per-request model, prompt version, cost, review queue | Foundry traces |",
            "| Effort to build | ~1,000 lines of Python | ~40 lines + portal |",
            "",
            "Takeaway: the managed agent is far faster to stand up and is a good prototyping and "
            "baseline tool; the custom pipeline keeps the controls a government deployment needs "
            "(fail-closed guardrails, measurable grounding threshold, human escalation, "
            "per-request audit). See ADR 0014.",
        ]
    lines += ["", "## Gate failures", ""]
    for name, _, r in rows:
        fails = r["gate"]["failures"]
        lines.append(f"- **{name}**: " + ("none" if not fails else "; ".join(fails)))
    lines += [
        "",
        "## Notes",
        "",
        "- Retrieval recall@5 is identical across models (retrieval does not use the chat model "
        "except for query planning), so it is not shown.",
        "- Answer rate counts questions the model answered and that passed the groundedness "
        "self-check; the rest were escalated to human review or refused.",
        "- **Phi-4 and Llama 3.3 70B are deployed in the Foundry project but could not run the "
        "pipeline here:** although the deployments show 20K tokens/min, the service enforces "
        "1K tokens and 1 request per minute for non-OpenAI models on this (free-tier) "
        "subscription, and one RAG prompt (8 retrieved chunks) is ~4-6K tokens. Both answered "
        "short smoke-test prompts (including Arabic). On a pay-as-you-go subscription, run "
        "`compare_models.py --models Phi-4 Llama-3.3-70B-Instruct` to fill in their rows.",
        "- gpt-5-nano is 4x cheaper but escalated 47 of 50 questions: the same model also runs "
        "the in-pipeline groundedness self-check, and nano scores its own drafts below the 0.7 "
        "threshold. Answers it did give were fully grounded. It is unsuitable as both answerer "
        "and verifier; a mixed setup (nano answers, a stronger model verifies) is a follow-up.",
        "- gpt-5-nano ran one question at a time after hitting its rate limit at concurrency 4.",
        "- The Foundry agent's 100% answer rate reflects that it has no escalation path, not "
        "better coverage.",
        "- Costs use Azure Global Standard list prices per 1M tokens, set in "
        "`eval/compare_models.py`.",
        "- Not tested: DeepSeek (no quota in UAE North) and Marketplace-billed models such as "
        "Mistral and Llama 4 (not purchasable on this subscription type).",
        "",
        "Raw results: `eval/results/models/*.json`. Infra: `infra/modules/foundry.bicep`. "
        "Decision: [ADR 0014](adr/0014-microsoft-foundry-model-choice.md).",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=list(MODELS))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not a.report_only:
        for name in a.models:
            if run_model(name, a.limit) != 0:
                print(f"{name}: eval run exited non-zero", file=sys.stderr)
    DOC.write_text(build_report(), encoding="utf-8")
    print(f"\nwrote {DOC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
