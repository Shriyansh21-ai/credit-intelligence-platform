# Enterprise Threat Model

_Stage 4, Milestone 1 — Enterprise Threat Modeling for the AI Credit Intelligence Platform._

This document is the authoritative enterprise threat model for the platform. It
is produced by the additive **Security & Compliance** module
(`backend/app/services/security_compliance/threat_model.py`) and is served live
under `/api/sec/threat/*`. The model is **offline-first and deterministic**: the
same platform configuration always yields the same threats, boundaries, and
scores, so the model can be regression-tested and diffed across releases.

> [!IMPORTANT]
> **Highest residual risk: prompt injection → unauthorised tool use (STRIDE-E2, HIGH).**
> An attacker who lands hostile instructions in an LLM context (via a document,
> a retrieved record, or a chat turn) may coerce an agent into invoking tools or
> connectors beyond the user's authority. This is the single highest-residual
> threat in the catalog and the priority for the next hardening cycle.

---

## 1. Overview & methodology

The threat model combines three complementary techniques so that no single lens
is the sole source of assurance:

| Technique | Purpose | Where it appears |
|-----------|---------|------------------|
| **STRIDE** | Systematic per-component enumeration of Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, and Elevation of privilege | Threat catalog (§3), `/threat/stride` |
| **Attack trees** | Goal-oriented, attacker's-eye decomposition of how a high-value objective is reached (OR/AND paths) | Attack trees (§4), `/threat/attack-trees` |
| **DFD-level trust boundaries** | Data-flow decomposition that names every point where data crosses a privilege or ownership edge | System decomposition (§2), `/threat/boundaries` |

Each STRIDE threat is scored on **existing controls** and a **residual** rating
(`low` / `medium` / `high`). Residual is the risk that remains *after* the
platform's real, shipped controls are applied — it is not a theoretical
worst-case. Controls referenced in this document are the pre-existing Phase-11
platform controls (`core/authn.py`, `core/crypto.py`,
`core/security_middleware.py`, `core/tenant_middleware.py`,
`core/audit_middleware.py`, `services/rbac`) plus the analysis engines of the
Security & Compliance module.

### Scope

- **In scope:** the REST API (`/api/*`), authentication and session surfaces,
  document/OCR ingestion, the AI and ML platforms, tenant isolation, external
  connectors and the Open API, SaaS administration, webhooks, object storage,
  and operational probes.
- **Additive guarantee:** the module that produces this model modifies nothing
  from Stages 1–3. It reads configuration and catalogs and computes findings.

---

## 2. System decomposition & trust boundaries

The platform is decomposed along its data-flow diagram into **six trust
boundaries**. A trust boundary is any edge where data changes privilege level,
ownership, or trust domain, and is therefore a mandatory point of validation,
authentication, or authorization.

| # | Trust boundary | Crossing | Primary controls at the boundary | Key risk if weak |
|---|----------------|----------|----------------------------------|------------------|
| B1 | **Internet → Edge** | Untrusted client traffic reaching the edge/CDN/ALB | TLS-only, HSTS, `SecurityHeadersMiddleware` (CSP, XFO DENY, nosniff), rate limiting | MITM, volumetric DoS, header-based injection |
| B2 | **Edge → API** | Requests entering the application tier | JWT verification (`JwtKeyRing`), `require_permission` RBAC on every route, input validation | Spoofing, broken authz, injection |
| B3 | **API → Data** | Application reading/writing persistent stores | Field encryption (`FieldCipher`/`KeyRing`), parameterised queries, `PiiMasker` on egress, retention policy | Data-at-rest exposure, PII leakage |
| B4 | **Tenant A → Tenant B** | Logical isolation between tenants sharing infrastructure | Ambient tenant context (`TenantMiddleware`), tenant-scoped rows, per-tenant filters | Cross-tenant read/write (IDOR) |
| B5 | **App → Connectors / Open API** | Outbound calls to bureaus, GST/MCA, AA, ERP, payments, and inbound Open-API traffic | Signed requests, secret store, allow-lists, per-connector authz | SSRF, credential leakage, data exfiltration |
| B6 | **App → LLM / AI** | Prompts, retrieved context, and tool invocations flowing to/from models | Prompt construction controls, output validation, tool authorization, audit | Prompt injection, excessive agency, data disclosure |

