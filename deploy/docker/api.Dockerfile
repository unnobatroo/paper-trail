# api + worker images, context = repo root (see the compose file)
FROM ghcr.io/astral-sh/uv:0.11.2 AS uv
FROM python:3.12-slim AS base
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 papertrail && useradd --uid 10001 --gid 10001 --create-home papertrail
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY README.md LICENSE ./
RUN uv sync --frozen --no-dev && mkdir -p /app/data /app/model-cache && chown -R papertrail:papertrail /app/data /app/model-cache
USER papertrail
EXPOSE 8000
CMD ["uvicorn", "paper_trail.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips=*"]

FROM base AS api
COPY db ./db
# ops tools for the migrate service: import, gazetteer seed, checks
COPY scripts ./scripts

FROM base AS worker
USER root
RUN uv sync --frozen --no-dev --extra parsing --extra hungarian --extra ner
ARG HUSPACY_MODEL_URL
RUN if [ -n "$HUSPACY_MODEL_URL" ]; then uv pip install --python /app/.venv/bin/python "$HUSPACY_MODEL_URL"; fi
USER papertrail
CMD ["python", "-m", "paper_trail.worker"]
