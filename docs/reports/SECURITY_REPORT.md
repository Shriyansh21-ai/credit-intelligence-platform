# Security Report

_AI Credit Intelligence Platform — Phase 11 (M8, with M5/M12). Date: 2026-07-28._

## Posture

Defense-in-depth across pipeline, transport, application, data, and identity.
Bank-grade controls implemented and tested (26 M8 tests + integration). Full
detail in [SECURITY.md](SECURITY.md); compliance mapping in [COMPLIANCE.md](COMPLIANCE.md).

## Controls by layer

| Layer | Controls |
|-------|----------|
| **Pipeline (M5)** | SAST (bandit, semgrep, CodeQL), dependency audit (pip-audit, bun audit), **secret scanning (gitleaks, hard gate)**, IaC scan (trivy), signed/pinned actions guidance |
| **Transport (M8)** | TLS everywhere, HSTS(+preload), CSP, X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy, COOP/CORP |
| **Identity (M8)** | JWT key rotation (`kid`), refresh-token rotation w/ reuse detection, TOTP MFA, account lockout, risk-based step-up, password policy |
| **Data (M8)** | AES-256-GCM (or authenticated stdlib) field encryption + key rotation + crypto-shred, PII masking, retention + secure deletion, signed URLs |
| **Secrets** | KMS-backed (Terraform), rotation scheduling, no secrets in VCS, references-only backup |
| **AuthZ** | RBAC + least privilege (existing), tenant isolation, per-key API scopes |
| **Audit** | Immutable audit trail (7y), correlation IDs, structured logs |

## Threat model coverage

| Threat | Mitigation |
|--------|-----------|
| Brute force / credential stuffing | Lockout + rate limiter + risk engine |
| Stolen refresh token | Rotation + family revocation on reuse |
| Signing-key compromise | JWT keyring rotation |
| Data-at-rest exposure | Field encryption + KMS + crypto-shred |
| XSS / clickjacking / MIME sniff | CSP + XFO + nosniff |
| MITM | HSTS + TLS-only bucket/edge policies |
| PII leakage (logs/exports) | Masking + retention + secure deletion |
| Secret in VCS | gitleaks hard gate |
| Vulnerable dependency | pip-audit/bun audit + Dependabot |
| Replay (webhooks) | Timestamped HMAC signatures + tolerance window |

## OWASP ASVS / Top-10 alignment

- A01 Broken Access Control → RBAC, tenant isolation, API scopes.
- A02 Cryptographic Failures → AES-GCM, TLS, KMS, key rotation.
- A03 Injection → ORM/parameterized queries; semgrep OWASP ruleset in CI.
- A05 Misconfiguration → strict startup validation, security headers, IaC scan.
- A07 Auth Failures → MFA, lockout, rotation, risk-based auth.
- A08 Integrity Failures → signed webhooks, SBOM + provenance on release images.
- A09 Logging/Monitoring → structured logs, metrics, SLO alerts, audit trail.

## Findings & gate policy

- **Hard gate:** leaked secrets. **Soft gate (SARIF triage):** SAST/IaC —
  adoption posture on a large legacy tree; ratchet to blocking after triage
  (see [TECHNICAL_DEBT_REPORT.md](TECHNICAL_DEBT_REPORT.md) §6).
- No known high-severity application vulnerabilities introduced in Phase 11.

## Pre-go-live security actions

1. Set strong `SECRET_KEY` / `JWT_SECRET_KEY` / `ENCRYPTION_KEY` /
   `CONNECTOR_MASTER_KEY` (startup validation rejects defaults in staging/prod).
2. Point secrets at the cloud secret manager; enable KMS key rotation.
3. Enable code scanning + secret-scanning push protection on the repo.
4. Review CSP against the real frontend origins; enable HSTS preload after
   verifying subdomains.
5. Run a penetration test against staging before production traffic.
