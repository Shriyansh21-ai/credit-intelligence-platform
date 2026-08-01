# Monitoring, Logging & Alerting

*The production observability stack, the centralized logging pipeline, and the
SLO alert catalog with on-call response guidance — verified for Stage 3.*

The full monitoring stack ships under [`deploy/monitoring/`](../../deploy/monitoring)
and is scrape-wired to the application's `/metrics` endpoint. This document maps
what is deployed to how on-call responds.

## The stack (M6)

| Signal | Tool | Config |
|--------|------|--------|
| Metrics | Prometheus | `deploy/monitoring/prometheus/prometheus.yml` |
| Dashboards | Grafana | `deploy/monitoring/grafana/dashboards/{platform-overview,slo}.json` |
| Alert routing | Alertmanager | `deploy/monitoring/alertmanager/alertmanager.yml` |
| Logs | Loki | `deploy/monitoring/loki/loki-config.yml` |
| Traces | Tempo (OpenTelemetry) | `deploy/monitoring/tempo/tempo-config.yml` |

The app exposes Prometheus metrics at `GET /metrics` (verified `200`,
`aicredit_*` families) and OTLP traces via `OTEL_EXPORTER_OTLP_ENDPOINT`.
Recording rules (`recording.rules.yml`) precompute the `job:aicredit_*` series
the dashboards and alerts consume.

## Centralized logging (M7)

- **Structured JSON logs** in production (`LOG_FORMAT=json`) so every line is
  machine-parseable; `console` format for local development.
- **`ObservabilityMiddleware`** stamps a correlation id on each request; logs,
  metrics and traces share it so a single request can be followed end-to-end.
- **Loki** aggregates container stdout/stderr; Grafana's Loki datasource
  (`provisioning/datasources/datasources.yml`) makes logs queryable alongside
  metrics and traces (logs↔traces↔metrics correlation).
- **Retention & PII:** log retention is governed centrally; PII is masked before
  it reaches logs (`core/crypto.py` `PiiMasker`). See
  [Security Architecture](../security/SECURITY_ARCHITECTURE.md).

## SLO alert catalog (M6)

Alerts (`prometheus/rules/alerts.rules.yml`) are **SLO-based** — multi-window
error-budget burn plus latency/availability objectives. `severity: page` calls
the on-call; `severity: ticket` files a ticket.

| Alert | Trigger | Severity | First response |
|-------|---------|----------|----------------|
| `ApiTargetDown` | `up{job="ai-credit-api"} == 0` | page | Check pod health/rollout; `kubectl get pods`; inspect `/readyz`. |
| `ApiErrorBudgetFastBurn` | 14.4× burn (fast) | page | Correlate with recent deploy; consider rollback (`deploy.yml`). |
| `ApiErrorBudgetSlowBurn` | 3× burn (slow) | ticket | Investigate error class via Loki + `/api/saas/observability/errors`. |
| `ApiLatencyP99High` | p99 > 750 ms | ticket | Check slow queries, downstream latency, saturation → HPA. |
| `HighErrorRate` | error rate > 1/s (5m) | ticket | Trace a failing request by correlation id in Tempo. |
| `DatabaseSlowQuerySpike` | slow-query rate > 0.5 | ticket | Review `/api/saas/observability/slow-queries`; check pool saturation. |
| `MlInferenceLatencyHigh` | ML p95 > 500 ms | ticket | Check model service load and cache hit rate. |

## Quick verification

```bash
curl -fsS localhost:8000/metrics | grep -c aicredit_   # metric families present
promtool check rules deploy/monitoring/prometheus/rules/*.yml   # rules valid
```

---

← Back to [Operations Documentation](index.md) ·
See also [Observability](OBSERVABILITY.md) · [Runbook](RUNBOOK.md) ·
[Incident Response](INCIDENT_RESPONSE.md)
