# Compliance Frameworks & Readiness

_Stage 4, M7 — control mapping, gap analysis, and audit readiness for the AI Credit Intelligence Platform._

This document is produced by the compliance engine
(`backend/app/services/security_compliance/compliance.py`) which maps the
platform's **actual** technical controls to the requirements of the frameworks a
Tier-1 lender must satisfy. Coverage is **derived** from the control catalogue
(`catalog.py`) and scored deterministically (`common.py`), not asserted by hand.
Every readiness number below is reproducible from the live API.

All figures reflect the **development profile**. Two environment-specific items
(placeholder secrets, unpinned dependencies) are remediated in a
production-configured deployment; see [COMPLIANCE.md](COMPLIANCE.md) and
[SUPPLY_CHAIN_SECURITY.md](SUPPLY_CHAIN_SECURITY.md).

---

## 1. API surface

| Endpoint | Method | Permission | Purpose |
|----------|--------|-----------|---------|
| `/api/sec/compliance/matrix` | GET | `sec.compliance.view` | Full control-to-framework mapping |
| `/api/sec/compliance/gap-analysis` | GET | `sec.compliance.view` | Partial / gap controls with remediation |
| `/api/sec/compliance/readiness` | GET | `sec.compliance.view` | Per-framework and overall readiness scorecard |
| `/api/sec/compliance/framework/{id}` | GET | `sec.compliance.view` | Single-framework detail |
| `/api/sec/compliance/assess` | POST | `sec.compliance.manage` | Persist a point-in-time assessment (`sec_compliance_assessments`) |
| `/api/sec/compliance/assessments` | GET | `sec.compliance.view` | Historical assessments |

Read access is owned by `compliance_officer` and `risk_manager`; oversight roles
inherit read; `administrator` holds all Security & Compliance permissions.
Assessments are tenant-scoped (nullable `tenant_id`) and audit-logged.

---

## 2. Consolidated readiness scorecard

Readiness is the weighted proportion of framework requirements met by an
implemented or partially-implemented control, expressed on a 0–100 scale.

| Framework | Readiness | Band | Assessment |
|-----------|-----------|------|------------|
| SOC 2 (Trust Services Criteria) | **95.0** | Strong | Ready for Type II window |
| PCI DSS v4.0 | **94.4** | Strong | Card-data controls in place |
| RBI Cyber Security Framework | **91.7** | Strong | Baseline + Annex controls met |
| NIST CSF 2.0 | **91.7** | Strong | Identify→Recover coverage |
| ISO/IEC 27001:2022 | **90.0** | Strong | Annex A largely satisfied |
| GDPR | **83.3** | Substantial | Privacy engineering in place |
| RBI Digital Lending | **75.0** | Substantial | Disclosure controls partial |
| RBI Outsourcing (IT / SAR) | **70.0** | Substantial | Vendor-governance gaps |
| **Overall** | **86.4** | **Substantial** | Audit-ready with tracked gaps |

The overall figure (86.4) is the same value that feeds the `compliance`
dimension of the enterprise security posture.

---

## 3. Per-framework control mapping

Status legend: **Satisfied** — control implemented and evidenced; **Partial** —
implemented with a documented residual gap; **Gap** — planned, not yet
delivered.

### 3.1 SOC 2 — 95.0

| Control ID | Domain | Requirement | Status | Evidence |
|-----------|--------|-------------|--------|----------|
| CC6.1 | Logical access | Authentication & MFA | Satisfied | `core/authn.py` `Totp`, risk step-up |
| CC6.6 | Boundary protection | Network / edge controls | Satisfied | `SecurityHeadersMiddleware`, edge trust boundary |
| CC6.7 | Data at rest | Encryption of stored data | Satisfied | `core/crypto.py` `FieldCipher` (AES-256-GCM) |
| CC7.2 | Monitoring | Security event logging | Satisfied | `audit_middleware.py` (one row per mutation) |
| CC7.3 | Incident response | Evaluate & respond to events | Satisfied | `sec_findings`, risk register workflow |
| CC8.1 | Change management | Controlled change | Partial | CI/CD + branch protection; lockfile pending |
| A1.2 | Availability | Backup / recovery | Satisfied | DR drill checklist, backup retention |

