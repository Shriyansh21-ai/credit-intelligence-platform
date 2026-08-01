# Secret Management

_Stage 4, Milestone 5 — Secret inventory, providers, and rotation for the AI Credit Intelligence Platform._

This document is the authoritative secret-management audit. It is produced by the
additive **Security & Compliance** module
(`backend/app/services/security_compliance/secrets.py`) and served live under
`/api/sec/secrets`. Like the rest of the module it is **offline-first and
deterministic**.

Secrets are the highest-leverage assets on the platform: a single leaked signing
key or database credential can undermine every other control. The platform's
posture is therefore built on two rules that this audit verifies:

> [!IMPORTANT]
> **Never store secrets in plaintext, and never store them by value in the
> repository — only by reference.** Secrets are resolved at runtime from a
> configured provider (environment, file, AWS Secrets Manager, or HashiCorp
> Vault). The codebase and config carry the *name* of a secret, never its value.

> [!WARNING]
> **Secrets posture (development profile): 20 / 100.** This is an *intentional,
> honest* low score. The development profile ships default/placeholder secrets
> and the scanner correctly flags them as **CRITICAL** via the `INSECURE_SECRETS`
> check. In a production deployment with real secrets set, this dimension rises to
> **~100**. The low dev score is the single largest drag on overall posture and is
> **fully remediable by configuration alone** — no code change is required.

---

## 1. Managed-secret inventory

The following secrets are tracked. Each has a purpose, a recommended rotation
interval, a criticality, and a current (development-profile) status. In dev, the
signing/encryption secrets carry placeholder values and are flagged CRITICAL; in
production they must be real, high-entropy values sourced from a provider.

| Secret | Purpose | Rotation interval | Criticality | Dev status |
|--------|---------|-------------------|-------------|-----------|
| **SECRET_KEY** | Application-wide signing / CSRF / misc. token signing | 90 days | Critical | Default placeholder — **flagged CRITICAL** |
| **JWT_SECRET_KEY** | HS256 JWT signing (via `JwtKeyRing`) | 90 days (with `kid` overlap) | Critical | Default placeholder — **flagged CRITICAL** |
| **ENCRYPTION_KEY** | Root/field encryption key material (`KeyRing`) | 180 days | Critical | Default placeholder — **flagged CRITICAL** |
| **CONNECTOR_MASTER_KEY** | Encrypts stored per-connector credentials | 180 days | Critical | Default placeholder — **flagged CRITICAL** |
| **DATABASE_URL** | Primary datastore connection (credentials embedded) | 90 days | Critical | Local dev value |
| **REDIS_URL** | Cache / queue connection | 90 days | High | Local dev value |
| **S3_SECRET_ACCESS_KEY** | Object-storage access credential | 90 days | High | Placeholder / unset |
| **SMTP_PASSWORD** | Outbound email credential | 90 days | Medium | Placeholder / unset |
| **ANTHROPIC_API_KEY** | LLM / AI-platform provider key | 90 days | High | Placeholder / unset |
| **STRIPE_API_KEY** | Payments / billing provider key | 90 days | High | Placeholder / unset |

The signing and encryption secrets (SECRET_KEY, JWT_SECRET_KEY, ENCRYPTION_KEY,
CONNECTOR_MASTER_KEY) are the crown jewels: they underpin authentication,
field-level encryption, and connector-credential protection respectively.

---

## 2. Secret providers

Secrets are resolved at runtime through a pluggable provider abstraction. The
provider is selected per environment; higher environments use managed secret
stores.

| Provider | Mechanism | Typical use | Notes |
|----------|-----------|-------------|-------|
| **env** | Process environment variables | Development, containers with injected env | Simplest; values must still be real in prod |
| **file** | Mounted secret files (e.g. Docker/K8s secrets) | Staging, on-prem | Files mounted read-only, outside the repo |
| **aws** | AWS Secrets Manager | Production (cloud) | Central rotation, IAM-scoped access, versioned |
| **vault** | HashiCorp Vault | Production (multi-cloud / on-prem) | Dynamic secrets, leases, audit of secret access |

