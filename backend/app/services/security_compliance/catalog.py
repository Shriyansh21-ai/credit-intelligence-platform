"""Canonical security & compliance catalogs — pure data, no I/O.

Single source of truth for the Stage 4 security programme: STRIDE categories
trust boundaries, the platform attack surface, OWASP Top 10 / API Top 10 / ASVS
controls, compliance frameworks (SOC 2, ISO 27001, GDPR, PCI DSS, RBI Digital
Lending, RBI Cyber Security, NIST CSF), the PII catalog and data-classification
levels.

Kept free of ORM/SQLAlchemy imports so it can be consumed from migrations
tests, docs generators and the runtime alike (mirrors ``rbac/catalog.py``).
"""

from __future__ import annotations

from typing import Dict, List, TypedDict


# ===========================================================================
# STRIDE
# ===========================================================================
STRIDE_CATEGORIES: Dict[str, str] = {
    "spoofing": "Impersonating an identity (authentication threats).",
    "tampering": "Unauthorised modification of data or code (integrity threats).",
    "repudiation": "Denying an action without a verifiable trail (non-repudiation).",
    "information_disclosure": "Exposure of information to unauthorised parties (confidentiality).",
    "denial_of_service": "Degrading or denying availability of a service.",
    "elevation_of_privilege": "Gaining capabilities beyond those granted (authorization).",
}


class StrideThreat(TypedDict):
    id: str
    category: str
    component: str
    threat: str
    existing_controls: List[str]
    residual: str  # low|medium|high


# Threats mapped to the actual platform components and the controls that already
# exist in the codebase (JWT, RBAC, audit middleware, field crypto, tenant
# middleware, security headers, refresh-token rotation, account lockout, ...).
STRIDE_THREATS: List[StrideThreat] = [
    {
        "id": "STRIDE-S1", "category": "spoofing", "component": "Authentication (JWT)",
        "threat": "Forged or replayed bearer tokens impersonate a user.",
        "existing_controls": ["HS256 signed JWT", "JwtKeyRing kid rotation",
                               "token expiry (ACCESS_TOKEN_EXPIRE_MINUTES)",
                               "refresh-token rotation with reuse detection"],
        "residual": "low",
    },
    {
        "id": "STRIDE-S2", "category": "spoofing", "component": "Login endpoint",
        "threat": "Credential stuffing / brute force to guess passwords.",
        "existing_controls": ["AccountLockout throttling", "PasswordPolicy",
                               "RiskEngine step-up MFA", "bcrypt hashing"],
        "residual": "low",
    },
    {
        "id": "STRIDE-T1", "category": "tampering", "component": "API request body",
        "threat": "Mass-assignment / parameter tampering to change protected fields.",
        "existing_controls": ["Pydantic request schemas", "RBAC permission gates",
                               "server-side ownership checks"],
        "residual": "medium",
    },
    {
        "id": "STRIDE-T2", "category": "tampering", "component": "Data at rest",
        "threat": "Direct modification of sensitive fields in the datastore.",
        "existing_controls": ["FieldCipher authenticated encryption (AES-GCM/EtM)",
                               "audit trail on mutations"],
        "residual": "low",
    },
    {
        "id": "STRIDE-R1", "category": "repudiation", "component": "Mutating API calls",
        "threat": "A user denies performing a privileged action.",
        "existing_controls": ["AuditMiddleware (one row per mutation)",
                               "correlation ids", "immutable audit retention (7y)"],
        "residual": "low",
    },
    {
        "id": "STRIDE-I1", "category": "information_disclosure", "component": "Logs & exports",
        "threat": "PII leaks into logs, error messages or exports.",
        "existing_controls": ["PiiMasker", "structured logging", "signed expiring URLs"],
        "residual": "medium",
    },
    {
        "id": "STRIDE-I2", "category": "information_disclosure", "component": "Multi-tenant data",
        "threat": "Cross-tenant read due to a missing tenant filter (IDOR).",
        "existing_controls": ["TenantMiddleware ambient context", "tenant_id scoping",
                               "tenant-isolation test suite"],
        "residual": "medium",
    },
    {
        "id": "STRIDE-D1", "category": "denial_of_service", "component": "Public API",
        "threat": "Request flooding exhausts resources.",
        "existing_controls": ["rate limiting (API platform)", "pagination caps",
                               "upload size limits (MAX_UPLOAD_MB)", "GZip guardrails"],
        "residual": "medium",
    },
    {
        "id": "STRIDE-D2", "category": "denial_of_service", "component": "Document/OCR pipeline",
        "threat": "Malicious documents trigger expensive processing (zip bombs, huge PDFs).",
        "existing_controls": ["content-type allow-list", "size limits",
                               "isolated processing"],
        "residual": "medium",
    },
    {
        "id": "STRIDE-E1", "category": "elevation_of_privilege", "component": "RBAC",
        "threat": "A low-privilege user invokes an admin-only capability.",
        "existing_controls": ["require_permission dependency on every route",
                               "least-privilege role catalog", "separation of duties"],
        "residual": "low",
    },
    {
        "id": "STRIDE-E2", "category": "elevation_of_privilege", "component": "AI agents / tools",
        "threat": "Prompt injection coerces an agent into unauthorised tool use.",
        "existing_controls": ["tool allow-lists", "permission checks on agent actions",
                               "human-in-the-loop for high-impact actions"],
        "residual": "high",
    },
]


