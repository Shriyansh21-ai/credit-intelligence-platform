# Phase 10 — Migration Report

## Revision
- **ID:** `e2f3a4b5c6d7` — "Enterprise Banking Operating System tables (Phase 10)"
- **down_revision:** `d0e1f2a3b4c5` (Phase 9 head) → Phase 10 is now the single head.
- **File:** `backend/alembic/versions/e2f3a4b5c6d7_banking_os_phase10.py`

## Scope
Creates **25 new `os_*` tables** with their indexes and unique constraints. **Purely
additive** — no `ALTER`/`DROP` on any existing table. `upgrade()` creates tables in FK-safe
order; `downgrade()` drops them in exact reverse order.

## Verification performed
```
DATABASE_URL="sqlite:///./scratch.db" alembic upgrade head    # Phase 1 → 10, reaches e2f3a4b5c6d7
  → 25 os_* tables present
DATABASE_URL="sqlite:///./scratch.db" alembic downgrade -1     # Phase 10 → 9
  → 0 os_* tables (clean reversible downgrade)
```
The full chain applies cleanly on a fresh database and is idempotent with the runtime (the
app never calls `create_all`; migrations are the single source of truth). Tests build their
schema via `Base.metadata.create_all`, which stays in lock-step with the ORM models.

## RBAC / seed changes
- 16 new permissions in the `Banking OS` category are reconciled at startup by the existing
  `sync_rbac` bootstrap (no bespoke data migration needed) — total permissions **86 → 102**.
- Marketplace built-in plugins are seeded on demand via `POST /api/os/marketplace/seed`
  (per-tenant), not at migration time.

## Deployment procedure
1. Deploy code. 2. `alembic upgrade head`. 3. App boot runs `sync_rbac` (idempotent) to
register the new permissions/grants. 4. (Optional) seed marketplace plugins per tenant.
No downtime; no backfill required (all new columns are additive with sane server defaults).

## Rollback
`alembic downgrade d0e1f2a3b4c5` drops all 25 Phase 10 tables. Because the layer is additive
and isolated, rollback does not affect any Phase 1–9 data or behavior.
