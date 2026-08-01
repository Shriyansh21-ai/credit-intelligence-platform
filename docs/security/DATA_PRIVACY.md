# Data Privacy Engineering

_Stage 4, M12 — privacy engineering, retention, and data-subject rights for the AI Credit Intelligence Platform._

This document is produced by the privacy engine
(`backend/app/services/security_compliance/privacy.py`), backed by the
platform's data-protection primitives in `core/crypto.py`
(`RetentionRegistry`, `KeyRing`, `PiiMasker`). It records how personal data is
classified, retained, minimised, and erased, and how data-subject requests
(DSARs) are serviced.

The privacy dimension scores **87.5 / 100** in the development profile — the
strongest of the AI/data dimensions. One area (AI memory retention) is
**partial**, a documented finding with a defined remediation.

---

## 1. API surface

| Endpoint | Method | Permission | Purpose |
|----------|--------|-----------|---------|
| `/api/sec/privacy` | GET | `sec.privacy.view` | Privacy posture report + score |
| `/api/sec/privacy/requests` | GET | `sec.privacy.view` | List DSAR requests (`sec_privacy_requests`) |
| `/api/sec/privacy/requests` | POST | `sec.privacy.manage` | Raise a DSAR |
| `/api/sec/privacy/requests` | PATCH | `sec.privacy.manage` | Advance a DSAR through its lifecycle |

Read access is owned by `compliance_officer` and `risk_manager`; `administrator`
holds all permissions. Requests are tenant-scoped and audit-logged.

---

## 2. Consent

Personal data is processed under a purpose-scoped, versioned, append-only consent
model (GDPR Art. 6/7). Consent is recorded per subject and purpose, with
point-in-time lookup and full history, so any processing decision can be
reconstructed for audit. Withdrawal takes effect immediately (latest state
wins) and downstream processing halts for the affected purpose.

---

## 3. Retention

The `RetentionRegistry` catalogue defines the authoritative retention period for
each data category. Retention is enforced as a first-class control, not left to
ad-hoc cleanup.

| Data category | Retention | Rationale |
|---------------|-----------|-----------|
| Audit logs (`audit`) | 7 years | Regulatory audit trail (SOC 2 / PCI / RBI) |
| KYC records (`KYC`) | 10 years | RBI KYC record-keeping obligation |
| Loan applications (`application`) | 7 years | Lending record retention |
| Sessions (`session`) | 90 days | Operational; minimised after expiry |
| Access logs (`access_log`) | 1 year | Security monitoring |
| PII exports (`pii_export`) | 30 days | Short-lived DSAR export artifacts |

Retention periods map directly to GDPR Art. 5 (storage limitation) and the RBI
record-keeping requirements referenced in
[COMPLIANCE_FRAMEWORKS.md](COMPLIANCE_FRAMEWORKS.md).

---

## 4. Deletion & right to erasure

Erasure is implemented by **crypto-shredding**: encrypted data is rendered
permanently unrecoverable by destroying its key version via
`core/crypto.py` `KeyRing.shred`, rather than relying on best-effort row
deletion. File artifacts are additionally overwritten (`secure_overwrite_file`).

| Mechanism | Applies to | Effect |
|-----------|-----------|--------|
| Crypto-shredding (`KeyRing.shred`) | Field-encrypted PII | Key destroyed → ciphertext unrecoverable |
| Secure overwrite (`secure_overwrite_file`) | Stored file artifacts | Content overwritten before unlink |
| Retention expiry | All categories | Automatic removal at end of retention window |

Crypto-shredding satisfies GDPR Art. 17 (right to erasure) even where data is
replicated or backed up, because the ciphertext is useless once its key version
is destroyed.

---

## 5. Data-subject access requests (DSAR)

Six request types are supported, each mapped to its GDPR article, under a
**30-day SLA**. Requests are persisted to `sec_privacy_requests`, RBAC-gated, and
identity-verified in the calling endpoint.

| Request type | GDPR article | Description | SLA |
|--------------|--------------|-------------|-----|
| Access | Art. 15 | Provide a copy of the subject's personal data | 30 days |
| Erasure | Art. 17 | Delete the subject's data (crypto-shredding) | 30 days |
| Rectification | Art. 16 | Correct inaccurate personal data | 30 days |
| Portability | Art. 20 | Export data in a portable, machine-readable form | 30 days |
| Restriction | Art. 18 | Restrict processing of the subject's data | 30 days |
| Objection | Art. 21 | Object to a specific processing purpose | 30 days |

Each request moves through a tracked lifecycle (raise → in-progress → complete)
via the PATCH endpoint, producing an auditable record of fulfilment against the
SLA.

---

## 6. PII catalogue & masking

Personal data elements are catalogued with their classification, masking, and
encryption treatment (one of four classifications: public, internal,
confidential, restricted). Masking is applied by `PiiMasker` at display and
before any AI prompt (see [AI_SECURITY.md](AI_SECURITY.md)).

| Element | Classification | Masked | Encrypted |
|---------|----------------|--------|-----------|
| Email | Confidential | Yes | Yes |
| Phone | Confidential | Yes | Yes |
| Password | Restricted | Yes (never stored plaintext) | Hashed (bcrypt) |
| PAN | Restricted | Yes | Yes |
| Aadhaar | Restricted | Yes | Yes |
| Bank account | Restricted | Yes | Yes |
| Card number | Restricted | Yes | Yes |
| Credit score | Confidential | No | Yes |
| Financial statements | Confidential | No | Yes |
| IP address | Internal | Partial | No |

---

## 7. Retention across subsystems

| Subsystem | Retention control | Status |
|-----------|-------------------|--------|
| Audit trail | 7-year retention (`RetentionRegistry`) | Satisfied |
| Document lifecycle | Category-based retention + secure overwrite | Satisfied |
| Backup retention | Bounded backup windows with crypto-shred alignment | Satisfied |
| AI memory retention | Per-tenant memory; **TTL enforcement pending** | Partial |

### Documented finding — AI memory retention (Partial)
Agent / RAG memory is correctly **tenant-isolated** (see
[AI_SECURITY.md](AI_SECURITY.md)), but a **time-to-live (TTL) expiry** on stored
memory is **not yet enforced**. Without a TTL, personal context can persist in
agent memory beyond its purpose window.

**Remediation:** apply a retention TTL to AI memory consistent with the
`RetentionRegistry` categories, so memory entries expire automatically and are
covered by crypto-shredding on erasure. This is the single open item holding the
privacy dimension below 100.

---

## 8. Operating model

- Retention periods are enforced from the `RetentionRegistry`; changes are
  reviewed at the compliance forum.
- DSARs are serviced within the 30-day SLA, RBAC-gated, identity-verified, and
  audit-logged; overdue requests surface in the privacy report.
- Erasure uses crypto-shredding so it holds across replicas and backups.
- The AI-memory TTL finding is tracked in the risk register with an owner and
  target date; closing it raises the privacy dimension toward 100.
