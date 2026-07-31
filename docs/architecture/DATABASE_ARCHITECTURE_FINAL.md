# Database Architecture — Final (v1.0.0)

## Migration lineage

All schema is managed by Alembic with a **single linear head**. Each phase/track
appends one reversible, metadata-derived migration:

```
… → e2f3a4b5c6d7 (Phase 10 banking_os)
   → f3a4b5c6d7e8 (Track 2 ai_platform, 31 aip_* tables)
   → a1b2c3d4e5f6 (Track 3 financial_intelligence, 21 fin_* tables)
   → b2c3d4e5f6a7 (Track 4 enterprise_platform, 29 ent_* tables)   ← HEAD
```

Every additive migration follows the same safe pattern: import the models module
to register the tables on the shared metadata, select only the prefixed tables,
`create_all(checkfirst=True)` on upgrade, drop-in-reverse on downgrade. This
means the migration can never drift from the ORM and is idempotent over an
existing database.

## Additive table families

| Prefix | Track/Phase | Count | Purpose |
|--------|-------------|-------|---------|
| `aip_*` | Track 2 | 31 | RAG, agents, memory, prompts, eval, reports, workflows, governance |
| `fin_*` | Track 3 | 21 | treasury, portfolio, regulatory, economic, ESG, market, quant, twin, strategic |
| `ent_*` | Track 4 | 29 | UX, workspaces, developer, marketplace, integration, MDM, ops, security, success, deploy, monitoring, BI, launch |
| `os_*` | Phase 10 | 25 | Banking OS |
| core | Phase 1–9 | many | assessments, RBAC, approvals, covenants, ML, SaaS, connectors |

## Conventions (all additive tables)

- Integer PK `id`, indexed.
- Nullable `tenant_id` (multi-tenant isolation, backward compatible).
- String refs (`company_ref`, `subject_ref`, `user_ref`) instead of hard FKs to
  domain objects, to stay loosely coupled and avoid cross-model FK-ordering pain
  in targeted test schemas. FKs are used *within* a track's own tables.
- JSON columns (nullable=False, default list/dict) for rich payloads keep the
  schema stable while storing structured results.
- `created_at` / `updated_at` timestamps; `created_by` string where relevant.
- Content-addressed `checksum` columns on computed/result tables for audit and
  reproducibility.

## Track 4 `ent_*` tables

`ent_user_preferences`, `ent_saved_layouts`, `ent_workspaces`,
`ent_workspace_members`, `ent_workspace_items`, `ent_api_keys`, `ent_webhooks`,
`ent_webhook_deliveries`, `ent_api_requests`, `ent_plugins`,
`ent_plugin_versions`, `ent_plugin_installs`, `ent_pipelines`,
`ent_pipeline_runs`, `ent_mdm_records`, `ent_data_rules`, `ent_data_jobs`,
`ent_ops_incidents`, `ent_runbooks`, `ent_security_events`, `ent_access_reviews`,
`ent_customers`, `ent_customer_events`, `ent_environments`, `ent_deployments`,
`ent_traces`, `ent_sla_records`, `ent_bi_dashboards`, `ent_checklists`.

## Integrity & recovery

- Every migration is reversible (verified up/down for each track).
- API-key secrets are never stored — only SHA-256 hashes + a display prefix.
- Backups and RPO/RTO are covered operationally (see `OPERATIONS_GUIDE.md`).