# ===========================================================================
# Trust / privilege / authentication boundaries + attack surface
# ===========================================================================
TRUST_BOUNDARIES: List[Dict[str, str]] = [
    {"name": "Internet -> Edge", "description": "Untrusted clients cross into the reverse proxy / TLS termination.",
     "controls": "TLS, HSTS, security headers, CORS allow-list, WAF-ready"},
    {"name": "Edge -> API", "description": "Authenticated requests enter the FastAPI application.",
     "controls": "JWT verification, rate limiting, request validation"},
    {"name": "API -> Data", "description": "Application accesses the datastore and object storage.",
     "controls": "least-privilege DB user, parameterised queries (ORM), field encryption"},
    {"name": "Tenant A -> Tenant B", "description": "Logical isolation between tenants sharing infrastructure.",
     "controls": "tenant_id scoping, ambient tenant context, isolation tests"},
    {"name": "App -> External connectors", "description": "Outbound calls to bureaus, GST/MCA, AA, ERPs, payments.",
     "controls": "encrypted connector credentials, SSRF guards, timeouts, provider abstraction"},
    {"name": "App -> LLM/AI", "description": "Prompts and context sent to LLM providers / agents.",
     "controls": "prompt hardening, output validation, tool allow-lists, PII masking"},
]

ATTACK_SURFACE: List[Dict[str, str]] = [
    {"surface": "REST API (/api/*, /user, /loan, ...)", "exposure": "authenticated",
     "risk": "medium", "notes": "Primary surface; guarded by JWT + RBAC."},
    {"surface": "Auth endpoints (/auth/*)", "exposure": "public",
     "risk": "high", "notes": "Login/signup/refresh; brute-force + credential targets."},
    {"surface": "Document upload / OCR", "exposure": "authenticated",
     "risk": "high", "notes": "File parsing; malicious-document and traversal risk."},
    {"surface": "AI platform (/api/aip/*, agents, RAG, chat)", "exposure": "authenticated",
     "risk": "high", "notes": "Prompt injection, RAG poisoning, tool abuse."},
    {"surface": "ML platform (/api/ml/*)", "exposure": "authenticated",
     "risk": "medium", "notes": "Model registry, training, inference integrity."},
    {"surface": "Connectors / Open API (/api/integrations/*)", "exposure": "authenticated + outbound",
     "risk": "high", "notes": "SSRF, credential handling, third-party trust."},
    {"surface": "SaaS admin (/api/saas/*)", "exposure": "privileged",
     "risk": "high", "notes": "Cross-tenant administration; strong authz required."},
    {"surface": "Webhooks", "exposure": "inbound/outbound",
     "risk": "medium", "notes": "Signature verification, replay protection."},
    {"surface": "Metrics / probes (/metrics, /health)", "exposure": "internal",
     "risk": "low", "notes": "Should not be publicly exposed in production."},
    {"surface": "Object storage / signed URLs", "exposure": "authenticated",
     "risk": "medium", "notes": "Time-limited signed URLs; bucket isolation."},
]


