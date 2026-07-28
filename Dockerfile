# syntax=docker/dockerfile:1.7
# =============================================================================
# AI Credit Intelligence Platform — Python application image (Phase 11, M2)
# =============================================================================
# One multi-stage source produces three role images via build targets, all
# sharing the same dependency layer for fast rebuilds and cache reuse:
#
#   docker build --target backend   -t ai-credit-backend   .   (default target)
#   docker build --target worker     -t ai-credit-worker    .
#   docker build --target scheduler  -t ai-credit-scheduler .
#
# Build tools live only in the `builder` stage; the runtime stages copy a
# self-contained virtualenv, so the shipped image carries no compilers.
# All runtime stages run as an unprivileged user.
# -----------------------------------------------------------------------------

# ----------------------------- base ------------------------------------------
FROM python:3.13-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# ----------------------------- builder ---------------------------------------
# Compiles/collects all Python dependencies into an isolated virtualenv.
FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv "$VIRTUAL_ENV"
COPY requirements.txt ./
# Cache the (large) dependency install layer independently of app code so code
# changes do not trigger a full reinstall.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && pip install -r requirements.txt

# ----------------------------- runtime ---------------------------------------
# Common runtime: slim OS libs the ML/OCR stack needs at run time, the venv,
# the application code, and a non-root user.
FROM base AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libgomp1 \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

# Application code (see .dockerignore for what is excluded from the context).
COPY . .

# Unprivileged user; owns /app and a writable heartbeat/tmp location.
RUN useradd -m -u 10001 appuser \
    && mkdir -p /app/backend/storage \
    && chmod +x /app/deploy/entrypoint.sh \
    && chown -R appuser:appuser /app
USER appuser
ENV WORKER_HEARTBEAT_FILE=/tmp/worker-heartbeat \
    APP_ENV=production

# entrypoint applies DB migrations (RUN_MIGRATIONS=1) then execs the CMD.
ENTRYPOINT ["/app/deploy/entrypoint.sh"]

# ----------------------------- worker ----------------------------------------
FROM runtime AS worker
# Workers do not own schema; the backend/init job runs migrations.
ENV RUN_MIGRATIONS=0
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -m backend.app.workers.healthcheck --max-age 60 || exit 1
CMD ["python", "-m", "backend.app.workers.worker"]

# ----------------------------- scheduler -------------------------------------
FROM runtime AS scheduler
ENV RUN_MIGRATIONS=0
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -m backend.app.workers.healthcheck --max-age 120 || exit 1
CMD ["python", "-m", "backend.app.workers.scheduler"]

# ----------------------------- backend (DEFAULT — keep last) -----------------
# The final stage is Docker's default target, so a bare `docker build .`
# (and the existing compose `build: .`) produces the API server image.
FROM runtime AS backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/livez || exit 1
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
