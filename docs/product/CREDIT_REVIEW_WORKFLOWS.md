# Enterprise Credit Review Workflows

Credit review cases connect a tenant's borrower record and approved financial
statements to human-authored assessments, approval decisions, conditions, and
an append-only activity history. The feature uses the existing
`Company`/`CompanyFinancials`/`Document` provenance model, authenticated tenant
resolution, RBAC permissions, and audit log.

## Case lifecycle

```text
draft -> in_review -> pending_approval -> approved
                                      -> declined
                                      -> deferred -> in_review
                                      -> returned_for_revision -> in_review
approved / declined -> in_review (explicitly authorized reopen)
```

The backend owns the transition rules. A complete submitted assessment is
required before a case can enter `in_review`; an in-review case can be sent to
the approval queue only when its latest assessment has been submitted. A
decision requires a rationale and a pending case. Approval with conditions
requires at least one condition. Deferred and returned cases can resume through
an explicit action. Reopening a finalized case requires the
`credit_reviews.reopen` permission and a reason; earlier decisions remain in
history, the case's cycle number increments, and the next decision links to
the previous one. Active tenant users are assignable only when their RBAC role
includes the assessment or decision permission required for that assignment.
The pre-existing `administrator` role explicitly has the catalog's wildcard
permission grant; no separate approval bypass is added.

Assessment saves create immutable versions. A recommendation is recorded with
its assessment and is not a final credit decision. Decision rows and condition
events are historical records; the API has no ordinary-user edit or delete
operation for them. Completing a condition requires notes and explicit user
action. Waiving one requires a reason; uploading a document does not complete a
condition automatically.

## Permissions and separation of duties

| Role | Review capabilities |
| --- | --- |
| Credit Analyst | View/create cases, draft and submit assigned assessments, request approval, resume assigned cases. |
| Senior Analyst | Analyst capabilities plus assignment, decisions, and condition management. |
| Risk Manager | Senior capabilities plus explicit reopening. |
| Auditor, Compliance Officer, Viewer | Read-only review visibility. |

The API derives the actor and tenant from authenticated server context; client
payloads cannot set tenant, actor, audit timestamps, or decision-maker. Every
case and linked record is tenant-filtered. Assignments require active
membership in the case tenant. A reviewer must differ from the analyst, and
the analyst cannot make the final decision even if they hold the decision
permission. When a named reviewer is assigned, only that reviewer can decide.

## Evidence and provenance

Only `CompanyFinancials` rows that join to a same-tenant, same-company
`Document` with status `approved` are snapshotted into a case. Each displayed
financial period includes its source document reference and approval label.
Missing values remain missing; no new credit metric or score is calculated.
Available stored company credit-profile and portfolio-exposure values are
displayed as-is.

The existing financial-analysis and early-warning records are not consistently
linked to tenant companies: financial analyses are user/assessment-scoped, and
risk alerts are user/assessment-scoped. The review feature therefore does not
attach or display those records as company evidence until a verifiable
tenant/company relationship exists. The current case workspace shows approved
financial evidence, stored company risk-profile values, and portfolio exposure
when present. It also includes applicable active portfolio/sector/company
limits and company covenant definitions with their latest stored evaluation
history; these are evidence only and do not update an assessment or decision.
See [Portfolio Risk Intelligence](./PORTFOLIO_RISK_INTELLIGENCE.md) for
calculation and data-quality rules.

## HTTP API

All routes are under `/api/credit-reviews`:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/dashboard` | Tenant case counts, current user's cases, and authorized approval queue. |
| `GET` | `/companies` | Companies available in the current tenant. |
| `GET` | `/assignment-candidates` | Active tenant users available to assign (assignment permission required). |
| `GET` | `/cases` | Tenant-filtered cases; supports `status`, `review_type`, `company_id`, and `assigned_to`. |
| `POST` | `/cases` | Create a draft for a tenant-owned company. |
| `GET` | `/cases/{id}` | Case, approved evidence, assessments, decisions, conditions, and audit history. |
| `PATCH` | `/cases/{id}/assignment` | Assign an active tenant analyst/reviewer. |
| `POST` | `/cases/{id}/assessments` | Append an assessment draft or submitted assessment. |
| `POST` | `/cases/{id}/submit-for-approval` | Send the submitted assessment to the approval queue. |
| `POST` | `/cases/{id}/decisions` | Record approval, conditional approval, decline, defer, or return. |
| `POST` | `/cases/{id}/resume` | Resume a deferred or returned case. |
| `POST` | `/cases/{id}/reopen` | Start a new cycle after an approved/declined decision. |
| `PATCH` | `/cases/{id}/conditions/{condition_id}` | Complete or waive an open condition with notes. |

Dashboard counts are queried from stored tenant cases, not demo fixtures. The
approval queue only includes a pending case if the current user has decision
permission, is not its analyst, and is its named reviewer (or no reviewer is
named).

## Manual acceptance

1. Sign in as a Credit Analyst and open **Credit Reviews**.
2. Create a case for a company in the current tenant. Confirm only approved,
   company-linked financial periods and source documents appear.
3. Save an assessment draft, then submit a summary, evidence references,
   recommendation, and rationale. Confirm the previous draft remains visible
   in history.
4. Sign in as a Senior Analyst or Risk Manager, assign an eligible active
   tenant analyst and a separate eligible reviewer.
5. As the assigned analyst, send the submitted assessment to the approval
   queue.
6. As the assigned reviewer, inspect the evidence and assessment, then approve
   with conditions or choose another outcome and provide a rationale.
7. Complete or waive an open condition with explicit notes and confirm its
   condition history event.
8. As a Risk Manager, reopen a finalized case with a reason. Verify the prior
   decision is still present and a subsequent decision links to it.
9. Try direct cross-tenant reads/writes and an analyst self-approval; the API
   should reject them without revealing the other tenant's record.
