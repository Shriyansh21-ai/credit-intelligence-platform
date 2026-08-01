"""Data-protection primitives.

Bank-grade, dependency-light building blocks for protecting data at rest and in
transit

* :class:`FieldCipher` / :class:`KeyRing` — authenticated field-level encryption
  with key versioning + rotation. Prefers AES-256-GCM via the optional
  ``cryptography`` package; falls back to a pure-stdlib **encrypt-then-MAC**
  construction (HMAC-SHA256 keystream + HMAC-SHA256 tag) so the platform has
  real, authenticated encryption even with no third-party crypto installed.
* Signed URLs — HMAC-signed, expiring URLs for time-limited access to resources.
* :class:`PiiMasker` — deterministic masking/redaction of PII (email, phone
  card, PAN, Aadhaar, …) for logs, exports, and lower environments.
* Retention + secure deletion — a retention-policy registry, crypto-shredding
  and best-effort secure file overwrite.

Everything is stdlib-only by default and safe to import anywhere.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.app.core.settings import get_settings

# Optional strong backend.
try:  # pragma: no cover - depends on optional dependency
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    _HAVE_AESGCM = True
except Exception:  # pragma: no cover
    _HAVE_AESGCM = False


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def derive_key(secret: str, salt: bytes, *, length: int = 32) -> bytes:
    """PBKDF2-HMAC-SHA256 key derivation."""
    return hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, 200_000, dklen=length)


class DecryptionError(Exception):
    """Raised when a ciphertext fails authentication or cannot be parsed."""


# ===========================================================================
# Field-level encryption
# ===========================================================================
class FieldCipher:
    """Authenticated symmetric encryption for a single key version.

    Token format: ``<scheme>.<version>.<nonce>.<ciphertext>.<tag>`` (dot-joined
    urlsafe-base64 parts). ``scheme`` is ``g`` (AES-GCM) or ``s`` (stdlib EtM).
    """

    def __init__(self, key_material: str, version: int = 1) -> None:
        self._key_material = key_material
        self.version = version

    # -- public API -------------------------------------------------------
    def encrypt(self, plaintext: str) -> str:
        nonce = secrets.token_bytes(12 if _HAVE_AESGCM else 16)
        data = plaintext.encode("utf-8")
        if _HAVE_AESGCM:  # pragma: no cover - optional path
            key = derive_key(self._key_material, b"gcm", length=32)
            ct = AESGCM(key).encrypt(nonce, data, None)
            return ".".join(["g", str(self.version), _b64e(nonce), _b64e(ct), ""])
        ct, tag = self._etm_encrypt(data, nonce)
        return ".".join(["s", str(self.version), _b64e(nonce), _b64e(ct), _b64e(tag)])

    def decrypt(self, token: str) -> str:
        try:
            scheme, _ver, nonce_b, ct_b, tag_b = token.split(".")
            nonce, ct = _b64d(nonce_b), _b64d(ct_b)
        except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
            raise DecryptionError("malformed ciphertext token") from exc
        if scheme == "g":  # pragma: no cover - optional path
            if not _HAVE_AESGCM:
                raise DecryptionError("AES-GCM token but cryptography not installed")
            key = derive_key(self._key_material, b"gcm", length=32)
            try:
                return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
            except Exception as exc:
                raise DecryptionError("authentication failed") from exc
        if scheme == "s":
            return self._etm_decrypt(ct, nonce, _b64d(tag_b)).decode("utf-8")
        raise DecryptionError(f"unknown cipher scheme {scheme!r}")

    # -- stdlib encrypt-then-MAC -----------------------------------------
    def _keystream(self, enc_key: bytes, length: int) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < length:
            out.extend(hashlib.sha256(enc_key + counter.to_bytes(8, "big")).digest())
            counter += 1
        return bytes(out[:length])

    def _etm_encrypt(self, data: bytes, nonce: bytes) -> tuple[bytes, bytes]:
        enc_key = derive_key(self._key_material, b"enc" + nonce)
        mac_key = derive_key(self._key_material, b"mac" + nonce)
        ct = bytes(a ^ b for a, b in zip(data, self._keystream(enc_key, len(data)), strict=False))
        tag = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
        return ct, tag

    def _etm_decrypt(self, ct: bytes, nonce: bytes, tag: bytes) -> bytes:
        mac_key = derive_key(self._key_material, b"mac" + nonce)
        expected = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, tag):
            raise DecryptionError("authentication failed")
        enc_key = derive_key(self._key_material, b"enc" + nonce)
        return bytes(a ^ b for a, b in zip(ct, self._keystream(enc_key, len(ct)), strict=False))


class KeyRing:
    """Holds multiple key versions to support seamless key rotation.

    Encryption always uses the active version; decryption dispatches on the
    version embedded in the token, so ciphertext written under a retired key
    still decrypts until it is re-encrypted or crypto-shredded.
    """

    def __init__(self) -> None:
        self._ciphers: dict[int, FieldCipher] = {}
        self._active: int | None = None

    def add_key(self, version: int, key_material: str, *, activate: bool = True) -> None:
        self._ciphers[version] = FieldCipher(key_material, version)
        if activate or self._active is None:
            self._active = version

    def rotate(self, version: int, key_material: str) -> None:
        """Add a new key and make it active; older versions remain for reads."""
        self.add_key(version, key_material, activate=True)

    def shred(self, version: int) -> None:
        """Crypto-shred: drop a key so its ciphertext becomes unrecoverable."""
        self._ciphers.pop(version, None)
        if self._active == version:
            self._active = max(self._ciphers) if self._ciphers else None

    @property
    def active_version(self) -> int | None:
        return self._active

    def encrypt(self, plaintext: str) -> str:
        if self._active is None:
            raise RuntimeError("KeyRing has no active key")
        return self._ciphers[self._active].encrypt(plaintext)

    def decrypt(self, token: str) -> str:
        try:
            version = int(token.split(".")[1])
        except (IndexError, ValueError) as exc:
            raise DecryptionError("cannot determine key version") from exc
        cipher = self._ciphers.get(version)
        if cipher is None:
            raise DecryptionError(f"no key for version {version}")
        return cipher.decrypt(token)


_default_keyring: KeyRing | None = None


def get_keyring() -> KeyRing:
    """Process-wide keyring seeded from settings (active key = current version)."""
    global _default_keyring  # noqa: PLW0603 - process-wide singleton
    if _default_keyring is None:
        settings = get_settings()
        ring = KeyRing()
        ring.add_key(settings.encryption_key_version, settings.effective_encryption_key)
        _default_keyring = ring
    return _default_keyring


def encrypt_field(plaintext: str) -> str:
    return get_keyring().encrypt(plaintext)


def decrypt_field(token: str) -> str:
    return get_keyring().decrypt(token)


# ===========================================================================
# Signed URLs
# ===========================================================================
def _signing_secret(secret: str | None) -> str:
    return secret or get_settings().secret_key


def sign_url(
    path: str,
    *,
    expires_in: int | None = None,
    secret: str | None = None,
    now: Callable[[], datetime] | None = None,
) -> str:
    """Return ``path`` with ``exp`` + ``sig`` query params for time-limited access."""
    settings = get_settings()
    ttl = expires_in if expires_in is not None else settings.signed_url_ttl_seconds
    clock = now or (lambda: datetime.now(UTC))
    exp = int((clock() + timedelta(seconds=ttl)).timestamp())
    sig = _url_signature(path, exp, _signing_secret(secret))
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}exp={exp}&sig={sig}"


def _url_signature(path: str, exp: int, secret: str) -> str:
    msg = f"{path}|{exp}".encode()
    return _b64e(hmac.new(secret.encode(), msg, hashlib.sha256).digest())


def verify_signed_url(
    path: str,
    exp: int,
    sig: str,
    *,
    secret: str | None = None,
    now: Callable[[], datetime] | None = None,
) -> bool:
    """Constant-time verify a signed URL and check it has not expired."""
    clock = now or (lambda: datetime.now(UTC))
    expected = _url_signature(path, exp, _signing_secret(secret))
    if not hmac.compare_digest(expected, sig):
        return False
    return int(clock().timestamp()) <= exp


# ===========================================================================
# PII masking
# ===========================================================================
class PiiMasker:
    """Deterministic PII masking for logs, exports, and non-prod data."""

    _EMAIL = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
    _PHONE = re.compile(r"(?<!\d)(\+?\d[\d\s-]{7,}\d)(?!\d)")
    _CARD = re.compile(r"(?<!\d)(\d[\d ]{11,17}\d)(?!\d)")
    _PAN = re.compile(r"\b([A-Z]{5})(\d{4})([A-Z])\b")  # India PAN
    _AADHAAR = re.compile(r"(?<!\d)(\d{4})\s?(\d{4})\s?(\d{4})(?!\d)")

    @staticmethod
    def mask_email(value: str) -> str:
        return PiiMasker._EMAIL.sub(lambda m: f"{m.group(1)}***{m.group(2)}", value)

    @staticmethod
    def mask_phone(value: str) -> str:
        def _m(m: re.Match) -> str:
            digits = re.sub(r"\D", "", m.group(1))
            return "*" * (len(digits) - 4) + digits[-4:] if len(digits) >= 4 else "*" * len(digits)

        return PiiMasker._PHONE.sub(_m, value)

    @staticmethod
    def mask_card(value: str) -> str:
        def _m(m: re.Match) -> str:
            digits = re.sub(r"\D", "", m.group(1))
            if len(digits) < 12:
                return m.group(1)
            return "*" * (len(digits) - 4) + digits[-4:]

        return PiiMasker._CARD.sub(_m, value)

    @staticmethod
    def mask_pan(value: str) -> str:
        return PiiMasker._PAN.sub(lambda m: f"{m.group(1)[:2]}***{m.group(3)}", value)

    @staticmethod
    def mask_aadhaar(value: str) -> str:
        return PiiMasker._AADHAAR.sub(lambda m: f"XXXX XXXX {m.group(3)}", value)

    @classmethod
    def mask_text(cls, text: str) -> str:
        """Apply all masks to free text (order matters: specific before generic)."""
        if not text:
            return text
        out = cls.mask_pan(text)
        out = cls.mask_aadhaar(out)
        out = cls.mask_card(out)
        out = cls.mask_email(out)
        return cls.mask_phone(out)


def mask_pii(text: str) -> str:
    return PiiMasker.mask_text(text)


def mask_mapping(record: dict[str, object], sensitive_fields: Iterable[str]) -> dict[str, object]:
    """Return a shallow copy with the named fields replaced by ``"***"``."""
    sensitive = set(sensitive_fields)
    return {k: ("***" if k in sensitive and v is not None else v) for k, v in record.items()}


# ===========================================================================
# Retention + secure deletion
# ===========================================================================
@dataclass(frozen=True)
class RetentionPolicy:
    category: str
    retention_days: int
    legal_hold: bool = False
    description: str = ""

    def is_expired(self, created_at: datetime, *, now: datetime | None = None) -> bool:
        if self.legal_hold:
            return False
        ref = now or datetime.now(UTC)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return ref >= created_at + timedelta(days=self.retention_days)


@dataclass
class RetentionRegistry:
    """Central catalogue of retention policies keyed by data category."""

    _policies: dict[str, RetentionPolicy] = field(default_factory=dict)

    def register(self, policy: RetentionPolicy) -> None:
        self._policies[policy.category] = policy

    def get(self, category: str) -> RetentionPolicy | None:
        return self._policies.get(category)

    def expired(self, category: str, created_at: datetime, *, now: datetime | None = None) -> bool:
        policy = self._policies.get(category)
        return bool(policy and policy.is_expired(created_at, now=now))

    def all(self) -> dict[str, RetentionPolicy]:
        return dict(self._policies)


# Default regulatory-informed retention catalogue (tunable per deployment).
default_retention = RetentionRegistry()
for _p in (
    RetentionPolicy("audit_log", 2555, description="7y — financial audit trail"),
    RetentionPolicy("kyc_document", 3650, description="10y — KYC/AML records"),
    RetentionPolicy("application", 2555, description="7y — credit application"),
    RetentionPolicy("session", 90, description="90d — auth sessions"),
    RetentionPolicy("access_log", 365, description="1y — access logs"),
    RetentionPolicy("pii_export", 30, description="30d — generated data exports"),
):
    default_retention.register(_p)


def secure_overwrite_file(path: str, *, passes: int = 3) -> bool:
    """Best-effort secure delete: overwrite the file's bytes then unlink.

    Returns True on success. Note: on copy-on-write / journaling filesystems and
    SSDs, overwrite does not guarantee physical erasure — crypto-shredding (see
    :meth:`KeyRing.shred`) is the durable mechanism for encrypted data.
    """
    p = Path(path)
    if not p.is_file():
        return False
    try:
        length = p.stat().st_size
        with p.open("r+b", buffering=0) as fh:
            for _ in range(max(1, passes)):
                fh.seek(0)
                fh.write(secrets.token_bytes(length))
                fh.flush()
                os.fsync(fh.fileno())  # durability: force bytes to disk
        p.unlink()
        return True
    except OSError:
        return False


__all__ = [
    "DecryptionError",
    "FieldCipher",
    "KeyRing",
    "PiiMasker",
    "RetentionPolicy",
    "RetentionRegistry",
    "decrypt_field",
    "default_retention",
    "derive_key",
    "encrypt_field",
    "get_keyring",
    "mask_mapping",
    "mask_pii",
    "secure_overwrite_file",
    "sign_url",
    "verify_signed_url",
]
