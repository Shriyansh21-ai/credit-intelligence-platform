# STRIDE Analysis

_Stage 4, Milestone 1 — Enterprise Threat Modeling for the AI Credit Intelligence Platform._

This document is the deep, per-category STRIDE analysis behind the enterprise
[threat model](THREAT_MODEL.md). For each of the six STRIDE categories it gives a
definition, the threats in that category (drawn from the 11-threat catalog), the
platform's **real, shipped controls** that address them, and the residual risk.
The analysis is computed by
`backend/app/services/security_compliance/threat_model.py` and served under
`/api/sec/threat/stride` (gated by `sec.threat.view`).

The controls cited below are concrete platform modules, not aspirations:

| Control | Module | What it provides |
|---------|--------|------------------|
| **JWT / `JwtKeyRing`** | `core/authn.py` + `core/security.py` | HS256 access tokens with `kid`-based signing-key rotation and expiry |
| **RBAC `require_permission`** | `services/rbac` | Deny-by-default permission check on every route |
| **`AuditMiddleware`** | `core/audit_middleware.py` | One immutable audit row per mutation |
| **`FieldCipher` / `KeyRing`** | `core/crypto.py` | AES-256-GCM authenticated field encryption with versioned keys, rotation, crypto-shred |
| **`PiiMasker`** | `core/crypto.py` | Masking of email/phone/card/PAN/Aadhaar in logs, exports, non-prod |
| **`TenantMiddleware`** | `core/tenant_middleware.py` | Ambient, non-client-supplied tenant context |
| **`AccountLockout`** | `core/authn.py` | Threshold-based lockout on repeated auth failure |
| **`RefreshTokenService`** | `core/authn.py` | Rotating refresh tokens with reuse detection + family revocation |

Supporting controls also referenced: `PasswordPolicy`, `Totp` (RFC 6238 MFA),
`RiskEngine` (risk-based step-up), and `SecurityHeadersMiddleware`.

---

## 1. Spoofing

**Definition.** Illegitimately assuming the identity of a user, service, or
component — impersonation through stolen, guessed, or forged credentials/tokens.

**Threats in this category:**

| ID | Component | Threat |
|----|-----------|--------|
| STRIDE-S1 | Auth endpoints | Credential stuffing / brute-force to impersonate a user |
| STRIDE-S2 | Session / tokens | Stolen or replayed JWT / refresh token used to assume an identity |

**Existing controls.**
- **S1:** `AccountLockout` locks accounts after repeated failures within a
  window; `PasswordPolicy` rejects weak/common/username-derived passwords; rate
  limiting throttles guessing; `RiskEngine` forces step-up (MFA) on suspicious
  device/IP/geo/velocity signals; `Totp` provides RFC 6238 MFA.
- **S2:** `JwtKeyRing` verifies token signatures and rotates signing keys via
  `kid`; `RefreshTokenService` issues rotating, family-bound refresh tokens and
  **revokes the entire family on reuse of a consumed token**, defeating stolen
  refresh tokens; short access-token expiry limits the replay window.

**Residual.** **Low** for both. Identity is the platform's most mature area; the
`authz` dimension scores 90 and these controls are all satisfied.

---

## 2. Tampering

**Definition.** Unauthorised modification of data — in transit, at rest, or
within models/artifacts — to alter behaviour or outcomes.

**Threats in this category:**

| ID | Component | Threat |
|----|-----------|--------|
| STRIDE-T1 | API → Data | Unauthorised modification of records or payloads |
| STRIDE-T2 | ML / model artifacts | Poisoning of training data, features, or model artifacts |

**Existing controls.**
- **T1:** TLS protects data in transit; `FieldCipher` (AES-256-GCM) provides
  *authenticated* encryption so tampering with ciphertext is detected;
  parameterised queries prevent injection-based tampering; RBAC write scopes
  (`require_permission`) restrict who may mutate; `AuditMiddleware` records every
  change.
- **T2:** Model-registry integrity checks, dataset lineage, SHAP-integrity
  verification, and drift detection guard the ML pipeline against poisoning.

**Residual.** **Low** for T1; **Medium** for T2. Model/feature poisoning is
partially mitigated — signed artifacts and stricter lineage attestation are the
recommended hardening (ml_security dimension 78.6).

---

## 3. Repudiation

**Definition.** A party denies having performed an action, and the system cannot
prove otherwise due to missing or mutable logs.

**Threats in this category:**

| ID | Component | Threat |
|----|-----------|--------|
| STRIDE-R1 | Audit trail | A user denies a mutating action they performed |

**Existing controls.** `AuditMiddleware` writes exactly **one immutable audit row
per mutation**, capturing actor, action, and resource. Audit records are held
under the retention registry (**audit 7 years**), and access itself is logged.
This yields non-repudiation for every state-changing operation.

**Residual.** **Low.** Comprehensive, immutable, per-mutation auditing with
long-horizon retention.

---

## 4. Information disclosure

**Definition.** Exposure of information to parties not authorised to see it —
through responses, logs, exports, or cross-tenant leakage.

**Threats in this category:**

| ID | Component | Threat |
|----|-----------|--------|
| STRIDE-I1 | API → Data | Exposure of PII / financial data via responses, logs, or exports |
| STRIDE-I2 | Tenant A → Tenant B | One tenant reads another tenant's data (cross-tenant IDOR) |

