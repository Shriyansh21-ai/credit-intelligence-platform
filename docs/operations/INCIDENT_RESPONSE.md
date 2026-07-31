# Incident Response

How we detect, triage, mitigate, and learn from production incidents on the
**AI Credit Intelligence Platform**. Optimized for fast, blameless recovery.

See also: [Runbook](RUNBOOK.md) · [Disaster Recovery](DISASTER_RECOVERY.md) ·
[Observability](OBSERVABILITY.md) · [Operator Guide](OPERATOR_GUIDE.md).

## Severity levels

| Sev | Definition | Examples | Response |
|-----|------------|----------|----------|
| **S1** | Critical outage / data loss / security breach | API down, DB unreachable, credential leak, data corruption | Page immediately, all-hands, 24/7 |
| **S2** | Major degradation, no full workaround | Elevated 5xx, P95 far over SLO, workers stalled, one region down | Page on-call, work until mitigated |
| **S3** | Minor / partial degradation with workaround | One non-critical endpoint failing, delayed jobs | Business hours, same day |
| **S4** | Low impact / cosmetic | UI glitch, noisy alert, single user report | Backlog, next sprint |

When unsure, round **up**; a Sev can be downgraded once scope is understood.

## On-call flow

1. **Acknowledge** the page within the SLA (S1/S2: minutes).
2. **Assess** severity from dashboards and probes.
3. **Declare** an incident for S1/S2 — open the incident channel, assign roles.
4. **Mitigate** first (restore service), diagnose root cause after.
5. **Communicate** status on a fixed cadence until resolved.
6. **Close** and schedule the postmortem.

## Detection

- **Alerts / SLO burn:** Prometheus alert rules on RED metrics (rate, errors,
  duration) and SLO burn-rate; worker heartbeat age; DB pool saturation. See
  [Observability](OBSERVABILITY.md).
- **Probes:** `/livez`, `/readyz`, `/healthz` failures surface in Kubernetes and
  the deploy smoke test.
- **Signals:** error spikes in logs (structured JSON + correlation IDs), traces,
  customer reports, failed deploy rollouts.

## Triage

- Confirm blast radius: which environment, service, tenant, endpoint.
- Check recent changes first — deploys, migrations, config/flag flips are the
  most common trigger. `kubectl -n <ns> rollout history deploy/backend`.
- Pull the correlation ID from a failing request and follow it across services.
- Decide mitigation path: rollback, scale, disable a feature, or fail over.

## Mitigation

- **Bad deploy:** `kubectl -n <ns> rollout undo deploy/<svc>` (see
  [Deployment](../deployment/DEPLOYMENT.md)).
- **Overload:** scale replicas / raise HPA max; shed load.
- **Bad config or flag:** revert the ConfigMap/flag and
  `rollout restart`.
- **Dependency down (DB/Redis/broker):** fail over per
  [Disaster Recovery](DISASTER_RECOVERY.md); data loss/restore follows the RTO/RPO
  plan there.
- **Security incident:** rotate the affected secret
  (`SECRET_KEY`/`CONNECTOR_MASTER_KEY`/tokens), revoke sessions, follow
  [Security](../security/SECURITY_ARCHITECTURE.md).

Step-by-step procedures for specific failure modes live in the
[Runbook](RUNBOOK.md).

## Communication

- One incident channel; the Communications Lead posts updates at a fixed cadence
  (S1: every 30 min) with current impact, actions, and next update time.
- Keep a running timeline (UTC) — detection, decisions, actions, effects.
- Notify stakeholders/customers per severity and any regulatory obligations
  ([Compliance](../security/COMPLIANCE.md)).

## Escalation

- No acknowledgement within SLA → escalate to the secondary, then the lead.
- Cross-team dependency → page that team's on-call.
- S1 beyond ~30 min without a mitigation path → engage engineering management
  and, for security/data, legal & compliance.

## Roles

- **Incident Commander (IC):** owns the incident, decisions, and severity; does
  not fix — coordinates.
- **Communications Lead:** stakeholder/customer updates and the timeline.
- **Operations/Subject-Matter lead(s):** hands-on mitigation and diagnosis.

For small incidents one person may hold multiple roles; for S1 keep them
separate.

## Postmortem (blameless)

Written for every S1/S2 within five business days. Focus on systems and
contributing factors, never individuals.

```markdown
# Postmortem — <short title>

- **Date / duration:**
- **Severity:**
- **Authors / IC:**
- **Status:** Draft | Reviewed | Actions tracked

## Summary
One paragraph: what happened and the customer impact.

## Impact
Users/tenants affected, requests failed, data affected, duration, $ / SLA.

## Timeline (UTC)
- HH:MM — detection
- HH:MM — action / effect
- HH:MM — mitigated / resolved

## Root cause
Technical root cause and the conditions that allowed it.

## Detection
How we found out; how long detection took; gaps.

## Resolution
What actually restored service.

## What went well / what went poorly

## Action items
| Action | Owner | Priority | Due | Tracking |
|--------|-------|----------|-----|----------|
```

Action items must be tracked to completion and reviewed in the next operational
review.
