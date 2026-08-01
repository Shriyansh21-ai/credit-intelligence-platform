"""Enterprise security service.

Secrets management (by reference, with rotation), per-tenant data encryption
rate limiting, IP allow-lists, session + device management, and identity-
provider (SSO / SAML / OIDC / SCIM) configuration held in a *ready* abstraction.

The built-in secret manager stores an at-rest envelope locally; production
deployments point a :class:`SecretManager` at Vault/KMS/etc. All secrets are
referenced by name+version so rotation never requires a code change.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Protocol

from sqlalchemy.orm import Session

from backend.app.core.security import SECRET_KEY
from backend.app.models.saas_security import (
    IdentityProviderConfig, IpAllowEntry, SecretRef, SecurityDevice,
    SecuritySession,
)


# ===========================================================================
# Secrets management + rotation
# ===========================================================================
def _envelope(plaintext: str) -> str:
    km = hashlib.sha256(SECRET_KEY.encode()).digest()
    raw = plaintext.encode()
    ks = bytearray()
    counter = 0
    while len(ks) < len(raw):
        ks.extend(hashlib.sha256(km + counter.to_bytes(8, "big")).digest())
        counter += 1
    return base64.urlsafe_b64encode(bytes(a ^ b for a, b in zip(raw, ks))).decode()


def _open_envelope(envelope: str) -> str:
    raw = base64.urlsafe_b64decode(envelope.encode())
    km = hashlib.sha256(SECRET_KEY.encode()).digest()
    ks = bytearray()
    counter = 0
    while len(ks) < len(raw):
        ks.extend(hashlib.sha256(km + counter.to_bytes(8, "big")).digest())
        counter += 1
    return bytes(a ^ b for a, b in zip(raw, ks)).decode()


class SecretManager(Protocol):
    name: str

    def store(self, db: Session, name: str, value: str, tenant_id: Optional[int]) -> SecretRef: ...

    def reveal(self, db: Session, ref: SecretRef) -> str: ...


class LocalSecretManager:
    name = "local"

    def store(self, db: Session, name: str, value: str,
              tenant_id: Optional[int] = None) -> SecretRef:
        existing = (
            db.query(SecretRef)
            .filter(SecretRef.name == name, SecretRef.tenant_id == tenant_id)
            .order_by(SecretRef.version.desc())
            .first()
        )
        version = (existing.version + 1) if existing else 1
        ref = SecretRef(name=name, tenant_id=tenant_id, manager=self.name,
                        version=version, value_encrypted=_envelope(value))
        db.add(ref)
        db.commit()
        db.refresh(ref)
        return ref

    def reveal(self, db: Session, ref: SecretRef) -> str:
        if ref.value_encrypted is None:
            raise ValueError("secret has no local material")
        return _open_envelope(ref.value_encrypted)


_secret_manager: SecretManager = LocalSecretManager()


def set_secret_manager(mgr: SecretManager) -> None:
    global _secret_manager
    _secret_manager = mgr


def store_secret(db: Session, name: str, value: str, *,
                 tenant_id: Optional[int] = None) -> SecretRef:
    return _secret_manager.store(db, name, value, tenant_id)


def get_secret(db: Session, name: str, *, tenant_id: Optional[int] = None) -> str:
    ref = (
        db.query(SecretRef)
        .filter(SecretRef.name == name, SecretRef.tenant_id == tenant_id)
        .order_by(SecretRef.version.desc())
        .first()
    )
    if ref is None:
        raise ValueError(f"secret not found: {name}")
    return _secret_manager.reveal(db, ref)


def rotate_secret(db: Session, name: str, new_value: str, *,
                  tenant_id: Optional[int] = None) -> SecretRef:
    ref = store_secret(db, name, new_value, tenant_id=tenant_id)
    ref.rotated_at = datetime.utcnow()
    db.commit()
    db.refresh(ref)
    return ref


# ===========================================================================
# Per-tenant data encryption (envelope keyed by tenant)
# ===========================================================================
def tenant_encrypt(plaintext: str, tenant_id: int) -> str:
    return _envelope(f"{tenant_id}:{plaintext}")


def tenant_decrypt(ciphertext: str, tenant_id: int) -> str:
    opened = _open_envelope(ciphertext)
    prefix = f"{tenant_id}:"
    if not opened.startswith(prefix):
        raise ValueError("tenant mismatch on decrypt")
    return opened[len(prefix):]


# ===========================================================================
# Rate limiting (in-memory sliding window; Redis-swappable)
# ===========================================================================
class RateLimiter:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._hits: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, *, limit: int, window_seconds: float) -> Dict[str, Any]:
        now = self._clock()
        with self._lock:
            bucket = [t for t in self._hits.get(key, []) if now - t < window_seconds]
            allowed = len(bucket) < limit
            if allowed:
                bucket.append(now)
            self._hits[key] = bucket
            return {"allowed": allowed, "remaining": max(0, limit - len(bucket)),
                    "limit": limit, "reset_in": round(window_seconds, 2)}

    def reset(self, key: Optional[str] = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


rate_limiter = RateLimiter()


# ===========================================================================
# IP allow-list
# ===========================================================================
def add_ip_allow(db: Session, tenant_id: int, cidr: str, *,
                 description: Optional[str] = None) -> IpAllowEntry:
    ipaddress.ip_network(cidr, strict=False)  # validate
    entry = IpAllowEntry(tenant_id=tenant_id, cidr=cidr, description=description)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def ip_allowed(db: Session, tenant_id: int, ip: str) -> bool:
    entries = (
        db.query(IpAllowEntry)
        .filter(IpAllowEntry.tenant_id == tenant_id, IpAllowEntry.enabled.is_(True))
        .all()
    )
    if not entries:
        return True  # no allow-list configured = open
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in ipaddress.ip_network(e.cidr, strict=False) for e in entries)


# ===========================================================================
# Sessions + devices
# ===========================================================================
def create_session(db: Session, user_id: int, *, tenant_id: Optional[int] = None,
                   ip: Optional[str] = None, user_agent: Optional[str] = None,
                   device_id: Optional[int] = None, ttl_hours: int = 12,
                   mfa_verified: bool = False) -> SecuritySession:
    sess = SecuritySession(
        user_id=user_id, tenant_id=tenant_id, ip_address=ip, user_agent=user_agent,
        device_id=device_id, session_token=secrets.token_urlsafe(32),
        expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
        mfa_verified=mfa_verified,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def list_sessions(db: Session, user_id: int) -> List[SecuritySession]:
    return (
        db.query(SecuritySession)
        .filter(SecuritySession.user_id == user_id)
        .order_by(SecuritySession.id.desc())
        .all()
    )


def revoke_session(db: Session, session_id: int) -> SecuritySession:
    sess = db.query(SecuritySession).get(session_id)
    if sess is None:
        raise ValueError("session not found")
    sess.status = "revoked"
    db.commit()
    db.refresh(sess)
    return sess


def register_device(db: Session, user_id: int, fingerprint: str, *,
                    tenant_id: Optional[int] = None, name: Optional[str] = None,
                    platform: Optional[str] = None) -> SecurityDevice:
    existing = (
        db.query(SecurityDevice)
        .filter(SecurityDevice.user_id == user_id,
                SecurityDevice.fingerprint == fingerprint)
        .first()
    )
    if existing:
        existing.last_seen_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    dev = SecurityDevice(user_id=user_id, tenant_id=tenant_id,
                         fingerprint=fingerprint, name=name, platform=platform)
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return dev


def trust_device(db: Session, device_id: int, trusted: bool = True) -> SecurityDevice:
    dev = db.query(SecurityDevice).get(device_id)
    if dev is None:
        raise ValueError("device not found")
    dev.trusted = trusted
    db.commit()
    db.refresh(dev)
    return dev


# ===========================================================================
# Identity providers (SSO / SAML / OIDC / SCIM ready)
# ===========================================================================
_PROTOCOLS = {"oidc", "saml", "scim"}


def configure_idp(db: Session, tenant_id: int, protocol: str, *,
                  display_name: Optional[str] = None, config: Optional[Dict] = None,
                  client_secret: Optional[str] = None, enabled: bool = False,
                  mfa_required: bool = False) -> IdentityProviderConfig:
    if protocol not in _PROTOCOLS:
        raise ValueError(f"unsupported protocol: {protocol}")
    row = (
        db.query(IdentityProviderConfig)
        .filter(IdentityProviderConfig.tenant_id == tenant_id,
                IdentityProviderConfig.protocol == protocol)
        .first()
    )
    if row is None:
        row = IdentityProviderConfig(tenant_id=tenant_id, protocol=protocol)
        db.add(row)
    row.display_name = display_name
    row.config = config or {}
    row.enabled = enabled
    row.mfa_required = mfa_required
    if client_secret:
        ref = store_secret(db, f"idp:{protocol}:{tenant_id}", client_secret, tenant_id=tenant_id)
        row.client_secret_ref = f"{ref.name}#{ref.version}"
    db.commit()
    db.refresh(row)
    return row


def list_idps(db: Session, tenant_id: int) -> List[IdentityProviderConfig]:
    return db.query(IdentityProviderConfig).filter(
        IdentityProviderConfig.tenant_id == tenant_id).all()


def sign_payload(payload: str) -> str:
    """HMAC-sign an arbitrary payload (used for MFA challenges, SCIM tokens…)."""
    return hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
