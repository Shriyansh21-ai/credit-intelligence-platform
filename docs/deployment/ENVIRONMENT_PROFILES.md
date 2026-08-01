# Environment Profiles & Deployment Configuration

*How the platform separates development, testing, staging and production
configuration — and how it fails fast on misconfiguration.*

The platform is **12-factor**: all configuration comes from the environment,
parsed once at startup into a typed, validated settings object
([`backend/app/core/settings.py`](../../backend/app/core/settings.py)). Nothing
secret is hardcoded, and the zero-config local defaults keep development and
tests running with no environment set.

## Profiles

`APP_ENV` selects the active profile. Validation rules **tighten** for the
production-like profiles.

| Profile | Purpose | Validation | Typical backends |
|---------|---------|------------|------------------|
| `development` | Local dev | Advisory (warnings) | SQLite · in-process cache/broker · local storage |
| `testing` | CI / pytest | Advisory (warnings) | SQLite · in-memory |
| `staging` | Pre-prod, prod-like | **Fail-fast** | PostgreSQL · Redis · object storage · JSON logs |
| `production` | Live | **Fail-fast** | PostgreSQL (HA) · Redis · object storage · HSTS preload |

Runtime detection is available on the settings object: `is_development`,
`is_testing`, `is_staging`, `is_production`, and `is_production_like`
(staging **or** production).

## Profile templates

Ready-to-adapt templates live in [`deploy/env/`](../../deploy/env):

| Template | Copy to | Notes |
|----------|---------|-------|
| `development.env.example` | `.env` | Zero-config SQLite; console logs. |
| `testing.env.example` | `.env` | Hermetic, fast; advisory validation. |
| `staging.env.example` | secret store → env | PostgreSQL/Redis/S3; JSON logs; tracing on. |
| `production.env.example` | secret store → env | Strictest; HSTS preload; migrations gated. |

```bash
cp deploy/env/development.env.example .env   # local development
```

The repo-root [`.env.example`](../../.env.example) remains the fully-annotated
reference for **every** variable.

## Secret management

- Secrets come from the environment via `SECRETS_PROVIDER` (`env` · `file` ·
  `aws` · `vault`). **No secret values are committed** — templates use
  `__REPLACE_WITH_…__` placeholders.
- Well-known insecure defaults (`dev-insecure-change-me`, `changeme`, …) are
  enumerated in `INSECURE_SECRETS` and **rejected in staging/production**.
- `JWT_SECRET_KEY` and `ENCRYPTION_KEY` fall back to `SECRET_KEY` when unset
  (`effective_jwt_secret`, `effective_encryption_key`).
- Generate strong secrets with `openssl rand -hex 32`.

## Startup validation (fail-fast)

On boot, [`core/startup.py`](../../backend/app/core/startup.py) logs a
**non-secret** configuration summary and runs `settings.validate_runtime()`.
Findings are `error` (fatal in staging/production) or `warning` (advisory).
In a production-like profile, any error raises `ConfigurationError` and the
process refuses to start.

Checks include: insecure/short secrets, SQLite in production, wildcard CORS
(especially with credentials), a `redis`/`rabbitmq`/`kafka` broker or
`redis` cache without its connection URL, object-storage backends without a
bucket/connection string, `stripe`/`razorpay` without an API key, `smtp` mail
without a host, and `DEBUG` in production.

Validate a profile before rollout:

```bash
APP_ENV=production python -c \
  "from backend.app.core.startup import validate_configuration as v; v()"
```

## Health & readiness

Deployment probes are exposed by the SaaS observability router — `/healthz`
(liveness), `/livez`, `/readyz` (readiness) — and the monitoring router's
health endpoint surfaces the configuration summary. Wire these into your
Kubernetes `livenessProbe` / `readinessProbe` (see the `deploy/k8s` overlays).

## Feature toggles

Two complementary mechanisms:

- **Static, environment-level** toggles are plain typed settings (e.g.
  `TRACING_ENABLED`, `METRICS_ENABLED`, `SECURITY_HEADERS_ENABLED`,
  `COMPRESSION_ENABLED`, `RUN_MIGRATIONS`).
- **Dynamic, per-tenant** feature flags are served by the SaaS `flags` module
  (Phase 8) for runtime product gating without a redeploy.

---

← Back to [Deployment Documentation](index.md) ·
See also [Configuration](CONFIGURATION.md)
