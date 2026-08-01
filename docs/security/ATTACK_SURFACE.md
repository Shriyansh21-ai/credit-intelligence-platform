# Attack Surface Enumeration

_Stage 4, Milestone 1 — Enterprise Threat Modeling for the AI Credit Intelligence Platform._

This document enumerates the platform's externally and internally reachable
attack surface. It is produced by the additive **Security & Compliance** module
(`backend/app/services/security_compliance/threat_model.py`) and served live at
**`GET /api/sec/threat/attack-surface`** (gated by `sec.threat.view`). The
enumeration is deterministic, so the surface can be diffed release-to-release to
catch unintended exposure growth.

---

## 1. Methodology

The attack surface is the set of points where an actor can supply input,
authenticate, or otherwise interact with the platform. Each surface is
characterised on three axes:

| Axis | Values | Meaning |
|------|--------|---------|
| **Exposure** | public / authenticated / privileged / internal | Who can reach it before any resource-level check |
| **Risk** | high / medium / low | Likelihood × impact of an exploit against that surface |
| **Notes** | free text | The dominant threat and the controls that reduce it |

Surface entries map back to the trust boundaries in
[THREAT_MODEL.md](THREAT_MODEL.md) §2 and to the STRIDE catalog. The goal of the
enumeration is twofold: (1) make every reachable entry point explicit, and
(2) drive the reduction recommendations in §7.

---

## 2. The attack surfaces

Ten attack surfaces are enumerated. This is the canonical list returned by
`GET /api/sec/threat/attack-surface`.

| # | Surface | Exposure | Risk | Notes |
|---|---------|----------|------|-------|
| 1 | **REST API (`/api/*`)** | authenticated | Medium | Broadest surface; every route behind JWT verification + `require_permission` RBAC; input validation on payloads |
| 2 | **Auth endpoints** | public | High | Unauthenticated by definition; primary spoofing target — `AccountLockout`, `PasswordPolicy`, rate limiting, `RiskEngine`, `Totp` MFA |
| 3 | **Document / OCR upload** | authenticated | High | Untrusted binary ingestion; risks: malicious files, parser exploits, injection into downstream AI context; validated + sandboxed processing |
| 4 | **AI platform** | authenticated | High | Prompt / chat / agent surface; carries the highest-residual threat (STRIDE-E2 prompt injection → tool use) |
| 5 | **ML platform** | authenticated | Medium | Training, registry, feature store, inference; risks: model/data poisoning, drift; integrity + lineage controls |
| 6 | **Connectors / Open API** | authenticated | High | Outbound bureau/GST/MCA/AA/ERP/payments calls + inbound Open-API; risks: SSRF, credential leakage, exfiltration; signed requests + secret store + allow-lists |
| 7 | **SaaS admin** | privileged | High | Tenant and platform administration; requires elevated RBAC (`sec.admin` and admin roles); fully audited |
| 8 | **Webhooks** | authenticated | Medium | Inbound event callbacks; risks: forged/replayed events; signature verification + idempotency |
| 9 | **Metrics / probes** | internal | Low | Health and metrics endpoints reachable only from the internal network / orchestrator; no PII |
| 10 | **Object storage** | authenticated | Medium | Document and export artifacts; access via signed, expiring URLs; TLS-only; per-tenant isolation |

---

## 3. External integrations & their risk

External integrations expand the surface beyond the platform's own perimeter and
are concentrated at trust boundaries **B5 (App → Connectors)** and **B6 (App →
LLM/AI)**.

| Integration class | Direction | Dominant risk | Reducing controls |
|-------------------|-----------|---------------|-------------------|
| **Connectors** (bureau, GST/MCA, AA, ERP, payments, collateral) | Outbound | SSRF, credential leakage, third-party data exfiltration | Secret store (no committed secrets), signed requests, per-connector allow-lists and authz |
| **Open API** | Inbound | Abuse of programmatic access, broken object-level authz | JWT + RBAC scopes, tenant scoping, rate limiting |
| **LLM / AI services** | Bidirectional | Prompt injection, sensitive-info disclosure in prompts/outputs, excessive agency | Prompt construction controls, output validation, tool authorization, `PiiMasker` |
| **Webhooks** | Inbound | Forged or replayed events | Signature verification, idempotency keys, audit |

---

## 4. AI / ML / OCR / document-processing surface

This is the platform's most distinctive and highest-risk surface, and the reason
STRIDE-E2 is the top residual risk.