### 3.2 ISO/IEC 27001:2022 — 90.0

| Control ID | Domain | Requirement | Status | Evidence |
|-----------|--------|-------------|--------|----------|
| A.5.15 | Access control | Access policy | Satisfied | RBAC `require_permission` on every route |
| A.8.5 | Identity | Secure authentication | Satisfied | `JwtKeyRing`, `RefreshTokenService` reuse detection |
| A.8.24 | Cryptography | Use of cryptography | Satisfied | `KeyRing` versioning + rotation |
| A.8.28 | Secure coding | Secure development | Partial | ASVS partials (A03/A06/A08) |
| A.5.23 | Cloud security | Cloud service use | Satisfied | Profile-aware `settings.validate_runtime()` |
| A.8.8 | Vulnerability mgmt | Technical vulnerabilities | Partial | SBOM present; deps unpinned |
| A.5.30 | Continuity | ICT readiness for BCP | Satisfied | HA + DR documentation |

### 3.3 GDPR — 83.3

| Control ID | Domain | Requirement | Status | Evidence |
|-----------|--------|-------------|--------|----------|
| Art.5 | Principles | Retention limitation | Satisfied | `RetentionRegistry` catalog |
| Art.15 | Subject rights | Right of access | Satisfied | DSAR `access` request type |
| Art.17 | Subject rights | Right to erasure | Satisfied | Crypto-shredding via `KeyRing.shred` |
| Art.20 | Subject rights | Data portability | Satisfied | DSAR `portability` export bundle |
| Art.30 | Accountability | Records of processing | Partial | PII catalog present; ROPA export pending |
| Art.32 | Security | Security of processing | Satisfied | Encryption, masking, access control |
| Art.35 | Accountability | DPIA | Partial | Threat model covers AI flows; formal DPIA pending |

### 3.4 PCI DSS v4.0 — 94.4

| Control ID | Domain | Requirement | Status | Evidence |
|-----------|--------|-------------|--------|----------|
| Req 3.4 | Protect stored data | Render PAN unreadable | Satisfied | `FieldCipher` + `PiiMasker` (card/PAN) |
| Req 3.5 | Key management | Protect cryptographic keys | Satisfied | `KeyRing` key versioning |
| Req 6.4 | Secure development | Change control | Partial | Branch protection; dependency pinning pending |
| Req 8.4 | Authentication | MFA for access | Satisfied | `Totp` RFC 6238 |
| Req 8.5 | Authentication | MFA robustness | Satisfied | Risk-based step-up |
| Req 10.1 | Logging | Audit trails | Satisfied | Audit middleware (7y retention) |
| Req 10.2 | Logging | Automated audit trails | Satisfied | One audit row per mutation |

### 3.5 RBI Digital Lending — 75.0

| Control ID | Domain | Requirement | Status | Evidence |
|-----------|--------|-------------|--------|----------|
| DL-1 | Disclosure | Key Fact Statement transparency | Partial | Product surface present; automated KFS pending |
| DL-2 | Data | Data minimisation & consent | Satisfied | PII catalog + consent ledger |
| DL-3 | Data localisation | Storage in India | Satisfied | Region-pinned residency policy |
| DL-4 | Grievance | Cooling-off / grievance redress | Partial | Workflow scaffolding; SLA automation pending |
| DL-5 | Audit | Auditable lending trail | Satisfied | Audit middleware + lifecycle events |
| DL-6 | Third parties | LSP oversight | Partial | Connector governance; formal LSP register pending |

### 3.6 RBI Cyber Security Framework — 91.7

| Control ID | Domain | Requirement | Status | Evidence |
|-----------|--------|-------------|--------|----------|
| CS-1 | Inventory | Asset & data inventory | Satisfied | SBOM + PII catalog |
| CS-2 | Access | Least-privilege access | Satisfied | RBAC 20 sec-permissions + tenant isolation |
| CS-3 | Secure config | Baseline hardening | Satisfied | Container score 100, security headers |
| CS-4 | Encryption | Data protection | Satisfied | AES-256-GCM at rest, TLS/HSTS in transit |
| CS-5 | Monitoring | SOC / event capture | Satisfied | Findings + posture snapshots |
| CS-6 | Secrets | Secrets management | Partial | Dev placeholders flagged CRITICAL; prod-injected |

