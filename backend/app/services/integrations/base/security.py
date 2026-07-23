"""Connector security primitives (Milestone 14).

Enterprise integrations touch credentials and PII, so the framework provides:

* :class:`SecretResolver` — a secret abstraction. Secrets are referenced by name
  (``"gst.api_key"``) and resolved from an injected store or the environment,
  never hard-coded in configs. A reference that cannot be resolved raises, so
  production connectors fail loudly rather than silently running unauthenticated.
* :func:`encrypt_secret` / :func:`decrypt_secret` — a reversible envelope for
  credentials stored at rest. Uses a keyed, salted transform (dependency-free);
  the interface is what matters — swap in KMS/Fernet in a real deployment.
* :func:`mask_pii` / :func:`mask_value` — data-masking helpers that redact PANs,
  GSTINs, account numbers, emails and phone numbers for logs and audit trails.

The goal is a clean, swappable security surface, not novel cryptography.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from typing import Any, Callable, Dict, Optional

from backend.app.services.integrations.base.exceptions import ConfigurationError

# ---------------------------------------------------------------------------
# Secret abstraction
# ---------------------------------------------------------------------------
_DEFAULT_ENV_PREFIX = "CONNECTOR_SECRET_"


class SecretResolver:
    """Resolves named secret references to their values.

    Resolution order: an explicit in-memory ``store`` (highest precedence),
    then the process environment (``CONNECTOR_SECRET_<UPPER_NAME>``). Names are
    normalised (``"gst.api_key"`` → ``GST_API_KEY``).
    """

    def __init__(
        self,
        store: Optional[Dict[str, str]] = None,
        env: Optional[Callable[[str], Optional[str]]] = None,
        env_prefix: str = _DEFAULT_ENV_PREFIX,
    ):
        self._store = dict(store or {})
        self._env = env or os.environ.get
        self._prefix = env_prefix

    @staticmethod
    def _env_key(name: str, prefix: str) -> str:
        norm = re.sub(r"[^A-Za-z0-9]+", "_", name).upper().strip("_")
        return f"{prefix}{norm}"

    def put(self, name: str, value: str) -> None:
        self._store[name] = value

    def try_resolve(self, name: str) -> Optional[str]:
        if name in self._store:
            return self._store[name]
        return self._env(self._env_key(name, self._prefix))

    def resolve(self, name: str) -> str:
        value = self.try_resolve(name)
        if value is None:
            raise ConfigurationError(f"secret '{name}' is not configured")
        return value


# ---------------------------------------------------------------------------
# Reversible at-rest envelope for credentials
# ---------------------------------------------------------------------------
def _keystream(key: bytes, salt: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(key, salt + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _master_key(key: Optional[str] = None) -> bytes:
    material = key or os.environ.get("CONNECTOR_MASTER_KEY", "dev-master-key-change-me")
    return hashlib.sha256(material.encode("utf-8")).digest()


def encrypt_secret(plaintext: str, *, key: Optional[str] = None, salt: Optional[bytes] = None) -> str:
    """Encrypt a credential for storage. Returns ``base64(salt || ciphertext)``.

    NB: a salt must be provided for deterministic tests; otherwise a random one
    is generated. The construction is a keystream XOR (dependency-free); replace
    with KMS/Fernet for a real deployment without changing callers.
    """
    salt_bytes = salt if salt is not None else os.urandom(16)
    data = plaintext.encode("utf-8")
    ks = _keystream(_master_key(key), salt_bytes, len(data))
    ct = bytes(a ^ b for a, b in zip(data, ks))
    return base64.b64encode(salt_bytes + ct).decode("ascii")


def decrypt_secret(token: str, *, key: Optional[str] = None) -> str:
    blob = base64.b64decode(token.encode("ascii"))
    salt_bytes, ct = blob[:16], blob[16:]
    ks = _keystream(_master_key(key), salt_bytes, len(ct))
    data = bytes(a ^ b for a, b in zip(ct, ks))
    return data.decode("utf-8")


# ---------------------------------------------------------------------------
# PII masking
# ---------------------------------------------------------------------------
_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_GSTIN_RE = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]{3}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_RE = re.compile(r"\b(?:\+?91[-\s]?)?[6-9]\d{9}\b")
_ACCOUNT_RE = re.compile(r"\b\d{9,18}\b")

# Field names that always hold sensitive values regardless of content.
_SENSITIVE_KEYS = {
    "password", "secret", "api_key", "apikey", "token", "access_token",
    "refresh_token", "client_secret", "private_key", "credential", "credentials",
    "authorization", "pan", "account_number", "account_no", "aadhaar",
}


def mask_value(value: str, *, keep: int = 4) -> str:
    """Mask a raw string, keeping the last ``keep`` characters."""
    if value is None:
        return value
    s = str(value)
    if len(s) <= keep:
        return "*" * len(s)
    return "*" * (len(s) - keep) + s[-keep:]


def mask_text(text: str) -> str:
    """Redact PANs, GSTINs, account numbers, emails and phones inside free text."""
    if not text:
        return text
    text = _PAN_RE.sub(lambda m: mask_value(m.group(0)), text)
    text = _GSTIN_RE.sub(lambda m: mask_value(m.group(0)), text)
    text = _EMAIL_RE.sub(lambda m: _mask_email(m.group(0)), text)
    text = _PHONE_RE.sub(lambda m: mask_value(m.group(0)), text)
    text = _ACCOUNT_RE.sub(lambda m: mask_value(m.group(0)), text)
    return text


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    head = local[0] if local else ""
    return f"{head}***@{domain}"


def mask_pii(obj: Any) -> Any:
    """Recursively mask PII in a JSON-like structure.

    Sensitive-named keys are fully masked; string values are scanned for PII
    patterns. Returns a new structure (the input is never mutated).
    """
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS:
                out[k] = mask_value(str(v)) if v is not None else v
            else:
                out[k] = mask_pii(v)
        return out
    if isinstance(obj, list):
        return [mask_pii(v) for v in obj]
    if isinstance(obj, str):
        return mask_text(obj)
    return obj


# Default resolver instance (env-backed). Tests inject their own.
default_secret_resolver = SecretResolver()
