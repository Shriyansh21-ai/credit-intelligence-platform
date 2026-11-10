# Phase 7.3 Security and Tenant-Isolation Validation

**Validation date:** 2026-11-05
**Verdict:** **FAIL**
**Scope:** Authentication, authorization, tenant isolation, object references, and workflow controls in the credit-intelligence platform.

## Executive summary

Authentication and route-level RBAC checks are present. Tenant scoping is applied in the newer company, document, credit-review, portfolio-risk, exposure-exception, and company-covenant flows reviewed. However, isolated SQLite tests reproduced cross-tenant reads through three legacy areas:

1. Application lifecycle records and history.
2. Legacy application-based covenants and alerts.
3. Audit history and aggregate endpoints.

The affected legacy models do not persist a tenant identifier. No code or migration changes were made: safely assigning historical records requires an explicit tenant-attribution and backfill policy.

## Authentication and authorization architecture

- HTTP Bearer authentication provides a JWT. `get_current_user` decodes it and resolves the user from the database.
- `get_current_tenant_id` resolves the user's active tenant membership, provisioning an isolated tenant when needed. It does not automatically scope routes that do not depend on it.
- `require_permission` checks server-side permission grants derived from assigned roles. The canonical permission and role catalog is in `backend/app/services/rbac/catalog.py`.
- Therefore, permission checks alone do not ensure tenant isolation; object and list queries must also constrain by tenant.

## Endpoint-to-control inventory

| Domain / endpoints reviewed | Authentication and permission controls | Tenant/object scope | Result |
|---|---|---|---|
| Company and financial-data access; portfolio company and overview paths | Authenticated routes with portfolio permissions | Reviewed portfolio service queries constrain company records by tenant | No defect demonstrated in reviewed paths |
| Document upload, extraction, review, approval/rejection, history, file retrieval, and deletion | Document/approval permissions and authenticated user context | Document and company lookups are tenant-aware; approval persistence uses tenant-matched financial records | No defect demonstrated in reviewed paths; some document workflow tests skipped under system Python |
| Credit-review cases and decisions | Operation-specific `credit_reviews.*` permissions | Tenant ID passed to case, company, assignment, and decision services | No defect demonstrated in reviewed paths |
| Portfolio limits, exposures, breaches, exceptions, and event history | `portfolio.view` / `portfolio.limits.manage` | Breaches are looked up through tenant-owned limits; limit history validates its parent; exception review prevents self-review | No defect demonstrated in reviewed paths |
| New company-covenant monitoring | Portfolio permissions | Tenant/company-scoped records and evidence | No defect demonstrated in reviewed paths |
| Legacy applications, lifecycle, and status history (`/api/applications`) | `applications.*` permissions | List and object lookups are global; `Application` and its history lack tenant attribution | **Cross-tenant reads reproduced; writes through global ID lookup remain at risk** |
| Legacy application-based covenants (`/api/covenants`) | `covenants.view` / `covenants.manage` | Application, covenant, and alert queries use IDs without tenant context; legacy covenant records lack tenant attribution | **Cross-tenant read reproduced; write routes use similarly unscoped objects** |
| Audit search, stats, and actions (`/api/audit`) | `audit.view` | Query and aggregates are global; `AuditLog` has no tenant identifier | **Cross-tenant audit read reproduced** |

## Findings

### 1. HIGH — Application endpoints do not enforce tenant isolation

- **Location:** `backend/app/routes/applications.py`, including `_get_app`, list, detail, update, transition, rollback, cancel, and history endpoints.
- **Evidence:** In an isolated fixture, a user from Tenant B with the auditor role received HTTP 200 when retrieving a Tenant A application ID. The global list included that application.
- **Impact:** Tenant-authorized users may access foreign application details and history. Mutation endpoints also retrieve targets using the same unscoped ID lookup; cross-tenant writes were not directly exercised.
- **Confidence:** 10/10.

### 2. HIGH — Legacy covenant endpoints do not enforce tenant isolation

- **Location:** `backend/app/routes/covenants.py`, including application-based list/create, covenant measurement/trend, batch measurements, alerts, and alert updates.
- **Evidence:** In an isolated fixture, a Tenant B auditor retrieved a Tenant A covenant through the application covenant list.
- **Impact:** Foreign covenant and alert details are exposed; write-capable endpoints use similarly unscoped object references. Cross-tenant writes were not directly exercised.
- **Confidence:** 10/10.

### 3. HIGH — Audit endpoints expose global audit data to tenant auditors

- **Location:** `backend/app/services/audit/query.py` and `backend/app/routes/audit.py`.
- **Evidence:** In an isolated fixture, a Tenant B auditor with `audit.view` received Tenant A's audit entry. The query layer also computes global statistics and action catalogs.
- **Impact:** Audit history and its aggregate metadata can be disclosed across tenant boundaries.
- **Confidence:** 10/10.

## Validation scenarios

- Created isolated SQLite fixtures with separate tenant memberships and real catalog roles.
- Directly tested cross-tenant application detail and list, legacy covenant listing, and audit history reads.
- Tested unauthenticated requests to `/api/applications`, `/api/audit`, and `/api/covenants/metrics`; each returned HTTP 403.
- Ran focused portfolio, document, RBAC, credit-review, covenant, and audit tests.
- Did not directly exercise cross-tenant writes on legacy application/covenant routes, cross-tenant administrator behavior, or every individual object-reference variant.
- No production or external systems were contacted; test records were synthetic and isolated.

## Fixes and migration status

No fixes were made. The legacy `Application`, `Covenant`/alert, and `AuditLog` records do not persist tenant attribution. Deriving ownership only from a user's current membership is unsafe where memberships can be multiple or change, and audit events can be recorded without a tenant actor. A safe remediation requires an explicit source-of-truth and historical backfill rule. No migration was created or modified.

## Validation commands and results

| Command | Result |
|---|---|
| `.venv\Scripts\python.exe -m pytest backend/tests -q` | **1,508 passed** |
| Focused suite: `python -m pytest backend/tests/test_portfolio_risk.py backend/tests/test_document_workflow.py backend/tests/test_documents.py backend/tests/test_security_rbac.py backend/tests/test_rbac.py backend/tests/test_credit_reviews.py backend/tests/test_covenants.py backend/tests/test_audit.py -q` | **76 passed, 7 skipped**; skipped document tests lacked PyMuPDF under system Python |
| `python -m pytest backend/tests -q` | **1,499 passed, 7 skipped, 2 failed**; system Python lacked LightGBM for two ML tests. The configured project virtual environment had the dependency and the full suite passed there. |
| `.venv\Scripts\ruff.exe check backend` | **All checks passed** |
| `git diff --check` | **Passed** |

An additional isolated run including `test_lifecycle.py` failed during SQLAlchemy metadata setup because that selection did not register the `companies` table; this was a fixture/table-registration issue, not a passing security check.

## Gaps and environment status

- Cross-tenant write attempts on legacy application and covenant endpoints were not directly exercised.
- Tenant-administrator and platform-administrator cross-tenant boundary behavior was not established.
- PostgreSQL integration validation was **not run** because a PostgreSQL test instance was unavailable.
- No live PostgreSQL-specific behavior is claimed as verified.

## Git worktree

Initial and final status: `main...origin/main [ahead 1]`, clean worktree. No source files or migrations were changed during validation.
