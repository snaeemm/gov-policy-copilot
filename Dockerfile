# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/snaeemm/gov-policy-copilot" \
      org.opencontainers.image.description="Gov Policy Copilot - bilingual RAG over public UAE policy documents" \
      org.opencontainers.image.licenses="MIT"
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build --chown=app /app /app
COPY --chown=app prompts ./prompts
COPY --chown=app frontend ./frontend
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 APP_ENV=prod REVIEW_DB_PATH=/tmp/reviews.db
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["uvicorn", "gov_copilot.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
