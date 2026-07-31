# API Reference Guide (v1.0.0)

The platform exposes a large REST surface under `/api/*`, all documented live at
`/docs` (Swagger UI) and `/openapi.json`. Every route is RBAC-gated; pass a
bearer token and the caller must hold the required permission.

## Route namespaces

| Prefix | Layer | Auth scope family |
|--------|-------|-------------------|
| `/api/*` | core (assessments, applications, approvals, covenants, RBAC, audit) | applications.*, approvals.*, … |
| `/api/ml/*` | ML platform | mlops.* |
| `/api/integrations/*` | banking connectors | integrations.*, collateral.*, customer360.* |
| `/api/saas/*` | multi-tenant SaaS | tenancy.*, billing.*, flags.*, … |
| `/api/ai/*` | autonomous intelligence | (phase 9) |
| `/api/os/*` | Banking OS | policy.*, committee.*, prompt.*, … |
| `/api/aip/*` | AI Intelligence Platform | aip.* |
| `/api/fin/*` | Financial Intelligence | fin.* |
| `/api/ent/*` | Enterprise Platform | ent.* |

## Track 4 endpoint catalog (`/api/ent/*`, 104 routes)

| Module | Base | Key routes |
|--------|------|-----------|
| UX | `/api/ent/ux` | `GET/POST /preferences`, `GET/POST /layouts`, `GET /commands` |
| Workspaces | `/api/ent/workspaces` | `GET/POST ""`, `/{id}`, `/members`, `/items`, `/{id}/analytics` |
| Developer | `/api/ent/developer` | `/keys`, `/webhooks`, `/webhooks/test`, `/sandbox`, `/requests`, `/explorer` |
| Marketplace | `/api/ent/marketplace` | `/publish`, `/versions`, `/review`, `/{id}/publish`, `/{id}/install`, `/analytics/summary` |
| Integration | `/api/ent/integration` | `/node-types`, `/validate`, `GET/POST ""`, `/run`, `/{id}/runs` |
| Data | `/api/ent/data` | `/golden`, `/duplicates`, `/merge`, `/resolve`, `/rules`, `/quality-scan`, `/import`, `/export`, `/catalog` |
| Operations | `/api/ent/operations` | `/dashboard`, `/incidents`, `/incidents/update`, `/incidents/{id}/rca`, `/runbooks` |
| Security | `/api/ent/security` | `/dashboard`, `/events`, `/analyze-session`, `/escalation-check`, `/access-reviews`, `/key-rotation` |
| Success | `/api/ent/success` | `/dashboard`, `GET/POST ""`, `/events`, `/onboarding/advance`, `/{id}/recommendations` |
| Deployment | `/api/ent/deployment` | `/environments`, `/deploy`, `/rollback`, `/history`, `/versions` |
| Monitoring | `/api/ent/monitoring` | `/traces`, `/dependency-graph`, `/latency`, `/sla`, `/cost`, `/capacity`, `/dashboard` |
| BI | `/api/ent/bi` | `/categories`, `/analytics`, `/board-report`, `/dashboards` |
| Launch | `/api/ent/launch` | `/generate`, `/generate-all`, `/items/update`, `/checklists`, `/readiness` |

## Conventions

- Request bodies are Pydantic-validated; responses are JSON dicts.
- Errors: `400` for validation/domain errors (`{"detail": "..."}`), `403` for
  missing permission, `404` for not-found.
- `tenant_id` is an optional query param on tenant-scoped routes; it defaults to
  the resolved current tenant.
- Computed results embed a `grounding`/`checksum` for reproducibility; AI results
  embed `confidence`, `reasoning`, `citations`, `evidence`.

## Discovering the full surface

`GET /api/ent/developer/explorer` returns live path counts and groups; `/docs`
renders the interactive OpenAPI UI for every namespace above.
