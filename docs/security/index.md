# Security Documentation

*Security architecture, controls, and compliance for the AI Credit Intelligence Platform.*

| Document | Description |
| --- | --- |
| [COMPLIANCE](COMPLIANCE.md) | Regulatory and compliance posture, controls, and attestations. |
| [SECURITY_ARCHITECTURE](SECURITY_ARCHITECTURE.md) | Security design: identity, authorization, encryption, and boundaries. |
| [SECURITY_GUIDE](SECURITY_GUIDE.md) | Practical security guidance and hardening practices. |

## Enterprise Security & Compliance Platform

Deliverables of the enterprise security & compliance programme. The live control
plane is exposed under `/api/sec/*` and the Security Center dashboard.

| Document | Milestone | Description |
| --- | --- | --- |
| [SECURITY_CERTIFICATION](SECURITY_CERTIFICATION.md) | M15 | Certification statement + milestone completion |
| [SECURITY_SCORECARD](SECURITY_SCORECARD.md) | M14/M15 | Quantitative posture by dimension |
| [SECURITY_REPORT](SECURITY_REPORT.md) | M15 | Master engineering report + validation log |
| [SECURITY_ARCHITECTURE_FINAL](SECURITY_ARCHITECTURE_FINAL.md) | M15 | Consolidated defense-in-depth architecture |
| [SECURITY_CHECKLIST](SECURITY_CHECKLIST.md) | M15 | Production go-live security checklist |
| [PENETRATION_TEST_GUIDE](PENETRATION_TEST_GUIDE.md) | M15 | External pentest scoping + test cases |
| [COMPLIANCE_REPORT](COMPLIANCE_REPORT.md) | M7/M15 | Executive compliance readiness report |
| [THREAT_MODEL](THREAT_MODEL.md) | M1 | Enterprise threat model (STRIDE + attack trees) |
| [ATTACK_SURFACE](ATTACK_SURFACE.md) | M1 | Attack-surface enumeration |
| [STRIDE_ANALYSIS](STRIDE_ANALYSIS.md) | M1 | Deep STRIDE analysis |
| [OWASP_SECURITY_REVIEW](OWASP_SECURITY_REVIEW.md) | M2 | OWASP Top 10 / API Top 10 / ASVS |
| [AUTHENTICATION_HARDENING](AUTHENTICATION_HARDENING.md) | M3 | Auth & authorization hardening audit |
| [MULTI_TENANT_SECURITY](MULTI_TENANT_SECURITY.md) | M4 | Multi-tenant isolation audit |
| [SECRET_MANAGEMENT](SECRET_MANAGEMENT.md) | M5 | Secret inventory & rotation |
| [DATA_PROTECTION](DATA_PROTECTION.md) | M6 | Classification, PII catalog, encryption |
| [COMPLIANCE_FRAMEWORKS](COMPLIANCE_FRAMEWORKS.md) | M7 | Compliance matrix + gap analysis |
| [SUPPLY_CHAIN_SECURITY](SUPPLY_CHAIN_SECURITY.md) | M8 | SBOM, dependency & license reports |
| [CONTAINER_KUBERNETES_SECURITY](CONTAINER_KUBERNETES_SECURITY.md) | M9 | Container / K8s hardening guide |
| [AI_SECURITY](AI_SECURITY.md) | M10 | AI security (OWASP LLM Top 10) |
| [ML_SECURITY](ML_SECURITY.md) | M11 | ML pipeline / registry / integrity security |
| [DATA_PRIVACY](DATA_PRIVACY.md) | M12 | Privacy engineering (consent/retention/DSAR) |

> [!NOTE]
> To report a vulnerability, follow the process in the root [SECURITY.md](../../SECURITY.md).
> AI-specific security is covered in [AI_SECURITY](../ai/AI_SECURITY.md).

← Back to [Documentation Home](../index.md)
