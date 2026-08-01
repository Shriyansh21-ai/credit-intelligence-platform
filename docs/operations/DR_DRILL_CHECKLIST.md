# Disaster Recovery — Drill Checklist

*A repeatable, hands-on DR exercise that validates the backup/restore machinery
described in [Disaster Recovery](DISASTER_RECOVERY.md). Run quarterly and after
any change to the data tier.*

## Objectives

| Metric | Target |
|--------|--------|
| **RPO** (max data loss) | ≤ `PITR_WINDOW_DAYS` window; continuous within it |
| **RTO** (max recovery time) | Restore + validate within the documented window |
| Backup retention | `BACKUP_RETENTION_DAYS` (default 35) |

## What ships

- **Automated backups:** `deploy/k8s/base/backup-cronjob.yaml` (scheduled,
  non-root, resource-bounded).
- **Point-in-time recovery:** window governed by `PITR_WINDOW_DAYS`.
- **Config-driven paths:** `BACKUP_DIR`, `BACKUP_RETENTION_DAYS`.

## Drill procedure

1. **Pre-checks**
   - [ ] Confirm the backup CronJob's last run succeeded and an artifact exists.
   - [ ] Record the current data checksum / row counts for a sample of tables.
   - [ ] Announce the drill window; use a non-production target.
2. **Simulate loss**
   - [ ] Provision a clean, isolated database instance (the "recovery target").
3. **Restore**
   - [ ] Restore the most recent backup into the recovery target.
   - [ ] Apply point-in-time replay to the chosen timestamp (within the PITR window).
4. **Migrate & boot**
   - [ ] Point a staging app at the recovery target (`DATABASE_URL`).
   - [ ] `alembic upgrade head` — confirm a single head and clean upgrade.
   - [ ] Boot with `APP_ENV=staging`; confirm startup validation passes.
5. **Validate**
   - [ ] `/readyz` returns healthy with the database check passing.
   - [ ] Sample row counts / checksums match the pre-loss snapshot (within RPO).
   - [ ] Spot-check a critical read flow (e.g. dashboard overview, an assessment).
6. **Record**
   - [ ] Capture actual RPO and RTO achieved vs. target.
   - [ ] File any gaps as tickets; update this checklist if steps changed.
7. **Teardown**
   - [ ] Decommission the recovery target; confirm no residual secrets.

## Failure-mode coverage

| Scenario | Recovery path |
|----------|---------------|
| Accidental data deletion | PITR replay to just before the event |
| DB instance loss | Restore latest backup + PITR to now |
| Region outage | Fail over to replica / re-provision via `infra/terraform/` |
| Corrupt migration | Restore + re-run gated migration step |

---

← Back to [Operations Documentation](index.md) ·
See also [Disaster Recovery](DISASTER_RECOVERY.md) ·
[Incident Response](INCIDENT_RESPONSE.md)
