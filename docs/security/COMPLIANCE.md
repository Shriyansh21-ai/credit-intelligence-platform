# Compliance Toolkit

_Phase 11, M12 — compliance abstractions for the AI Credit Intelligence Platform._

This toolkit (`core/compliance.py`) maps the platform's **actual** technical
controls (delivered across M5–M11) to the frameworks a Tier-1 bank must satisfy,
and provides the operational machinery for privacy rights, residency, and
auditor evidence. Coverage is **derived** from the control catalogue, not asserted.

---

## 1. Frameworks & control mapping

Supported: **SOC 2**, **ISO 27001**, **PCI DSS**, **GDPR**, **RBI**.

The `control_catalog` maps each internal control to the framework requirement
ids it satisfies and its implementation status. Example mappings:

| Control | Implemented by | SOC 2 | ISO 27001 | PCI DSS | GDPR | RBI |
|---------|----------------|-------|-----------|---------|------|-----|
| Encryption at rest | `crypto.FieldCipher` + KMS | CC6.7 | A.10.1 | 3.4, 3.5 | Art.32 | data-encryption |
| MFA | `authn.Totp` + risk step-up | CC6.1 | A.9.4 | 8.4, 8.5 | — | mfa |
| Audit logging | `AuditMiddleware` (7y) | CC7.2/3 | A.12.4 | 10.1/2 | — | audit-trail |
| Backup / DR | `core/dr` (M11) | A1.2/3 | A.17.1 | — | — | bcp-dr |
| Change management | CI/CD + branch protection | CC8.1 | A.12.1.2 | 6.4 | — | — |
| Data retention + erasure | `crypto.RetentionRegistry` | — | A.18.1 | — | Art.5/17 | data-retention |
| Data subject rights | `DataExporter`/`DataEraser` | — | — | — | Art.15/17/20 | — |
| Data residency | `ResidencyPolicy` + regional infra | — | — | — | Art.44 | data-localisation |

```python
from backend.app.core.compliance import generate_report, policy_matrix, Framework
generate_report(Framework.PCI_DSS)   # -> coverage %, per-control status, requirements covered
policy_matrix()                        # control -> {framework: [requirement ids]}
```

## 2. Consent management (GDPR Art. 6/7)

Purpose-scoped, versioned, append-only ledger with point-in-time lookup:

```python
from backend.app.core.compliance import ConsentLedger
ledger = ConsentLedger()
ledger.grant("subject-123", "marketing", policy_version="2.0")
ledger.has_consent("subject-123", "marketing")   # True
ledger.withdraw("subject-123", "marketing")       # latest state wins
ledger.history("subject-123")                      # full audit trail
```

## 3. Data residency (RBI localisation / GDPR Art. 44)

```python
from backend.app.core.compliance import ResidencyPolicy
policy = ResidencyPolicy()
policy.allow("kyc", {"ap-south-1", "ap-south-2"})   # India-only
policy.enforce("kyc", region)   # raises ResidencyViolation if disallowed
```

Backed by the region-pinned Terraform environments (M6) and per-tenant region
placement.

## 4. Data subject rights

- **Export / portability (Art. 15/20):** `DataExporter` assembles a subject's
  data across registered per-source collectors into a portable JSON bundle.
- **Erasure (Art. 17):** `DataEraser` orchestrates deletion across sources
  (each returns a count); pairs with crypto-shredding (`crypto.KeyRing.shred`)
  for encrypted data and secure file overwrite for artifacts.

```python
exporter.register("applications", lambda sid: repo.applications_for(sid))
bundle = exporter.export("subject-123")
result = eraser.erase("subject-123")   # ErasureResult(total=..., erased={source: n})
```

Both actions are audit-logged (M8 audit trail) and gated by RBAC + identity
verification in the calling endpoint.

## 5. Evidence collection & audit export

```python
from backend.app.core.compliance import EvidenceCollector, export_audit_ndjson
collector = EvidenceCollector()
collector.register("mfa", lambda: {"enabled": True, "users_enrolled": 4821})
bundle = collector.collect()   # auditor-ready snapshot; provider failures captured, never raised
export_audit_ndjson(audit_rows)   # hand-off format for external auditors
```

## 6. Operating model

- Controls are re-evaluated each release; `generate_report` output is archived as
  point-in-time evidence.
- Evidence collection runs on a schedule and before each audit window.
- Gaps (`status != implemented`) are tracked in
  [TECHNICAL_DEBT_REPORT.md](TECHNICAL_DEBT_REPORT.md) with owners and dates.
- Data-subject requests (export/erasure) are logged, RBAC-gated, and identity-verified.
