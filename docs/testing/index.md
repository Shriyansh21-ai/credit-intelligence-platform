# Testing Documentation

*Testing philosophy and quality assurance for the AI Credit Intelligence Platform.*

The platform is backed by a comprehensive automated test suite: **1,300+ tests across 115
test modules** under `backend/tests`, executed with **pytest**.

## Principles

- **Zero-regression, additive policy** — new capabilities are added without breaking existing
  behavior; the full suite must stay green.
- **Migration round-trip verification** — Alembic migrations are verified for upgrade/downgrade
  integrity as part of CI.
- **Broad coverage** — tests span routes, services, models, ML integration, and background
  workers.

## Related reports

| Report | Description |
| --- | --- |
| [PHASE10_TESTING_REPORT](../reports/PHASE10_TESTING_REPORT.md) | Detailed testing results and coverage for the latest phase. |
| [SYSTEM_HEALTH_REPORT](../reports/SYSTEM_HEALTH_REPORT.md) | Overall system health, including test and stability status. |

> [!TIP]
> Run the full suite with `pytest` from the backend directory before opening a pull request.

← Back to [Documentation Home](../index.md)
