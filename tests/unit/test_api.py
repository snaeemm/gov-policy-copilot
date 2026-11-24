from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from gov_copilot.agent.review_queue import ReviewQueue
from gov_copilot.agent.schemas import AgentResult, Outcome
from gov_copilot.api.auth import Role, User, user_from_claims
from gov_copilot.api.main import create_app
from gov_copilot.config import get_settings


class FakeTools:
    def __init__(self) -> None:
        self.queue = ReviewQueue(":memory:")


class FakeCopilot:
    model = "fake-model"

    def __init__(self) -> None:
        self.tools = FakeTools()

    def _result(self, q: str) -> AgentResult:
        return AgentResult(
            request_id="r1",
            question=q,
            answer="Answer [1]",
            language="en",
            outcome=Outcome.ANSWERED,
            prompt_version="v1",
            model=self.model,
        )

    async def stream(self, question: str, user: str = "") -> AsyncIterator[dict[str, Any]]:
        yield {"type": "status", "step": "planning"}
        yield {"type": "token", "text": "Answer"}
        yield {"type": "final", "result": self._result(question).model_dump()}

    async def ask(self, question: str, user: str = "") -> AgentResult:
        return self._result(question)


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    with TestClient(create_app(FakeCopilot())) as c:  # type: ignore[arg-type]
        yield c  # type: ignore[misc]


def test_chat_json(client: TestClient) -> None:
    r = client.post("/api/chat", json={"question": "What is the charter?"})
    assert r.status_code == 200
    assert r.json()["outcome"] == "answered"


def test_chat_validation(client: TestClient) -> None:
    assert client.post("/api/chat", json={"question": ""}).status_code == 422


def test_chat_stream_emits_events(client: TestClient) -> None:
    r = client.post("/api/chat/stream", json={"question": "hello there"})
    assert r.status_code == 200
    assert "event: status" in r.text and "event: final" in r.text


def test_reviews_and_admin_available_to_dev_admin(client: TestClient) -> None:
    assert client.get("/api/reviews").json() == []
    assert client.get("/api/admin/stats").json()["model"] == "fake-model"


def test_auth_enabled_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    try:
        with TestClient(create_app(FakeCopilot())) as c:  # type: ignore[arg-type]
            assert c.post("/api/chat", json={"question": "hi there"}).status_code == 401
            assert c.get("/healthz").status_code == 200
    finally:
        get_settings.cache_clear()


def test_role_hierarchy() -> None:
    admin = User(oid="a", name="", roles={Role.ADMIN})
    viewer = user_from_claims({"oid": "v", "roles": ["Copilot.Viewer", "Unknown.Role"]})
    assert admin.has(Role.REVIEWER) and admin.has(Role.VIEWER)
    assert viewer.has(Role.VIEWER) and not viewer.has(Role.REVIEWER)
    assert viewer.roles == {Role.VIEWER}
