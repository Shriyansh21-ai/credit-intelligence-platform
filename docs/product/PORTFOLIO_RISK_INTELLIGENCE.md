# Portfolio Risk Intelligence

Portfolio risk controls are built on the tenant-scoped `Company`,
`PortfolioExposure`, `CompanyFinancials`, and approved `Document` records. They
are independent of the older user-scoped assessment portfolio endpoint. Every
API request resolves its tenant from the authenticated user; request bodies
cannot select a tenant.

## Exposure metrics and data quality

`GET /api/portfolio-risk/overview` returns company counts, exposure totals
grouped by stored currency, and counts of missing/invalid or unpriced exposure
records. Currency groups are intentionally not combined or converted.

An exposure is eligible for limit calculation only when it has a finite,
non-negative amount and its stored exposure currency matches the configured
limit currency. All companies in the requested scope must have a compatible
exposure record. If any company is missing an exposure or has a missing,
negative, non-finite, or different-currency amount, the limit calculation
returns `insufficient_data`; it does not report zero exposure or utilization.
Historical exposure rows are not assigned a currency automatically. CSV
imports retain a currency only when the import explicitly supplied one.
Eligible exposure is summed before presentation rounding. Returned exposure and
headroom are rounded to two decimal places, and utilization is rounded to six;
limit status is determined from the unrounded sum.

## Exposure limits and breaches

The supported scopes are:

* `portfolio`, with scope key `*`;
* `company`, verified against the authenticated tenant; and
* `sector`, verified against at least one company in that tenant.

Thresholds must be positive. Currency is an explicit uppercase ISO-style
three-letter code; no exchange-rate conversion is performed. Breach comparison
is `eligible_exposure > threshold`. An approaching state is reported only when
an explicit `approaching_ratio` is configured and utilization is greater than
or equal to that ratio. Missing limits are not breaches.

`POST /api/portfolio-risk/limits/evaluate` evaluates active limits and persists
state changes. There is one current breach record per limit, so repeated
evaluation does not create duplicate detection records. First detection,
resolution, reopening, acknowledgement, and configuration changes are
preserved in limit events. Acknowledgement records the actor and reason but
does not resolve the breach; only a later valid evaluation below the threshold
does that. Disabling a limit does not erase an existing breach.

An authorized user may request a reasoned exception for an active breach.
Approval or rejection requires `portfolio.limits.manage` and a different user
from the requester. Request, review, expiry, and remediation-note changes are
recorded in the same append-only limit-event history. Repeated identical
requests and reviews are idempotent. An exception never changes measured
exposure, the limit threshold, the breach status, or the evaluation result.
An approved exception is active until its optional expiry; it can also carry
an optional review date. Evaluation marks expired requests/approvals as
`expired` and leaves the underlying breach in monitoring. A breach resolves
only when a valid exposure evaluation is within its threshold. Each breach
retains its latest exception snapshot; prior request/review cycles remain
available as limit-event history.

`portfolio.limits.manage` is required to create/update limits, evaluate
breaches, and acknowledge them. Read-only users can list visible limits and
bounded event history but cannot modify them. Server-side permission checks
are authoritative.

## Company covenant monitoring

Company covenants support only metrics derivable from the persisted financial
schema:

| Metric key | Formula | Breach rule |
| --- | --- | --- |
| `current_ratio_min` | `current_assets / current_liabilities` | value `<` threshold |
| `debt_to_equity_max` | `debt / equity` | value `>` threshold |
| `debt_to_ebitda_max` | `debt / EBITDA` | value `>` threshold |

Company covenant ratios are rounded to eight decimal places before comparison;
equality with the threshold is compliant.
Evaluations use the latest same-tenant, same-company `CompanyFinancials` row
that joins to a same-tenant, same-company document in `approved` status. A
missing field, negative numerator, zero/negative denominator, or absent
approved statement produces `insufficient_data`, not a breach. The exact
source financial record, source document, extraction reference, fiscal year,
threshold, and input snapshot are stored with each evaluation. Re-evaluation
of identical evidence and threshold returns the existing evaluation; changed
evidence or threshold creates a new history row. Acknowledgement is separate
from the evaluation result and retains the breached status.