Boundaries B4 and B6 are the two highest-value targets: B4 protects tenant
confidentiality on shared infrastructure, and B6 is where the platform's
AI-native surface concentrates the most residual risk (see §4.3 and the callout
above).

---

## 3. Threat catalog (STRIDE)

The catalog documents **11 threats** across the six STRIDE categories. Each is
served from `/api/sec/threat/stride` with its component, mapped controls, and
residual.

| ID | STRIDE category | Component | Threat | Existing controls | Residual |
|----|-----------------|-----------|--------|-------------------|----------|
| **STRIDE-S1** | Spoofing | Auth endpoints | Credential stuffing / brute-force against login to impersonate a user | `AccountLockout`, `PasswordPolicy`, rate limiting, `RiskEngine` step-up, optional `Totp` MFA | Low |
| **STRIDE-S2** | Spoofing | Session / tokens | Stolen or replayed JWT / refresh token used to assume an identity | `JwtKeyRing` (kid rotation), `RefreshTokenService` (rotation + reuse detection + family revocation), short access-token expiry | Low |
| **STRIDE-T1** | Tampering | API → Data | Unauthorised modification of records or request payloads in transit / at rest | TLS, `FieldCipher` (AES-256-GCM, authenticated), parameterised queries, RBAC write scopes | Low |
| **STRIDE-T2** | Tampering | ML / model artifacts | Poisoning of training data, features, or model artifacts to bias decisions | Model registry integrity, dataset lineage, drift detection, SHAP integrity checks | Medium |
| **STRIDE-R1** | Repudiation | Audit trail | A user denies a mutating action they performed | `AuditMiddleware` (one immutable audit row per mutation), retention (audit 7y) | Low |
| **STRIDE-I1** | Information disclosure | API → Data | Exposure of PII / financial data via responses, logs, or exports | `PiiMasker`, field encryption, RBAC read scopes, retention + secure deletion | Medium |
| **STRIDE-I2** | Information disclosure | Tenant A → Tenant B | One tenant reads another tenant's data (cross-tenant IDOR) | `TenantMiddleware` ambient context, tenant-scoped queries, per-request tenant filters | Low |
| **STRIDE-D1** | Denial of service | Edge / API | Volumetric or application-layer flooding degrades availability | Rate limiting, security headers, edge/CDN, autoscaling | Medium |
| **STRIDE-D2** | Denial of service | AI / ML platform | Model-DoS: expensive prompts / inference exhaust compute or budget | Request quotas, model-DoS controls (satisfied), timeouts | Medium |
| **STRIDE-E1** | Elevation of privilege | Authorization | A user performs actions above their role (broken authz) | `require_permission` on every route, RBAC catalog, deny-by-default | Low |
| **STRIDE-E2** | Elevation of privilege | AI agent / tool use | **Prompt injection coerces an agent into unauthorised tool / connector use** | Prompt-injection mitigations (partial), output validation, tool authorization, audit | **High** |

---

## 4. Attack trees

Four attacker goals are decomposed into OR/AND paths. An **OR** node succeeds if
any child path succeeds; an **AND** node requires all children. Leaf mitigations
are the controls that break the path.

### 4.1 Goal — Compromise a user account

```
Compromise account (OR)
├── Guess / stuff credentials ──► mitigated by AccountLockout + PasswordPolicy + rate limit + RiskEngine
├── Steal a session token (AND)
│   ├── Obtain token (XSS / interception) ──► mitigated by CSP + XFO + HSTS + TLS
│   └── Replay it ──────────────────────────► mitigated by RefreshTokenService reuse detection + short expiry
└── Bypass MFA ──────────────────────────────► mitigated by Totp + RiskEngine step-up
```

### 4.2 Goal — Read another tenant's data

