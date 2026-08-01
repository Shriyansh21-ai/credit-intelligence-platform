# Architecture Documentation

*System, database, and platform architecture for the AI Credit Intelligence Platform.*

| Document | Description |
| --- | --- |
| [ARCHITECTURE](ARCHITECTURE.md) | Core platform architecture: layers, modules, and cross-cutting concerns. |
| [DIAGRAMS](DIAGRAMS.md) | Visual reference: 22 documentation-quality Mermaid diagrams (system, frontend, backend, data, AI/ML/OCR/RAG, security, deployment, Kubernetes, multi-tenancy, knowledge graph, digital twin, workflow). |
| [ARCHITECTURE_TRACK3](ARCHITECTURE_TRACK3.md) | Architecture of the Advanced Financial Intelligence layer. |
| [DATABASE_ARCHITECTURE_FINAL](DATABASE_ARCHITECTURE_FINAL.md) | Final data model: SQLAlchemy schema, migrations, and persistence design. |
| [SYSTEM_ARCHITECTURE_FINAL](SYSTEM_ARCHITECTURE_FINAL.md) | End-to-end system topology, service boundaries, and integration flows. |

## Architecture Decision Records

> [!NOTE]
> ADRs capture significant, long-lived architectural decisions and the context behind them.

| ADR | Description |
| --- | --- |
| [0000 — ADR Template](adr/0000-adr-template.md) | Template and conventions for authoring new ADRs. |
| [0001 — Monorepo Structure](adr/0001-monorepo-structure.md) | Rationale for the single-repository backend + frontend layout. |
| [0002 — Two-Tier Lint Adoption](adr/0002-two-tier-lint-adoption.md) | Phased linting strategy across the codebase. |

← Back to [Documentation Home](../index.md)