| Sub-surface | Threat | Status / controls |
|-------------|--------|-------------------|
| **Prompt / chat / agent input** | Prompt injection → unauthorised tool use (STRIDE-E2) | **High residual**; partial injection mitigations + tool authorization + audit |
| **Insecure output handling** | LLM output executed / rendered unsafely downstream | Partial; output validation and encoding |
| **RAG / retrieval context** | Poisoned documents or records injected into context | Partial; source controls + integrity checks |
| **Memory / model poisoning** | Persistent corruption of agent memory or model | Partial; integrity checks, lineage |
| **Document / OCR ingestion** | Malicious file, parser exploit, injection into AI context via extracted text | Validated + sandboxed processing; treated as untrusted input |
| **Model DoS** | Expensive prompts / inference exhaust compute or budget | Satisfied; quotas, timeouts |
| **Sensitive-info disclosure** | PII leaked through prompt or completion | Satisfied; `PiiMasker` + output filtering |

The AI security dimension scores **65 / 100** (OWASP LLM Top 10 mapping) and the
ML security dimension **78.6 / 100** — both reflect the partial status of the
injection, insecure-output, RAG, plugin, agency, and model-poisoning controls.
See [STRIDE_ANALYSIS.md](STRIDE_ANALYSIS.md) and the AI security docs for detail.

---

## 5. Supply-chain & plugin surface

The supply chain is a first-class attack surface: dependencies and plugins run
with the application's privileges.

| Surface element | Risk | Current state |
|-----------------|------|---------------|
| **Python dependencies** | Vulnerable or malicious packages; unpinned versions admit drift | `requirements.txt` lists **27 production deps with no version constraints** — an accurate, flagged finding; pinning + lockfile remediates |
| **SBOM** | Blind spots in what is actually shipped | SBOM generated and served via `/api/sec/supply-chain/sbom` |
| **Licenses** | Non-compliant or copyleft obligations | License inventory via `/api/sec/supply-chain/licenses` |
| **AI plugins / tools** | Insecure plugin design grants excessive agency | Partial (OWASP LLM07); tool authorization at boundary B6 |

The **supply_chain** dimension scores **60 / 100** in the development profile,
driven by the unpinned dependencies. This is an environment-remediable finding:
pinning versions and committing a lockfile raises the dimension materially. The
**container** dimension already scores **100**.

---

## 6. SaaS / tenant-isolation surface

The platform is multi-tenant, so the boundary between tenants (B4) is a security
boundary, not merely a data-partitioning convenience.

| Surface | Risk | Controls |
|---------|------|----------|
| **Tenant data plane** | Cross-tenant read/write (IDOR) | Ambient tenant context via `TenantMiddleware` (tenant id is *not* client-supplied), tenant-scoped queries, per-request filters |
| **SaaS admin plane** | Tenant/platform admin abuse | Privileged exposure; elevated RBAC (`sec.admin`), full audit trail |
| **Shared stores / caches** | Leakage across tenants through shared infrastructure | Per-tenant keys, object-storage isolation, signed URLs |

Tenant isolation is the platform's strongest posture dimension at **97 / 100**,
and cross-tenant disclosure (STRIDE-I2) is rated **Low** residual.

---

## 7. Public vs authenticated vs privileged breakdown

| Exposure tier | Surfaces | Security posture |
|---------------|----------|------------------|
| **Public** | Auth endpoints (2) | Smallest tier by design; hardened with lockout, rate limiting, MFA, risk-based step-up |
| **Authenticated** | REST API (1), Document/OCR (3), AI (4), ML (5), Connectors/Open API (6), Webhooks (8), Object storage (10) | Every entry behind JWT + `require_permission`; resource access additionally tenant-scoped |
| **Privileged** | SaaS admin (7) | Elevated RBAC + audit; deny-by-default |
| **Internal** | Metrics / probes (9) | Not internet-reachable; no sensitive data |

Minimising the **public** tier to the authentication surface alone, and placing
everything else behind authentication plus RBAC plus tenant scoping, is the core
of the platform's surface-reduction strategy.

---

## 8. Reduction recommendations

1. **Shrink the AI tool-use surface (B6).** Constrain which tools each agent may
   call, require typed/structured tool outputs, and add human-in-the-loop for
   high-impact actions. This directly reduces STRIDE-E2 (the top residual).
2. **Pin dependencies and commit a lockfile.** Remediates the `supply_chain`
   finding (27 unpinned deps) and raises that dimension out of 60.
3. **Provision real secrets per environment.** The dev profile's placeholder
   secrets are correctly flagged CRITICAL; production secrets lift the `secrets`
   dimension toward ~100.
4. **Tighten document ingestion.** Continue treating all uploaded files and
   OCR-extracted text as untrusted input to the AI context; validate and sandbox.
5. **Verify webhook signatures and idempotency** on every inbound event to close
   forgery/replay.
6. **Continuously diff the surface.** Poll `GET /api/sec/threat/attack-surface`
   in CI to detect any new public or high-risk entry point before release.

---

## 9. Related documents

- [THREAT_MODEL.md](THREAT_MODEL.md) — full enterprise threat model and trust boundaries.
- [STRIDE_ANALYSIS.md](STRIDE_ANALYSIS.md) — deep per-category STRIDE analysis.
- [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md) — the underlying controls.

← Back to [Security Documentation](index.md)
