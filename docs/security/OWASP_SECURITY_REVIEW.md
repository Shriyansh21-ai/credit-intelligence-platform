# OWASP Security Review

_Stage 4, Milestone 2 — OWASP-aligned application security review for the AI Credit Intelligence Platform._

This document is the authoritative OWASP audit of the platform. It is produced by
the additive **Security & Compliance** module
(`backend/app/services/security_compliance/owasp.py`) and served live under
`/api/sec/owasp/*`. Like the rest of the module it is **offline-first and
deterministic**: the same platform configuration always yields the same category
verdicts and the same aggregate score, so the review can be regression-tested and
diffed across releases.

The review is conducted against three complementary OWASP standards so no single
list is the sole source of assurance:

| Standard | Purpose | Endpoint |
|----------|---------|----------|
| **OWASP Top 10 2021** | The canonical web-application risk categories (A01–A10) | `GET /api/sec/owasp/top10` |
| **OWASP API Security Top 10 2023** | API-specific risks (API1–API10) for the `/api/*` surface | `GET /api/sec/owasp/api-top10` |
| **OWASP ASVS** | The Application Security Verification Standard chapters (V1–V14) as a verification checklist | `GET /api/sec/owasp/asvs` |

> [!IMPORTANT]
> **Overall OWASP posture (development profile): 78.6 / 100.**
> The deductions are concentrated in five `partial` categories — injection
> hardening (A03), outdated/unpinned components (A06), software & data integrity
> (A08), SSRF on the connector surface (A10), and prompt injection on the AI
> boundary. None of these are broken identity or access-control categories; the
> authentication, authorization and cryptographic-storage categories are all
> `satisfied`.

---

## 1. OWASP Top 10 2021 (A01–A10)

Verdicts use three states: **satisfied** (the platform's shipped controls fully
cover the category), **partial** (controls exist but coverage or hardening is
incomplete — an open finding), and **gap** (no meaningful control). No category
is currently a full gap.

| # | Category | What it covers | Platform controls | Status |
|---|----------|----------------|-------------------|--------|
| **A01** | Broken Access Control | Enforcing least privilege and object ownership | `require_permission` on every route, RBAC catalog (deny-by-default), ambient tenant scoping (`TenantMiddleware`), tenant-scoped rows | **Satisfied** |
| **A02** | Cryptographic Failures | Protecting data at rest and in transit | TLS/HSTS, `FieldCipher` AES-256-GCM (authenticated) with `KeyRing` versioning, `PiiMasker`, signed expiring URLs | **Satisfied** |
| **A03** | Injection | SQL, command, and template injection | Parameterised ORM queries, input validation (pydantic), output encoding — **but LLM prompt/RAG injection paths remain partially mitigated** | **Partial** |
| **A04** | Insecure Design | Security designed in, not bolted on | Enterprise threat model (STRIDE + attack trees), trust-boundary decomposition, deny-by-default authz | **Satisfied** |
| **A05** | Security Misconfiguration | Hardened, profile-aware configuration | `SecurityHeadersMiddleware`, profile-aware `settings.py` with `validate_runtime()` flagging wildcard CORS / sqlite-in-prod / default secrets | **Satisfied** |
| **A06** | Vulnerable & Outdated Components | Managing dependency risk | SBOM + dependency/license inventory (`supply_chain.py`) — **but `requirements.txt` lists 27 unpinned production deps** | **Partial** |
| **A07** | Identification & Authentication Failures | Robust identity and session handling | `JwtKeyRing`, `RefreshTokenService` (rotation + reuse detection + family revocation), `PasswordPolicy` (min 12 + complexity), `AccountLockout`, `Totp` MFA, `RiskEngine` step-up | **Satisfied** |
| **A08** | Software & Data Integrity Failures | Trusting only verified code/data/artifacts | Audit trail on mutations, model-registry integrity, dataset lineage — **but artifact/dependency signing and lockfile integrity are incomplete** | **Partial** |
| **A09** | Security Logging & Monitoring Failures | Detecting and recording security events | `AuditMiddleware` (one immutable row per mutation), retention (audit 7y), posture snapshots, findings & risk registers | **Satisfied** |
| **A10** | Server-Side Request Forgery (SSRF) | Preventing forced server-side requests | Connector allow-lists, signed outbound requests, secret store, per-connector authz — **but comprehensive egress filtering on all connector paths is incomplete** | **Partial** |

**Top 10 score: 78.6 / 100** — six `satisfied`, four `partial`, zero `gap`.

---

## 2. OWASP API Security Top 10 2023 (API1–API10)

The `/api/*` surface (45 Security & Compliance routes plus the broader platform
API) is mapped against the API-specific list.