```
Read another tenant's data (OR)
├── Manipulate tenant id in request ──► mitigated by ambient TenantMiddleware context (not client-supplied)
├── IDOR on a resource id ────────────► mitigated by tenant-scoped queries + RBAC read scopes
└── Exploit a shared cache / store ───► mitigated by per-tenant keys + object-storage isolation
```

### 4.3 Goal — Exfiltrate data via the AI layer

```
Exfiltrate via AI (OR)
├── Prompt injection → tool use (STRIDE-E2) ─► partial: tool authorization + output validation  ◄ HIGHEST RESIDUAL
├── RAG / memory poisoning ─────────────────► partial: source controls + integrity checks
└── Sensitive-info disclosure in output ────► mitigated by PiiMasker + output filtering (satisfied)
```

### 4.4 Goal — Escalate to administrator

```
Escalate to admin (OR)
├── Abuse a missing authz check ───────► mitigated by require_permission on every route (deny-by-default)
├── Forge / elevate a token claim ─────► mitigated by JwtKeyRing signature verification
└── Exploit SaaS admin surface ───────► mitigated by privileged-surface RBAC (sec.admin) + audit
```

---

## 5. Residual risk summary & prioritization

Residual ratings across the 11 threats:

| Residual | Count | Threats |
|----------|-------|---------|
| **High** | 1 | STRIDE-E2 |
| **Medium** | 4 | STRIDE-T2, I1, D1, D2 |
| **Low** | 6 | STRIDE-S1, S2, T1, R1, I2, E1 |

Prioritised remediation backlog:

1. **STRIDE-E2 (High)** — Harden the AI tool-use boundary (B6): stricter tool
   authorization, structured/typed tool outputs, injection-resistant prompt
   construction, and human-in-the-loop for high-impact actions.
2. **STRIDE-T2 (Medium)** — Strengthen ML integrity: signed model artifacts,
   stricter dataset-lineage attestation, tighter drift thresholds.
3. **STRIDE-I1 (Medium)** — Extend PII masking coverage on all export and log
   paths; verify field encryption on every restricted column.
4. **STRIDE-D1 / D2 (Medium)** — Tune rate limits and per-tenant inference
   budgets; add circuit breakers on model calls.

The identity and authorization threats (S1, S2, E1, I2) are already **Low**
residual thanks to the mature `core/authn.py` and RBAC controls, and the
`authz` (90) and `tenant_isolation` (97) posture dimensions reflect this.

---

## 6. How to run it live

The model is not a static artifact — it is computed by the running platform and
exposed as read-only JSON. All endpoints are gated by the **`sec.threat.view`**
RBAC permission (Security & Compliance category; granted to `compliance_officer`,
`risk_manager`, oversight roles read-only, and `administrator`).

| Endpoint | Returns |
|----------|---------|
| `GET /api/sec/threat` | The full threat model: boundaries, STRIDE catalog, attack surface, and attack trees, with the aggregate `threat_model` score |
| `GET /api/sec/threat/stride` | The 11 STRIDE threats with category, component, controls, and residual |
| `GET /api/sec/threat/attack-surface` | The 10 attack-surface entries (see [ATTACK_SURFACE.md](ATTACK_SURFACE.md)) |
| `GET /api/sec/threat/attack-trees` | The 4 attacker-goal trees with OR/AND paths and mitigations |
| `GET /api/sec/threat/boundaries` | The 6 trust boundaries and their controls |

Example:

```bash
curl -H "Authorization: Bearer $TOKEN" \
     https://<host>/api/sec/threat/stride
```

The current **development-profile** `threat_model` dimension scores **77 / 100**.
This is an honest, computed number; the deductions come from the partial AI
prompt-injection controls (STRIDE-E2) and the medium-residual ML and DoS
threats, not from missing identity controls.

---

## 7. Related documents

- [ATTACK_SURFACE.md](ATTACK_SURFACE.md) — full attack-surface enumeration.
- [STRIDE_ANALYSIS.md](STRIDE_ANALYSIS.md) — deep per-category STRIDE analysis.
- [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md) — the underlying controls.

← Back to [Security Documentation](index.md)
