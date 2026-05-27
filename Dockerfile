# ENIAK backend image — used by Railway and any container host.
# Multi-stage build keeps the runtime layer small.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Copy workspace manifests first for better layer caching.
COPY pyproject.toml uv.lock* ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/eniak-evidence/pyproject.toml packages/eniak-evidence/pyproject.toml
COPY packages/eniak-radar/pyproject.toml packages/eniak-radar/pyproject.toml
COPY packages/eniak-orchestrator/pyproject.toml packages/eniak-orchestrator/pyproject.toml
COPY packages/eniak-writer/pyproject.toml packages/eniak-writer/pyproject.toml
COPY packages/eniak-publisher/pyproject.toml packages/eniak-publisher/pyproject.toml

# Source code.
COPY apps/api apps/api
COPY packages packages

# Sync prod deps for all workspace members. Skip dev extras in the image.
ENV UV_LINK_MODE=copy
RUN uv sync --frozen --no-dev --all-packages 2>/dev/null || uv sync --no-dev --all-packages

# ---------- runtime ----------

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    ENIAK_ENV=production

WORKDIR /app
RUN groupadd -r eniak && useradd -r -g eniak eniak
COPY --from=builder --chown=eniak:eniak /app /app
USER eniak

EXPOSE 8000
# Use shell form so $PORT (injected by Railway / Fly / etc.) expands.
CMD uvicorn eniak_api.app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers
