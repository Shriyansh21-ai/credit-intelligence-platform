# Enterprise Credit Decision Platform
## Engineering Report

Phase 5 transforms the platform from an AI risk-analysis application into a
complete **Credit Decision Platform** covering the full enterprise credit
workflow: Application → Documents → Financial Analysis → AI Assessment → Human
Review → Committee Approval → Loan Decision → Monitoring.

All work is **additive**. No Phase 1–4 endpoint, table, or business rule was
removed or altered. The Phase 1–4 AI/risk engines are untouched and fully
preserved.

- **Backend tests:** 155 (start) → **266 (all green)**, target was 200+.
- **Frontend:** `npm run build` clean, `npx tsc --noEmit` clean.
- **Migrations added:** 7 (chain head `d6f7a8b9c0e1`), ~14 new tables.
- **New service packages:** 12. **New route modules:** 12. **New endpoints:** ~60.

---

## 1. Workflow Engine Architecture

Two cooperating engines drive an application through its life.

**Lifecycle state machine** (`services/lifecycle/`)
- `state_machine.py` defines all **14 statuses** (Draft → Submitted → Documents
  Pending → Under AI Analysis → Analyst Review → Senior Analyst Review → Credit
  Committee → Approved / Conditionally Approved / Rejected → Disbursed →
  Monitoring → Closed / Cancelled) and an explicit `ALLOWED_TRANSITIONS` graph.
- `validate_transition()` is the single gatekeeper — no status changes without it.
- `service.py` provides `create / transition / rollback / get_timeline`. Every
  change appends an immutable `ApplicationStatusHistory` row (from/to, actor,
  reason, comment, kind) **and** an audit record. Rollback reverts to the prior
  recorded status (a deliberate, audited undo that bypasses the forward graph).

**Multi-stage approval workflow** (`services/approvals/`)
- A **configurable** `ApprovalWorkflow` (stages stored as editable JSON) with the
  default 6-stage bank matrix: Junior Analyst → Senior Analyst → Risk Manager →
  Credit Committee → Regional Manager → Admin Override.
- Six actions — **approve / reject / request_changes / escalate / hold / comment**
  — each permission-gated. Decisions are recorded (`ApprovalDecision`) and, where
  appropriate, drive the lifecycle state machine so a transition is validated,
  historised, and audited exactly once. The decision log **is** the approval
  timeline.

## 2. RBAC Design

Fully **database-driven** access control (`services/rbac/`).

- `catalog.py` is the single pure-data source of truth: **41 fine-grained
  permissions** across 11 categories and **8 roles** (Administrator, Relationship
  Manager, Credit Analyst, Senior Analyst, Risk Manager, Auditor, Compliance
  Officer, Viewer); Administrator maps to `"*"`.
- Schema: `roles`, `permissions`, and the `role_permissions` / `user_roles`
  many-to-many tables; `User` gained a `roles` relationship (non-breaking).
- `sync_rbac()` idempotently reconciles the DB with the catalog (run in the RBAC
  migration and on app startup). Existing users were backfilled to Administrator
  so nobody was locked out; new signups receive Credit Analyst.
- Enforcement via `require_permission("code")` / `require_any_permission(...)`
  dependency factories that resolve the caller's effective permissions and raise
  403 on a miss. Admin API at `/api/rbac`.

## 3. Audit System

Append-only, best-effort, searchable (`services/audit/`).

- `AuditLog` captures user, timestamp, IP, browser (UA), method/path, action,
  entity type/id, **previous & new value**, reason, status, and metadata.
- `record()` / `record_safe()` — recording never breaks a business action.
- `AuditMiddleware` logs every mutating API request (read/static paths skipped);
  domain events (transitions, approvals, RBAC changes, config edits, reports,
  breaches) are recorded explicitly at the service layer.
- Searchable/filterable/paginated dashboard API `/api/audit` (+ `/stats`,
  `/actions`), gated on `audit.view`.

