# Data Protection

_Stage 4, Milestone 6 — Data classification, PII protection, and encryption for the AI Credit Intelligence Platform._

This document is the authoritative data-protection audit. It is produced by the
additive **Security & Compliance** module
(`backend/app/services/security_compliance/data_protection.py`) and served live
under `/api/sec/data` and `/api/sec/data/pii-catalog`. Like the rest of the module
it is **offline-first and deterministic**.

The platform processes highly sensitive financial and identity data — credit
scores, bank accounts, PAN and Aadhaar numbers, financial statements. Data
protection is therefore built in layers: classify the data, mask it on egress,
encrypt it at the field level under versioned keys, and destroy it on schedule
(or on demand via crypto-shredding). The concrete controls are the pre-existing
`core/crypto.py` primitives — `FieldCipher`, `KeyRing`, `PiiMasker`,
`RetentionRegistry`, and `secure_overwrite_file`.

> [!IMPORTANT]
> **Data-protection posture (development profile): 50 / 100.**
> The primitives are strong (AES-256-GCM field encryption, versioned keys,
> crypto-shred, comprehensive masking), but coverage is not yet exhaustive across
> every restricted column and egress path — the dimension reflects
> *breadth of application*, not weakness of mechanism. Extending `FieldCipher` and
> `PiiMasker` to every restricted field and export/log path is the remediation.

---

## 1. Data classification

All data is classified into four tiers. Higher tiers attract stricter handling,
masking, encryption, and access controls.

| Classification | Definition | Example data | Controls |
|----------------|-----------|--------------|----------|
| **Public** | Safe for unrestricted disclosure | Marketing copy, public docs, product metadata | No special handling; integrity only |
| **Internal** | Non-sensitive but not for public release | Internal configuration, non-PII operational data | RBAC-gated; TLS in transit |
| **Confidential** | Sensitive business or limited personal data | Application metadata, IP addresses, credit scores | RBAC least privilege, encryption in transit, masked in general views, audited access |
| **Restricted** | Highly sensitive PII / regulated data | Passwords, PAN, Aadhaar, bank accounts, card numbers, financial statements | Field-level encryption (`FieldCipher`), masking on all egress, tightest RBAC, full audit, retention + crypto-shred |

---

## 2. PII catalog

The catalog tracks each PII field with its classification and whether masking and
field encryption apply. Served from `GET /api/sec/data/pii-catalog`.

| Field | Classification | Masking | Encryption |
|-------|----------------|---------|------------|
| **email** | Confidential | `PiiMasker` email (local-part masked) | In transit; at rest where restricted |
| **phone** | Confidential | `PiiMasker` phone (last digits shown) | In transit |
| **password** | Restricted | Never displayed | bcrypt hash (never reversibly stored) |
| **pan** | Restricted | `PiiMasker` PAN | `FieldCipher` AES-256-GCM |
| **aadhaar** | Restricted | `PiiMasker` Aadhaar | `FieldCipher` AES-256-GCM |
| **bank_account** | Restricted | Masked (last 4) | `FieldCipher` AES-256-GCM |
| **card_number** | Restricted | `PiiMasker` card (PAN-style, last 4) | `FieldCipher` AES-256-GCM + tokenization |
| **ip_address** | Confidential | Partial masking | In transit; retained per access-log policy |
| **financial_statements** | Restricted | Masked in summaries | `FieldCipher` AES-256-GCM |
| **credit_score** | Confidential | Masked in general views | Encrypted where restricted |

---

## 3. Masking, tokenization, and field encryption

### 3.1 Masking — `PiiMasker`

`PiiMasker` (`core/crypto.py`) applies format-aware masking so values remain
recognisable for support/ops without exposing the underlying secret:

| Type | Masking behaviour |
|------|-------------------|
| **email** | Masks the local part, preserves domain (e.g. `j••••@bank.com`) |
| **phone** | Reveals only the last few digits |
| **card** | Reveals only the last 4 digits (PAN-style) |
| **PAN** | Masks all but a recognisable remainder |
| **Aadhaar** | Masks all but the last 4 digits |

Masking is applied on egress — API responses, logs, and exports — so restricted
data is never emitted in the clear to a channel that does not require it.

### 3.2 Tokenization

High-sensitivity identifiers (notably card numbers) can be **tokenized** —
replaced with a non-sensitive surrogate — so downstream systems and analytics
operate on tokens rather than raw values, shrinking the sensitive-data footprint.

### 3.3 Field encryption — `FieldCipher` / `KeyRing`

- **Algorithm:** `FieldCipher` uses **AES-256-GCM** (authenticated encryption)
  with a **stdlib Encrypt-then-MAC (EtM) fallback** when the primary AEAD backend
  is unavailable, so encryption is always available and always authenticated.
