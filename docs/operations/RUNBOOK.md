# Operations Runbook

_Phase 11, M13 — operational procedures for the AI Credit Intelligence Platform._

Quick-reference procedures for on-call. For incident process see
[INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md); for recovery see
[DISASTER_RECOVERY.md](DISASTER_RECOVERY.md).

---

## 1. Health & first checks

```bash
curl -fsS $APP_URL/livez     # process alive
curl -fsS $APP_URL/readyz    # dependencies healthy (DB, ...)
curl -fsS $APP_URL/metrics | grep aicredit_   # Prometheus metrics
kubectl -n $NS get pods,deploy,hpa
kubectl -n $NS logs deploy/backend --tail=200   # structured JSON, has correlation_id
```

Dashboards: **AI Credit — Platform Overview** and **SLO / Error Budget**
(Grafana). Alerts route via Alertmanager (see [OBSERVABILITY.md](OBSERVABILITY.md)).

## 2. Common alerts → response

| Alert | Likely cause | First actions |
|-------|--------------|---------------|
| `ApiTargetDown` | pods crashed / not ready | `kubectl get pods`; check `readyz`, recent deploy → rollback |
| `ApiErrorBudgetFastBurn` | spike in 5xx | check logs by correlation id; recent change → rollback (§5) |
| `ApiLatencyP99High` | slow queries / saturation | slow-query report (§6); scale (§4); check DB CPU |
| `DatabaseSlowQuerySpike` | missing index / N+1 | index recommendations (§6) |
| `HighErrorRate` | dependency failure | check dependency health; feature-flag off the faulty path |
| `RedisCpuHigh`/`RdsCpuHigh` | load / hot keys | scale instance (Terraform); investigate hot path |

## 3. Triage by correlation ID

Every response carries `X-Correlation-ID`; every log line and span carries it.

```bash
kubectl -n $NS logs deploy/backend | grep "<correlation-id>"
```

Then follow the trace in Tempo/Jaeger for the same id.

## 4. Scaling

```bash
kubectl -n $NS scale deploy/backend --replicas=N     # manual
kubectl -n $NS get hpa                                # autoscaler status
# Persistent capacity change: bump replicas in deploy/k8s/overlays/<env> and re-apply.
```

Managed data tiers (Postgres/Redis) scale via Terraform (`instance_size`,
`num_nodes`) — plan/apply the relevant environment.

## 5. Deploy & rollback

```bash
# Deploy: GitHub Actions → Deploy workflow (environment-gated; prod needs approval)
# Rollback (immediate):
kubectl -n $NS rollout undo deploy/backend
kubectl -n $NS rollout status deploy/backend
```

The Deploy workflow auto-rolls-back on failed rollout. Image tags are immutable
(semver / sha), so rollback = redeploy the previous tag.

## 6. Performance investigation

```python
from backend.app.core.performance import analyze_slow_queries, recommend_indexes
analyze_slow_queries()     # ranked slow-query patterns
recommend_indexes()        # candidate indexes (validate with EXPLAIN first)
```

Enable `QUERY_PROFILING_ENABLED=1` to capture N+1 patterns per unit of work.

## 7. Migrations

```bash
alembic heads            # must be exactly one
alembic upgrade head     # apply (idempotent; also run by container entrypoint)
alembic downgrade -1     # revert last (only if safe/reversible)
```

Migrations run automatically via the migrations Job / entrypoint
(`RUN_MIGRATIONS=1`). Never edit an applied migration; add a new one.

## 8. Workers & scheduler

```bash
kubectl -n $NS logs deploy/worker --tail=100
kubectl -n $NS logs deploy/scheduler --tail=100
```

Worker/scheduler health is probed via `backend.app.workers.healthcheck`
(heartbeat file). Queue depth is on the overview dashboard
(`aicredit_queue_depth`). Restart: `kubectl rollout restart deploy/worker`.

## 9. Backups & restore

Scheduled by the backup CronJob. To validate / restore see
[DISASTER_RECOVERY.md](DISASTER_RECOVERY.md) (integrity check, PITR, drills).

## 10. Configuration & secrets

Config is env-driven (`core/settings.py`); change via the environment/ConfigMap
and restart. Secrets come from the secret manager (never the repo); rotate via
`KeyRing`/`JwtKeyRing` (see [SECURITY.md](SECURITY.md)). `GET /readyz` reports
config validation status.

## 11. Escalation

S1/S2 → page platform on-call → engineering lead. Follow
[INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md). Record actions with timestamps for
the postmortem.