In every case the application holds a **reference** (the secret's name/path) and
fetches the value at boot or on demand — the value is never committed. This
satisfies OWASP A05 (Security Misconfiguration) and API8, and aligns with the
Secure SDLC controls (gitleaks secret scanning in CI, `.gitleaks.toml`) described
in [SECURITY_GUIDE.md](SECURITY_GUIDE.md).

---

## 3. Key versioning and rotation

Two key rings provide versioned, rotatable key material so that rotation never
requires downtime or a flag-day re-encryption.

| Key ring | Domain | Versioning | Rotation behaviour |
|----------|--------|-----------|--------------------|
| **`KeyRing`** (`core/crypto.py`) | Field-level encryption keys for `FieldCipher` (AES-256-GCM) | Each key has a version id; ciphertext records the version used | New writes use the current key; old ciphertext still decrypts under its recorded version. Crypto-shred by destroying a version's key |
| **`JwtKeyRing`** (`core/authn.py`) | JWT signing keys | Each key has a `kid` (key id) embedded in the token header | New tokens sign with the current `kid`; in-flight tokens signed by a still-trusted `kid` remain valid until expiry, then the old key is retired |

### 3.1 Rotation principles

- **Overlap, don't break.** Both rings keep prior versions trusted for
  verification/decryption while new material is used for signing/encryption, so
  rotation is zero-downtime.
- **Version-tagged data.** Ciphertext carries its key version and tokens carry
  their `kid`, so the correct key is always selectable.
- **Crypto-shredding.** Destroying a `KeyRing` version renders all data encrypted
  under it permanently unrecoverable — the basis for data-destruction guarantees
  (see [DATA_PROTECTION.md](DATA_PROTECTION.md)).

---

## 4. The `INSECURE_SECRETS` validation

The profile-aware settings layer (`core/settings.py`) exposes `validate_runtime()`,
which checks configuration against the `INSECURE_SECRETS` set and other misconfig
rules. When a managed secret still holds a known default/placeholder value, it is
flagged **CRITICAL**.

| Behaviour | Development profile | Production profile |
|-----------|--------------------|--------------------|
| Default secrets present | Detected and flagged CRITICAL; platform still boots for local work | Boot is refused / hard-blocked — production must not run on default secrets |
| Wildcard CORS, sqlite-in-prod, other misconfig | Flagged | Blocked |
| Effect on `secrets` dimension | **20 / 100** | **~100 / 100** once real secrets are set |

This is why the development-profile overall posture is dragged down: the scanner
is being *honest*. The remediation is purely operational — provision real secrets
through a provider (§2) — and the dimension recovers to near-full immediately.

---

## 5. Findings

| # | Finding | Severity | Detail | Remediation |
|---|---------|----------|--------|-------------|
| **SEC-01** | Default signing/encryption secrets in the development profile | **Critical (dev only)** | `SECRET_KEY`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, `CONNECTOR_MASTER_KEY` hold placeholders; flagged by `INSECURE_SECRETS` | Set real high-entropy secrets via a provider in staging/production. `validate_runtime()` blocks insecure production boot |
| **SEC-02** | Provider-side rotation not yet automated end-to-end | **Low** | Rotation intervals are defined; automated provider-driven rotation (AWS/Vault) is operational rather than enforced in code | Wire scheduled rotation in the chosen provider; both key rings already support zero-downtime rotation |

---

## 6. How to run it live

The audit is computed by the running platform and exposed as read-only JSON, gated
by the **`sec.secrets.view`** RBAC permission (Security & Compliance category;
granted to `compliance_officer`, `risk_manager`, oversight roles read-only, and
`administrator`). Note that the endpoint reports secret **metadata and status
only** — never secret values.

| Endpoint | Returns |
|----------|---------|
| `GET /api/sec/secrets` | The managed-secret inventory (purpose, rotation interval, criticality, status), provider configuration, and the aggregate `secrets` score |

```bash
curl -H "Authorization: Bearer $TOKEN" \
     https://<host>/api/sec/secrets
```

The current development-profile `secrets` dimension scores **20 / 100** by design;
a production deployment with real secrets scores **~100**.

---

## 7. Related documents

- [DATA_PROTECTION.md](DATA_PROTECTION.md) — `KeyRing`, `FieldCipher`, and the key hierarchy that these secrets anchor.
- [AUTHENTICATION_HARDENING.md](AUTHENTICATION_HARDENING.md) — the JWT default-secret CRITICAL finding.
- [OWASP_SECURITY_REVIEW.md](OWASP_SECURITY_REVIEW.md) — A05 / API8 (Security Misconfiguration).
- [SECURITY_GUIDE.md](SECURITY_GUIDE.md) — Secure SDLC and secret scanning in CI.

← Back to [Security Documentation](index.md)
