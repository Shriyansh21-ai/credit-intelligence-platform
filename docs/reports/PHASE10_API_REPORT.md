# API Report

**12 routers, 83 routes**, all under `/api/os/*`, versioned and additive. Every route
enforces RBAC via `require_permission(...)`; mutating routes validate typed Pydantic
bodies; errors surface as `400` (validation), `403` (permission), `404` (missing).

## Router map

| Router | Prefix | Milestone | Representative endpoints |
|--------|--------|-----------|--------------------------|
| Policy Engine | `/api/os/policy` | M7 | `GET /domains`, `POST /`, `POST /{id}/versions`, `POST /{key}/evaluate`, `POST /playground` |
| Committee | `/api/os/committee` | M4 | `POST /committees`, `POST /meetings`, `POST /agenda`, `POST /agenda/{id}/vote`, `POST /agenda/{id}/decide`, `GET /analytics` |
| Search | `/api/os/search` | M2 | `POST /`, `POST /index`, `POST /reindex`, `GET /autocomplete`, `GET /facets`, `POST /saved` |
| Prompt | `/api/os/prompt` | M8 | `POST /`, `POST /{id}/versions`, `POST /{id}/versions/{v}/approve`, `.../deploy`, `POST /{id}/render` |
| Multi-LLM | `/api/os/llm` | M9 | `GET/POST /providers`, `PATCH /providers/{id}`, `POST /route`, `POST /complete`, `GET /analytics` |
| Data Fabric | `/api/os/fabric` | M14 | `GET /catalog`, `POST /datasets`, `POST /lineage`, `GET /impact/{name}`, `POST /contracts`, `POST /quality` |
| Workflow Studio | `/api/os/workflow` | M11 | `POST /definitions`, `POST /validate`, `POST /run`, `POST /runs/{id}/resume`, `GET /runs` |
| Marketplace | `/api/os/marketplace` | M12 | `GET /plugins`, `POST /seed`, `PATCH /plugins/{key}`, `POST /run`, `GET /recommendations` |
| Scenario | `/api/os/scenario` | M5/M6 | `GET /library`, `POST /run`, `GET /plans` |
| Fairness | `/api/os/fairness` | M13 | `POST /evaluate`, `POST /drift`, `GET /history` |
| Graph Analytics | `/api/os/graph` | M1 | `GET /ubo/{ref}`, `GET /connected-lending/{ref}`, `GET /cross-holdings`, `GET /timeline/{ref}` |
| Executive Center | `/api/os/exec` | M10 | `GET /personas`, `GET /dashboard/{persona}` |

## Conventions
- **Tenant scoping:** optional `tenant_id` query param, else resolved from the Phase 8
  ambient tenant context (`_tenant()` helper).
- **Response shape:** plain JSON dicts assembled by service `*_dict` serializers
  (no leaking ORM objects), mirroring Phase 9.
- **AI/decision outputs** always include `confidence`, `reasons`/`rationale`,
  `evidence` and source references.
- **Permission mapping:** `policy.*`, `committee.*`, `prompt.*`, `llm.*`, `fabric.*`,
  `workflowstudio.*`, `marketplace.*` (new); scenario reuses `simulation.run`, graph reuses
  `intelligence.view`, exec reuses `command.center`, fairness reuses `governance.view`;
  search reuses `search.use`.
