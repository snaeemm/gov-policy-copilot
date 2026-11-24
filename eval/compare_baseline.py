"""Compare an eval run against a baseline and flag regressions (drift).

Usage: uv run python eval/compare_baseline.py [--current PATH] [--baseline PATH] [--tolerances PATH]
Exit code 1 and writes eval/results/drift-report.md when any metric regresses beyond tolerance.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_BASELINE = ROOT / "results" / "baseline-v2-6docs.json"


def compare(
    current: dict[str, float], baseline: dict[str, float], tolerances: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return one row per checked metric with a `regressed` flag."""
    rows: list[dict[str, Any]] = []
    for metric, rule in tolerances.items():
        if metric.startswith("_") or metric not in current or metric not in baseline:
            continue
        cur, base = float(current[metric]), float(baseline[metric])
        regressed = False
        if "max_drop" in rule:
            regressed = (base - cur) > float(rule["max_drop"]) + 1e-9
            limit = f"drop ≤ {rule['max_drop']}"
        elif "max_increase_pct" in rule:
            allowed = base * (1 + float(rule["max_increase_pct"]) / 100)
            regressed = cur > allowed + 1e-12
            limit = f"increase ≤ {rule['max_increase_pct']}%"
        else:
            continue
        rows.append(
            {
                "metric": metric,
                "baseline": base,
                "current": cur,
                "limit": limit,
                "regressed": regressed,
            }
        )
    return rows


def render(rows: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    bad = [r for r in rows if r["regressed"]]
    lines = [
        f"## Eval drift report: {'❌ regression detected' if bad else '✅ no regression'}",
        "",
        f"Model `{meta.get('model')}` · prompt `{meta.get('prompt_version')}` · "
        f"sample {meta.get('n_golden')} golden / {meta.get('n_redteam')} red-team",
        "",
        "| metric | baseline | current | tolerance | status |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        status = "❌ regressed" if r["regressed"] else "ok"
        lines.append(
            f"| {r['metric']} | {r['baseline']:.4g} | {r['current']:.4g} "
            f"| {r['limit']} | {status} |"
        )
    lines += [
        "",
        "Small samples are noisy: confirm with a full run (`cd` workflow, full_eval=true).",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", default=str(ROOT / "results" / "latest.json"))
    ap.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    ap.add_argument("--tolerances", default=str(ROOT / "drift.json"))
    ap.add_argument("--report", default=str(ROOT / "results" / "drift-report.md"))
    a = ap.parse_args(argv)
    cur = json.loads(Path(a.current).read_text())
    base = json.loads(Path(a.baseline).read_text())
    tol = json.loads(Path(a.tolerances).read_text())
    rows = compare(cur["metrics"], base["metrics"], tol)
    report = render(rows, cur)
    Path(a.report).write_text(report, encoding="utf-8")
    print(report)
    return 1 if any(r["regressed"] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
