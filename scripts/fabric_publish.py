"""Publish the Gold layer to Microsoft Fabric (OneLake lakehouse).

Gold tables (CSV, then loaded as Delta tables):
  documents     - one row per source document (manifest + DQ status)
  chunks        - one row per indexed chunk (metadata only, no vectors)
  eval_results  - latest evaluation metrics, one row per metric

Auth: interactive browser login with a Fabric-enabled (e.g. university) account.
Creates workspace `gov-policy-copilot` and lakehouse `gold` if missing.

    uv run python scripts/fabric_publish.py
"""

from __future__ import annotations

import csv
import io
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests
from azure.identity import InteractiveBrowserCredential, TokenCachePersistenceOptions
from azure.storage.filedatalake import DataLakeServiceClient

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.fabric.microsoft.com/v1"
ONELAKE = "https://onelake.dfs.fabric.microsoft.com"
WORKSPACE = "gov-policy-copilot"
LAKEHOUSE = "gold"
AZ_CLI_CLIENT = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"


cred = InteractiveBrowserCredential(
    client_id=AZ_CLI_CLIENT,
    tenant_id="organizations",
    redirect_uri="http://localhost:8400",
    cache_persistence_options=TokenCachePersistenceOptions(name="gov-copilot-fabric"),
    timeout=900,
)


def _h() -> dict[str, str]:
    tok = cred.get_token("https://api.fabric.microsoft.com/.default").token
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    r = requests.request(method, f"{API}{path}", headers=_h(), json=body, timeout=60)
    if r.status_code == 202 and "Location" in r.headers:  # long-running op
        loc = r.headers["Location"]
        for _ in range(60):
            time.sleep(3)
            s = requests.get(loc, headers=_h(), timeout=60)
            st = s.json().get("status") if s.content else None
            if st in ("Succeeded", "Failed") or (s.status_code == 200 and st is None):
                if st == "Failed":
                    sys.exit(f"Operation failed: {s.text}")
                res = requests.get(loc + "/result", headers=_h(), timeout=60)
                return res.json() if res.ok and res.content else None
        sys.exit("Timed out waiting for Fabric operation")
    if not r.ok:
        sys.exit(f"{method} {path} -> {r.status_code}: {r.text}")
    return r.json() if r.content else None


def ensure_workspace() -> str:
    for ws in _call("GET", "/workspaces")["value"]:
        if ws["displayName"] == WORKSPACE:
            return str(ws["id"])
    caps = _call("GET", "/capacities")["value"]
    active = [c for c in caps if c.get("state") == "Active"]
    body: dict[str, Any] = {"displayName": WORKSPACE}
    if active:
        body["capacityId"] = active[0]["id"]
    else:
        print("WARNING: no active Fabric capacity found - start the Fabric trial first.")
    return str(_call("POST", "/workspaces", body)["id"])


def ensure_lakehouse(ws: str) -> str:
    for it in _call("GET", f"/workspaces/{ws}/lakehouses")["value"]:
        if it["displayName"] == LAKEHOUSE:
            return str(it["id"])
    _call("POST", f"/workspaces/{ws}/lakehouses", {"displayName": LAKEHOUSE})
    for it in _call("GET", f"/workspaces/{ws}/lakehouses")["value"]:
        if it["displayName"] == LAKEHOUSE:
            return str(it["id"])
    sys.exit("Lakehouse not created")


def _csv(rows: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def build_tables() -> dict[str, list[dict[str, Any]]]:
    sys.path.insert(0, str(ROOT / "src"))
    from gov_copilot.ingestion.chunker import chunk_markdown, count_tokens
    from gov_copilot.models import SourceDocument

    manifest = json.loads((ROOT / "data/manifest.json").read_text())
    dq_path = ROOT / "data/processed/dq-report.json"
    dq = json.loads(dq_path.read_text()) if dq_path.exists() else {}

    documents: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    for d in manifest["documents"]:
        doc = SourceDocument(**d)
        layout = ROOT / "data/processed" / f"{Path(d['file']).stem}.layout.json"
        indexed = layout.exists()
        n = 0
        if indexed:
            md = json.loads(layout.read_text())["markdown"]
            for c in chunk_markdown(md, doc):
                n += 1
                chunks.append(
                    {
                        "chunk_id": c.id,
                        "doc_id": c.doc_id,
                        "language": c.language,
                        "section": c.section,
                        "page": c.page,
                        "chunk_index": c.chunk_index,
                        "tokens": count_tokens(c.content),
                        "classification": c.classification,
                        "content": c.content.replace("\n", " ")[:2000],
                    }
                )
        documents.append(
            {
                "doc_id": d["doc_id"],
                "title": d.get("title", ""),
                "language": d.get("language", ""),
                "publisher": d.get("publisher", ""),
                "year": d.get("year", ""),
                "source_url": d.get("source_url", ""),
                "classification": d.get("classification", "public"),
                "indexed": indexed,
                "chunk_count": n,
            }
        )

    ev = json.loads((ROOT / "eval/results/baseline-v2-6docs.json").read_text())
    eval_rows: list[dict[str, Any]] = [
        {
            "run": "baseline-v2-6docs",
            "model": ev.get("model", ""),
            "scope": "overall",
            "metric": k,
            "value": v,
        }
        for k, v in ev["metrics"].items()
        if isinstance(v, (int, float))
    ]
    for lang, m in (ev.get("by_language") or {}).items():
        if isinstance(m, dict):
            eval_rows += [
                {
                    "run": "baseline-v2-6docs",
                    "model": ev.get("model", ""),
                    "scope": lang,
                    "metric": k,
                    "value": v,
                }
                for k, v in m.items()
                if isinstance(v, (int, float))
            ]
    dq_rows = [
        {"check": k, "result": json.dumps(v) if not isinstance(v, (int, float, str)) else v}
        for k, v in (dq.get("by_check") or {}).items()
    ] or [{"check": "overall", "result": dq.get("passed", "")}]
    return {
        "documents": documents,
        "chunks": chunks,
        "eval_results": eval_rows,
        "dq_checks": dq_rows,
    }


def main() -> None:
    tables = build_tables()
    print({k: len(v) for k, v in tables.items()})
    ws = ensure_workspace()
    lh = ensure_lakehouse(ws)
    print(f"workspace={ws} lakehouse={lh}")

    dl = DataLakeServiceClient(ONELAKE, credential=cred)
    fs = dl.get_file_system_client(ws)
    for name, rows in tables.items():
        if not rows:
            continue
        path = f"{lh}/Files/gold/{name}.csv"
        fs.get_file_client(path).upload_data(_csv(rows), overwrite=True)
        print(f"uploaded {path}")
        _call(
            "POST",
            f"/workspaces/{ws}/lakehouses/{lh}/tables/{name}/load",
            {
                "relativePath": f"Files/gold/{name}.csv",
                "pathType": "File",
                "mode": "Overwrite",
                "formatOptions": {"format": "Csv", "header": True, "delimiter": ","},
            },
        )
        print(f"loaded Delta table {name}")

    out = ROOT / "docs/evidence/fabric-gold.md"
    out.write_text(
        "# Fabric Gold layer - evidence\n\n"
        f"Published {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} by `scripts/fabric_publish.py`.\n\n"
        f"- Workspace: `{WORKSPACE}` (`{ws}`)\n- Lakehouse: `{LAKEHOUSE}` (`{lh}`)\n\n"
        "| Delta table | Rows |\n|---|---|\n"
        + "".join(f"| `{k}` | {len(v)} |\n" for k, v in tables.items())
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
