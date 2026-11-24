"""FastAPI application: chat (JSON + SSE streaming), review queue, admin, health."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from gov_copilot import __version__
from gov_copilot.agent.orchestrator import Copilot
from gov_copilot.agent.review_queue import ReviewItem, ReviewQueue, ReviewStatus
from gov_copilot.agent.schemas import AgentResult
from gov_copilot.api.auth import Role, User, require
from gov_copilot.config import get_settings

FRONTEND = Path(__file__).resolve().parents[3] / "frontend"


def _rate_key(request: Request) -> str:
    user = getattr(request.state, "user", None)
    return f"user:{user.oid}" if user else get_remote_address(request)


limiter = Limiter(key_func=_rate_key)


class Health(BaseModel):
    status: str
    version: str
    prompt_version: str
    llm_provider: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


class ReviewDecision(BaseModel):
    approve: bool
    final_answer: str | None = Field(default=None, max_length=4000)


def build_copilot() -> Copilot:
    from gov_copilot.guardrails_azure import make_guardrails
    from gov_copilot.llm.clients import make_client
    from gov_copilot.retrieval.retriever import HybridRetriever

    s = get_settings()
    return Copilot(
        s, make_client(s), HybridRetriever(s), ReviewQueue(s.review_db_path), make_guardrails(s)
    )


def create_app(copilot: Copilot | None = None) -> FastAPI:
    s = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        from gov_copilot.observability import setup_telemetry

        setup_telemetry(app)
        app.state.copilot = copilot or build_copilot()
        yield

    app = FastAPI(title="Gov Policy Copilot", version=__version__, lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    def cp(request: Request) -> Copilot:
        return request.app.state.copilot  # type: ignore[no-any-return]

    @app.get("/healthz", response_model=Health)
    async def healthz() -> Health:
        return Health(
            status="ok",
            version=__version__,
            prompt_version=s.prompt_version,
            llm_provider=s.llm_provider.value,
        )

    @app.get("/api/config")
    async def public_config() -> dict[str, object]:
        """Non-secret config the SPA needs for MSAL login."""
        return {
            "authEnabled": s.auth_enabled,
            "tenantId": s.entra_tenant_id,
            "clientId": s.entra_spa_client_id,
            "apiScope": f"{s.entra_api_audience}/access_as_user",
        }

    @app.post("/api/chat", response_model=AgentResult)
    @limiter.limit(s.rate_limit)
    async def chat(
        request: Request,
        body: ChatRequest,
        user: Annotated[User, Depends(require(Role.VIEWER))],
    ) -> AgentResult:
        return await cp(request).ask(body.question, user=user.oid)

    @app.post("/api/chat/stream")
    @limiter.limit(s.rate_limit)
    async def chat_stream(
        request: Request,
        body: ChatRequest,
        user: Annotated[User, Depends(require(Role.VIEWER))],
    ) -> EventSourceResponse:
        async def events() -> AsyncIterator[dict[str, str]]:
            async for ev in cp(request).stream(body.question, user=user.oid):
                yield {"event": ev["type"], "data": json.dumps(ev, ensure_ascii=False)}

        return EventSourceResponse(events())

    @app.get("/api/reviews", response_model=list[ReviewItem])
    async def list_reviews(
        request: Request,
        _: Annotated[User, Depends(require(Role.REVIEWER))],
        status: ReviewStatus | None = None,
    ) -> list[ReviewItem]:
        return await cp(request).tools.queue.list(status)

    @app.post("/api/reviews/{review_id}", response_model=ReviewItem)
    async def decide_review(
        request: Request,
        review_id: str,
        body: ReviewDecision,
        user: Annotated[User, Depends(require(Role.REVIEWER))],
    ) -> ReviewItem:
        item = await cp(request).tools.queue.decide(
            review_id, approve=body.approve, reviewer=user.oid, final_answer=body.final_answer
        )
        if item is None:
            raise HTTPException(404, "Review not found")
        return item

    @app.get("/api/admin/stats")
    async def admin_stats(
        request: Request, _: Annotated[User, Depends(require(Role.ADMIN))]
    ) -> dict[str, object]:
        items = await cp(request).tools.queue.list()
        return {
            "model": cp(request).model,
            "prompt_version": s.prompt_version,
            "reranker": s.reranker.value,
            "reviews": {st.value: sum(i.status is st for i in items) for st in ReviewStatus},
        }

    @app.get("/me")
    async def me(user: Annotated[User, Depends(require(Role.VIEWER))]) -> dict[str, object]:
        return {"name": user.name, "roles": sorted(r.value for r in user.roles)}

    if FRONTEND.exists():
        app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

        @app.get("/", include_in_schema=False)
        async def index() -> FileResponse:
            return FileResponse(FRONTEND / "index.html")

    return app


app = create_app()