# ===========================================================================
# OWASP
# ===========================================================================
class OwaspControl(TypedDict):
    id: str
    name: str
    description: str
    platform_controls: List[str]
    status: str  # satisfied|partial|gap


OWASP_TOP_10_2021: List[OwaspControl] = [
    {"id": "A01", "name": "Broken Access Control",
     "description": "Enforcement of least privilege and object-level authorization.",
     "platform_controls": ["RBAC require_permission on routes", "tenant_id scoping",
                            "ownership checks", "separation of duties in role catalog"],
     "status": "satisfied"},
    {"id": "A02", "name": "Cryptographic Failures",
     "description": "Protection of data in transit and at rest.",
     "platform_controls": ["TLS/HSTS", "AES-GCM field encryption + key rotation",
                            "bcrypt password hashing", "signed URLs"],
     "status": "satisfied"},
    {"id": "A03", "name": "Injection",
     "description": "SQL/command/template/prompt injection defences.",
     "platform_controls": ["SQLAlchemy ORM parameterisation", "Pydantic validation",
                            "prompt hardening + output validation"],
     "status": "partial"},
    {"id": "A04", "name": "Insecure Design",
     "description": "Threat modeling and secure-by-design controls.",
     "platform_controls": ["STRIDE threat model", "risk register", "secure SDLC docs"],
     "status": "satisfied"},
    {"id": "A05", "name": "Security Misconfiguration",
     "description": "Hardened defaults, security headers, no verbose errors.",
     "platform_controls": ["SecurityHeadersMiddleware", "profile-aware settings validation",
                            "no create_all (migrations only)", "debug off in prod"],
     "status": "satisfied"},
    {"id": "A06", "name": "Vulnerable & Outdated Components",
     "description": "Dependency and supply-chain hygiene.",
     "platform_controls": ["pinned requirements", "SBOM generation", "dependency scan",
                            "gitleaks secret scanning"],
     "status": "partial"},
    {"id": "A07", "name": "Identification & Authentication Failures",
     "description": "Strong authentication, session and credential management.",
     "platform_controls": ["JWT + expiry", "refresh rotation w/ reuse detection",
                            "AccountLockout", "PasswordPolicy", "TOTP MFA ready"],
     "status": "satisfied"},
    {"id": "A08", "name": "Software & Data Integrity Failures",
     "description": "Integrity of code, models and data pipelines.",
     "platform_controls": ["model registry integrity", "content hashing",
                            "signed artifacts readiness", "audit trail"],
     "status": "partial"},
    {"id": "A09", "name": "Security Logging & Monitoring Failures",
     "description": "Sufficient logging, monitoring and alerting.",
     "platform_controls": ["AuditMiddleware", "structured logging", "OpenTelemetry",
                            "Prometheus metrics", "security dashboard"],
     "status": "satisfied"},
    {"id": "A10", "name": "Server-Side Request Forgery (SSRF)",
     "description": "Validation of outbound requests from connectors.",
     "platform_controls": ["connector allow-lists", "URL validation", "timeouts",
                            "no raw user-controlled fetch"],
     "status": "partial"},
]

