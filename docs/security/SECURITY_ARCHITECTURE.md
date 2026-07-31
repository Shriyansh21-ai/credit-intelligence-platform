# Security Architecture & Hardening

_Phase 11, M8 — bank-grade security controls for the AI Credit Intelligence Platform._

This document describes the platform's security controls. M8 is **additive**: it
extends the Phase-8 security base (per-tenant secret store, field encryption,
rate limiter, sessions, devices, IP allow-lists — `services/saas/security.py`)
with the controls below. No existing API changed.

---

## 1. Modules

| Concern | Module | Key APIs |
|---------|--------|----------|
| Response headers | `core/security_middleware.py` | `SecurityHeadersMiddleware` |
| Field encryption + key rotation | `core/crypto.py` | `FieldCipher`, `KeyRing`, `encrypt_field`, `decrypt_field` |
| Signed URLs | `core/crypto.py` | `sign_url`, `verify_signed_url` |
| PII masking | `core/crypto.py` | `PiiMasker`, `mask_pii`, `mask_mapping` |
| Retention + secure deletion | `core/crypto.py` | `RetentionPolicy`, `RetentionRegistry`, `default_retention`, `secure_overwrite_file` |
| JWT key rotation | `core/authn.py` | `JwtKeyRing`, `get_jwt_keyring` |
| Refresh-token rotation | `core/authn.py` | `RefreshTokenService` (+ reuse detection) |
| Password policy | `core/authn.py` | `PasswordPolicy` |
| Account lockout | `core/authn.py` | `AccountLockout` |
| MFA (TOTP) | `core/authn.py` | `Totp` |
| Risk-based auth | `core/authn.py` | `RiskEngine`, `RiskSignals` |

## 2. Transport & response headers (OWASP)

`SecurityHeadersMiddleware` stamps, on every response (togglable via
`SECURITY_HEADERS_ENABLED`):

- **HSTS** `Strict-Transport-Security` (max-age from `HSTS_MAX_AGE`, `includeSubDomains`, optional `preload`)
- **CSP** `Content-Security-Policy` (default `default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'`)
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`

Headers are only set if absent, so a route can override per-response.

## 3. Encryption

**Field-level encryption** (`FieldCipher`) is authenticated:
- Preferred: **AES-256-GCM** via the optional `cryptography` package.
- Fallback (no third-party crypto): **encrypt-then-MAC** — an HMAC-SHA256
  keystream for confidentiality plus an HMAC-SHA256 tag verified in constant
  time. PBKDF2-HMAC-SHA256 (200k iterations) derives per-nonce keys.

Tokens are self-describing (`<scheme>.<version>.<nonce>.<ct>.<tag>`), so
`KeyRing` supports **key rotation**: new writes use the active version; old
ciphertext still decrypts under its retired key until re-encrypted or
**crypto-shredded** (`KeyRing.shred` drops the key, rendering data unrecoverable
— the durable deletion mechanism on SSD/CoW filesystems).

**Secrets** are provisioned as encrypted containers by the Terraform `secrets`
module (KMS-backed) and read at runtime; no secret values are committed.

## 4. Authentication hardening

- **JWT rotation** (`JwtKeyRing`): tokens carry a `kid`; signing uses the active
  key, verification accepts any held key → zero-downtime signing-key rotation.
- **Refresh-token rotation** (`RefreshTokenService`): opaque HMAC-signed tokens
  bound to a *family*. Each use rotates the token and consumes the old one;
  **replaying a consumed/revoked token revokes the entire family** (detects
  stolen refresh tokens).
- **Password policy** (`PasswordPolicy`): min length (`PASSWORD_MIN_LENGTH`),
  ≥3 character classes, common-password and username-substring rejection, run
  detection, and a 0-100 strength score.
- **Account lockout** (`AccountLockout`): locks after `ACCOUNT_LOCKOUT_THRESHOLD`
  failures within `ACCOUNT_LOCKOUT_WINDOW_SECONDS`, for
  `ACCOUNT_LOCKOUT_DURATION_SECONDS`.
- **MFA** (`Totp`): RFC 6238 TOTP (stdlib) with provisioning URIs for
  authenticator apps and a configurable verification drift window.
- **Risk-based auth** (`RiskEngine`): scores device/IP/geo/velocity/failure
  signals → `low` (allow), `medium` (step-up MFA), `high` (step-up / deny on
  impossible travel).

## 5. Data protection & privacy

- **PII masking** (`PiiMasker`): email, phone, card (PAN), India PAN, Aadhaar,
  and a free-text redactor for logs/exports/non-prod.
- **Retention** (`default_retention`): regulatory-informed catalogue (audit 7y,
  KYC 10y, sessions 90d, exports 30d, …) with legal-hold support.
- **Secure deletion**: `secure_overwrite_file` (multi-pass overwrite + fsync +
  unlink) for local artifacts; crypto-shredding for encrypted data.

## 6. Configuration

All controls are configurable (`core/settings.py`): `SECURITY_HEADERS_ENABLED`,
`HSTS_MAX_AGE`, `CONTENT_SECURITY_POLICY`, `PERMISSIONS_POLICY`,
`ENCRYPTION_KEY(_VERSION)`, `SECRETS_PROVIDER`, `SIGNED_URL_TTL_SECONDS`,
`PASSWORD_MIN_LENGTH`, `PASSWORD_REQUIRE_COMPLEXITY`,
`ACCOUNT_LOCKOUT_THRESHOLD/WINDOW/DURATION`, `MFA_ISSUER`,
`REFRESH_TOKEN_EXPIRE_DAYS`.

## 7. Pipeline controls (M5)

SAST (bandit, semgrep, CodeQL), dependency audit (pip-audit, bun audit), secret
scanning (gitleaks — hard gate), and IaC scanning (trivy) run in CI. See
[CICD.md](../deployment/CICD.md).

## 8. Threat-model coverage (summary)

| Threat | Control |
|--------|---------|
| Credential stuffing / brute force | Account lockout + rate limiter + risk engine |
| Stolen refresh token | Rotation + reuse detection (family revocation) |
| Signing-key compromise | JWT key rotation (`kid`) |
| Data at rest exposure | AES-GCM field encryption + KMS + crypto-shred |
| Clickjacking / XSS / MIME sniffing | CSP + XFO + nosniff headers |
| PII leakage in logs/exports | PII masking + retention + secure deletion |
| MITM | HSTS + TLS-only (ALB/CloudFront, S3 TLS-only policy) |
| Secret leakage in VCS | gitleaks hard gate + no secrets in IaC |
