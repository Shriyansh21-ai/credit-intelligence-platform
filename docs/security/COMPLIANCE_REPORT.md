# Compliance Report — Stage 4

Executive compliance report for the AI Credit Intelligence Platform. Generated
from the compliance engine (`/api/sec/compliance/*`). Companion to the detailed
[COMPLIANCE_FRAMEWORKS.md](COMPLIANCE_FRAMEWORKS.md).

## Executive summary

The platform maps to **8 regulatory and industry frameworks** with an aggregate
readiness of **86.4% ("substantial")**. Control coverage is strongest for the
technical security frameworks (SOC 2, PCI DSS, NIST CSF, ISO 27001, RBI Cyber
Security) and has documented, deployment-owned gaps for governance/process items
(formal IR plan, RoPA/DPIA, board-approved outsourcing policy, data-localisation
attestation) that are organisational rather than code-level.

## Readiness scorecard

| Framework | Version | Readiness | Bucket |
|---|---|---:|---|
| SOC 2 (Trust Services Criteria) | 2017 TSC | 95.0% | ready |
| ISO/IEC 27001 (Annex A) | 2022 | 90.0% | ready |
| EU GDPR | 2016/679 | 83.3% | substantial |
| PCI DSS | 4.0 | 94.4% | ready |
| RBI Digital Lending Guidelines | 2022 | 75.0% | substantial |
| RBI Cyber Security Framework | 2016+ | 91.7% | ready |
| RBI Outsourcing Guidelines | 2023 | 70.0% | partial |
| NIST Cybersecurity Framework | 2.0 | 91.7% | ready |
| **Aggregate** | — | **86.4%** | **substantial** |

## Control coverage highlights

| Domain | Status | Evidence |
|---|---|---|
| Access control (least privilege) | satisfied | RBAC catalog, `require_permission` |
| Encryption (transit + at rest) | satisfied | TLS/HSTS, FieldCipher AES-256-GCM |
| Authentication (MFA-ready) | satisfied | JWT rotation, TOTP, lockout, password policy |
| Logging & monitoring | satisfied | Audit middleware, OpenTelemetry, metrics |
| Change management | satisfied | Alembic migrations, CI/CD, code review |
| Backup & DR | satisfied | DR module, backup cronjob, PITR |
| Data-subject rights (access/erasure/portability) | satisfied | Privacy (DSAR) workflow + crypto-shredding |
| Data minimisation & retention | satisfied | PII catalog, RetentionRegistry |

## Open gaps (deployment / organisational)

| Framework | Control | Gap | Owner |
|---|---|---|---|
| SOC 2 / NIST | Incident Response | Formal IR plan + tabletop exercises | Security ops |
| GDPR | Art.30 / Art.35 | Full RoPA + DPIA documentation | DPO |
| GDPR | Art.33 | Formal 72h breach-notification process | Security ops |
| RBI Digital Lending | Data localisation | India-region attestation | Infra/legal |
| RBI Digital Lending | KFS / grievance | KFS templates + nodal officer config | Product/compliance |
| RBI Outsourcing | Governance | Board-approved outsourcing policy; vendor due-diligence records | Board/legal |
| ISO 27001 | Cloud security | CSPM tooling | Infra |

These gaps are **process/organisational**, not product defects; the platform
provides the technical substrate (audit trail, provider abstraction, consent
tracking, monitoring) to satisfy them once the organisational artefacts are in
place.

## Continuous compliance

Compliance is assessed on demand and recorded to `sec_compliance_assessments`
(`POST /api/sec/compliance/assess`), enabling point-in-time evidence and trend
tracking. The gap analysis (`/api/sec/compliance/gap-analysis`) enumerates every
partial/gap control across all frameworks with remediation guidance.

## Attestation

- Assessment date: 2026-08-01
- Method: automated control mapping (`security_compliance.compliance`) + manual review
- Aggregate readiness: **86.4% (substantial)**
- Recommendation: **fit for regulated production** once the deployment-owned gaps
  above and the [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md) blockers are closed.
