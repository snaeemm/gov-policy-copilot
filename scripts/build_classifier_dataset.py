"""Build the bilingual (EN/AR) query-routing dataset for the fine-tuned classifier.

Labels: charter | international_policy | ethics | data_protection | out_of_scope

Sources
- corpus:   gpt-5-mini writes realistic user questions for every indexed chunk, in the chunk's
            language and in the other language (cross-lingual routing).
- synthetic_topic: data-protection (PDPL-style) questions from topic areas - the PDPL itself
            is not indexed (download blocked), so these come from topic prompts, not the text.
- synthetic_oos: generic out-of-scope questions (cooking, sports, coding, travel, ...).
- golden / redteam: the evaluation sets, placed ONLY in the test split (no leakage).

Usage: uv run python scripts/build_classifier_dataset.py
"""

import asyncio
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from gov_copilot.agent.orchestrator import completion_kwargs
from gov_copilot.ingestion.chunker import chunk_markdown
from gov_copilot.ingestion.text import detect_language, normalize_arabic
from gov_copilot.llm.clients import chat_model, make_client
from gov_copilot.models import SourceDocument

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "classifier"
SEED = 42
LABELS = ["charter", "international_policy", "ethics", "data_protection", "out_of_scope"]
DOC_LABEL = {
    "ai-charter": "charter",
    "ai-policy": "international_policy",
    "ai-ethics": "ethics",
    "pdpl": "data_protection",
}
REDTEAM_TO_OOS = {"jailbreak", "prompt_injection", "out_of_scope", "harmful"}

CHUNK_PROMPT = """You create training data for a query router of a UAE government policy assistant.
Below is a passage from "{title}". Write realistic questions that a citizen, civil servant or
journalist might type, which this passage would help answer. Vary style: short keyword
queries, full questions, informal phrasing. Do not copy sentences verbatim.
Return JSON: {{"en": [3 English questions], "ar": [3 Modern Standard Arabic questions]}}

PASSAGE:
{text}"""

TOPIC_PROMPT = """Write {n} diverse, realistic user questions in {lang} about UAE federal personal
data protection law (Federal Decree-Law No. 45 of 2021, PDPL). Cover: consent, data subject
rights (access, correction, erasure, objection), data breach notification, cross-border data
transfer, data protection officer, sensitive data, controller/processor duties, penalties,
scope and exemptions. Mix short keyword queries and full questions.
Return JSON: {{"questions": [...]}}"""

OOS_PROMPT = """Write {n} diverse, realistic questions in {lang} that someone might type into a chat
box but that are NOT about UAE government policy, law, AI governance or data protection.
Topics: cooking, sports, programming help, travel and tourism, shopping, personal finance,
health tips, entertainment, weather, maths homework, UAE trivia unrelated to policy (malls,
restaurants, beaches). Include a few that mention "AI" or "UAE" casually but are still
off-topic (e.g. "best AI photo editor app", "UAE national day fireworks timing").
Return JSON: {{"questions": [...]}}"""


def norm_key(text: str) -> str:
    t = normalize_arabic(text).lower()
    t = re.sub(r"[^\w\s]", "", t)
    return hashlib.sha1(re.sub(r"\s+", " ", t).strip().encode()).hexdigest()  # noqa: S324


def label_for(doc_id: str) -> str:
    for prefix, label in DOC_LABEL.items():
        if doc_id.startswith(prefix):
            return label
    raise ValueError(doc_id)


class Gen:
    def __init__(self) -> None:
        self.client = make_client()
        self.model = chat_model()
        self.kw = completion_kwargs(self.model)
        self.sem = asyncio.Semaphore(6)
        self.tokens = [0, 0]

    async def json(self, prompt: str) -> dict[str, Any]:
        async with self.sem:
            for _ in range(3):
                try:
                    r = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                        **self.kw,
                    )
                    if r.usage:
                        self.tokens[0] += r.usage.prompt_tokens
                        self.tokens[1] += r.usage.completion_tokens
                    data: dict[str, Any] = json.loads(r.choices[0].message.content or "{}")
                    return data
                except Exception:
                    await asyncio.sleep(2)
            return {}


