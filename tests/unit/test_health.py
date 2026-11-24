from fastapi.testclient import TestClient

from gov_copilot.api.main import create_app


def test_healthz() -> None:
    r = TestClient(create_app()).get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["prompt_version"]
