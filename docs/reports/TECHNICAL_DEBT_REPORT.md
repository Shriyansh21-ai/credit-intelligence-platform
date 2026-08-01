# Technical Debt Report

_AI Credit Intelligence Platform — Phase 11. Date: 2026-07-28._

Debt is catalogued with severity, impact, and a remediation path. **None of the
items below block a controlled production rollout.**

## Legend
Severity: high · medium · low

---

## 1. Legacy lint findings (gradual adoption)

- **What:** The repo-wide ruff gate enforces the correctness core (`E9,F,PLE`)
  and ignores pre-existing `F401` (unused imports) and `F841` (unused locals) —
  ~79 occurrences across Phases 1–10.
- **Why deferred:** Fixing them touches many prior-phase files; risk/noise
  outweighs benefit for a one-shot sweep. New code is held to the full standard
  via the CI diff gate.
- **Path:** clean per-file as those files are next modified; re-enable `F401/F841`
  repo-wide once at zero. Owner: platform. Effort: S (incremental).

## 2. Legacy typing & SQLAlchemy 2.0 idioms

- **What:** ~1600 `UP045`/`UP006` (old `Optional[...]`/`List[...]`), plus
  `declarative_base()`, `Query.get()`, `datetime.utcnow()` deprecation warnings in
  Phase 1–10 code.
- **Impact:** Cosmetic today; `utcnow`/`Query.get` become hard errors in future
  lib majors.
- **Path:** modernize opportunistically (diff gate enforces on new code); a
  focused SQLAlchemy-2.0 migration PR before upgrading SQLAlchemy majors.
  Owner: backend. Effort: M.

## 3. FastAPI `on_event` → lifespan

- **What:** Startup hooks in `main.py` use the deprecated `@app.on_event`.
- **Impact:** Deprecation warnings; still functional.
- **Path:** migrate to a `lifespan` context manager (single, low-risk change).
  Owner: backend. Effort: S.

## 4. Multi-cloud Terraform breadth

- **What:** AWS has all 11 modules; Azure/GCP implement the core 5 + stack.
  Peripheral domains (CDN, DNS, secrets, monitoring, logging) are AWS-only.
- **Impact:** Full breadth only on AWS today.
- **Path:** mirror the AWS module pattern per provider as those clouds are
  targeted. `terraform validate`/`fmt` not run locally (binary absent) — add to CI
  with cloud OIDC. Owner: platform/SRE. Effort: M per cloud.

## 5. DR / secrets cloud adapters

- **What:** DR backup targets and the secrets provider ship real file/env
  implementations; cloud-native adapters (RDS snapshot, S3 versioning, Secrets
  Manager/Vault) are the documented extension point.
- **Path:** implement per the `BackupTarget`/`SecretManager` interfaces.
  Owner: platform. Effort: M.

## 6. Security scan soft-gates

- **What:** SAST (bandit/semgrep) + IaC (trivy) upload SARIF but don't block
  (adoption posture); only secret leaks hard-gate.
- **Path:** ratchet to blocking on high severity once the legacy backlog is triaged.
  Owner: security. Effort: S (policy).

## 7. Frontend test depth

- **What:** Frontend CI runs lint + typecheck + build; unit/component test depth
  is lighter than backend.
- **Path:** add Vitest/RTL suites for critical components.
  Owner: frontend. Effort: M.

---

## Summary

| Severity | Count |
|----------|:-----:|
| High | 0 |
| Medium | 3 |
| Low | 4 |

No high-severity debt. Medium items are modernization/breadth, addressable
incrementally without disrupting production.
