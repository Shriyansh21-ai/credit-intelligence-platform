# CI/CD Pipeline

_Phase 11, M5 — GitHub Actions delivery pipeline for the AI Credit Intelligence Platform._

This document describes the automated build, test, security, and deployment
pipeline. It is additive to the platform and does not change any application
behaviour.

---

## 1. Overview

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| **CI** | `.github/workflows/ci.yml` | PR + push to `main`/`develop` | Lint, type-check, unit tests (OS × Python matrix), migration round-trip, Docker build, calls Security |
| **Security** | `.github/workflows/security.yml` | `workflow_call`, weekly cron, push to `main` | SAST (bandit, semgrep, CodeQL), dependency audit (pip-audit, bun audit), secret scan (gitleaks), IaC scan (trivy) |
| **Deploy** | `.github/workflows/deploy.yml` | Manual dispatch + auto `develop`→dev | Environment-gated Kubernetes rollout with migrations, smoke test, and automatic rollback |
| **Release** | `.github/workflows/release.yml` | Semver tag `v*` push | Re-test, publish multi-arch images to GHCR, changelog, GitHub Release |

The single **required status check** for branch protection is `CI / CI success`
(the `ci-success` aggregator job). It passes when every non-skipped job passed;
path-filtered jobs that are skipped do not block.

---

## 2. Backend pipeline

Runs when `backend/**`, `requirements.txt`, `pyproject.toml`, or `alembic.ini`
change.

1. **Lint & format** (`backend-lint`)
   - **Repo correctness-core gate:** `ruff check backend` — Pyflakes / syntax /
     Pylint-error rules. Green on the entire legacy tree today.
   - **Strict diff gate:** the full ruff rule set (`E,W,F,I,B,C4,UP,SIM,RET,ISC,
     PIE,RUF,PLE,PLC,PLW,S,DTZ,ASYNC,LOG,G,T20,ARG,PTH`) runs only on the Python
     files changed in the PR, plus `ruff format --check`. New code meets the
     full standard without rewriting prior phases. See
     [CODING_STANDARDS.md](../development/CODING_STANDARDS.md).
2. **Unit tests** (`backend-test`) — matrix of `{ubuntu, windows} × {3.12, 3.13}`
   (windows limited to 3.13 to trim the matrix). Runs `pytest -n auto` with
   coverage; uploads JUnit XML and `coverage.xml` artifacts.
3. **Migration round-trip** (`backend-migrations`) — against a real Postgres 16
   service: asserts a single Alembic head, then `upgrade head → downgrade base →
   upgrade head`.
4. **Docker build** (`docker-build`) — builds the `backend`, `worker`, and
   `scheduler` targets with buildx GHA cache (no push).
5. **Security** — see below.

## 3. Frontend pipeline

Runs when `frontend/**` changes, matrixed over Node `20` and `22`:
`lint → typecheck (tsc --noEmit) → build → bundle analysis` (top assets and total
`dist` size written to the job summary; `dist/` uploaded as an artifact).

## 4. Security pipeline

Gate policy (enterprise adoption posture):

- **HARD gate:** leaked secrets (gitleaks). Blocks the build.
- **SOFT gate:** SAST (bandit, semgrep) and IaC (trivy) upload SARIF to the
  **Security → Code scanning** tab for triage; they do not block, enabling
  adoption on a large legacy tree.
- **Report:** dependency advisories (`pip-audit`, `bun audit`) are always
  captured as artifacts; tighten to a hard gate once the backlog is clean.
- **CodeQL** runs semantic analysis for Python and JS/TS on every PR and weekly.

## 5. Deployment pipeline

Deployments flow through **GitHub Environments**: `development`, `staging`,
`production`. Protection rules (reviewers, wait timers, allowed branches) are
configured per environment in repo settings (see
[BRANCH_PROTECTION.md](../development/BRANCH_PROTECTION.md)); production's manual approval is
enforced by the platform, not workflow code.

Per environment the `deploy` job:

1. Resolves the immutable image tag (semver for prod, SHA for auto-dev).
2. Runs migrations as a one-shot idempotent Alembic Job (optional toggle).
3. `kustomize edit set image` → `kubectl apply -k deploy/k8s/overlays/<env>`.
4. Waits for every Deployment's rollout.
5. **On failure, `kubectl rollout undo` every workload** (automatic rollback).
6. Smoke-tests `/livez` and `/readyz`.

Required repo/environment configuration:

| Kind | Name | Notes |
|------|------|-------|
| Secret (per env) | `KUBE_CONFIG_B64` | base64 kubeconfig for that cluster |
| Variable (per env) | `K8S_NAMESPACE` | e.g. `ai-credit-dev`, `ai-credit-staging`, `ai-credit` |
| Variable (per env) | `APP_URL` | public URL for the smoke test |

Auto-deploy: a green **CI** run on `develop` triggers a deploy to
`development`.

## 6. Release & versioning

- **Semantic versioning.** Releases are cut by pushing a tag
  `vMAJOR.MINOR.PATCH[-prerelease]`. The tag is the single source of truth.
- **Artifact versioning.** Images are pushed to GHCR tagged with the exact
  version, `sha-<12>`, and (for non-prereleases) the moving `MAJOR`, `MAJOR.MINOR`,
  and `latest` aliases. Multi-arch (`amd64`/`arm64`) with SBOM + provenance.
- **Changelog** is generated from commits since the previous tag and attached to
  a GitHub Release; the frontend `dist` tarball is uploaded as a release asset.

```bash
# Cut a release
git tag v1.4.0
git push origin v1.4.0
```

## 7. Caching & performance

- pip wheel cache via `actions/setup-python` keyed on `requirements.txt`.
- Docker layer cache via buildx `type=gha` scoped per target.
- bun install cache via `oven-sh/setup-bun`.
- `pytest -n auto` (xdist) parallelises the suite across cores.
- Concurrency groups cancel superseded PR runs (never on protected branches).

## 8. Local parity

```bash
ruff check backend                       # repo gate
ruff format --check <changed-files>      # strict format (new code)
pytest backend/tests -n auto             # tests
alembic upgrade head && alembic downgrade base && alembic upgrade head
cd frontend && bun run lint && bun run typecheck && bun run build
```