OWASP_API_TOP_10_2023: List[OwaspControl] = [
    {"id": "API1", "name": "Broken Object Level Authorization",
     "description": "Object-level access checks (IDOR).",
     "platform_controls": ["tenant_id scoping", "ownership checks", "RBAC"],
     "status": "partial"},
    {"id": "API2", "name": "Broken Authentication",
     "description": "Token and credential security.",
     "platform_controls": ["JWT rotation", "refresh reuse detection", "lockout"],
     "status": "satisfied"},
    {"id": "API3", "name": "Broken Object Property Level Authorization",
     "description": "Excessive data exposure / mass assignment.",
     "platform_controls": ["Pydantic response schemas", "field masking"],
     "status": "partial"},
    {"id": "API4", "name": "Unrestricted Resource Consumption",
     "description": "Rate limiting and quotas.",
     "platform_controls": ["rate limiting", "pagination caps", "upload limits"],
     "status": "partial"},
    {"id": "API5", "name": "Broken Function Level Authorization",
     "description": "Function/endpoint-level authorization.",
     "platform_controls": ["require_permission on every route", "role catalog"],
     "status": "satisfied"},
    {"id": "API6", "name": "Unrestricted Access to Sensitive Business Flows",
     "description": "Abuse of business flows (bulk scoring, exports).",
     "platform_controls": ["RBAC", "approval workflows", "audit"],
     "status": "partial"},
    {"id": "API7", "name": "Server-Side Request Forgery",
     "description": "Outbound request validation.",
     "platform_controls": ["connector allow-lists", "URL validation"],
     "status": "partial"},
    {"id": "API8", "name": "Security Misconfiguration",
     "description": "Hardened configuration and headers.",
     "platform_controls": ["SecurityHeadersMiddleware", "settings validation"],
     "status": "satisfied"},
    {"id": "API9", "name": "Improper Inventory Management",
     "description": "API versioning and inventory.",
     "platform_controls": ["API versioning middleware", "OpenAPI spec", "deprecation headers"],
     "status": "satisfied"},
    {"id": "API10", "name": "Unsafe Consumption of APIs",
     "description": "Safe consumption of third-party APIs.",
     "platform_controls": ["provider abstraction", "response validation", "timeouts"],
     "status": "partial"},
]

# OWASP ASVS L1/L2 verification chapters (condensed) for the review checklist.
ASVS_CHAPTERS: List[Dict[str, str]] = [
    {"id": "V1", "name": "Architecture, Design & Threat Modeling", "status": "satisfied"},
    {"id": "V2", "name": "Authentication", "status": "satisfied"},
    {"id": "V3", "name": "Session Management", "status": "satisfied"},
    {"id": "V4", "name": "Access Control", "status": "satisfied"},
    {"id": "V5", "name": "Validation, Sanitization & Encoding", "status": "partial"},
    {"id": "V6", "name": "Stored Cryptography", "status": "satisfied"},
    {"id": "V7", "name": "Error Handling & Logging", "status": "satisfied"},
    {"id": "V8", "name": "Data Protection", "status": "satisfied"},
    {"id": "V9", "name": "Communications", "status": "satisfied"},
    {"id": "V10", "name": "Malicious Code", "status": "partial"},
    {"id": "V11", "name": "Business Logic", "status": "partial"},
    {"id": "V12", "name": "Files & Resources", "status": "partial"},
    {"id": "V13", "name": "API & Web Service", "status": "satisfied"},
    {"id": "V14", "name": "Configuration", "status": "satisfied"},
]


# ===========================================================================
# Data classification & PII catalog
# ===========================================================================
DATA_CLASSIFICATIONS: List[Dict[str, str]] = [
    {"level": "public", "rank": "0", "description": "Non-sensitive, publicly shareable.",
     "controls": "none required"},
    {"level": "internal", "rank": "1", "description": "Internal business data.",
     "controls": "authentication, RBAC"},
    {"level": "confidential", "rank": "2", "description": "Sensitive business/financial data.",
     "controls": "RBAC least-privilege, encryption at rest, audit"},
    {"level": "restricted", "rank": "3", "description": "PII / regulated / credentials.",
     "controls": "field encryption, masking, strict RBAC, retention limits, audit"},
]


class PiiField(TypedDict):
    field: str
    classification: str
    category: str
    masking: str
    encryption: str  # required|recommended|n/a


