# Authentication & Authorization Hardening

_Stage 4, Milestone 3 — Audit of every authentication and authorization path for the AI Credit Intelligence Platform._

This document is the authoritative hardening audit of the platform's identity
surface. It is produced by the additive **Security & Compliance** module
(`backend/app/services/security_compliance/authz.py`) and served live under
`/api/sec/authz`. Like the rest of the module it is **offline-first and
deterministic**.

The audit covers the full identity lifecycle: how a principal proves who they are
(authentication), how a token represents that identity over time (session and
token management), and what that identity is permitted to do (authorization,
least privilege, tenant boundaries). The concrete controls audited are the
pre-existing platform primitives in `core/security.py`, `core/authn.py`, and
`services/rbac`.

> [!IMPORTANT]
> **Authorization posture (development profile): 90 / 100.**
> The identity and access-control machinery is mature — strong password policy,
> rotating refresh tokens with reuse detection, MFA, risk-based step-up, and
> deny-by-default RBAC on every route. The only material deduction is an
> **environment-specific CRITICAL finding**: the development profile ships a
> default `JWT_SECRET_KEY` / `SECRET_KEY`. `validate_runtime()` correctly flags
> these; setting real secrets in staging/production clears the finding. See
> [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md).

---

## 1. Authentication paths

Every way a principal can authenticate is enumerated below with its control and
verdict.

| Path | Mechanism | Control | Verdict |
|------|-----------|---------|---------|
| **Password login** | Username + password | bcrypt hashing (`core/security.py`), `PasswordPolicy` (min 12 + complexity) | **Satisfied** |
| **Brute-force resistance** | Repeated failed attempts | `AccountLockout` (progressive lockout) + rate limiting | **Satisfied** |
| **MFA** | Second factor | `Totp` (RFC 6238) time-based one-time passwords | **Satisfied** |
| **Risk-based step-up** | Anomalous session | `RiskEngine` scores failed logins, new/untrusted device, impossible travel, off-hours → `allow` / `step_up_mfa` / `block` | **Satisfied** |
| **Access token issuance** | Post-authentication | `create_access_token` (HS256), short expiry | **Satisfied** |
| **Token signing keys** | Signature material | `JwtKeyRing` with `kid` rotation | **Satisfied** (default secret in dev only — CRITICAL until real secret set) |
| **Refresh / re-authentication** | Long-lived session continuity | `RefreshTokenService` rotation + reuse detection + family revocation | **Satisfied** |

---

## 2. JWT and token lifecycle

| Control | Detail | Verdict |
|---------|--------|---------|
| **Algorithm** | HS256 signed tokens via `create_access_token` | **Satisfied** |
| **Expiration** | Short access-token TTL; expiry enforced on every request | **Satisfied** |
| **Key rotation** | `JwtKeyRing` supports multiple signing keys addressed by `kid`; rotation does not invalidate in-flight valid tokens signed by a still-trusted key | **Satisfied** |
| **Signature verification** | Every protected route verifies the signature before authorization; forged/altered claims are rejected | **Satisfied** |
| **Refresh token rotation** | `RefreshTokenService` issues a new refresh token on each use and invalidates the previous one | **Satisfied** |
| **Reuse detection** | Presentation of an already-rotated (stolen) refresh token is detected | **Satisfied** |
| **Family revocation** | On reuse detection the entire token family is revoked, forcing re-authentication | **Satisfied** |
| **Logout / session invalidation** | Logout revokes the active refresh-token family; subsequent refresh attempts fail | **Satisfied** |
| **Secret material** | `JWT_SECRET_KEY` — default placeholder in dev flagged CRITICAL by `validate_runtime()`; real secret required in prod | **Environment finding** |

### 2.1 Refresh-token rotation flow

```
Login ──► issue access(short TTL) + refresh(family F, gen 0)
Refresh(gen 0) ──► issue access + refresh(family F, gen 1); revoke gen 0
Refresh(gen 0 again = REUSE) ──► DETECTED ──► revoke entire family F ──► force re-auth
Logout ──► revoke family F
```

This flow directly mitigates STRIDE-S2 (stolen/replayed token) and keeps the
session-management posture strong even if a refresh token is exfiltrated.

---

## 3. Session and device management

| Control | Detail | Verdict |
|---------|--------|---------|
| **Session invalidation** | Logout and family revocation terminate sessions server-side | **Satisfied** |
| **Device sessions** | Sessions carry device/trust context feeding `RiskEngine`; new/untrusted devices raise the risk score and can trigger step-up | **Satisfied** |
| **Idle / absolute expiry** | Short access-token TTL bounds session lifetime; refresh required to continue | **Satisfied** |
| **Anomaly response** | High-risk sessions are stepped up (MFA) or blocked; anomalies are recorded | **Satisfied** |

