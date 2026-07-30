# Roadmap — v2 and beyond

v1.0.0 is commercial GA. The roadmap below is forward-looking and **non-binding**;
everything continues to follow the additive, backward-compatible architecture.

## Theme 1 — Live integrations

- Replace simulated market/alt-data providers with gated live feeds (the schema
  already carries a `source` field per quote/signal).
- Real webhook delivery with retries/backoff and dead-letter queues (the
  delivery model, signing and replay already exist).
- Production LLM providers beyond the gated Claude integration, with per-tenant
  routing and budget controls.

## Theme 2 — Deeper productization

- Drag-and-drop visual editors for the integration studio and workflow builder
  (backends and graph models already exist).
- Real-time collaboration on workspaces and dashboards.
- Native mobile / responsive polish beyond the current responsive layouts.
- Marketplace billing execution (metering + invoicing) on top of the existing
  billing-readiness fields.

## Theme 3 — Advanced analytics

- Model registry integration for the quant/forecasting engines (bring-your-own
  model) with champion/challenger.
- Streaming ingestion for alternative data and market ticks.
- Expanded ESG datasets and regulator-specific report templates.

## Theme 4 — Scale & reliability

- Read replicas and query-level tenant sharding for very large deployments.
- Native distributed tracing export (OpenTelemetry) from the existing trace model.
- Chaos testing and automated DR drills wired into the launch-readiness engine.

## Theme 5 — Compliance & certification

- SOC 2 / ISO 27001 evidence automation from the security center and access
  reviews.
- Regional data-residency controls at the tenant layer.
- Immutable audit export.

## Principles carried forward

- **Additive-only** — never remove APIs, tables, migrations or permissions.
- **Deterministic + grounded** — reproducible results, every AI response carrying
  confidence, reasoning, citations and evidence.
- **Multi-tenant, RBAC-first, reversible migrations** — always.