PII_CATALOG: List[PiiField] = [
    {"field": "email", "classification": "confidential", "category": "contact",
     "masking": "partial (local-part)", "encryption": "recommended"},
    {"field": "phone", "classification": "confidential", "category": "contact",
     "masking": "last-4", "encryption": "recommended"},
    {"field": "password", "classification": "restricted", "category": "credential",
     "masking": "full", "encryption": "hashed (bcrypt)"},
    {"field": "pan", "classification": "restricted", "category": "national_id",
     "masking": "first-2 + last-1", "encryption": "required"},
    {"field": "aadhaar", "classification": "restricted", "category": "national_id",
     "masking": "last-4 only", "encryption": "required"},
    {"field": "bank_account", "classification": "restricted", "category": "financial",
     "masking": "last-4", "encryption": "required"},
    {"field": "card_number", "classification": "restricted", "category": "financial",
     "masking": "last-4 (PCI)", "encryption": "required"},
    {"field": "ip_address", "classification": "internal", "category": "technical",
     "masking": "truncate", "encryption": "n/a"},
    {"field": "financial_statements", "classification": "confidential", "category": "financial",
     "masking": "n/a", "encryption": "recommended"},
    {"field": "credit_score", "classification": "confidential", "category": "financial",
     "masking": "n/a", "encryption": "recommended"},
]


# ===========================================================================
# Compliance frameworks
# ===========================================================================
class ComplianceControl(TypedDict):
    id: str
    domain: str
    requirement: str
    status: str  # satisfied|partial|gap|not_applicable
    evidence: str


