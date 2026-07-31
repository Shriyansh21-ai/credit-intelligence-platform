# API Platform

_Phase 11, M10 — enterprise API platform for the AI Credit Intelligence Platform._

Additive to the Phase-7 API surface (`services/integrations/apiplatform` —
API keys, scopes, rate limits, usage analytics, webhook subscriptions). M10 adds
versioning/lifecycle, replay-proof webhook signing with retry/replay, and
OpenAPI/SDK enablement.

---

## 1. Versioning & lifecycle

- **Scheme:** URL-prefixed major versions — `/api/v1/...`. The current version is
  declared in `core/api_versioning.registry`.
- **Lifecycle:** `active → deprecated → sunset`. `APIVersionMiddleware` stamps
  every response:
  - `X-API-Version: v1`
  - When deprecated: `Deprecation: true`, `Sunset: <ISO date>`,
    `Link: <docs>; rel="deprecation"` (IETF `draft-ietf-httpapi-deprecation-header`).
- **Deprecation policy:** a version is supported ≥12 months after a successor
  ships; it is marked `deprecated` (with a `sunset_on` ≥90 days out) before
  removal. Past `sunset_on`, the gateway should return `410 Gone`.

```python
from datetime import date
from backend.app.core.api_versioning import registry, APIVersion, VersionStatus
registry.register(APIVersion("v2"), current=True)
registry.register(APIVersion("v1", status=VersionStatus.DEPRECATED,
                             sunset_on=date(2027, 1, 1)))
```

## 2. API keys & rate limits (existing, Phase 7)

- `services/integrations/apiplatform/service.py`: `create_api_key` (hashed at
  rest), `verify_api_key`, `check_scope`, `enforce_rate_limit`, `revoke_api_key`,
  `record_usage`, `usage_analytics`.
- Keys are scoped; per-key rate limits enforced per request; usage is recorded
  for the analytics/usage dashboard.

## 3. Webhooks

Phase-7 handles subscriptions and emission
(`apiplatform/webhooks.py`). M10 (`core/webhooks.py`) adds delivery robustness:

- **Signing (replay-proof):** `sign(secret, body)` →
  `X-Webhook-Signature: t=<ts>,v1=<hmac-sha256>` over `"<ts>.<body>"`.
  `verify(...)` recomputes in constant time **and** rejects timestamps outside a
  tolerance window (default 300s) — a captured request cannot be replayed later.
- **Retry with backoff:** `RetryPolicy` (default 6 attempts, ×3 exponential,
  capped at 1h). `WebhookDispatcher.deliver(...)` retries non-2xx/exceptions per
  the policy and records every `DeliveryAttempt`.
- **Replay:** `WebhookDispatcher.replay(...)` re-delivers a past event with a
  fresh signature/timestamp (for the developer-portal "resend" action).

Consumer verification example:

```python
from backend.app.core.webhooks import verify
if not verify(endpoint_secret, request_body, request.headers["X-Webhook-Signature"]):
    return Response(status_code=400)
```

## 4. OpenAPI & SDK generation

- The FastAPI app ships enriched OpenAPI metadata (description, contact, license,
  tags) — `GET /openapi.json`, Swagger UI at `/docs`, ReDoc at `/redoc`.
- **SDK generation hook:** the committed spec drives client generation, e.g.
  ```bash
  curl -s http://localhost:8000/openapi.json > openapi.json
  openapi-generator-cli generate -i openapi.json -g python -o sdk/python
  openapi-generator-cli generate -i openapi.json -g typescript-axios -o sdk/ts
  ```
  Wire this into CI to publish versioned SDKs on release.

## 5. Developer portal structure

Recommended layout for the external developer portal (static site or Backstage):

```
developer-portal/
├── getting-started/        # auth, first request, sandbox keys
├── reference/              # rendered from /openapi.json (per version)
├── guides/                 # applications, decisioning, webhooks, pagination
├── webhooks/               # event catalogue + signature verification snippets
├── rate-limits/            # tiers, headers (X-RateLimit-*), backoff guidance
├── changelog/              # per-version changes + deprecation timeline
└── sdks/                   # generated client libraries + install docs
```

## 6. Standard conventions

- **Pagination:** all list endpoints use `core/pagination` (offset + keyset);
  page size clamped to ≤500.
- **Errors:** consistent JSON error bodies; `4xx` for client, `5xx` for server;
  correlation id echoed via `X-Correlation-ID` (M7).
- **Rate-limit headers:** advertise `X-RateLimit-Limit/Remaining/Reset`.
- **Idempotency:** mutating public endpoints should honour an `Idempotency-Key`
  header (recommended for the v2 surface).
