# Architecture

_Phase 11, M13 — architecture overview for the AI Credit Intelligence Platform._

An AI-native, multi-tenant enterprise banking platform: credit intelligence,
decisioning, ML risk models, banking connectors, a SaaS control plane, an
autonomous "AI brain", and a banking OS layer — built additively across Phases
1–11.

---

## 1. System context

```mermaid
flowchart TB
    subgraph Clients
      UI[React/TanStack SPA]
      API_Clients[API consumers / SDKs]
      WH[Webhook receivers]
    end
    subgraph Edge
      CDN[CDN] --> LB[Load Balancer / Ingress]
    end
    subgraph Platform[AI Credit Platform]
      API[FastAPI backend<br/>backend.app.main:app]
      WORKER[Workers]
      SCHED[Scheduler]
    end
    subgraph Data
      PG[(PostgreSQL)]
      REDIS[(Redis)]
      OBJ[(Object storage)]
    end
    subgraph Observability
      PROM[Prometheus] --> GRAF[Grafana]
      LOKI[Loki]
      TEMPO[Tempo/Jaeger]
    end
    UI --> CDN
    API_Clients --> LB
    LB --> API
    API --> PG & REDIS & OBJ
    WORKER --> PG & REDIS
    SCHED --> PG
    API -->|events| WH
    API -->|/metrics| PROM
    API -->|structured logs| LOKI
    API -->|OTLP spans| TEMPO
```

## 2. Layered architecture (Clean Architecture / DDD)

```mermaid
flowchart LR
    subgraph transport[Transport - routes/]
      R[FastAPI routers<br/>/api/*, /metrics, /livez]
      MW[Middleware:<br/>CORS, Audit, Tenant,<br/>Observability, Security,<br/>GZip, APIVersion]
    end
    subgraph domain[Domain - services/]
      SVC[analysis, ml, rbac, approvals,<br/>integrations, saas, autonomous,<br/>banking_os, financial_analysis]
    end
    subgraph core[Cross-cutting - core/]
      C[settings, security, crypto, authn,<br/>telemetry, performance, pagination,<br/>api_versioning, webhooks, dr, compliance,<br/>cache, middleware]
    end
    subgraph data[Persistence - models/ + db/]
      M[SQLAlchemy models]
      DB[engine + session + Alembic]
    end
    R --> SVC --> M --> DB
    MW -.-> R
    C -.-> R
    C -.-> SVC
```

Dependencies point inward: transport → domain → persistence. `core/` provides
cross-cutting capabilities to all layers. No layer imports outward.

## 3. Request lifecycle (middleware stack)

Outermost → innermost (response headers applied on the way out):

```
SecurityHeaders → APIVersion → GZip → Observability → Tenant → Audit → CORS → route
```

- **Observability** assigns a correlation id, times the request, records metrics.
- **Tenant** resolves the ambient tenant (multi-tenancy).
- **Audit** records one row per mutating request.
- **Security** stamps OWASP headers; **APIVersion** stamps lifecycle headers.

## 4. Credit decision — sequence

```mermaid
sequenceDiagram
    actor Analyst
    participant API as FastAPI (routes)
    participant SVC as Decision service
    participant ML as ML pipeline (services/ml)
    participant DB as PostgreSQL
    participant OBS as Telemetry

    Analyst->>API: POST /api/.../applications/{id}/assess
    API->>OBS: start correlation + span
    API->>SVC: run assessment (DI: db session)
    SVC->>DB: load application + financials
    SVC->>ML: score(features)
    ML-->>SVC: score + SHAP explanation
    SVC->>DB: persist decision + explanation (audit)
    SVC->>OBS: domain.ml_inference(...), business_event(...)
    SVC-->>API: decision
    API-->>Analyst: 200 decision (+ X-Correlation-ID)
```

## 5. Modules (backend/app)

| Package | Responsibility |
|---------|----------------|
| `core/` | settings, security/crypto/authn, telemetry, performance, pagination, api_versioning, webhooks, dr, compliance, cache, middleware |
| `routes/` | FastAPI routers (`/api/*`), probes, `/metrics` |
| `services/` | domain logic: analysis, ml, rbac, approvals, integrations, saas, autonomous, banking_os, financial_analysis |
| `models/` | SQLAlchemy ORM models (schema owned by Alembic) |
| `db/` | engine, session factory, `get_db` dependency |
| `ml/` | model artifacts + scoring/explainability |
| `workers/` | background worker + scheduler + healthcheck |
| `schemas/` | Pydantic request/response models |

## 6. Deployment topology

Three container images from one multi-stage `Dockerfile` (`backend`, `worker`,
`scheduler`), orchestrated on Kubernetes (`deploy/k8s`) with per-environment
Kustomize overlays, fronted by nginx + ingress, backed by managed Postgres/Redis/
object storage provisioned by Terraform (`infra/terraform`, AWS/Azure/GCP). See
[DEPLOYMENT.md](DEPLOYMENT.md) and [CONTAINERS.md](CONTAINERS.md).

## 7. Cross-cutting concerns → docs

| Concern | Doc |
|---------|-----|
| Observability / SLOs | [OBSERVABILITY.md](OBSERVABILITY.md) |
| Security | [SECURITY.md](SECURITY.md) |
| Performance | [PERFORMANCE.md](PERFORMANCE.md) |
| API platform | [API_PLATFORM.md](API_PLATFORM.md) |
| Disaster recovery | [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md) |
| Compliance | [COMPLIANCE.md](COMPLIANCE.md) |
| CI/CD | [CICD.md](CICD.md) |
| Configuration | [CONFIGURATION.md](CONFIGURATION.md) |

## 8. Architecture Decision Records

Significant decisions are recorded under [`adr/`](adr/) — start with
[ADR-0001 (monorepo)](adr/0001-monorepo-structure.md) and
[ADR-0002 (two-tier lint)](adr/0002-two-tier-lint-adoption.md).
