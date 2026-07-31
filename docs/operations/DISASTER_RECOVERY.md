# Disaster Recovery

_Phase 11, M11 — backup, restore, and disaster-recovery runbook for the AI
Credit Intelligence Platform._

---

## 1. Objectives (RTO / RPO)

| Tier | Data | RPO (max data loss) | RTO (max downtime) |
|------|------|---------------------|--------------------|
| **Tier 1** | Primary database (applications, decisions, audit) | ≤ 5 min (PITR) | ≤ 1 h |
| **Tier 2** | Object storage (documents) | ≤ 1 h | ≤ 4 h |
| **Tier 3** | Configuration, secret references | ≤ 24 h | ≤ 4 h |

## 2. What is backed up

Implemented via `core/dr.py` `BackupTarget`s (file-based by default; cloud
adapters in production):

| Target | Class | Mechanism |
|--------|-------|-----------|
| Database | `DatabaseBackupTarget` | logical dump (`pg_dump`) + RDS automated snapshots/PITR |
| Object storage | `FileTreeBackupTarget` | tar.gz / S3 versioning + cross-region replication |
| Configuration | `ConfigBackupTarget` | settings summary snapshot (12-factor; env is source of truth) |
| Secret **references** | `SecretRefBackupTarget` | encrypted manifest of names/versions — **never plaintext values** |

Every artifact is SHA-256 checksummed and catalogued (`catalog.json`).

## 3. Backup operations

```python
from backend.app.core.dr import (
    BackupManager, DatabaseBackupTarget, FileTreeBackupTarget,
    ConfigBackupTarget, SecretRefBackupTarget,
)

mgr = BackupManager()
mgr.register(DatabaseBackupTarget("primary", dump=pg_dump_bytes, load=pg_restore))
mgr.register(FileTreeBackupTarget("documents", "backend/storage/documents"))
mgr.register(ConfigBackupTarget())
mgr.register(SecretRefBackupTarget(list_secret_refs))

artifacts = mgr.run_all()      # scheduled by the k8s backup CronJob (deploy/k8s/base/backup-cronjob.yaml)
mgr.prune(retention_days=35)   # enforce retention
```

Schedule: database every 6 h + continuous WAL/PITR; storage daily; config +
secret-refs daily. Retention 35 days (`BACKUP_RETENTION_DAYS`).

## 4. Point-in-time recovery

```python
from backend.app.core.dr import PointInTimeRecovery
pitr = PointInTimeRecovery(window_days=7)          # PITR_WINDOW_DAYS
pitr.can_recover_to(target_ts)                     # within window?
base = pitr.resolve_restore_point(mgr.catalog(), target_ts)  # base backup to restore, then replay WAL
```

Restore-to-timestamp uses the most recent base backup at/before the target, then
replays the transaction log to the exact point (cloud PITR handles the replay).

## 5. Restore runbook

1. **Declare an incident**, page on-call (see [RUNBOOK.md](RUNBOOK.md) §incident).
2. **Provision** replacement infra with Terraform (`infra/terraform`) if needed.
3. **Restore database** from the chosen artifact / PITR timestamp; verify a
   single Alembic head (`alembic heads`) and `alembic upgrade head`.
4. **Restore storage** (`FileTreeBackupTarget.restore`) / re-point to replicated bucket.
5. **Re-materialise config & secrets** from the secret manager (references
   restored from the encrypted manifest; values come from the vault, never a backup).
6. **Validate** (§6), then flip DNS / scale up (`deploy/k8s/overlays/production`).
7. **Post-incident review**; record RTO/RPO achieved vs. objective.

```python
from backend.app.core.dr import RestoreManager
RestoreManager({t.name: t for t in targets}).restore(artifact)
```

## 6. Recovery validation & drills

- **Integrity:** `validate_backup(artifact)` recomputes the checksum.
- **Full round-trip drill:** `recovery_drill(target)` performs backup → validate
  → restore into a scratch location and returns a `DrillResult` (`ok`).
- **Cadence:** automated integrity check on every backup; a full restore drill in
  a scratch environment **monthly**, results recorded. A drill that is not `ok`
  pages the platform team.

```python
from backend.app.core.dr import recovery_drill
result = recovery_drill(DatabaseBackupTarget("primary", dump=pg_dump_bytes, load=pg_restore))
assert result.ok, result.error
```

## 7. Cross-region / BCP

- Database: multi-AZ (sync) + optional cross-region read replica (async) for
  regional failover — provisioned by the Terraform `database` module
  (`high_availability=true`).
- Storage: S3/GCS cross-region replication.
- Infra is fully reproducible from `infra/terraform` in an alternate region.
- Backups are stored in a separate region/account from production.
