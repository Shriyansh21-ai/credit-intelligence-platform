# ADR 0002: Two-tier ruff adoption (repo-wide correctness core + strict diff gate)

- **Status:** Accepted
- **Date:** 2026-07-28
- **Deciders:** Platform, Backend
- **Tags:** linting, ci-cd, code-quality, phase-11

## Context

Phase 11 M5 introduced Ruff as the backend linter and formatter. The backend is
a large, pre-existing codebase — roughly 350 modules produced across Phases 1–10
before any linter was enforced. Turning on Ruff's full rule set repo-wide would
have produced thousands of findings and forced a mass mechanical rewrite of code
from prior phases. That rewrite would be high-risk (large diffs across
well-tested modules), would bury real review signal, and would conflict with the
project's additive, backward-compatible working style.

At the same time, leaving the codebase unlinted means new code accrues the same
debt. We needed strict enforcement going forward without a disruptive
retroactive cleanup, and a gate that is **green today** so linting can be a hard
requirement immediately.

## Decision

We will run Ruff in **two tiers**:

1. **Repo-wide correctness-core gate** — configured in `pyproject.toml`
   (`[tool.ruff.lint] select = ["E9", "F", "PLE"]`): syntax/runtime errors,
   Pyflakes, and Pylint errors — "these are bugs," not style. Two pre-existing
   findings (`F401` unused imports, `F841` unused locals) are ignored repo-wide
   and tracked as debt. This makes `ruff check backend` green on the entire
   legacy tree, so it runs as a hard gate on every push (CI step
   *"Repo correctness-core gate"*).

2. **Strict full-rule gate on changed files only** — in
   `.github/workflows/ci.yml` (`backend-lint` job), CI computes the Python files
   changed in the PR (excluding `backend/alembic/versions`) and runs a much
   broader rule set against just those files:
   `--select "E,W,F,I,B,C4,UP,SIM,RET,ISC,PIE,RUF,PLE,PLC,PLW,S,DTZ,ASYNC,LOG,G,T20,ARG,PTH"`
   `--ignore "B008,S101"`, plus `ruff format --check` on the same files. Test
   modules get idiomatic per-file ignores (`[tool.ruff.lint.per-file-ignores]`
   in `pyproject.toml`).

New and modified code is therefore held to the complete standard; committed
history from earlier phases is not rewritten.

## Consequences

**Positive**

- Linting is adoptable **immediately** as a required check — the repo-wide gate
  is green from day one.
- All new/changed code meets the full standard, so quality ratchets up with
  every PR without a big-bang migration.
- Review noise stays low; diffs reflect intended changes, not mass reformatting.
- The correctness core still protects the whole tree from real defects
  (undefined names, broken imports, f-string errors).

**Negative / accepted trade-offs**

- Legacy files retain style/complexity issues until they are next touched
  (touching a file subjects it to the strict gate). Tracked as debt.
- Two rule lists must be kept in reasonable sync (`pyproject.toml` core vs. the
  CI `--select` list); the CI list is intentionally the superset.
- `F401`/`F841` are globally ignored today; new occurrences in changed files are
  still caught by the diff gate via `F`.

## Alternatives considered

- **Full ruleset repo-wide immediately:** rejected — thousands of findings, a
  risky mass rewrite of tested prior-phase code, and a red gate that can't be
  required.
- **Autofix + reformat the whole tree once:** rejected — an enormous,
  hard-to-review diff that churns stable modules and fights the additive-change
  policy; behavior-changing autofixes carry regression risk.
- **No linting / advisory only:** rejected — provides no enforcement and lets new
  debt accrue indefinitely.
- **Baseline/suppression file:** rejected — comparable outcome to the diff gate
  but with a large generated baseline to maintain; the changed-files approach is
  simpler and needs no artifact.

## References

- `pyproject.toml` (`[tool.ruff]`, `[tool.ruff.lint]`,
  `[tool.ruff.lint.per-file-ignores]`).
- `.github/workflows/ci.yml` (`backend-lint` job).
- [Coding Standards](../../development/CODING_STANDARDS.md), [Contributing](../../../CONTRIBUTING.md).