async def generate() -> list[dict[str, Any]]:
    manifest = json.loads((ROOT / "data/manifest.json").read_text())
    docs = [SourceDocument(**d) for d in manifest["documents"]]
    gen = Gen()
    rows: list[dict[str, Any]] = []

    async def from_chunk(doc: SourceDocument, text: str) -> None:
        data = await gen.json(CHUNK_PROMPT.format(title=doc.title, text=text[:2500]))
        for lang in ("en", "ar"):
            for q in data.get(lang, [])[:3]:
                if isinstance(q, str) and len(q.strip()) > 5:
                    rows.append(
                        {
                            "text": q.strip(),
                            "label": label_for(doc.doc_id),
                            "language": lang,
                            "source": f"corpus:{doc.doc_id}",
                        }
                    )

    tasks = []
    for doc in docs:
        cache = ROOT / "data/processed" / f"{Path(doc.file).stem}.layout.json"
        if not cache.exists():
            continue
        md = json.loads(cache.read_text())["markdown"]
        for c in chunk_markdown(md, doc):
            if len(c.content) > 120:
                tasks.append(from_chunk(doc, c.content))

    async def topic(prompt: str, n: int, lang: str, label: str, source: str) -> None:
        data = await gen.json(
            prompt.format(n=n, lang="English" if lang == "en" else "Modern Standard Arabic")
        )
        for q in data.get("questions", [])[:n]:
            if isinstance(q, str) and len(q.strip()) > 5:
                rows.append({"text": q.strip(), "label": label, "language": lang, "source": source})

    for lang in ("en", "ar"):
        tasks += [
            topic(TOPIC_PROMPT, 15, lang, "data_protection", "synthetic_topic") for _ in range(3)
        ]
        tasks += [topic(OOS_PROMPT, 25, lang, "out_of_scope", "synthetic_oos") for _ in range(3)]
    await asyncio.gather(*tasks)
    cost = gen.tokens[0] / 1e6 * 0.25 + gen.tokens[1] / 1e6 * 2.0
    print(f"LLM tokens in/out: {gen.tokens}  ~${cost:.3f}")
    return rows


def eval_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in (ROOT / "eval/golden.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            g = json.loads(line)
            rows.append(
                {
                    "text": g["question"],
                    "label": label_for(g["expected_doc_ids"][0]),
                    "language": g["language"],
                    "source": "golden",
                }
            )
    for line in (ROOT / "eval/redteam.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r["attack_type"] in REDTEAM_TO_OOS:
                rows.append(
                    {
                        "text": r["question"],
                        "label": "out_of_scope",
                        "language": r["language"],
                        "source": "redteam",
                    }
                )
    return rows


def split(
    rows: list[dict[str, Any]], held_out: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(SEED)
    held_keys = {norm_key(r["text"]) for r in held_out}
    seen: set[str] = set()
    uniq = []
    for r in rows:
        k = norm_key(r["text"])
        if k in seen or k in held_keys:
            continue
        seen.add(k)
        r["language"] = "ar" if detect_language(r["text"]) == "ar" else "en"
        uniq.append(r)
    strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in uniq:
        strata[(r["label"], r["language"])].append(r)
    out: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}
    for items in strata.values():
        rng.shuffle(items)
        n = len(items)
        n_val, n_test = round(n * 0.15), round(n * 0.15)
        out["val"] += items[:n_val]
        out["test"] += items[n_val : n_val + n_test]
        out["train"] += items[n_val + n_test :]
    out["test"] += held_out
    for k in out:
        rng.shuffle(out[k])
    return out


def main() -> None:
    rows = asyncio.run(generate())
    parts = split(rows, eval_rows())
    OUT.mkdir(parents=True, exist_ok=True)
    stats: dict[str, Any] = {}
    for name, items in parts.items():
        with (OUT / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for i, r in enumerate(items):
                f.write(json.dumps({"id": f"{name}-{i:05d}", **r}, ensure_ascii=False) + "\n")
        stats[name] = {
            "n": len(items),
            "by_label_language": dict(Counter(f"{r['label']}/{r['language']}" for r in items)),
            "by_source": dict(Counter(r["source"].split(":")[0] for r in items)),
        }
    (OUT / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    print(json.dumps({k: v["n"] for k, v in stats.items()}))


if __name__ == "__main__":
    main()
