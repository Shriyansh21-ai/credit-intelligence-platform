# ADR 0001: Single monorepo with backend / frontend / deploy / infra / docs

- **Status:** Accepted
- **Date:** 2026-07-28
- **Deciders:** Platform, Backend, Frontend, SRE
- **Tags:** repo-structure, ci-cd, phase-11

## Context

By Phase 10 the platform had grown across ten additive phases into a large
codebase: a FastAPI + SQLAlchemy backend (~350 modules, 1000+ tests), a
TanStack/React frontend, container and Kubernetes manifests, Terraform
infrastructure, and an expanding set of engineering docs. These artifacts are
tightly coupled: the same Alembic schema backs the API and the workers, the
frontend consumes the backend's API contract, and the `Dockerfile` +
`deploy/k8s` manifests must move in lockstep with application code and
migrations.

The Phase 11 M1–M4 restructuring had to settle how these artifacts are
organized before hardening CI/CD, containers, and configuration. The practical
choice was between splitting into multiple repositories (per service or per
concern) and consolidating into one. Multiple repos would force cross-repo
version pinning, multi-repo PRs for a single logical change (e.g. an endpoint +
its migration + its manifest), and duplicated CI plumbing — with no ownership
benefit we couldn't already get from CODEOWNERS.

## Decision

We will keep the platform in a **single monorepo** with a fixed top-level
layout:

```
backend/    FastAPI app (backend/app), Alembic (backend/alembic), tests
frontend/   TanStack/React + Vite app (managed with bun)
deploy/      Dockerfile assets, docker-compose, k8s base + overlays, entrypoint
infra/       Terraform (modules, environments, backends)
docs/        engineering documentation, including this ADR log
```

Tooling config lives at the root (`pyproject.toml`, `requirements.txt`,
`docker-compose.yml`, `.github/workflows`). Path-based ownership is enforced via
`.github/CODEOWNERS`, and CI uses path filters (`dorny/paths-filter`) so
untouched trees skip their lanes. A single `ci-success` aggregator is the one
required status check.

## Consequences

**Positive**

- One PR can carry a change and its migration, manifest, and doc update
  together, reviewed atomically and kept consistent.
- A single Alembic head and one test suite guarantee schema/app/worker coherence.
- Shared CI/CD, container build, and config live in one place; path filters keep
  doc- or infra-only changes fast.
- Ownership and required reviews are expressed per directory without repo
  sprawl.

**Negative / accepted trade-offs**

- The repo is large; contributors clone everything. Mitigated by path-filtered
  CI and clear directory boundaries.
- Fine-grained, per-service access control is coarser than separate repos;
  CODEOWNERS + branch protection cover the real need.
- Independent per-service release cadence requires discipline (immutable image
  tags per service at deploy time) rather than repo boundaries.

## Alternatives considered

- **Polyrepo (repo per service/concern):** rejected — cross-repo coordination
  for coupled changes, version-pinning overhead, and duplicated CI outweigh the
  isolation benefits for a small number of tightly-coupled services.
- **Backend/frontend split (two repos):** rejected — the frontend depends on the
  backend API contract; keeping them together makes contract changes atomic.
- **Status quo (unstructured tree):** rejected — the pre-Phase-11 layout lacked
  clear `deploy/`/`infra/` boundaries, which blocked hardening CI/CD and
  containers.

## References

- Phase 11 M1–M4 restructuring.
- `.github/CODEOWNERS`, `.github/workflows/ci.yml`.
- [Architecture](../ARCHITECTURE.md), [CI/CD](../CICD.md).
