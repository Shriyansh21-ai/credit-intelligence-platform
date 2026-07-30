# Operations Guide (v1.0.0)

## Operations Center

`/api/ent/operations` is the single operations console. `GET .../dashboard`
returns live component health (platform, AI, ML, connectors, storage, queues,
jobs, tenant), telemetry and open-incident count. Health is computed from real
platform counts and open-incident load — it is never a static placeholder.

## Incident management

- Open: `POST /api/ent/operations/incidents {title, component, severity(sev1–4),
  runbook_key?}`.
- Update / resolve: `POST /api/ent/operations/incidents/update {incident_id,
  status, note?, root_cause?}` (status: open→investigating→mitigated→resolved).
- Root-cause analysis: `GET /api/ent/operations/incidents/{id}/rca` correlates the
  incident with component health and recommends a runbook.

Severity weights degrade the affected component's health score (sev1 −40, sev2
−25, sev3 −12, sev4 −5), so opening a sev1 on `ai` immediately shows in the
dashboard.

## Runbooks

Seed the starter set with `POST /api/ent/operations/runbooks/seed` (high-latency,
AI-provider-outage, connector-failure). Author your own with
`POST /api/ent/operations/runbooks {title, steps, trigger, category}`.

## Monitoring

`/api/ent/monitoring` provides distributed tracing, the service dependency graph,
p50/p95/p99 latency, SLA tracking, AI/ML/infra cost monitoring and capacity
planning. `GET .../dashboard` is the executive observability roll-up. Record
traces (`POST .../traces`) and SLAs (`POST .../sla`) from your services.

## Golden signals & alerting

- Latency (p99), error rate, saturation (queue depth), traffic.
- SLA breaches surface in `GET /api/ent/monitoring/sla`.
- Cost drift surfaces in `GET /api/ent/monitoring/cost`.

## On-call flow

1. Alert fires (SLA breach / latency spike).
2. Open an incident, attach the relevant runbook.
3. Run RCA, follow the runbook steps.
4. Mitigate → resolve → record root cause.
5. Review in the next operational checklist (`/api/ent/launch`, type
   `operational`).

## Backups & DR

RPO/RTO targets and restore testing are tracked in the `dr` and `bcp`
launch-readiness checklists. Database backups should run automatically in
production (see the production checklist).