COMPLIANCE_FRAMEWORKS: Dict[str, Dict[str, object]] = {
    "soc2": {
        "name": "SOC 2 (Trust Services Criteria)",
        "version": "2017 TSC",
        "controls": [
            {"id": "CC1.1", "domain": "Control Environment", "requirement": "Commitment to integrity and ethics.",
             "status": "satisfied", "evidence": "Code of Conduct, security policies"},
            {"id": "CC2.1", "domain": "Communication", "requirement": "Security information communicated internally.",
             "status": "satisfied", "evidence": "SECURITY.md, docs/security/*"},
            {"id": "CC5.2", "domain": "Control Activities", "requirement": "Logical access controls (RBAC).",
             "status": "satisfied", "evidence": "RBAC catalog, require_permission"},
            {"id": "CC6.1", "domain": "Logical Access", "requirement": "Identity & access management.",
             "status": "satisfied", "evidence": "JWT, MFA-ready, lockout, password policy"},
            {"id": "CC6.6", "domain": "Logical Access", "requirement": "Encryption of data in transit/at rest.",
             "status": "satisfied", "evidence": "TLS/HSTS, field encryption"},
            {"id": "CC6.7", "domain": "Logical Access", "requirement": "Restrict transmission of sensitive data.",
             "status": "satisfied", "evidence": "PII masking, signed URLs"},
            {"id": "CC7.2", "domain": "System Operations", "requirement": "Security monitoring & anomaly detection.",
             "status": "satisfied", "evidence": "Audit middleware, telemetry, dashboard"},
            {"id": "CC7.3", "domain": "System Operations", "requirement": "Incident response.",
             "status": "partial", "evidence": "Runbooks; formal IR plan pending"},
            {"id": "CC8.1", "domain": "Change Management", "requirement": "Controlled change management.",
             "status": "satisfied", "evidence": "Alembic migrations, CI/CD, code review"},
            {"id": "A1.2", "domain": "Availability", "requirement": "Backup and recovery.",
             "status": "satisfied", "evidence": "DR module, backup cronjob, PITR window"},
        ],
    },
    "iso27001": {
        "name": "ISO/IEC 27001:2022 (Annex A)",
        "version": "2022",
        "controls": [
            {"id": "A.5.1", "domain": "Org policies", "requirement": "Information security policies.",
             "status": "satisfied", "evidence": "SECURITY.md, security architecture docs"},
            {"id": "A.5.15", "domain": "Access control", "requirement": "Access control policy.",
             "status": "satisfied", "evidence": "RBAC least privilege"},
            {"id": "A.5.17", "domain": "Authentication", "requirement": "Authentication information.",
             "status": "satisfied", "evidence": "bcrypt, JWT, MFA-ready"},
            {"id": "A.8.5", "domain": "Secure authentication", "requirement": "Secure authentication.",
             "status": "satisfied", "evidence": "Lockout, password policy, risk engine"},
            {"id": "A.8.12", "domain": "Data leakage", "requirement": "Data leakage prevention.",
             "status": "partial", "evidence": "PII masking; DLP tooling pending"},
            {"id": "A.8.24", "domain": "Cryptography", "requirement": "Use of cryptography.",
             "status": "satisfied", "evidence": "Field encryption, key rotation"},
            {"id": "A.8.15", "domain": "Logging", "requirement": "Logging.",
             "status": "satisfied", "evidence": "Audit trail, structured logs"},
            {"id": "A.8.16", "domain": "Monitoring", "requirement": "Monitoring activities.",
             "status": "satisfied", "evidence": "Telemetry, metrics, alerts"},
            {"id": "A.8.28", "domain": "Secure coding", "requirement": "Secure coding.",
             "status": "satisfied", "evidence": "Secure SDLC, ruff, review, tests"},
            {"id": "A.5.23", "domain": "Cloud security", "requirement": "Security for cloud services.",
             "status": "partial", "evidence": "K8s hardening; CSPM pending"},
        ],
    },
    "gdpr": {
        "name": "EU GDPR",
        "version": "2016/679",
        "controls": [
            {"id": "Art.5", "domain": "Principles", "requirement": "Lawfulness, minimisation, storage limitation.",
             "status": "satisfied", "evidence": "Retention registry, data minimisation"},
            {"id": "Art.15", "domain": "Data subject rights", "requirement": "Right of access.",
             "status": "satisfied", "evidence": "Privacy request (access) workflow"},
            {"id": "Art.17", "domain": "Data subject rights", "requirement": "Right to erasure.",
             "status": "satisfied", "evidence": "Erasure workflow + crypto-shredding"},
            {"id": "Art.20", "domain": "Data subject rights", "requirement": "Data portability.",
             "status": "satisfied", "evidence": "Portability request workflow"},
            {"id": "Art.25", "domain": "By design", "requirement": "Data protection by design & default.",
             "status": "satisfied", "evidence": "Encryption, masking, least privilege"},
            {"id": "Art.30", "domain": "Records", "requirement": "Records of processing activities.",
             "status": "partial", "evidence": "PII catalog; full RoPA pending"},
            {"id": "Art.32", "domain": "Security", "requirement": "Security of processing.",
             "status": "satisfied", "evidence": "Encryption, access control, resilience"},
            {"id": "Art.33", "domain": "Breach", "requirement": "Breach notification (72h).",
             "status": "partial", "evidence": "Monitoring; formal breach process pending"},
            {"id": "Art.35", "domain": "DPIA", "requirement": "Data protection impact assessment.",
             "status": "partial", "evidence": "Threat model; formal DPIA pending"},
        ],
    },
    "pci_dss": {
        "name": "PCI DSS",
        "version": "4.0",
        "controls": [
            {"id": "Req.1", "domain": "Network", "requirement": "Network security controls.",
             "status": "satisfied", "evidence": "K8s network policy, segmentation"},
            {"id": "Req.3", "domain": "Data", "requirement": "Protect stored account data.",
             "status": "satisfied", "evidence": "Field encryption, PAN masking last-4"},
            {"id": "Req.4", "domain": "Transmission", "requirement": "Encrypt transmission over open networks.",
             "status": "satisfied", "evidence": "TLS/HSTS"},
            {"id": "Req.6", "domain": "Secure systems", "requirement": "Develop/maintain secure systems.",
             "status": "satisfied", "evidence": "Secure SDLC, dependency scanning"},
            {"id": "Req.7", "domain": "Access", "requirement": "Restrict access by need-to-know.",
             "status": "satisfied", "evidence": "RBAC least privilege"},
            {"id": "Req.8", "domain": "Identity", "requirement": "Identify users and authenticate access.",
             "status": "satisfied", "evidence": "Unique IDs, MFA-ready, lockout"},
            {"id": "Req.10", "domain": "Logging", "requirement": "Log and monitor all access.",
             "status": "satisfied", "evidence": "Audit trail, telemetry"},
            {"id": "Req.11", "domain": "Testing", "requirement": "Test security regularly.",
             "status": "partial", "evidence": "Security tests; external pentest pending"},
            {"id": "Req.12", "domain": "Policy", "requirement": "Information security policy.",
             "status": "satisfied", "evidence": "Security policies & docs"},
        ],
    },
    "rbi_dl": {
        "name": "RBI Digital Lending Guidelines",
        "version": "2022",
        "controls": [
            {"id": "DL.1", "domain": "Data storage", "requirement": "Store data on servers located in India.",
             "status": "partial", "evidence": "Configurable region; deployment-dependent"},
            {"id": "DL.2", "domain": "Data minimisation", "requirement": "Collect only need-based data.",
             "status": "satisfied", "evidence": "Data minimisation, PII catalog"},
            {"id": "DL.3", "domain": "Consent", "requirement": "Explicit borrower consent for data.",
             "status": "satisfied", "evidence": "Consent tracking in privacy module"},
            {"id": "DL.4", "domain": "Transparency", "requirement": "Key Fact Statement & disclosures.",
             "status": "partial", "evidence": "Reporting; KFS templates deployment-side"},
            {"id": "DL.5", "domain": "Grievance", "requirement": "Grievance redressal mechanism.",
             "status": "partial", "evidence": "Workflow support; nodal officer config"},
            {"id": "DL.6", "domain": "Audit trail", "requirement": "Auditable trail of all actions.",
             "status": "satisfied", "evidence": "Immutable audit trail"},
        ],
    },
    "rbi_cyber": {
        "name": "RBI Cyber Security Framework",
        "version": "2016+",
        "controls": [
            {"id": "CS.1", "domain": "Inventory", "requirement": "Asset & data inventory.",
             "status": "satisfied", "evidence": "SBOM, data classification, PII catalog"},
            {"id": "CS.2", "domain": "Access", "requirement": "Access control & least privilege.",
             "status": "satisfied", "evidence": "RBAC"},
            {"id": "CS.3", "domain": "Encryption", "requirement": "Encryption of sensitive data.",
             "status": "satisfied", "evidence": "Field & transit encryption"},
            {"id": "CS.4", "domain": "Monitoring", "requirement": "Continuous security monitoring / SOC.",
             "status": "satisfied", "evidence": "Telemetry, audit, dashboard"},
            {"id": "CS.5", "domain": "Incident", "requirement": "Incident response & reporting.",
             "status": "partial", "evidence": "Runbooks; CERT-In reporting process pending"},
            {"id": "CS.6", "domain": "Resilience", "requirement": "Business continuity & DR.",
             "status": "satisfied", "evidence": "DR module, backups, HA"},
        ],
    },
    "rbi_outsourcing": {
        "name": "RBI Outsourcing Guidelines (IT Services)",
        "version": "2023",
        "controls": [
            {"id": "OS.1", "domain": "Governance", "requirement": "Board-approved outsourcing policy.",
             "status": "partial", "evidence": "Vendor governance docs; board policy org-side"},
            {"id": "OS.2", "domain": "Vendor risk", "requirement": "Due diligence on service providers.",
             "status": "partial", "evidence": "Supply-chain assessment, SBOM"},
            {"id": "OS.3", "domain": "Data protection", "requirement": "Confidentiality of customer data at vendors.",
             "status": "satisfied", "evidence": "Encryption, provider abstraction"},
            {"id": "OS.4", "domain": "Exit", "requirement": "Exit strategy & data portability.",
             "status": "satisfied", "evidence": "Provider abstraction, portable exports"},
            {"id": "OS.5", "domain": "Audit", "requirement": "Right to audit service providers.",
             "status": "partial", "evidence": "Connector audit logs; contractual org-side"},
        ],
    },
    "nist_csf": {
        "name": "NIST Cybersecurity Framework",
        "version": "2.0",
        "controls": [
            {"id": "GV", "domain": "Govern", "requirement": "Governance of cyber risk.",
             "status": "satisfied", "evidence": "Risk register, policies, RBAC"},
            {"id": "ID", "domain": "Identify", "requirement": "Asset & risk identification.",
             "status": "satisfied", "evidence": "SBOM, threat model, data classification"},
            {"id": "PR", "domain": "Protect", "requirement": "Protective safeguards.",
             "status": "satisfied", "evidence": "Encryption, RBAC, hardening"},
            {"id": "DE", "domain": "Detect", "requirement": "Detection of events.",
             "status": "satisfied", "evidence": "Monitoring, audit, anomaly detection"},
            {"id": "RS", "domain": "Respond", "requirement": "Response to incidents.",
             "status": "partial", "evidence": "Runbooks; formal IR plan pending"},
            {"id": "RC", "domain": "Recover", "requirement": "Recovery & resilience.",
             "status": "satisfied", "evidence": "DR, backups, HA"},
        ],
    },
}


