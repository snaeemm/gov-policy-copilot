"""FastAPI application entrypoint."""

from fastapi import FastAPI
from pydantic import BaseModel

from gov_copilot import __version__
from gov_copilot.config import get_settings


class Health(BaseModel):
    status: str
    version: str
    prompt_version: str
    llm_provider: str


def create_app() -> FastAPI:
    app = FastAPI(title="Gov Policy Copilot", version=__version__)

    @app.get("/healthz", response_model=Health)
    async def healthz() -> Health:
        s = get_settings()
        return Health(
            status="ok",
            version=__version__,
            prompt_version=s.prompt_version,
            llm_provider=s.llm_provider.value,
        )

    return app


app = create_app()
