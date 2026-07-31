# Coding Standards

_Phase 11, M13 — engineering standards for the AI Credit Intelligence Platform._

---

## 1. Principles

- **Backward compatibility first.** Never break or remove an existing public API,
  response shape, status code, or feature. All change is additive; refactor
  internals freely as long as the public surface is preserved.
- **SOLID + Clean Architecture + DDD.** Domain logic in `services/`, transport in
  `routes/`, persistence in `models/` + `db/`, cross-cutting concerns in `core/`.
- **Dependency injection.** Inject collaborators (DB session, clocks, transports,
  collectors) so units are testable without I/O — see M8–M12 modules for the pattern.
- **Everything configurable + typed.** New tunables go through
  `core/settings.py` (typed, validated). Public functions are type-annotated.
- **No placeholders, no TODOs, no fake implementations** in committed code.

## 2. Python

- Target **Python 3.13**. Prefer modern syntax: `X | None`, PEP 695 generics
  (`class Page[T]`), `StrEnum`, `datetime.now(UTC)`.
- Line length **100**. Double quotes. `snake_case` functions, `PascalCase`
  classes, `UPPER_SNAKE` constants.
- Modules start with a docstring stating purpose + how they fit the whole.
- Defensive cross-cutting code (telemetry, middleware) must be best-effort and
  never break request handling; use `contextlib.suppress` over bare `try/except/pass`.

## 3. Linting & formatting — two-tier ruff

The platform adopts ruff on a large pre-existing codebase without mass-rewriting
prior phases (see [ADR-0002](adr/0002-two-tier-lint-adoption.md)):

1. **Repo-wide correctness-core gate** — `pyproject.toml` selects `E9, F, PLE`
   (syntax/runtime errors, Pyflakes, Pylint errors). `ruff check backend` is
   **green on the entire tree** and runs in CI on every push.
2. **Strict diff gate** — CI (`.github/workflows/ci.yml`) runs the full rule set
   `E,W,F,I,B,C4,UP,SIM,RET,ISC,PIE,RUF,PLE,PLC,PLW,S,DTZ,ASYNC,LOG,G,T20,ARG,PTH`
   plus `ruff format --check` **only on the files changed in a PR**. New code
   meets the complete standard.

Run locally before pushing:

```bash
ruff check backend                                  # repo gate (must pass)
ruff check --select E,W,F,I,B,UP,SIM,RUF,S,PTH <changed.py>   # strict (new code)
ruff format <changed.py>
```

Test modules are exempt from security/path/redefinition lints (asserts, fixture
secrets, local imports are idiomatic in tests) via `per-file-ignores`.

The pre-existing `F401`/`F841` occurrences are ignored repo-wide and tracked in
[TECHNICAL_DEBT_REPORT.md](TECHNICAL_DEBT_REPORT.md) as gradual-adoption debt.

## 4. Tests

- `pytest backend/tests`, run from the repo root. Tests use `unittest.TestCase`
  style with in-memory SQLite (`StaticPool`) fixtures.
- **Never reduce coverage.** Every new module ships with tests; every bug fix
  adds a regression test.
- Make time/randomness deterministic by **injecting clocks** — do not rely on
  wall-clock in assertions.
- Register custom markers in `pyproject.toml` (`--strict-markers` is on).

## 5. Database & migrations

- Schema changes go through **Alembic** (`alembic revision --autogenerate`);
  `create_all` is never used at runtime. Keep a **single head**.
- Migrations must be **additive and reversible** — implement both `upgrade` and
  `downgrade`; the CI migration job runs `upgrade → downgrade → upgrade`.

## 6. API

- Follow the conventions in [API_PLATFORM.md](API_PLATFORM.md): versioned public
  routes, pagination on every list endpoint, consistent error bodies, correlation
  IDs, rate-limit headers.

## 7. Security & data

- No secrets in code or VCS (gitleaks hard-gates the pipeline).
- Encrypt sensitive fields (`core/crypto`), mask PII in logs/exports, honour
  retention. See [SECURITY.md](SECURITY.md).

## 8. Commits & reviews

See [CONTRIBUTING.md](CONTRIBUTING.md) — Conventional Commits, PR template,
Code Owner review, green `CI / CI success` required to merge.
