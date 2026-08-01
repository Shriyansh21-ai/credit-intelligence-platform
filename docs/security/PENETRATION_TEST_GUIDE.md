# Penetration Test Guide — Stage 4

A scoping and execution guide for an external penetration test / red-team
engagement against the AI Credit Intelligence Platform. Maps test cases to the
platform's controls and the Stage 4 threat model so findings can be triaged into
the risk register (`/api/sec/risk`) and findings store (`/api/sec/findings`).

## Scope

| In scope | Out of scope (unless contracted) |
|---|---|
| REST API `/api/*`, `/auth/*`, `/user`, `/loan` | Underlying cloud provider infrastructure |
| Authentication & session management | Physical / social engineering |
| RBAC / authorization (IDOR, priv-esc) | Third-party bureau / GST / MCA endpoints |
| Multi-tenant isolation | DoS/DDoS volumetric (coordinate separately) |
| Document upload / OCR pipeline | |
| AI platform (prompt injection, RAG, agents) | |
| ML platform (registry, inference) | |
| Connectors / Open API / webhooks | |

## Rules of engagement

- Use a dedicated non-production environment mirroring production config.
- Provision test accounts across roles: `administrator`, `risk_manager`,
  `credit_analyst`, `auditor`, `viewer`, plus two tenants (A/B).
- Rate-limit destructive tests; snapshot the DB before/after.
- Report criticals immediately; do not exfiltrate real PII.

## Test cases by category

### Authentication (STRIDE-S1/S2, OWASP A07/API2)
- [ ] JWT tampering: alter payload/signature; confirm rejection.
- [ ] Algorithm confusion (`alg=none`, HS/RS confusion); confirm rejection.
- [ ] Token expiry & replay after logout.
- [ ] Refresh-token reuse → confirm family revocation (`RefreshTokenService`).
- [ ] Credential brute force → confirm `AccountLockout`.
- [ ] Password policy bypass (weak/common passwords).
- [ ] MFA/TOTP bypass; risk step-up on new device/geo.

### Authorization / IDOR (STRIDE-E1, OWASP A01/API1/API5)
- [ ] Access another user's object by id manipulation.
- [ ] Invoke `*.manage` / admin endpoints as a low-privilege role → expect 403.
- [ ] Self-assign a role (`roles.manage`) → expect 403 + audit entry.
- [ ] Verify every `/api/sec/*` route enforces `require_permission`.

### Multi-tenant isolation (STRIDE-I2, M4)
- [ ] Read/list tenant B's data while authenticated to tenant A.
- [ ] Cache/RAG/AI-memory cross-tenant bleed.
- [ ] Cross-tenant object storage / signed-URL access.

### Injection (OWASP A03)
- [ ] SQL injection on every filter/search/sort parameter (expect ORM safety).
- [ ] Path traversal on document download / file endpoints.
- [ ] Prompt injection on AI chat/agent/RAG surfaces (STRIDE-E2, highest residual).
- [ ] RAG poisoning via malicious document ingestion.
- [ ] Template/CSV injection in exports.

### File upload (M1 attack surface)
- [ ] Upload disallowed content types; oversized files; zip/PDF bombs.
- [ ] Malicious document triggering OCR resource exhaustion.
- [ ] Polyglot / MIME-spoofed files.

### SSRF (OWASP A10/API7)
- [ ] Connector/webhook URLs pointing to internal metadata endpoints.
- [ ] Redirect-based SSRF; DNS rebinding.

### Session / headers / CSRF
- [ ] Verify security headers present (HSTS, CSP, X-Frame-Options, nosniff).
- [ ] CORS: confirm no wildcard-with-credentials.
- [ ] CSRF on state-changing endpoints (bearer-token API → low risk; verify).

### Rate limiting / abuse (STRIDE-D1)
- [ ] Bulk scoring / export abuse; pagination cap bypass.

### AI/ML (M10/M11)
- [ ] Jailbreak system prompts; unsafe tool execution via agents.
- [ ] Model registry: unauthorised promotion/rollback.
- [ ] Membership/model-inversion on inference endpoints.

## Reporting

Log each confirmed issue into the risk register with likelihood × impact, and as
a finding under the relevant category (`owasp`, `authz`, `tenant`, `ai_security`,
`ml_security`, `container`, `supply_chain`). Re-run `/api/sec/scans` (type `full`)
and re-snapshot posture after remediation to confirm closure.

## Reference tooling

OWASP ZAP / Burp Suite (API), sqlmap (injection, authorised), nuclei
(misconfig), Trivy/Grype (image CVEs), gitleaks (secrets), plus manual RBAC /
tenant-isolation and prompt-injection testing.
