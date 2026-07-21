"""Storage abstraction for uploaded documents.

Files are **never** stored as blobs in the database (Task 8). Instead a
``StorageBackend`` persists the bytes and the database keeps only an opaque
``uri``. The local backend writes to disk; an S3/GCS backend can be added later
by implementing the same protocol and swapping it in the factory.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from backend.app.config import settings


@dataclass(frozen=True)
class StoredFile:
    uri: str
    size: int
    content_hash: str


@runtime_checkable
class StorageBackend(Protocol):
    def save(self, namespace: str, filename: str, data: bytes) -> StoredFile: ...
    def open(self, uri: str) -> bytes: ...
    def delete(self, uri: str) -> None: ...
    def exists(self, uri: str) -> bool: ...


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

# All local URIs carry this scheme so a backend can recognise its own locators.
_LOCAL_SCHEME = "local://"


def _sanitize(filename: str) -> str:
    name = _SAFE_NAME.sub("_", (filename or "file").strip()) or "file"
    return name[-120:]


class LocalStorageBackend:
    """Stores files on the local filesystem under ``root``."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, namespace: str, filename: str, data: bytes) -> StoredFile:
        key = f"{namespace.strip('/')}/{uuid.uuid4().hex}__{_sanitize(filename)}"
        target = self._path_for_key(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return StoredFile(
            uri=f"{_LOCAL_SCHEME}{key}",
            size=len(data),
            content_hash=hashlib.sha256(data).hexdigest(),
        )

    def open(self, uri: str) -> bytes:
        return self._path_for_uri(uri).read_bytes()

    def delete(self, uri: str) -> None:
        path = self._path_for_uri(uri)
        if path.exists():
            path.unlink()

    def exists(self, uri: str) -> bool:
        try:
            return self._path_for_uri(uri).exists()
        except ValueError:
            return False

    # -- internal helpers -------------------------------------------------

    def _path_for_key(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        # Guard against path traversal via crafted keys.
        if not str(candidate).startswith(str(self.root)):
            raise ValueError("Resolved path escapes storage root")
        return candidate

    def _path_for_uri(self, uri: str) -> Path:
        if not uri.startswith(_LOCAL_SCHEME):
            raise ValueError(f"Unsupported storage uri: {uri!r}")
        return self._path_for_key(uri[len(_LOCAL_SCHEME):])


_backend: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Return the process-wide storage backend (local disk for development)."""
    global _backend
    if _backend is None:
        _backend = LocalStorageBackend(Path(settings.STORAGE_ROOT) / "documents")
    return _backend