---

## 4. Cookie, CSRF, and header context

| Control | Detail | Verdict |
|---------|--------|---------|
| **Cookies** | Secure attributes; tokens follow the bearer model rather than ambient cookies | **Satisfied** |
| **CSRF** | Bearer-token (non-cookie) auth model plus `SecurityHeadersMiddleware` (X-Frame-Options DENY) minimises CSRF surface | **Satisfied** |
| **Security headers** | HSTS, CSP, XFO DENY, X-Content-Type-Options nosniff, Referrer-Policy, Permissions-Policy, COOP/CORP | **Satisfied** |

---

## 5. Authorization & RBAC

Authorization is enforced by `services/rbac` with `require_permission` on **every
route**. The model is **deny-by-default**: a route with no granted permission is
inaccessible.

| Control | Detail | Verdict |
|---------|--------|---------|
| **Least privilege** | Fine-grained permission catalog; roles hold only the permissions they need | **Satisfied** |
| **Route enforcement** | `require_permission` gates every endpoint, including all 45 `/api/sec/*` routes | **Satisfied** |
| **Permission inheritance** | Roles map to permission sets; oversight roles receive read-only grants, owners receive manage grants | **Satisfied** |
| **Admin privileges** | `administrator` holds all permissions; the `sec.admin` permission gates the privileged Security & Compliance surface | **Satisfied** |
| **Tenant boundaries** | Ambient tenant context (`TenantMiddleware`) scopes every authorization decision to the caller's tenant (see [MULTI_TENANT_SECURITY.md](MULTI_TENANT_SECURITY.md)) | **Satisfied** |
| **Audit trail** | `AuditMiddleware` records one immutable row per mutating request; retention 7y | **Satisfied** |
| **Privilege-escalation detection** | Grants of ≥2 sensitive permissions are flagged; deny-by-default prevents implicit escalation | **Satisfied** |

### 5.1 Security & Compliance permission ownership

The module adds **20 permissions** in the "Security & Compliance" category
(`services/rbac/catalog.py`). Ownership follows least privilege:

| Role | Grants |
|------|--------|
| `compliance_officer` | Owner — view + manage across compliance, privacy, findings, risk |
| `risk_manager` | Owner — view + manage across risk, findings, and posture |
| Oversight roles | Read-only (`*.view`) |
| `administrator` | All 20 permissions |

The manage-tier permissions (`sec.privacy.manage`, `sec.compliance.manage`,
`sec.findings.manage`, `sec.risk.manage`, `sec.admin`) are held only by owners and
`administrator`; all other roles are read-only.

---

## 6. Authorization findings

| # | Finding | Severity | Remediation |
|---|---------|----------|-------------|
| **AUTHZ-01** | Development profile ships a default `JWT_SECRET_KEY` / `SECRET_KEY`; tokens are signable with a known key | **Critical (dev only)** | Set real, high-entropy secrets in staging/production. `validate_runtime()` already enforces this and blocks insecure production boot; no code change required |

No structural authorization defects were found. The `authz` dimension's 90/100
reflects a mature access-control implementation with the single environment-scoped
critical item above; once real secrets are configured the effective posture rises.

---

## 7. How to run it live

The audit is computed by the running platform and exposed as read-only JSON, gated
by the **`sec.authz.view`** RBAC permission (Security & Compliance category;
granted to `compliance_officer`, `risk_manager`, oversight roles read-only, and
`administrator`).

| Endpoint | Returns |
|----------|---------|
| `GET /api/sec/authz` | The full authorization audit with the aggregate `authz` score (90) |
| `GET /api/sec/authz/tenant-isolation` | The 14 tenant-isolation boundaries (see [MULTI_TENANT_SECURITY.md](MULTI_TENANT_SECURITY.md)) |

```bash
curl -H "Authorization: Bearer $TOKEN" \
     https://<host>/api/sec/authz
```

The current development-profile `authz` dimension scores **90 / 100**.

---

## 8. Related documents

- [MULTI_TENANT_SECURITY.md](MULTI_TENANT_SECURITY.md) — tenant boundary enforcement.
- [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md) — the default-secret CRITICAL finding and remediation.
- [OWASP_SECURITY_REVIEW.md](OWASP_SECURITY_REVIEW.md) — A07 / API2 mapping.
- [THREAT_MODEL.md](THREAT_MODEL.md) — STRIDE-S1/S2/E1 identity threats.

← Back to [Security Documentation](index.md)
