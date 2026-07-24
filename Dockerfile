# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# AI Credit Intelligence Platform — production image (Phase 8, Milestone 11)
# Multi-stage build: a slim runtime with a non-root user, Alembic migrations on
# start, and a uvicorn server. Horizontally scalable (stateless app process).
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

WORKDIR /app

# System deps kept minimal; add build-essential only if wheels need compiling.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Run as an unprivileged user.
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Liveness/readiness are served by the app (/livez, /readyz, /healthz).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/livez || exit 1

# entrypoint applies DB migrations then launches the server.
COPY deploy/entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