- **Key management:** keys come from `KeyRing` with **versioning + rotation**;
  each ciphertext records the key version used, enabling zero-downtime rotation
  and per-version crypto-shredding.
- **Coverage:** applied to restricted fields (PAN, Aadhaar, bank account, card
  number, financial statements). Extending coverage to every restricted column is
  the open data-protection finding.

---

## 4. Encryption at rest across stores

| Layer | Mechanism |
|-------|-----------|
| **Database** | Field-level `FieldCipher` on restricted columns, over transparent storage encryption at the engine/volume layer |
| **File** | Encrypted storage; `secure_overwrite_file` for secure deletion of on-disk artifacts |
| **Object storage** | Server-side encryption + per-tenant namespacing + signed expiring URLs |
| **Backups** | Encrypted at rest; crypto-shredding of a key version renders backups of that data unrecoverable without separate backup destruction |

---

## 5. Key hierarchy

Encryption keys are organised in a hierarchy so that a compromise or rotation at
one level is contained and so that data can be destroyed by destroying keys.

```
Root / KMS master key            (provider-held: AWS KMS / Vault; see SECRET_MANAGEMENT.md)
        │  wraps
        ▼
Data Encryption Keys (DEKs)      (KeyRing, versioned + rotatable)
        │  derive / protect
        ▼
Per-field ciphers                (FieldCipher AES-256-GCM per restricted field)
        │  parallel to
        ▼
Signing keys                     (JwtKeyRing kid; SECRET_KEY — see AUTHENTICATION_HARDENING.md)
```

- The **root/KMS key** is never exposed to the application; it wraps the DEKs.
- **DEKs** (via `KeyRing`) are versioned; rotation issues a new version while old
  versions remain available for decryption.
- **Per-field ciphers** encrypt individual restricted values under the current DEK
  version.
- **Signing keys** are a parallel branch protecting token and application
  integrity, managed by `JwtKeyRing` and `SECRET_KEY`.

---

## 6. Retention and crypto-shredding

Retention is governed by `RetentionRegistry` (`core/crypto.py`), which defines how
long each data class is kept before secure destruction.

| Data class | Retention | Basis |
|------------|-----------|-------|
| **audit** | 7 years | Regulatory audit-trail requirement |
| **KYC** | 10 years | KYC record-keeping obligation |
| **application** | 7 years | Credit-application record-keeping |
| **session** | 90 days | Operational / security window |
| **access_log** | 1 year | Security monitoring window |
| **pii_export** | 30 days | Minimise exported-PII footprint (aligns with DSAR SLA) |

**Crypto-shredding.** For restricted data, destruction is achieved by destroying
the `KeyRing` key version under which the data was encrypted: the ciphertext
becomes permanently unrecoverable even if copies persist in backups or replicas.
This provides a strong, verifiable data-destruction guarantee that underpins GDPR
erasure (Art. 17) DSAR handling and end-of-retention purging.

---

## 7. Findings

| # | Finding | Severity | Remediation |
|---|---------|----------|-------------|
| **DATA-01** | Field-encryption coverage not exhaustive across all restricted columns | **Medium** | Verify `FieldCipher` on every restricted field; the mechanism is proven — extend application |
| **DATA-02** | Masking not yet applied on every export/log egress path | **Medium** | Extend `PiiMasker` to all export and log sinks |

Both findings are breadth-of-coverage items, not defects in the cryptographic or
masking mechanisms; they are the reason the `data_protection` dimension is 50.

---

## 8. How to run it live

The audit is computed by the running platform and exposed as read-only JSON, gated
by the **`sec.data.view`** RBAC permission (Security & Compliance category;
granted to `compliance_officer`, `risk_manager`, oversight roles read-only, and
`administrator`).

| Endpoint | Returns |
|----------|---------|
| `GET /api/sec/data` | Data classifications, encryption posture, key hierarchy, retention, and the aggregate `data_protection` score (50) |
| `GET /api/sec/data/pii-catalog` | The 10 PII fields with classification, masking, and encryption columns |

```bash
curl -H "Authorization: Bearer $TOKEN" \
     https://<host>/api/sec/data/pii-catalog
```

The current development-profile `data_protection` dimension scores **50 / 100**.

---

## 9. Related documents

- [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md) — `KeyRing`, providers, and the root/KMS keys that anchor the hierarchy.
- [MULTI_TENANT_SECURITY.md](MULTI_TENANT_SECURITY.md) — tenant scoping of the data these controls protect.
- [OWASP_SECURITY_REVIEW.md](OWASP_SECURITY_REVIEW.md) — A02 (Cryptographic Failures) and ASVS V6 / V8.
- [THREAT_MODEL.md](THREAT_MODEL.md) — STRIDE-I1 (information disclosure).

← Back to [Security Documentation](index.md)