# ===========================================================================
# AI / ML security controls (Milestones 10 & 11)
# ===========================================================================
AI_SECURITY_CONTROLS: List[Dict[str, str]] = [
    {"id": "AI-1", "threat": "Prompt Injection", "owasp_llm": "LLM01",
     "control": "Input hardening, delimiter enforcement, instruction/data separation, allow-listed tools.",
     "status": "partial"},
    {"id": "AI-2", "threat": "Insecure Output Handling", "owasp_llm": "LLM02",
     "control": "Output validation/sanitisation before rendering or executing; no eval of model output.",
     "status": "partial"},
    {"id": "AI-3", "threat": "Training Data / RAG Poisoning", "owasp_llm": "LLM03",
     "control": "Source vetting, ingestion controls, content hashing, provenance in RAG index.",
     "status": "partial"},
    {"id": "AI-4", "threat": "Model Denial of Service", "owasp_llm": "LLM04",
     "control": "Token/rate limits, timeouts, context-size caps.",
     "status": "satisfied"},
    {"id": "AI-5", "threat": "Supply-Chain (models/plugins)", "owasp_llm": "LLM05",
     "control": "Provider abstraction, plugin allow-lists, marketplace review.",
     "status": "partial"},
    {"id": "AI-6", "threat": "Sensitive Information Disclosure", "owasp_llm": "LLM06",
     "control": "PII masking before prompts, output redaction, memory isolation per tenant.",
     "status": "satisfied"},
    {"id": "AI-7", "threat": "Insecure Plugin/Tool Design", "owasp_llm": "LLM07",
     "control": "Least-privilege tools, permission checks on agent actions, human-in-the-loop.",
     "status": "partial"},
    {"id": "AI-8", "threat": "Excessive Agency", "owasp_llm": "LLM08",
     "control": "Constrain agent autonomy, approvals for high-impact actions, audit.",
     "status": "partial"},
    {"id": "AI-9", "threat": "Overreliance / Hallucination", "owasp_llm": "LLM09",
     "control": "Explainability, confidence scoring, human review of AI decisions.",
     "status": "satisfied"},
    {"id": "AI-10", "threat": "Model / Memory Poisoning", "owasp_llm": "LLM10",
     "control": "Memory write controls, tenant isolation, drift detection.",
     "status": "partial"},
]

