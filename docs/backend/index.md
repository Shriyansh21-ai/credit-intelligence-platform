# Backend Documentation

*The FastAPI service that powers the AI Credit Intelligence Platform.*

The backend is a Python **FastAPI** application located under `backend/app`. It follows a
layered, modular structure that keeps HTTP routing, business logic, and persistence cleanly
separated.

## Application layout

| Layer | Location | Responsibility |
| --- | --- | --- |
| Core | `backend/app/core/` | Configuration, security, dependencies, and cross-cutting utilities. |
| Database | `backend/app/db/` | Engine/session management and connection wiring. |
| Models | `backend/app/models/` | **33 SQLAlchemy models** defining the persistent data model. |
| Schemas | `backend/app/schemas/` | Pydantic request/response schemas and validation. |
| Routes | `backend/app/routes/` | **37 route modules** exposed under `/api/*`. |
| Services | `backend/app/services/` | **24 service packages** holding business logic and orchestration. |
| ML | `backend/app/ml/` | Model integration, scoring, and inference utilities. |
| Workers | `backend/app/workers/` | Background jobs, async tasks, and scheduled processing. |

## Data & migrations

Persistence is backed by **SQLAlchemy** models with schema evolution managed through
**Alembic** migrations. Migrations are applied additively and verified for round-trip
integrity in CI.

> [!TIP]
> For request/response contracts and the full endpoint catalog, see the
> [API documentation](../api/index.md). For system topology, service boundaries, and the
> data model, see the [Architecture documentation](../architecture/index.md).

← Back to [Documentation Home](../index.md)
