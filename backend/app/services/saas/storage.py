"""Cloud storage platform (Phase 8, Milestone 7).

A tenant-scoped object store with a pluggable backend abstraction, object
versioning, at-rest encryption, lifecycle policies, signed URLs and large-file
(multipart) uploads.

Backends implement :class:`StorageBackend`; the built-ins are :class:`LocalBackend`
(filesystem, the default) and :class:`MemoryBackend` (tests). ``S3Backend`` /
``AzureBlobBackend`` / ``GCSBackend`` / ``MinioBackend`` are stubs that raise
until configured — object metadata (``storage_objects`` / versions) is identical
across backends so switching backend never changes application code.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Protocol

from sqlalchemy.orm import Session

from backend.app.core.security import SECRET_KEY
from backend.app.models.platform_ops import StorageObject, StorageObjectVersion

_LIFECYCLE_DAYS = {"ephemeral": 1, "short": 30, "standard": 365, "archive": 2555}


# ===========================================================================
# Encryption (at-rest envelope) — pluggable, keystream is per-tenant derived.
# ===========================================================================
def _keystream(key_material: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(key_material + counter.to_bytes(8, "big")).digest())
        counter += 1
    return bytes(out[:length])


def encrypt_bytes(data: bytes, tenant_id: int) -> bytes:
    km = hashlib.sha256(f"{SECRET_KEY}:{tenant_id}".encode()).digest()
    ks = _keystream(km, len(data))
    return bytes(a ^ b for a, b in zip(data, ks))


def decrypt_bytes(data: bytes, tenant_id: int) -> bytes:
    return encrypt_bytes(data, tenant_id)  # XOR keystream is symmetric


# ===========================================================================
# Backend abstraction
# ===========================================================================
class StorageBackend(Protocol):
    name: str

    def put(self, uri: str, data: bytes) -> None: ...

    def get(self, uri: str) -> bytes: ...

    def delete(self, uri: str) -> None: ...


class MemoryBackend:
    name = "memory"

    def __init__(self):
        self._store: Dict[str, bytes] = {}

    def put(self, uri: str, data: bytes) -> None:
        self._store[uri] = data

    def get(self, uri: str) -> bytes:
        if uri not in self._store:
            raise FileNotFoundError(uri)
        return self._store[uri]

    def delete(self, uri: str) -> None:
        self._store.pop(uri, None)


class LocalBackend:
    name = "local"

    def __init__(self, root: Optional[str] = None):
        from backend.app.config import settings
        self.root = root or os.path.join(settings.STORAGE_ROOT, "saas_objects")

    def _path(self, uri: str) -> str:
        return os.path.join(self.root, uri)

    def put(self, uri: str, data: bytes) -> None:
        path = self._path(uri)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)

    def get(self, uri: str) -> bytes:
        with open(self._path(uri), "rb") as fh:
            return fh.read()

    def delete(self, uri: str) -> None:
        try:
            os.remove(self._path(uri))
        except FileNotFoundError:
            pass


class _UnconfiguredBackend:  # pragma: no cover - abstraction placeholder
    def __init__(self, name: str):
        self.name = name

    def put(self, uri: str, data: bytes) -> None:
        raise NotImplementedError(f"{self.name} backend not configured")

    def get(self, uri: str) -> bytes:
        raise NotImplementedError(f"{self.name} backend not configured")

    def delete(self, uri: str) -> None:
        raise NotImplementedError(f"{self.name} backend not configured")


_BACKENDS: Dict[str, StorageBackend] = {
    "memory": MemoryBackend(),
    "s3": _UnconfiguredBackend("s3"),
    "azure": _UnconfiguredBackend("azure"),
    "gcs": _UnconfiguredBackend("gcs"),
    "minio": _UnconfiguredBackend("minio"),
}
_active_backend_name = "memory"


def register_backend(name: str, backend: StorageBackend) -> None:
    _BACKENDS[name] = backend


def set_active_backend(name: str) -> None:
    global _active_backend_name
    if name == "local" and "local" not in _BACKENDS:
        _BACKENDS["local"] = LocalBackend()
    if name not in _BACKENDS:
        raise ValueError(f"unknown backend: {name}")
    _active_backend_name = name


def _backend() -> StorageBackend:
    if _active_backend_name == "local" and "local" not in _BACKENDS:
        _BACKENDS["local"] = LocalBackend()
    return _BACKENDS[_active_backend_name]


# ===========================================================================
# Object operations
# ===========================================================================
def put_object(db: Session, tenant_id: int, key: str, data: bytes, *,
               bucket: str = "default", content_type: Optional[str] = None,
               encrypt: bool = False, lifecycle_policy: Optional[str] = None,
               metadata: Optional[Dict] = None) -> StorageObject:
    """Store bytes and create/version the object record."""
    checksum = hashlib.sha256(data).hexdigest()
    stored = encrypt_bytes(data, tenant_id) if encrypt else data
    backend = _backend()

    obj = (
        db.query(StorageObject)
        .filter(StorageObject.tenant_id == tenant_id,
                StorageObject.bucket == bucket, StorageObject.key == key)
        .first()
    )
    if obj is None:
        obj = StorageObject(
            tenant_id=tenant_id, bucket=bucket, key=key, backend=backend.name,
            content_type=content_type, size_bytes=len(data), checksum=checksum,
            current_version=1, encrypted=encrypt, lifecycle_policy=lifecycle_policy,
            metadata_json=metadata or {},
        )
        db.add(obj)
        db.flush()
        version = 1
    else:
        obj.current_version += 1
        obj.size_bytes = len(data)
        obj.checksum = checksum
        obj.content_type = content_type or obj.content_type
        obj.encrypted = encrypt
        obj.backend = backend.name
        if lifecycle_policy:
            obj.lifecycle_policy = lifecycle_policy
        obj.updated_at = datetime.utcnow()
        version = obj.current_version

    uri = f"t{tenant_id}/{bucket}/{key}.v{version}"
    backend.put(uri, stored)
    db.add(StorageObjectVersion(
        object_id=obj.id, version=version, size_bytes=len(data),
        checksum=checksum, physical_uri=uri,
    ))

    # Apply lifecycle expiry.
    policy = lifecycle_policy or obj.lifecycle_policy
    if policy and policy in _LIFECYCLE_DAYS:
        obj.expires_at = datetime.utcnow() + timedelta(days=_LIFECYCLE_DAYS[policy])
    db.commit()
    db.refresh(obj)
    return obj


def get_object(db: Session, tenant_id: int, key: str, *, bucket: str = "default",
               version: Optional[int] = None) -> bytes:
    obj = _find(db, tenant_id, bucket, key)
    if obj is None:
        raise FileNotFoundError(key)
    version = version or obj.current_version
    ver = (
        db.query(StorageObjectVersion)
        .filter(StorageObjectVersion.object_id == obj.id,
                StorageObjectVersion.version == version)
        .first()
    )
    if ver is None:
        raise FileNotFoundError(f"{key} v{version}")
    raw = _backend().get(ver.physical_uri)
    return decrypt_bytes(raw, tenant_id) if obj.encrypted else raw


def _find(db: Session, tenant_id: int, bucket: str, key: str) -> Optional[StorageObject]:
    return (
        db.query(StorageObject)
        .filter(StorageObject.tenant_id == tenant_id,
                StorageObject.bucket == bucket, StorageObject.key == key)
        .first()
    )


def list_objects(db: Session, tenant_id: int, *, bucket: Optional[str] = None,
                 prefix: Optional[str] = None) -> List[StorageObject]:
    q = db.query(StorageObject).filter(StorageObject.tenant_id == tenant_id)
    if bucket:
        q = q.filter(StorageObject.bucket == bucket)
    if prefix:
        q = q.filter(StorageObject.key.like(f"{prefix}%"))
    return q.all()


def list_versions(db: Session, object_id: int) -> List[StorageObjectVersion]:
    return (
        db.query(StorageObjectVersion)
        .filter(StorageObjectVersion.object_id == object_id)
        .order_by(StorageObjectVersion.version.desc())
        .all()
    )


def delete_object(db: Session, tenant_id: int, key: str, *, bucket: str = "default") -> None:
    obj = _find(db, tenant_id, bucket, key)
    if obj is None:
        return
    for ver in list_versions(db, obj.id):
        _backend().delete(ver.physical_uri)
        db.delete(ver)
    db.delete(obj)
    db.commit()


# ===========================================================================
# Signed URLs
# ===========================================================================
def sign_url(tenant_id: int, bucket: str, key: str, *, expires_in: int = 3600,
             action: str = "get") -> Dict[str, Any]:
    expiry = int((datetime.utcnow() + timedelta(seconds=expires_in)).timestamp())
    payload = f"{tenant_id}:{bucket}:{key}:{action}:{expiry}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()
    return {
        "url": f"/api/saas/storage/signed/{token}",
        "token": token, "expires_at": expiry, "action": action,
    }


def verify_signed_url(token: str) -> Dict[str, Any]:
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        tenant_id, bucket, key, action, expiry, sig = decoded.rsplit(":", 5)
    except Exception:
        raise ValueError("malformed token")
    payload = f"{tenant_id}:{bucket}:{key}:{action}:{expiry}"
    expected = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("bad signature")
    if int(expiry) < int(datetime.utcnow().timestamp()):
        raise ValueError("expired")
    return {"tenant_id": int(tenant_id), "bucket": bucket, "key": key, "action": action}


# ===========================================================================
# Large-file (multipart) upload — assemble parts, then store as one object.
# ===========================================================================
_MULTIPART: Dict[str, Dict[int, bytes]] = {}


def start_multipart(tenant_id: int, bucket: str, key: str) -> str:
    upload_id = uuid.uuid4().hex
    _MULTIPART[upload_id] = {}
    return upload_id


def upload_part(upload_id: str, part_number: int, data: bytes) -> None:
    if upload_id not in _MULTIPART:
        raise ValueError("unknown upload")
    _MULTIPART[upload_id][part_number] = data


def complete_multipart(db: Session, upload_id: str, tenant_id: int, key: str, *,
                       bucket: str = "default", content_type: Optional[str] = None,
                       encrypt: bool = False) -> StorageObject:
    parts = _MULTIPART.pop(upload_id, None)
    if parts is None:
        raise ValueError("unknown upload")
    data = b"".join(parts[n] for n in sorted(parts))
    return put_object(db, tenant_id, key, data, bucket=bucket,
                      content_type=content_type, encrypt=encrypt)


# ===========================================================================
# Lifecycle sweep (invoked by the background job platform)
# ===========================================================================
def run_lifecycle_sweep(db: Session, *, tenant_id: Optional[int] = None) -> int:
    now = datetime.utcnow()
    q = db.query(StorageObject).filter(StorageObject.expires_at.isnot(None),
                                       StorageObject.expires_at < now)
    if tenant_id is not None:
        q = q.filter(StorageObject.tenant_id == tenant_id)
    expired = q.all()
    count = 0
    for obj in expired:
        for ver in list_versions(db, obj.id):
            _backend().delete(ver.physical_uri)
            db.delete(ver)
        db.delete(obj)
        count += 1
    db.commit()
    return count


def storage_usage_gb(db: Session, tenant_id: int) -> float:
    total = sum(o.size_bytes for o in
                db.query(StorageObject).filter(StorageObject.tenant_id == tenant_id).all())
    return round(total / (1024 ** 3), 6)
