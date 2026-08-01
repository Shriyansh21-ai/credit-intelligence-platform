# Database Report

**Migration:** `e2f3a4b5c6d7_banking_os_phase10` (down_revision `d0e1f2a3b4c5`).
**Additive only** — 25 new `os_*` tables; no existing table altered/dropped.
Verified reversible (upgrade → 25 tables, downgrade → 0) across the full Phase 1→10 chain.

## Conventions
- Every table carries a nullable `tenant_id` (multi-tenant scoping; `NULL` = legacy single-tenant).
- Subjects referenced by stable `*_ref` strings (company name / GSTIN / PAN / application id) —
  loose coupling, no cross-module FK ordering pain.
- `JSON` columns for flexible/nested payloads (rules, graphs, evidence, metrics).
- Natural-key `UniqueConstraint`s for idempotent upserts.

## Tables (25)

| # | Table | Purpose | Key uniqueness |
|---|-------|---------|----------------|
| 1 | `os_policies` | Policy handle | `(tenant_id, key)` |
| 2 | `os_policy_versions` | Immutable rulesets | `(policy_id, version)` |
| 3 | `os_policy_evaluations` | Evaluation audit trail | — |
| 4 | `os_committees` | Standing committees | — |
| 5 | `os_committee_meetings` | Meetings | — |
| 6 | `os_agenda_items` | Decision items | — |
| 7 | `os_committee_votes` | Weighted signed votes | `(agenda_item_id, voter_user_id)` |
| 8 | `os_search_documents` | Universal index | `(tenant_id, doc_type, ref)` |
| 9 | `os_saved_searches` | Saved queries | — |
| 10 | `os_search_history` | Query history | — |
| 11 | `os_prompt_templates` | Prompt handles | `(tenant_id, key)` |
| 12 | `os_prompt_versions` | Immutable prompt revisions | `(template_id, version)` |
| 13 | `os_prompt_evaluations` | Prompt eval runs | — |
| 14 | `os_llm_providers` | Provider registry | `(tenant_id, name)` |
| 15 | `os_llm_invocations` | Call analytics | — |
| 16 | `os_datasets` | Data catalog | `(tenant_id, name)` |
| 17 | `os_data_lineage` | Lineage edges | `(tenant_id, dataset, upstream)` |
| 18 | `os_data_contracts` | Versioned contracts | `(tenant_id, dataset, version)` |
| 19 | `os_data_quality_runs` | Quality evaluations | — |
| 20 | `os_workflow_definitions` | Visual workflows | `(tenant_id, key, version)` |
| 21 | `os_workflow_runs` | Execution traces | — |
| 22 | `os_marketplace_plugins` | Plugin catalog | `(tenant_id, key)` |
| 23 | `os_plugin_recommendations` | Plugin outputs | — |
| 24 | `os_scenario_plans` | Scenario/MC results | — |
| 25 | `os_model_fairness_runs` | Fairness/drift runs | — |

## Indexing
Every `tenant_id` is indexed; high-cardinality lookup columns (`key`, `ref`, `doc_type`,
`domain`, `status`, `subject_ref`, `model_key`, `dataset`, `provider`) are indexed for the
list/filter query patterns the services use. FKs indexed on the child side
(`policy_id`, `template_id`, `meeting_id`, `agenda_item_id`, `committee_id`).

## Integrity
FK constraints tie versions/children to their parents (`os_policy_versions.policy_id`,
`os_committee_votes.agenda_item_id`, `os_prompt_versions.template_id`, etc.). Immutable
version tables are append-only; the parent's `current_version` / `deployed_version`
pointer selects the live revision.