| # | Category | Platform control | Status |
|---|----------|------------------|--------|
| **API1** | Broken Object Level Authorization (BOLA) | Tenant-scoped queries + RBAC read scopes; ambient tenant context prevents client-supplied tenant id (tenant-isolation dimension 97) | **Satisfied** |
| **API2** | Broken Authentication | `JwtKeyRing` signature verification, `RefreshTokenService`, `AccountLockout`, MFA | **Satisfied** |
| **API3** | Broken Object Property Level Authorization | RBAC scopes + `PiiMasker` on egress — field-level response shaping is not yet exhaustive | **Partial** |
| **API4** | Unrestricted Resource Consumption | Rate limiting, per-tenant quotas, model-DoS controls, timeouts — inference-budget tuning ongoing | **Partial** |
| **API5** | Broken Function Level Authorization | `require_permission` on every route, deny-by-default RBAC catalog | **Satisfied** |
| **API6** | Unrestricted Access to Sensitive Business Flows | Risk-based step-up (`RiskEngine`), audit trail — flow-level abuse controls incomplete on some paths | **Partial** |
| **API7** | Server-Side Request Forgery | Connector allow-lists + signed requests (mirrors A10) | **Partial** |
| **API8** | Security Misconfiguration | `SecurityHeadersMiddleware` + `validate_runtime()` — dev profile ships default secrets (flagged CRITICAL) | **Partial** |
| **API9** | Improper Inventory Management | Documented route inventory + SBOM — full versioned API inventory maturing | **Partial** |
| **API10** | Unsafe Consumption of APIs | Connector authz + secret store + response validation on inbound bureau/GST/AA/ERP data | **Partial** |

---

## 3. OWASP ASVS chapter checklist (V1–V14)

The Application Security Verification Standard is used as a chapter-level
verification checklist. Served from `GET /api/sec/owasp/asvs`.

| Chapter | Area | Primary evidence | Status |
|---------|------|------------------|--------|
| **V1** | Architecture, Design & Threat Modeling | Enterprise threat model, trust boundaries, attack trees | **Satisfied** |
| **V2** | Authentication | `PasswordPolicy`, `AccountLockout`, `Totp` MFA, `RiskEngine` step-up | **Satisfied** |
| **V3** | Session Management | `JwtKeyRing`, `RefreshTokenService` rotation + reuse detection, short access-token expiry | **Satisfied** |
| **V4** | Access Control | `require_permission` RBAC, tenant scoping, deny-by-default | **Satisfied** |
| **V5** | Validation, Sanitization & Encoding | pydantic validation, parameterised queries, output encoding — LLM input paths partial | **Partial** |
| **V6** | Stored Cryptography | `FieldCipher` AES-256-GCM, `KeyRing` versioning + rotation + crypto-shred | **Satisfied** |
| **V7** | Error Handling & Logging | `AuditMiddleware`, structured findings, no sensitive data in errors | **Satisfied** |
| **V8** | Data Protection | Data classification + PII catalog + masking — full field-encryption coverage maturing (data-protection dimension 50) | **Partial** |
| **V9** | Communication | TLS-only, HSTS, secure headers | **Satisfied** |
| **V10** | Malicious Code | SBOM, dependency audit — artifact signing + lockfile integrity incomplete | **Partial** |
| **V11** | Business Logic | Risk-based step-up, deny-by-default flows | **Satisfied** |
| **V12** | Files & Resources | Upload validation on document/OCR path — path-traversal and content-type hardening partial | **Partial** |
| **V13** | API & Web Service | RBAC on every route + SSRF-relevant connector allow-lists | **Partial** |
| **V14** | Configuration | Profile-aware `settings.py` + `validate_runtime()` — dev profile default secrets flagged | **Partial** |

---

## 4. Focused review areas

The milestone requires an explicit verdict on each of the following surfaces.
Each row names the platform's concrete control and the review verdict.

