# Security Architecture (Final) — Stage 4

The consolidated, end-to-end security architecture of the AI Credit Intelligence
Platform after Stage 4. Complements the pre-existing
[SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md) with the security-programme
layer added in this stage.

## Defense-in-depth layers

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1. Edge / Network                                                      │
│    TLS 1.2+ · HSTS · CSP · security headers · CORS allow-list · WAF-   │
│    ready · K8s NetworkPolicy (default-deny)                            │
├──────────────────────────────────────────────────────────────────────┤
│ 2. Identity & Access                                                   │
│    JWT (HS256) + JwtKeyRing rotation · RefreshTokenService (rotation + │
│    reuse detection) · AccountLockout · PasswordPolicy · TOTP MFA ·     │
│    RiskEngine step-up · RBAC require_permission on every route         │
├──────────────────────────────────────────────────────────────────────┤
│ 3. Application                                                         │
│    Pydantic validation · SQLAlchemy ORM (parameterised) · ownership    │
│    checks · rate limiting · upload allow-list + size caps · audit      │
│    middleware (one row per mutation)                                   │
├──────────────────────────────────────────────────────────────────────┤
│ 4. Multi-tenant isolation                                             │
│    TenantMiddleware ambient context · tenant_id scoping · cache/       │
│    storage/RAG/AI-memory/search/graph isolation                        │
├──────────────────────────────────────────────────────────────────────┤
│ 5. Data protection                                                    │
│    FieldCipher (AES-256-GCM / stdlib EtM) · KeyRing versioning +       │
│    rotation + crypto-shred · PiiMasker · signed expiring URLs ·        │
│    RetentionRegistry                                                    │
├──────────────────────────────────────────────────────────────────────┤
│ 6. AI/ML safety                                                       │
│    tool allow-lists · output validation · PII masking pre-prompt ·     │
│    tenant memory isolation · model registry integrity · drift          │
├──────────────────────────────────────────────────────────────────────┤
│ 7. Observability & governance                                         │
│    structured logging · OpenTelemetry · Prometheus · audit trail ·     │
│    Security & Compliance platform (/api/sec/*) · risk register         │
└──────────────────────────────────────────────────────────────────────┘
```

## Security programme layer (Stage 4)

| Component | Path | Purpose |
|---|---|---|
| Assessment engines | `services/security_compliance/*.py` | Deterministic, offline scoring of 12 security dimensions |
| API | `routes/security_compliance.py` (`/api/sec/*`) | 45 RBAC-gated endpoints |
| Persistence | `models/security_compliance.py` (7 tables) | Scans, findings, compliance, risk, privacy, posture, secrets |
| Posture aggregator | `security_compliance/posture.py` | Weighted overall posture + grade |
| Dashboard | `/security-dashboard` (frontend) | Live security administration UI |

## Trust boundaries

| Boundary | Enforcement |
|---|---|
| Internet → Edge | TLS, HSTS, security headers, CORS |
| Edge → API | JWT verification, rate limiting, validation |
| API → Data | ORM parameterisation, least-privilege DB user, field encryption |
| Tenant A → Tenant B | tenant_id scoping, ambient context, isolation tests |
| App → Connectors | encrypted credentials, SSRF guards, timeouts |
| App → LLM/AI | prompt hardening, output validation, tool allow-lists, PII masking |

## Key management hierarchy

```
Root / KMS master key
  └── Data-encryption keys (versioned, KeyRing)
        └── Per-field ciphers (FieldCipher, AES-256-GCM)
  └── Signing / HMAC keys (JwtKeyRing kid rotation, signed URLs)
```

Rotation: add a new key version → re-encrypt lazily on read/write → crypto-shred
the retired version. JWT signing rotates by `kid`: sign with the active key,
verify against all live keys (zero-downtime).

## Data flow & classification

Data is classified `public | internal | confidential | restricted`. Restricted
data (PAN, Aadhaar, card, bank account, password) is encryption-required and
masked in logs/exports/lower environments. See [DATA_PROTECTION.md](DATA_PROTECTION.md).

## Separation of duties

- `administrator` — full access (wildcard).
- `compliance_officer` — owns compliance assessments + privacy (DSAR).
- `risk_manager` — owns findings triage + risk register + compliance.
- Oversight roles (`auditor`, others) — read-only on the security surfaces.
- Read-only roles never hold `*.manage` / `*.admin` (enforced by the RBAC audit).