Only users with `covenants.manage` may define, update, evaluate, or acknowledge
company covenants. `covenants.view` permits tenant-filtered listing.

## Credit review

Credit-review case detail adds applicable active limit states and company
covenant history as read-only evidence. The evidence is derived from the
case's verified tenant/company relationship. It does not mutate assessment
versions, conditions, or decisions.

Financial analyses and early-warning alerts remain user/assessment-scoped in
the current schema and lack a reliable company/tenant foreign-key relationship.
They are not attached to company risk summaries or credit-review cases. No
company ownership is inferred from names, frontend-supplied IDs, or historical
assessment content. `EnterpriseAssessment` currently has no company or tenant
foreign key, and the analysis/alert rows refer only to the assessment and user.
The legacy `Application` link does not close this gap: it has an assessment
foreign key but only a denormalized company name and no tenant/company foreign
key. Autonomous `EWSAssessment` and `IntelligenceAlert` rows likewise use a
nullable tenant value plus a free-form `company_ref` and assessment value,
neither foreign-keyed to the canonical company or assessment records.
`CreditReviewCase` has authoritative tenant/company keys but has no foreign-key
path to those legacy analysis or EWS rows. Safe company/tenant association
therefore requires a separately approved mapping model and validated write
path; no migration or legacy backfill is made until that authoritative
relationship exists. Ambiguous historical records remain unlinked.

## HTTP API

All routes are under `/api/portfolio-risk`:

| Method | Path | Permission | Purpose |
| --- | --- | --- | --- |
| `GET` | `/overview` | `portfolio.view` | Exposure totals by currency and data-quality counts. |
| `GET` | `/companies` | `portfolio.view` | Bounded tenant-owned company choices. |
| `GET` | `/limits` | `portfolio.view` | Limits, current utilization, and current breach state. |
| `POST` | `/limits` | `portfolio.limits.manage` | Create portfolio/company/sector limit. |
| `PATCH` | `/limits/{id}` | `portfolio.limits.manage` | Change threshold, approaching ratio, or active state with reason. |
| `POST` | `/limits/evaluate` | `portfolio.limits.manage` | Evaluate limits and persist breach transitions. |
| `GET` | `/limits/{id}/events` | `portfolio.view` | Read up to 200 limit and breach events. |
| `POST` | `/breaches/{id}/acknowledge` | `portfolio.limits.manage` | Record an acknowledgement without resolving the breach. |
| `POST` | `/breaches/{id}/exceptions` | `portfolio.limits.manage` | Request an exception with justification and optional expiry/review date. |
| `POST` | `/breaches/{id}/exceptions/review` | `portfolio.limits.manage` | Approve/reject a request; requester cannot review their own request. |
| `POST` | `/breaches/{id}/remediation` | `portfolio.limits.manage` | Record an auditable remediation note without resolving the breach. |
| `GET` | `/companies/{company_id}/covenants` | `covenants.view` | Read covenant definitions and up to 50 evaluations per covenant. |
| `POST` | `/companies/{company_id}/covenants` | `covenants.manage` | Create a company-scoped covenant. |
| `PATCH` | `/covenants/{id}` | `covenants.manage` | Update threshold or active state with a reason. |
| `POST` | `/covenants/{id}/evaluate` | `covenants.manage` | Evaluate against the latest approved financial evidence. |
| `POST` | `/covenant-evaluations/{id}/acknowledge` | `covenants.manage` | Record reviewer acknowledgement without changing the result. |

## Operational limitations

The migration adds a nullable currency to existing exposure records. Legacy
values remain unpriced unless their currency is explicitly provided; the
migration does not guess or backfill it. Covenant evaluation requires approved
document-linked financial records; imported or ad-hoc values without approved
source provenance do not qualify. No PostgreSQL integration service was part
of local development validation; consult deployment CI for database-specific
validation before production rollout.