| Area | Platform control | Verdict |
|------|------------------|---------|
| **Authentication** | `PasswordPolicy` (min 12 + complexity), `AccountLockout`, `Totp` (RFC 6238) MFA, `RiskEngine` step-up, bcrypt hashing (`core/security.py`) | **Satisfied** |
| **Authorization** | `require_permission` on every route, RBAC catalog with deny-by-default, 20 Security & Compliance permissions | **Satisfied** |
| **JWT** | HS256 tokens via `create_access_token`, `JwtKeyRing` kid rotation, short expiry, signature verification | **Satisfied** |
| **Cookies** | Secure attributes and CSP-backed context; tokens are not exposed to client script paths | **Satisfied** |
| **CSRF** | Bearer-token (non-cookie) auth model + `SecurityHeadersMiddleware` (XFO DENY) reduces CSRF surface | **Satisfied** |
| **CORS** | Profile-aware allow-lists; `validate_runtime()` flags wildcard CORS in production | **Satisfied** |
| **SSRF** | Connector allow-lists, signed outbound requests, secret store — egress filtering incomplete on some connector paths | **Partial** |
| **IDOR** | Ambient tenant context (not client-supplied) + tenant-scoped queries + RBAC read scopes (tenant-isolation 97) | **Satisfied** |
| **SQL Injection** | Parameterised ORM queries throughout; no string-built SQL | **Satisfied** |
| **Prompt Injection** | Prompt-construction controls, output validation, tool authorization — highest residual (STRIDE-E2) | **Partial** |
| **RAG Injection** | Source controls + integrity checks on retrieved context — poisoning not fully mitigated | **Partial** |
| **Path Traversal** | Canonicalised paths + `secure_overwrite_file`; upload path hardening ongoing | **Partial** |
| **File Upload** | Content-type and size validation on document/OCR ingestion — deep content inspection maturing | **Partial** |
| **Rate Limiting** | Edge/API rate limiting + per-tenant quotas | **Satisfied** |
| **Brute Force** | `AccountLockout` + `RiskEngine` step-up + rate limiting on auth endpoints | **Satisfied** |
| **Session Management** | `RefreshTokenService` rotation + reuse detection + family revocation, short access-token expiry | **Satisfied** |
| **Headers** | `SecurityHeadersMiddleware`: HSTS, CSP, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy, Permissions-Policy, COOP/CORP | **Satisfied** |

---

## 5. Open findings

The `partial` verdicts above roll up into the following open findings, ordered by
priority. These are tracked in the findings register (`/api/sec/findings`) and
mapped to the threat model where applicable.

| # | Finding | Categories | Severity | Remediation |
|---|---------|-----------|----------|-------------|
| **OWASP-01** | Prompt / RAG injection on the AI boundary partially mitigated | A03, LLM01/LLM03, STRIDE-E2 | **High** | Injection-resistant prompt construction, typed/structured tool outputs, strict tool authorization, human-in-the-loop for high-impact actions |
| **OWASP-02** | 27 unpinned production dependencies; no lockfile | A06, A08, V10 | **Medium** | Pin all versions, add a lockfile, wire dependency audit into CI |
| **OWASP-03** | SSRF egress filtering incomplete on some connector paths | A10, API7, V13 | **Medium** | Enforce allow-list egress + response validation on every connector |
| **OWASP-04** | Field-encryption coverage not exhaustive across restricted columns | V8, A02 | **Medium** | Verify `FieldCipher` on every restricted field; extend masking to all export/log paths |
| **OWASP-05** | Dev profile ships default secrets (flagged CRITICAL by scanner) | A05, API8, V14 | **Environment** | Set real secrets in staging/production; `validate_runtime()` already enforces this |

> [!NOTE]
> OWASP-05 is an **environment-specific** finding, not a code defect. In a
> production deployment with real secrets set, the misconfiguration category
> clears and the related posture dimensions rise sharply. See
> [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md).

---

## 6. How to run it live

The review is computed by the running platform and exposed as read-only JSON. All
endpoints are gated by the **`sec.owasp.view`** RBAC permission (Security &
Compliance category; granted to `compliance_officer`, `risk_manager`, oversight
roles read-only, and `administrator`).

| Endpoint | Returns |
|----------|---------|
| `GET /api/sec/owasp` | The full review: Top 10, API Top 10, and ASVS with the aggregate `owasp` score (78.6) |
| `GET /api/sec/owasp/top10` | The A01–A10 category verdicts and controls |
| `GET /api/sec/owasp/api-top10` | The API1–API10 verdicts |
| `GET /api/sec/owasp/asvs` | The V1–V14 chapter checklist |

```bash
curl -H "Authorization: Bearer $TOKEN" \
     https://<host>/api/sec/owasp
```

The current development-profile `owasp` dimension scores **78.6 / 100**. This is
an honest, computed number; the deductions come from the five `partial`
categories, not from missing identity or access-control controls.

---

## 7. Related documents

- [THREAT_MODEL.md](THREAT_MODEL.md) — STRIDE catalog and attack trees (STRIDE-E2 maps to OWASP-01).
- [AUTHENTICATION_HARDENING.md](AUTHENTICATION_HARDENING.md) — deep audit of the identity surface (A07 / API2).
- [MULTI_TENANT_SECURITY.md](MULTI_TENANT_SECURITY.md) — tenant isolation (A01 / API1).
- [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md) — the OWASP-05 environment finding.

← Back to [Security Documentation](index.md)
