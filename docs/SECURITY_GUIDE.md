# Security Guide (v1.0.0)

Security spans RBAC (all phases), the Phase 8 SaaS security module, and the
Track 4 Security Center (`/api/ent/security`).

## Zero-trust

- **Session analysis** — `POST /api/ent/security/analyze-session` scores a
  session deterministically on failed logins, new/untrusted device, impossible
  travel and off-hours access, returning a risk score and a decision
  (`allow` / `step_up_mfa` / `block`). High-risk sessions record an anomaly event.
- **Device trust** and **behaviour analytics** feed the same score.
- **Privilege-escalation detection** — `POST .../escalation-check` flags grants of
  ≥2 sensitive permissions (`roles.manage`, `users.manage`, `config.manage`,
  `platform.admin`, `ent.security.manage`, `ent.deploy.manage`).

## RBAC

175 fine-grained permissions across categories, seeded from a single catalog
(`services/rbac/catalog.py`) and synced to the DB. Every route enforces a
permission via `require_permission`. Roles map to permission sets; `administrator`
holds `*`, `platform_admin` owns the full enterprise-platform surface. Access
reviews (`POST /api/ent/security/access-reviews`) auto-summarise a role's
sensitive grants.

## Credentials & keys

- **API keys** are shown **once** at creation and stored only as SHA-256 hashes
  plus a short display prefix. Verification hashes the presented secret.
- **Key rotation** posture: `GET /api/ent/security/key-rotation` reports active /
  never-used keys and recommends rotation.
- **Webhook signing secrets** (`whsec_…`) sign every delivery.

## Compliance dashboard

`GET /api/ent/security/dashboard` returns the security posture, security score,
open-event roll-up by severity, pending access reviews, key-rotation posture and
zero-trust flags (MFA enforced, least privilege, device trust).

## Secure SDLC

CI runs SAST, dependency audit, secret scanning (gitleaks), IaC scan and CodeQL
(`.github/workflows/security.yml`). No secrets are committed; `.gitleaks.toml`
guards the repo.

## Data protection

- Multi-tenant isolation via `tenant_id` on every additive table.
- No external network calls from the additive tracks; market/alt-data providers
  are stubbed behind a `source` field for later gated integration.
- Audit middleware records one row per mutating request.

## Security checklist

Generate with `POST /api/ent/launch/generate {checklist_type: "security"}`:
zero-trust, threat detection, access-review cadence, key-rotation policy and a
third-party penetration test.
