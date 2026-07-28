# Observability

_Phase 11, M7 — enterprise observability for the AI Credit Intelligence Platform._

The platform emits the three pillars — **metrics**, **logs**, and **traces** —
correlated by a per-request **correlation ID**. This document is the reference
for what is emitted, how it is collected, and the SLOs it backs.

---

## 1. Architecture

```
                       ┌───────────────────────── API / worker / scheduler ─────────────────────────┐
                       │  telemetry.py                                                               │
   request ──► ObservabilityMiddleware ──► correlation id + latency metric + root span               │
                       │  domain.* metric facades (business / ML / db / queue / api / ws)             │
                       │  structured JSON logs (correlation_id, trace_id)                             │
                       │  OpenTelemetry (OTLP) spans  ─────────────────────────────────────────────┐ │
                       └──────────────┬───────────────────────────┬──────────────────────────────┘ │
                            GET /metrics (Prometheus)       stdout logs                       OTLP    │
                                       │                           │                             │    │
                                  Prometheus ◄── recording+alert   Loki  ◄── promtail        Tempo/Jaeger
                                       │          rules            │                             │
                                       └────────────► Grafana ◄────┴─────────────────────────────┘
                                                        │
                                                  Alertmanager ──► pager / e-mail / Slack
```

Collection stack (see `deploy/monitoring/` and `deploy/compose/docker-compose.monitoring.yml`):
Prometheus, Grafana, Loki, Tempo, Jaeger, Alertmanager, node/postgres/redis/kafka exporters.

## 2. Metrics

Exposed at **`GET /metrics`** (root, Prometheus text format, `aicredit_*`
namespace). Backed by the in-process `MetricsRegistry`
(`services/saas/observability.py`) and rendered by `core/telemetry.py`.
Toggle with `METRICS_ENABLED` (default on).

| Family | Example series | Emitted by |
|--------|----------------|------------|
| **API** | `aicredit_http_requests{method,status}`, `aicredit_http_latency_ms{path,quantile}` | `ObservabilityMiddleware`, `domain.api_request` |
| **Business** | `aicredit_business_<event>{...}` | `domain.business_event` / `business_value` |
| **ML** | `aicredit_ml_predictions{model,outcome}`, `aicredit_ml_inference_ms`, `aicredit_ml_drift` | `domain.ml_inference` / `ml_drift` |
| **Database** | `aicredit_db_query_ms{operation}`, `aicredit_db_slow_query`, `aicredit_db_pool_*` | `domain.db_query` / `db_pool`, `observability.record_query` |
| **Queue / jobs** | `aicredit_queue_depth{queue}`, `aicredit_queue_jobs{status,queue}`, `aicredit_queue_job_ms` | `domain.queue_depth` / `job` |
| **WebSocket** | `aicredit_ws_active`, `aicredit_ws_connections_total`, `aicredit_ws_messages{direction}` | `domain.ws_connection` / `ws_message` |
| **Errors** | `aicredit_errors{kind}` | `observability.record_error` |
| **Build** | `aicredit_build_info{version,env,service}` | telemetry |

Histograms are exposed as Prometheus summaries (`_count`, `_sum`, `quantile`
`0.5/0.95/0.99`, plus an auxiliary `_max` gauge).

Adding a metric — never touch the exposition layer, just record into the shared
registry via a facade:

```python
from backend.app.core.telemetry import domain
domain.business_event("loan_approved", tenant=str(tenant_id))
domain.ml_inference("scorecard", duration_ms=12.4, outcome="ok")
```

## 3. Logs

Structured JSON when `LOG_FORMAT=json` (recommended for staging/prod), otherwise
a human console format. Every record carries `correlation_id` and `trace_id`
injected from the request context, so a single request can be reconstructed
across services. Configured once via `telemetry.configure_logging()` (idempotent;
called from the app/worker startup). Shipped to Loki via promtail/agent and
queried in Grafana.

## 4. Traces

`ObservabilityMiddleware` starts a correlation/trace context per request and the
`observability.trace()` context manager records internal spans (persisted to
`TraceSpan` for the in-app trace timeline). When `TRACING_ENABLED=1` and
`OTEL_EXPORTER_OTLP_ENDPOINT` is set, `telemetry.init_tracing()` additionally
instruments FastAPI + SQLAlchemy with OpenTelemetry and exports OTLP spans to
Tempo/Jaeger. The OTel SDK is an optional dependency — absent, the app runs
unchanged.

Correlation ID propagation: clients may send `X-Correlation-ID`; it is echoed on
the response and threaded through logs, spans, and error records. Downstream
calls should forward the same header.

## 5. SLOs, SLIs & error budgets

Service Level Objectives for the API tier (rolling 30 days):

| SLO | SLI | Objective | Error budget |
|-----|-----|-----------|--------------|
| **Availability** | `1 - (5xx / total requests)` | **99.9%** | 0.1% (~43 min/30d) |
| **Latency** | p99 request latency | **≤ 750 ms** | 1% of requests may exceed |
| **ML freshness** | p95 inference latency | **≤ 500 ms** | advisory |
| **Data durability** | successful backup ratio | **100%** | 0 (see M11) |

SLIs are precomputed as Prometheus **recording rules**
(`deploy/monitoring/prometheus/rules/recording.rules.yml`) — e.g.
`job:aicredit_api_availability:ratio5m`, `job:aicredit_http_latency_ms:p99`.

**Error-budget policy.** Alerting uses the Google SRE multi-window burn-rate
method (`alerts.rules.yml`):

- **Fast burn** (14.4× budget over 1h & 5m) → `severity: page`.
- **Slow burn** (3× budget over 6h & 30m) → `severity: ticket`.

When the 30-day budget is exhausted, the release policy is: freeze
feature deploys, prioritise reliability work, and only ship changes that reduce
burn until the budget recovers.

Dashboards: **AI Credit — SLO / Error Budget** (`slo.json`) shows availability,
budget remaining, and live burn rate; **AI Credit — Platform Overview**
(`platform-overview.json`) shows the golden signals across all families.

## 6. Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `METRICS_ENABLED` | `true` | Serve `/metrics` |
| `TRACING_ENABLED` | `false` | Enable OTel export |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | OTLP collector endpoint |
| `OTEL_SERVICE_NAME` | `ai-credit-platform` | Service name on spans |
| `LOG_FORMAT` | `console` | `json` for structured logs |
| `LOG_LEVEL` | `INFO` | Root log level |

## 7. Local stack

```bash
docker compose -f deploy/compose/docker-compose.monitoring.yml up -d
# Grafana → http://localhost:3001 (admin/admin) — dashboards auto-provisioned
# Prometheus → http://localhost:9090   Jaeger → http://localhost:16686
```