ML_SECURITY_CONTROLS: List[Dict[str, str]] = [
    {"id": "ML-1", "area": "Training pipeline", "threat": "Data poisoning / label flipping",
     "control": "Dataset lineage, validation, provenance tracking.", "status": "partial"},
    {"id": "ML-2", "area": "Model registry", "threat": "Unauthorised model promotion/tampering",
     "control": "RBAC on promote/deploy, approval workflow, integrity hashing.", "status": "satisfied"},
    {"id": "ML-3", "area": "Feature store", "threat": "Feature tampering / leakage",
     "control": "Access control, tenant scoping, versioned features.", "status": "satisfied"},
    {"id": "ML-4", "area": "Model integrity", "threat": "Model file swap / corruption",
     "control": "Content hash on artifacts, signed-artifact readiness.", "status": "partial"},
    {"id": "ML-5", "area": "Explainability (SHAP)", "threat": "Manipulated explanations",
     "control": "Deterministic explainers, integrity checks on explanation store.", "status": "satisfied"},
    {"id": "ML-6", "area": "Drift detection", "threat": "Silent performance degradation / evasion",
     "control": "Continuous drift monitoring, alerting, retraining governance.", "status": "satisfied"},
    {"id": "ML-7", "area": "Inference", "threat": "Model inversion / membership inference",
     "control": "Rate limiting, output minimisation, access control.", "status": "partial"},
]


def framework_ids() -> List[str]:
    return list(COMPLIANCE_FRAMEWORKS.keys())