### 3.7 RBI Outsourcing (IT / SAR) — 70.0

| Control ID | Domain | Requirement | Status | Evidence |
|-----------|--------|-------------|--------|----------|
| OS-1 | Governance | Outsourcing policy | Partial | Vendor register pending formalisation |
| OS-2 | Due diligence | Provider assessment | Partial | Supply-chain report; scoring manual |
| OS-3 | Right to audit | Contractual audit rights | Gap | Contract clauses tracked outside platform |
| OS-4 | Data | Data confidentiality | Satisfied | Encryption + tenant isolation |
| OS-5 | Continuity | Exit / continuity plan | Satisfied | DR + HA runbooks |
| OS-6 | Concentration | Concentration risk | Partial | Connector dependency mapping pending |

### 3.8 NIST CSF 2.0 — 91.7

| Control ID | Function | Requirement | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| GV.RM | Govern | Risk management strategy | Satisfied | `sec_risk_register` workflow |
| ID.AM | Identify | Asset management | Satisfied | SBOM + attack-surface inventory |
| PR.AC | Protect | Identity & access control | Satisfied | RBAC + MFA + tenant isolation |
| PR.DS | Protect | Data security | Satisfied | Encryption + masking + retention |
| DE.CM | Detect | Continuous monitoring | Satisfied | Scans, findings, posture snapshots |
| RS.MA | Respond | Incident management | Partial | Finding workflow; playbook automation pending |
| RC.RP | Recover | Recovery planning | Satisfied | DR drill checklist |

---

## 4. Gap analysis

The engine (`/api/sec/compliance/gap-analysis`) surfaces every control whose
status is **Partial** or **Gap**, with owner and remediation. Consolidated:

| Framework | Control | Status | Finding | Remediation | Owner |
|-----------|---------|--------|---------|-------------|-------|
| SOC 2 / PCI / ISO | Change management (CC8.1 / Req 6.4 / A.8.8) | Partial | Dependencies unpinned; no committed lockfile | Pin `requirements.txt`, commit lockfile, enforce in CI | Platform Eng |
| RBI Cyber | Secrets (CS-6) | Partial | Dev profile ships placeholder secrets, flagged CRITICAL | Inject real secrets via secret manager in prod | Platform Eng |
| GDPR | ROPA (Art.30) | Partial | Records of processing not auto-exported | Generate ROPA from PII catalog | Compliance |
| GDPR | DPIA (Art.35) | Partial | No formal DPIA artifact for AI flows | Author DPIA using STRIDE AI boundary | Compliance |
| RBI DL | KFS / grievance (DL-1, DL-4) | Partial | Automated disclosure & grievance SLA pending | Wire KFS generation + grievance SLA timers | Product |
| RBI DL | LSP oversight (DL-6) | Partial | No formal LSP register | Add Lending Service Provider register | Compliance |
| ISO / OWASP | Secure coding (A.8.28) | Partial | ASVS A03/A06/A08 partial | Close output-encoding & component-integrity items | Platform Eng |
| RBI Outsourcing | Right to audit (OS-3) | Gap | Audit clauses tracked outside platform | Import vendor contract register | Vendor Mgmt |
| RBI Outsourcing | Governance / concentration (OS-1, OS-6) | Partial | Vendor & concentration mapping manual | Formalise vendor register + dependency map | Vendor Mgmt |

None of the open items are CRITICAL in a production configuration; the two
environment-specific items (secrets, unpinned deps) resolve on deployment.

---

## 5. Operating model

- Controls are re-scored each release; `POST /compliance/assess` archives a
  point-in-time snapshot to `sec_compliance_assessments` for auditor evidence.
- Gap items are tracked with owners and target dates; the readiness scorecard is
  reviewed at each compliance forum.
- A production-configured deployment (real secrets, pinned dependencies) lifts
  the environment-dependent controls, raising the overall enterprise posture
  into the A-/B+ band (~88–90) while the framework readiness figures above hold.