## 4. Monitoring Engine

**Covenant monitoring** (`services/covenants/`)
- 7 metric definitions (DSCR, Debt Ratio, Current Ratio, Interest Coverage, Net
  Worth, EBITDA, Leverage) with min/max semantics. Each measurement is evaluated
  to **ok / warning (5% band) / breach / unknown** with signed headroom; a breach
  auto-raises a `CovenantAlert`, audits, and notifies the owner. Tracks current
  value, threshold, status, trend, and alert history.

**Post-disbursement monitoring** (`services/monitoring/`)
- 7 record types (financial update, quarterly, annual, GST, bank statement,
  payment behaviour, rating change). Adding a record runs **automatic
  deterioration detection** — health-score drop ≥5 pts, rating downgrade (ordinal
  band comparison), late/defaulted payment → `MonitoringAlert` + owner
  notification. Produces a health timeline and risk-trend signal.

## 5. Collaboration Module

`services/collaboration/`
- Threaded notes/comments on applications (`parent_id` replies), pinned notes
  (surfaced first), soft-delete.
- **@mentions** resolved from an explicit id list *and* `@email` tokens parsed
  from the body; each fires a `mention` notification.
- **File attachments** reusing the Phase 2 storage backend (no DB blobs).
- **Unified activity feed** aggregating status history + approval decisions +
  notes + tasks into one chronological stream. API `/api/collaboration`.

## 6. Task System

`services/tasks/`
- Tasks (7 types) attached to applications with owner / priority / due date /
  status / comments.
- Side effects through the notification engine: assign → owner, complete →
  creator, reassign → new owner. `scan_due_tasks()` is a background-job-ready
  sweep for due/overdue tasks. API `/api/tasks`.

## 7. Notification Architecture

