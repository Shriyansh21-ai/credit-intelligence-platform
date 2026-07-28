# Configuration Guide

> Phase 11, Milestone 1 — Production Configuration System

The platform is configured entirely through the environment (12-Factor). There
is a single, typed, validated source of truth:
[`backend/app/core/settings.py`](../backend/app/core/settings.py). Every other
module reads configuration from it — there are no hardcoded secrets, database
URLs, or backend selections left in the codebase.

## Quick start

```bash
cp .env.example .env         # optional — the app runs zero-config without it
uvicorn backend.app.main:app --reload
```

With an empty environment the platform runs with safe local defaults: SQLite,
in-process cache/broker, local file storage, and a development secret. This is
the exact behaviour that existed before M1, so no local or CI flow changes.

## How configuration is loaded

1. Process environment variables (highest precedence).
2. A `.env` file in the working directory, if present.
3. The typed defaults declared in `AppSettings`.

Access it in code via the cached accessor:

```python
from backend.app.core.settings import get_settings

settings = get_settings()          # cached singleton
settings.database_url
settings.is_production              # profile helpers
settings.effective_jwt_secret      # JWT_SECRET_KEY or SECRET_KEY
```

Tests that mutate the environment call `reload_settings()` to re-read it.

## Profiles (`APP_ENV`)

| Profile        | Purpose                       | Validation |
|----------------|-------------------------------|------------|
| `development`  | Local dev (default)           | Warnings only |
| `testing`      | Automated tests               | Warnings only |
| `staging`      | Pre-production, prod-like      | **Fatal** on errors |
| `production`   | Production                    | **Fatal** on errors |

In `staging`/`production` the application **fails fast at startup**
(`ConfigurationError`) if any error-level validation issue is present. In
`development`/`testing` the same issues are logged as warnings so the
zero-config experience is preserved.

## Startup validation

On boot, [`core/startup.py`](../backend/app/core/startup.py) logs a non-secret
configuration summary and every validation finding. Error-level findings abort
startup under a prod-like profile. Rules include:

- **Insecure secrets** — `SECRET_KEY`, `JWT_SECRET_KEY`, or
  `CONNECTOR_MASTER_KEY` left at a well-known default value.
- **SQLite in production** — `DATABASE_URL` must be PostgreSQL in prod-like
  profiles.
- **Wildcard CORS with credentials** — rejected by browsers; flagged.
- **Half-configured backends** — e.g. `CACHE_BACKEND=redis` without
  `REDIS_URL`, `JOB_BROKER=kafka` without `KAFKA_BOOTSTRAP_SERVERS`,
  `STORAGE_BACKEND=azure` without a connection string, `PAYMENT_GATEWAY=stripe`
  without `STRIPE_API_KEY`, `MAIL_BACKEND=smtp` without `SMTP_HOST`.

Generate strong secrets with:

```bash
openssl rand -hex 32
```

## Reference

All variables, defaults, and notes live in
[`.env.example`](../.env.example). Summary by section:

| Section | Key variables |
|---------|---------------|
| Core | `APP_ENV`, `SECRET_KEY`, `DEBUG`, `CORS_ORIGINS`, `LOG_LEVEL`, `LOG_FORMAT` |
| Database | `DATABASE_URL`, `RUN_MIGRATIONS`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_PRE_PING`, `DB_POOL_RECYCLE`, `DB_ECHO` |
| Cache | `CACHE_BACKEND`, `REDIS_URL`, `CACHE_DEFAULT_TTL` |
| Messaging | `JOB_BROKER`, `RABBITMQ_URL`, `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_CLIENT_ID` |
| Storage | `STORAGE_BACKEND`, `STORAGE_ROOT`, `S3_*`, `AZURE_STORAGE_*`, `GCS_*`, `MINIO_*` |
| Auth / JWT | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` |
| LLM | `COPILOT_LLM_PROVIDER`, `COPILOT_CLAUDE_MODEL`, `ANTHROPIC_API_KEY` |
| Observability | `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `TRACING_ENABLED`, `METRICS_ENABLED` |
| Mail | `MAIL_BACKEND`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS`, `MAIL_FROM` |
| OCR | `OCR_ENGINE`, `TESSERACT_CMD`, `MAX_UPLOAD_MB` |
| Connectors | `CONNECTOR_MASTER_KEY` |
| Billing | `PAYMENT_GATEWAY`, `STRIPE_API_KEY`, `RAZORPAY_API_KEY` |
| ML | `MODEL_PATH`, `ML_DEFAULT_MODEL`, `ML_EXPLAINER` |

`CORS_ORIGINS` accepts a comma-separated string (`https://a.com,https://b.com`)
or a JSON array (`["https://a.com","https://b.com"]`).

## Example: production `.env`

```env
APP_ENV=production
DEBUG=false
SECRET_KEY=<openssl rand -hex 32>
CONNECTOR_MASTER_KEY=<openssl rand -hex 32>
LOG_FORMAT=json
CORS_ORIGINS=https://app.yourbank.com,https://admin.yourbank.com

DATABASE_URL=postgresql+psycopg://credit:<pw>@db.internal:5432/credit
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

CACHE_BACKEND=redis
REDIS_URL=redis://cache.internal:6379/0

JOB_BROKER=rabbitmq
RABBITMQ_URL=amqp://credit:<pw>@mq.internal:5672/

STORAGE_BACKEND=s3
S3_BUCKET=yourbank-credit-docs
S3_REGION=ap-south-1

MAIL_BACKEND=smtp
SMTP_HOST=smtp.internal
SMTP_USER=credit
SMTP_PASSWORD=<pw>

OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.internal:4317
TRACING_ENABLED=true
```

## Backward compatibility

- `from backend.app.config import settings` still works; the legacy uppercase
  attributes (`STORAGE_ROOT`, `MAX_UPLOAD_MB`, `max_upload_bytes`,
  `ALLOWED_UPLOAD_TYPES`, `ML_DEFAULT_MODEL`, …) delegate to the new settings.
- `backend.app.core.security` still exports `SECRET_KEY`, `ALGORITHM`,
  `ACCESS_TOKEN_EXPIRE_MINUTES` — now sourced from settings.
- `backend.app.db.database` still exports `DATABASE_URL`, `engine`,
  `SessionLocal`, `Base`, `get_db` (used by Alembic and all repositories).
- All historical environment variable names are unchanged.
