# Contributing

Thanks for contributing to the **AI Credit Intelligence Platform**. This guide
covers the branch model, commit and PR conventions, required checks, and the
backward-compatibility rules that keep a large, multi-phase codebase stable.

See also: [Branch Protection](BRANCH_PROTECTION.md) · [CI/CD](CICD.md) ·
[Developer Guide](DEVELOPER_GUIDE.md) · [Coding Standards](CODING_STANDARDS.md).

## Branch model

- `main` — always releasable; protected.
- `develop` — integration branch; auto-deploys to the development environment on
  green CI.
- Feature branches off `develop` (or `main` for hotfixes):
  `feat/<scope>-<summary>`, `fix/<scope>-<summary>`, `chore/…`, `docs/…`.

Both long-lived branches enforce protection rules (required reviews, Code Owner
review, required status checks, linear history). Details in
[Branch Protection](BRANCH_PROTECTION.md).

## Commit conventions

Use **[Conventional Commits](https://www.conventionalcommits.org/)**:

```
<type>(<scope>): <summary>

<body — what and why, not how>

<footer — BREAKING CHANGE:, refs #123>
```

Types: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`, `ci`,
`chore`. Keep the summary imperative and under ~72 chars. `feat`/`fix`/
`BREAKING CHANGE` drive release notes and versioning (`release.yml`).

## DCO / sign-off

All commits must be signed off under the Developer Certificate of Origin:

```bash
git commit -s -m "fix(auth): reject expired refresh tokens"
```

This adds a `Signed-off-by:` trailer. Configure `git config user.name/email`
first so it matches your GitHub identity.

## Pull request process

1. Branch, implement, and add tests. Keep PRs focused and reasonably small.
2. Run tests and lint locally (below) before pushing.
3. Open a PR into `develop` and fill in the template.
4. CI must be green and **Code Owners** must approve (see `.github/CODEOWNERS` —
   e.g. schema changes require backend + DBA, security surfaces require the
   security team).
5. Squash-merge with a Conventional-Commit title once approved.

### PR template

```markdown
## What
Short description of the change.

## Why
Problem / motivation / linked issue.

## How
Key implementation notes and trade-offs.

## Backward compatibility
- [ ] No breaking API changes (or documented + versioned)
- [ ] Migrations are additive and reversible
- [ ] Config changes documented in docs/CONFIGURATION.md

## Testing
How it was verified; new/updated tests.

## Docs
Docs updated (link) or N/A.
```

## Required CI checks

The `ci-success` aggregator in `.github/workflows/ci.yml` is the single required
status check. It gates on:

- **Backend lint & format** — repo-wide correctness-core `ruff check backend`
  plus the strict full-rule gate on changed files (see
  [ADR 0002](adr/0002-two-tier-lint-adoption.md)).
- **Backend tests** — pytest across the OS × Python matrix.
- **Migration round-trip** — upgrade → downgrade → re-upgrade on real Postgres,
  single-head assertion.
- **Security** — dependency/secret/code scanning.
- **Frontend** — lint, type-check, build (bun).
- **Docker build** — backend/worker/scheduler targets.

Path filters skip lanes for untouched trees; skipped ≠ failed.

## Run tests & lint locally

```bash
pip install -r requirements.txt
pytest backend/tests                # full suite from repo root
ruff check backend                  # correctness-core gate
ruff format --check backend         # formatting
# frontend
cd frontend && bun install && bun run lint && bun run typecheck && bun run build
```

To mirror the strict PR gate on your changes:

```bash
ruff check --select "E,W,F,I,B,C4,UP,SIM,RET,ISC,PIE,RUF,PLE,PLC,PLW,S,DTZ,ASYNC,LOG,G,T20,ARG,PTH" \
  --ignore "B008,S101" <your-changed-files>
```

## Additive & backward-compatibility rules

The platform grows in additive phases; existing behavior must keep working.

- **Never break existing APIs.** Add new fields/endpoints; do not remove or
  repurpose existing ones. Breaking changes require a new version and a
  deprecation path — see [API Platform](API_PLATFORM.md).
- **Migrations are additive and reversible.** No destructive column drops/renames
  while live code reads them; every migration must downgrade cleanly. Keep a
  single Alembic head.
- **Config is additive.** New settings get safe defaults in
  `backend/app/core/settings.py`; document them in
  [Configuration](CONFIGURATION.md).
- **Prefer new modules over rewrites** of prior-phase code; hold new code to the
  full lint standard without mass-rewriting history.