`services/notifications/`
- **12 event types**, each with a default severity.
- **Pluggable channels**: `InAppChannel` persists rows; `EmailChannel` /
  `WebhookChannel` share the same interface as log-only stubs ("email-ready /
  webhook-ready") — swapping in a provider is filling one method.
- `notify()` honours **per-user, per-event preferences** (in-app on, email/webhook
  off by default); `notify_safe()` is used for cross-module hooks so delivery
  never breaks a business action.
- Read/unread, unread-count, mark-all-read, preference management. API
  `/api/notifications`, always scoped to the caller's own messages.
- **Cross-module wiring:** lifecycle transitions, approval decisions, covenant
  breaches, and monitoring deterioration all emit notifications to the
  application's owner/assignee.

## 8. Report Generator

`services/reports/`
- **8 report types** — Credit Memo, Executive Summary, Financial, Risk, Committee
  Pack, Portfolio, Compliance, Audit — composed from existing engines into a
  normalised section document (kv / table / text sections). Defensive: missing
  linked data yields a placeholder, never an error.
- **5 formats**: JSON, HTML, **PDF (reportlab, live)**, **CSV (opens in Excel)**,
  **RTF (opens in Word)**. Only `reportlab` is installed in this environment, so
  the Excel/Word families use zero-dependency, natively-openable formats (CSV /
  RTF); PDF degrades to HTML if reportlab is ever absent. API `/api/reports`
  (`reports.view` for JSON, `reports.export` for downloads).

## 9. Dashboard Improvements

- **Backend** `services/dashboards/` + `/api/dashboards/*`: 7 permission-gated
  aggregate endpoints (operations, admin, analyst, manager, portfolio,
  compliance, monitoring) that compute everything server-side.
- **Frontend** `features/operations/`: a feature folder (types, api, hooks,
  formatters, `OpsLayout`, Recharts charts, applications table) reusing the
  existing risk-intelligence primitives. **7 dashboard routes** wired to live
  APIs with **no placeholder data**, each degrading to a permission-required empty
  state. A new "Credit Operations" sidebar group links them.

## 10. Database Changes

7 Alembic migrations (chain head `d6f7a8b9c0e1`):

| Revision | Tables |
|---|---|
| `e1f2a3b4c5d6` | permissions, roles, role_permissions, user_roles, audit_logs |
| `f2b3c4d5e6a7` | applications, application_status_history, approval_workflows, approval_decisions |
| `a3c4d5e6f7b8` | covenants, covenant_measurements, covenant_alerts, monitoring_records, monitoring_alerts |
| `b4d5e6f7a8c9` | tasks, task_comments, notifications, notification_preferences |
| `c5e6f7a8b9d0` | notes, note_mentions, note_attachments |
| `d6f7a8b9c0e1` | system_config |

Migrations seed data where required (RBAC catalog + user backfill, default
approval workflow, system-config defaults). Indexes are added on every foreign
key and common filter/sort column. `User` gained a `roles` relationship only.

## 11. APIs Added (~60 endpoints)

`/api/rbac`, `/api/audit`, `/api/applications`, `/api/approvals`,
`/api/covenants`, `/api/monitoring`, `/api/tasks`, `/api/notifications`,
`/api/collaboration`, `/api/search`, `/api/reports`, `/api/config`,
`/api/dashboards`, `/api/jobs`. All are additive and permission-gated; Phase 1–4
routes are unchanged.

## 12. Services Added

`services/rbac`, `services/audit`, `services/lifecycle`, `services/approvals`,
`services/covenants`, `services/monitoring`, `services/tasks`,
`services/notifications`, `services/collaboration`, `services/search`,
`services/reports`, `services/config`, `services/dashboards`, `services/jobs`,
plus `core/cache.py` and `core/audit_middleware.py`.

## 13. Security Improvements

- Database-driven RBAC with least-privilege role defaults and fine-grained,
  per-action permission checks on every new endpoint.
- Full audit trail (who/what/when/where + before/after values) with a compliance
  dashboard and automatic API-call logging.
- Notifications and personal dashboards are strictly scoped to the current user.
- Report exports separated from views by permission (`reports.export`).
- Path-traversal-safe storage (reused from Phase 2) for attachments.

> Note (pre-existing, out of Phase-5 scope): the dev JWT secret in
> `core/security.py` is hardcoded and should move to an environment variable
> before production. Flagged, not changed, to preserve behaviour.

## 14. Performance Optimizations

- **Caching**: `core/cache.py` TTL cache (thread-safe, injectable clock),
  applied to hot config reads with write-through invalidation.
- **Background jobs**: `services/jobs/` registry + runner (`due_task_scan`,
  `open_alert_summary`), isolated failures, admin API `/api/jobs` — scheduler-
  ready for cron/APScheduler/Celery beat.
- **Batch processing**: `POST /api/covenants/batch-measurements` records many
  measurements in one call; `scan_due_tasks` batches due-task notifications.
- **Pagination** on every list/search/audit endpoint; **indexes** on all FKs and
  common filter/sort columns; dashboard aggregation done in SQL (`GROUP BY` /
  `COUNT` / `SUM`) rather than in Python.

## 15. Testing Summary

- **266 backend tests, all green** (was 155), via `unittest` + in-memory SQLite
  (StaticPool); API tests mount isolated apps with `get_db` / `get_current_user`
  overridden and RBAC seeded per suite.
- New suites: RBAC, audit, lifecycle, approvals, covenants, monitoring, tasks,
  notifications, collaboration, search, reports, config, dashboards, performance
  (cache/jobs/batch), and an **end-to-end integration test** covering create →
  submit → analysis → approval → covenant breach → monitoring deterioration with
  assertions on the audit trail and cross-module notifications.
- **Frontend**: `npm run build` and `npx tsc --noEmit` both clean. No regressions
  in any prior phase.

Run backend tests: `python -m unittest discover -s backend/tests -p "test_*.py"`
(from the repo root). Apply schema: `python -m alembic upgrade head`.