**Existing controls.**
- **I1:** `PiiMasker` redacts email/phone/card/PAN/Aadhaar on egress and in
  logs/exports; `FieldCipher` encrypts sensitive columns at rest; RBAC read
  scopes gate access; the retention registry plus secure deletion limit exposure
  windows. The PII catalog classifies 10 element types with masking/encryption
  columns across four classifications (public/internal/confidential/restricted).
- **I2:** `TenantMiddleware` supplies tenant context *ambiently* (never from
  client input), and all data-plane queries are tenant-scoped, closing
  cross-tenant IDOR.

**Residual.** **Medium** for I1 (extend masking/encryption coverage across all
export and log paths — data_protection dimension 50 in dev). **Low** for I2
(tenant_isolation dimension 97).

---

## 5. Denial of service

**Definition.** Degrading or denying availability to legitimate users through
resource exhaustion at the network, application, or model layer.

**Threats in this category:**

| ID | Component | Threat |
|----|-----------|--------|
| STRIDE-D1 | Edge / API | Volumetric or application-layer flooding |
| STRIDE-D2 | AI / ML platform | Model-DoS: expensive prompts / inference exhaust compute or budget |

**Existing controls.**
- **D1:** Rate limiting, `SecurityHeadersMiddleware`, edge/CDN absorption, and
  horizontal autoscaling.
- **D2:** Per-request quotas, model-DoS controls (satisfied in the OWASP LLM
  mapping), and inference timeouts.

**Residual.** **Medium** for both. Recommended hardening: tune per-tenant
inference budgets and add circuit breakers on model calls.

---

## 6. Elevation of privilege

**Definition.** Gaining capabilities beyond those granted — acting above one's
role, or coercing a privileged component into acting on the attacker's behalf.

**Threats in this category:**

| ID | Component | Threat |
|----|-----------|--------|
| STRIDE-E1 | Authorization | A user performs actions above their role (broken authz) |
| STRIDE-E2 | AI agent / tool use | **Prompt injection coerces an agent into unauthorised tool / connector use** |

**Existing controls.**
- **E1:** `require_permission` guards **every** route with a deny-by-default RBAC
  check against the permission catalog; the Security & Compliance module itself
  adds 20 scoped permissions. Privileged surfaces (SaaS admin) require elevated
  roles and are audited.
- **E2:** Partial. Tool authorization at the App→LLM boundary (B6), output
  validation, and audit reduce but do not eliminate the risk that hostile
  in-context instructions cause an agent to invoke tools beyond the user's
  authority.

**Residual.** **Low** for E1. **High** for E2 — this is the **highest residual
risk in the entire model**. See [THREAT_MODEL.md](THREAT_MODEL.md) §4.3 and the
attack tree "Exfiltrate via AI". Recommended hardening: strict per-agent tool
allow-lists, typed tool outputs, injection-resistant prompt construction, and
human-in-the-loop approval for high-impact tool actions.

---

## 7. Residual-distribution summary

| STRIDE category | Threats | High | Medium | Low |
|-----------------|---------|------|--------|-----|
| Spoofing | S1, S2 | 0 | 0 | 2 |
| Tampering | T1, T2 | 0 | 1 | 1 |
| Repudiation | R1 | 0 | 0 | 1 |
| Information disclosure | I1, I2 | 0 | 1 | 1 |
| Denial of service | D1, D2 | 0 | 2 | 0 |
| Elevation of privilege | E1, E2 | 1 | 0 | 1 |
| **Total** | **11** | **1** | **4** | **6** |

The single **High** residual is STRIDE-E2 (prompt injection → tool use). The
identity and authorization spine of the platform (S1, S2, E1, I2, R1, T1) is
uniformly **Low**.

---

## 8. STRIDE → platform-control mapping

| STRIDE category | Primary platform controls |
|-----------------|---------------------------|
| **Spoofing** | `AccountLockout`, `PasswordPolicy`, `Totp` MFA, `RiskEngine`, JWT / `JwtKeyRing`, `RefreshTokenService` |
| **Tampering** | `FieldCipher` / `KeyRing` (authenticated AES-256-GCM), RBAC write scopes, parameterised queries, `AuditMiddleware`, ML integrity/lineage |
| **Repudiation** | `AuditMiddleware` (immutable per-mutation audit), retention registry (audit 7y) |
| **Information disclosure** | `PiiMasker`, `FieldCipher`, RBAC read scopes, `TenantMiddleware`, retention + secure deletion |
| **Denial of service** | Rate limiting, `SecurityHeadersMiddleware`, edge/CDN + autoscaling, model quotas/timeouts |
| **Elevation of privilege** | RBAC `require_permission` (deny-by-default), `JwtKeyRing` signature verification, tool authorization at B6, audit |

---

## 9. Related documents

- [THREAT_MODEL.md](THREAT_MODEL.md) — full enterprise threat model, boundaries, attack trees.
- [ATTACK_SURFACE.md](ATTACK_SURFACE.md) — attack-surface enumeration.
- [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md) — the underlying controls in depth.

← Back to [Security Documentation](index.md)
