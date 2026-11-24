"""Offline evaluation + CI quality gate.

Metrics
- retrieval_recall_at_5: share of golden questions where an expected document is in the top-5 hits
- groundedness:          Azure AI Evaluation GroundednessEvaluator (1-5, normalized to 0-1)
- relevance:             Azure AI Evaluation RelevanceEvaluator (1-5, normalized to 0-1)
- citation_accuracy:     share of emitted citations that point to an expected document
- answer_rate:           share of golden questions answered (not escalated / not_found)
- key_fact_recall:       share of reference key facts present in answers (informational)
- redteam_pass_rate:     share of adversarial prompts with an acceptable outcome
- latency p50/p95, cost per query

Usage: uv run python eval/run_eval.py [--limit N] [--gate]
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from gov_copilot.agent.orchestrator import Copilot
from gov_copilot.agent.review_queue import ReviewQueue
from gov_copilot.agent.schemas import AgentResult
from gov_copilot.config import get_settings
from gov_copilot.guardrails_azure import make_guardrails
from gov_copilot.ingestion.text import normalize_arabic
from gov_copilot.llm.clients import make_client
from gov_copilot.retrieval.retriever import HybridRetriever

ROOT = Path(__file__).resolve().parent
CONCURRENCY = 4


def load(name: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = max(0, min(len(values) - 1, round(q * (len(values) - 1))))
    return values[k]


def norm(text: str) -> str:
    return normalize_arabic(text).lower()


def make_judges() -> tuple[Any, Any]:
    from azure.ai.evaluation import (
        AzureOpenAIModelConfiguration,
        GroundednessEvaluator,
        RelevanceEvaluator,
    )
    from azure.identity import DefaultAzureCredential

    s = get_settings()
    cfg = AzureOpenAIModelConfiguration(
        azure_endpoint=s.azure_openai_endpoint,
        azure_deployment=s.azure_openai_chat_deployment,
        api_version="2025-04-01-preview",
    )
    cred = DefaultAzureCredential()
    reasoning = s.azure_openai_chat_deployment.startswith(("gpt-5", "o"))
    return (
        GroundednessEvaluator(cfg, credential=cred, is_reasoning_model=reasoning),
        RelevanceEvaluator(cfg, credential=cred, is_reasoning_model=reasoning),
    )


async def main(limit: int | None, gate: bool) -> int:
    s = get_settings()
    copilot = Copilot(
        s, make_client(s), HybridRetriever(s), ReviewQueue(":memory:"), make_guardrails(s)
    )
    retriever = HybridRetriever(s)
    golden = load("golden.jsonl")[:limit]
    redteam = load("redteam.jsonl")[:limit]
    ground_eval, rel_eval = make_judges()
    sem = asyncio.Semaphore(CONCURRENCY)

    async def run_golden(item: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            hits = await retriever.retrieve(item["question"], top_n=5)
            t0 = time.perf_counter()
            r: AgentResult = await copilot.ask(item["question"], user="eval")
            wall = time.perf_counter() - t0
            row: dict[str, Any] = {
                "id": item["id"],
                "language": item["language"],
                "category": item.get("category"),
                "outcome": r.outcome.value,
                "recall_hit": any(h.doc_id in item["expected_doc_ids"] for h in hits),
                "latency_s": wall,
                "cost_usd": r.usage.cost_usd,
                "answer": r.answer,
            }
            if r.outcome.value == "answered":
                cites = [c.doc_id in item["expected_doc_ids"] for c in r.citations]
                row["citation_acc"] = sum(cites) / len(cites) if cites else 0.0
                facts = item.get("key_facts", [])
                row["key_fact_recall"] = (
                    sum(norm(f) in norm(r.answer) for f in facts) / len(facts) if facts else None
                )
                ctx = "\n\n".join(r.contexts)
                g = await asyncio.to_thread(
                    ground_eval, query=item["question"], response=r.answer, context=ctx
                )
                rel = await asyncio.to_thread(rel_eval, query=item["question"], response=r.answer)
                row["groundedness"] = (float(g["groundedness"]) - 1) / 4
                row["relevance"] = (float(rel["relevance"]) - 1) / 4
            print(
                f"  {item['id']} {row['outcome']:<12} recall={row['recall_hit']} {wall:.1f}s",
                flush=True,
            )
            return row

    async def run_red(item: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            r = await copilot.ask(item["question"], user="eval-redteam")
            ok = r.outcome.value in item["expected_outcomes"]
            print(
                f"  {item['id']} {item['attack_type']:<16} {r.outcome.value:<12} "
                f"{'PASS' if ok else 'FAIL'}",
                flush=True,
            )
            return {
                "id": item["id"],
                "attack_type": item["attack_type"],
                "outcome": r.outcome.value,
                "pass": ok,
            }

    print(f"Golden set: {len(golden)} questions")
    g_rows = await asyncio.gather(*(run_golden(i) for i in golden))
    print(f"Red-team set: {len(redteam)} prompts")
    r_rows = await asyncio.gather(*(run_red(i) for i in redteam))

    answered = [r for r in g_rows if r["outcome"] == "answered"]

    def mean(key: str, rows: list[dict[str, Any]]) -> float:
        vals = [r[key] for r in rows if r.get(key) is not None]
        return round(statistics.mean(vals), 4) if vals else 0.0

    lat = [r["latency_s"] for r in g_rows]
    metrics = {
        "retrieval_recall_at_5": round(sum(r["recall_hit"] for r in g_rows) / len(g_rows), 4),
        "groundedness": mean("groundedness", answered),
        "relevance": mean("relevance", answered),
        "citation_accuracy": mean("citation_acc", answered),
        "answer_rate": round(len(answered) / len(g_rows), 4),
        "key_fact_recall": mean("key_fact_recall", answered),
        "redteam_pass_rate": round(sum(r["pass"] for r in r_rows) / max(1, len(r_rows)), 4),
        "latency_p50_s": round(pct(lat, 0.5), 2),
        "latency_p95_s": round(pct(lat, 0.95), 2),
        "cost_per_query_usd": round(statistics.mean(r["cost_usd"] for r in g_rows), 6),
    }
    by_lang = {
        lang: {
            "n": len(rows := [r for r in g_rows if r["language"] == lang]),
            "recall_at_5": round(sum(r["recall_hit"] for r in rows) / max(1, len(rows)), 3),
            "answer_rate": round(
                sum(r["outcome"] == "answered" for r in rows) / max(1, len(rows)), 3
            ),
        }
        for lang in ("en", "ar")
    }
    thresholds = json.loads((ROOT / "thresholds.json").read_text())
    failures = []
    for k, rule in thresholds.items():
        if k.startswith("_"):
            continue
        v = metrics[k]
        if "min" in rule and v < rule["min"]:
            failures.append(f"{k}={v} < {rule['min']}")
        if "max" in rule and v > rule["max"]:
            failures.append(f"{k}={v} > {rule['max']}")

    report = {
        "model": copilot.model,
        "prompt_version": s.prompt_version,
        "reranker": s.reranker.value,
        "n_golden": len(g_rows),
        "n_redteam": len(r_rows),
        "metrics": metrics,
        "by_language": by_lang,
        "gate": {"passed": not failures, "failures": failures},
        "redteam": r_rows,
        "golden": [{k: v for k, v in r.items() if k != "answer"} for r in g_rows],
    }
    out = ROOT / "results" / "latest.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        json.dumps({"metrics": metrics, "by_language": by_lang, "gate": report["gate"]}, indent=2)
    )
    if gate and failures:
        print("EVAL GATE FAILED - blocking deployment", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.limit, a.gate)))
