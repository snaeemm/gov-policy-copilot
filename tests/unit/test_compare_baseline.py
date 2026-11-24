import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "compare_baseline", ROOT / "eval" / "compare_baseline.py"
)
assert spec and spec.loader
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)

TOL = json.loads((ROOT / "eval" / "drift.json").read_text())
BASE = {
    "groundedness": 0.95,
    "answer_rate": 0.90,
    "redteam_pass_rate": 1.0,
    "latency_p95_s": 10.0,
    "cost_per_query_usd": 0.002,
}


def _regressed(cur: dict[str, float]) -> set[str]:
    return {r["metric"] for r in cb.compare(cur, BASE, TOL) if r["regressed"]}


def test_no_regression_within_tolerance() -> None:
    cur = dict(
        BASE, groundedness=0.91, answer_rate=0.81, latency_p95_s=14.9, cost_per_query_usd=0.0029
    )
    assert _regressed(cur) == set()


def test_detects_each_kind_of_regression() -> None:
    cur = dict(
        BASE,
        groundedness=0.89,
        answer_rate=0.79,
        redteam_pass_rate=0.96,
        latency_p95_s=15.1,
        cost_per_query_usd=0.0031,
    )
    assert _regressed(cur) == set(BASE)


def test_improvements_never_regress() -> None:
    cur = dict(BASE, groundedness=1.0, latency_p95_s=5.0, cost_per_query_usd=0.001)
    assert _regressed(cur) == set()


def test_main_writes_report_and_exit_code(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    cur = tmp_path / "cur.json"
    report = tmp_path / "r.md"
    base.write_text(json.dumps({"metrics": BASE}))
    cur.write_text(json.dumps({"metrics": dict(BASE, redteam_pass_rate=0.9), "model": "m"}))
    rc = cb.main(["--current", str(cur), "--baseline", str(base), "--report", str(report)])
    assert rc == 1
    assert "regression detected" in report.read_text()
    cur.write_text(json.dumps({"metrics": BASE}))
    assert cb.main(["--current", str(cur), "--baseline", str(base), "--report", str(report)]) == 0
