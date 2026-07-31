# Admin Guide (v1.0.0)

For platform administrators and the `platform_admin` / `administrator` roles.

## Roles & permissions

RBAC is the single control plane. 175 permissions across categories
(Applications, Approvals, Analysis, Portfolio, AI Intelligence Platform,
Financial Intelligence Platform, Enterprise Platform, Administration, …). The
catalog (`services/rbac/catalog.py`) is the source of truth and is synced to the
DB (`sync_rbac`). Key roles:

| Role | Scope |
|------|-------|
| `administrator` | `*` — every permission |
| `platform_admin` | full SaaS + full enterprise-platform (`ent.*`) surface |
| `risk_manager` | risk/governance across AI, financial and enterprise ops/security |
| `senior_analyst` | run/manage analytics, integration, data, twin, deployment-view |
| `credit_analyst` / `relationship_manager` | run analytics, broad read access |
| `compliance_officer` / `auditor` | read + eval + oversight |

Manage users and roles via the core RBAC APIs (`users.manage`, `roles.manage`).

## Tenant administration

Multi-tenant via Phase 8 SaaS (`/api/saas/*`): create tenants, branding, billing,
feature flags, quotas. Every additive table is tenant-scoped by `tenant_id`.
Tenant health is visible in the operations dashboard.

## Personalization & workspaces

Users set theme/density/accent (`/api/ent/ux/preferences`) and save layouts.
Admins can create team/department/organization workspaces
(`/api/ent/workspaces`) and manage members and shared items.

## Operations & security

- Operations Center (`/api/ent/operations`) — health, incidents, runbooks, RCA.
- Security Center (`/api/ent/security`) — zero-trust, access reviews, key
  rotation, compliance dashboard. Run periodic access reviews per role.
- Monitoring (`/api/ent/monitoring`) — tracing, SLA, cost, capacity.

## Launch readiness

Generate all checklists: `POST /api/ent/launch/generate-all`; track the overall
readiness grade at `GET /api/ent/launch/readiness`. Update items as controls are
completed (`POST /api/ent/launch/items/update`).

## Business intelligence

`/api/ent/bi` provides live executive analytics and a board report. Save curated
dashboards for recurring review.

## Housekeeping

- Run `alembic upgrade head` after each release; verify a down/up round-trip in
  staging.
- Rotate never-used API keys (`GET /api/ent/security/key-rotation`).
- Review the audit log (`audit.view`) for mutating activity.
- Keep the plugin marketplace curated (review before publish; check compatibility).
