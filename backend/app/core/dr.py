"""Disaster recovery toolkit.

Provider-agnostic backup / restore / point-in-time-recovery abstractions with a
real, file-based default implementation so the whole flow is exercisable in
tests and local/dev without any cloud dependency. In production the same
:class:`BackupTarget` interface is implemented by cloud-native adapters (RDS
snapshots, S3 versioning, Secrets Manager) — the manager, catalog, retention
drill, and validation logic are identical.

Design
------
* :class:`BackupTarget` — a single backup-able subsystem (database, a storage
  tree, configuration, secret *references*). Produces a :class:`BackupArtifact`
  (checksummed) and can restore from one.
* :class:`BackupManager` — registers targets, runs backups, maintains a JSON
  catalog, prunes by retention.
* :class:`RestoreManager` — restores an artifact by id.
* :class:`PointInTimeRecovery` — abstraction describing the recovery window and
  resolving a restore point for a target timestamp.
* :func:`recovery_drill` / :func:`validate_backup` — recovery testing +
  validation used by the DR runbook and scheduled drills.

Secrets are backed up **by reference** (names/versions), never as plaintext, and
the reference manifest is itself encrypted with the field cipher (M8).
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import tarfile
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from backend.app.core.crypto import decrypt_field, encrypt_field
from backend.app.core.settings import get_settings


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class BackupArtifact:
    id: str
    kind: str
    created_at: str
    location: str
    size_bytes: int
    checksum: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@runtime_checkable
class BackupTarget(Protocol):
    name: str

    def backup(self, dest_dir: Path) -> BackupArtifact: ...

    def restore(self, artifact: BackupArtifact) -> bool: ...


# ===========================================================================
# Concrete file-based targets
# ===========================================================================
class DatabaseBackupTarget:
    """Backs up a database via an injected dump/restore pair.

    ``dump`` returns the logical backup bytes (e.g. `pg_dump`/`.sql`/sqlite copy)
    ``load`` applies them. Injecting these keeps the target engine-agnostic and
    unit-testable.
    """

    def __init__(
        self, name: str, dump: Callable[[], bytes], load: Callable[[bytes], None] | None = None
    ):
        self.name = name
        self._dump = dump
        self._load = load

    def backup(self, dest_dir: Path) -> BackupArtifact:
        data = self._dump()
        path = dest_dir / f"{self.name}-{uuid.uuid4().hex}.dump"
        path.write_bytes(data)
        return BackupArtifact(
            id=path.stem,
            kind="database",
            created_at=_utcnow().isoformat(),
            location=str(path),
            size_bytes=len(data),
            checksum=_checksum(data),
            metadata={"target": self.name},
        )

    def restore(self, artifact: BackupArtifact) -> bool:
        if self._load is None:
            return False
        data = Path(artifact.location).read_bytes()
        if _checksum(data) != artifact.checksum:
            raise DrError("checksum mismatch on restore")
        self._load(data)
        return True


class FileTreeBackupTarget:
    """Backs up a directory tree (object storage, configuration) as a tar.gz."""

    def __init__(self, name: str, source_dir: str, kind: str = "storage"):
        self.name = name
        self.kind = kind
        self._source = Path(source_dir)

    def backup(self, dest_dir: Path) -> BackupArtifact:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            if self._source.exists():
                tar.add(self._source, arcname=self._source.name)
        data = buf.getvalue()
        path = dest_dir / f"{self.name}-{uuid.uuid4().hex}.tar.gz"
        path.write_bytes(data)
        return BackupArtifact(
            id=path.stem,
            kind=self.kind,
            created_at=_utcnow().isoformat(),
            location=str(path),
            size_bytes=len(data),
            checksum=_checksum(data),
            metadata={"target": self.name, "source": str(self._source)},
        )

    def restore(self, artifact: BackupArtifact, *, into: str | None = None) -> bool:
        data = Path(artifact.location).read_bytes()
        if _checksum(data) != artifact.checksum:
            raise DrError("checksum mismatch on restore")
        dest = Path(into) if into else self._source.parent
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            # filter="data" rejects path traversal / unsafe members (3.12+).
            tar.extractall(dest, filter="data")
        return True


class ConfigBackupTarget:
    """Snapshots non-secret runtime configuration (the settings summary)."""

    name = "config"

    def backup(self, dest_dir: Path) -> BackupArtifact:
        data = json.dumps(get_settings().summary(), indent=2, sort_keys=True).encode()
        path = dest_dir / f"config-{uuid.uuid4().hex}.json"
        path.write_bytes(data)
        return BackupArtifact(
            id=path.stem,
            kind="config",
            created_at=_utcnow().isoformat(),
            location=str(path),
            size_bytes=len(data),
            checksum=_checksum(data),
        )

    def restore(self, artifact: BackupArtifact) -> bool:  # noqa: ARG002 - config is applied out of band
        # Configuration is 12-factor (env-driven); restore = re-materialise env
        # so this target is snapshot-only. Returning True signals "no action".
        return True


class SecretRefBackupTarget:
    """Backs up secret *references* (names/versions), never plaintext values.

    The manifest is encrypted with the field cipher so even the reference
    inventory is protected at rest.
    """

    name = "secret-refs"

    def __init__(self, refs: Callable[[], list[dict[str, Any]]]):
        self._refs = refs

    def backup(self, dest_dir: Path) -> BackupArtifact:
        manifest = json.dumps({"refs": self._refs(), "at": _utcnow().isoformat()}, sort_keys=True)
        token = encrypt_field(manifest).encode()
        path = dest_dir / f"secret-refs-{uuid.uuid4().hex}.enc"
        path.write_bytes(token)
        return BackupArtifact(
            id=path.stem,
            kind="secret-refs",
            created_at=_utcnow().isoformat(),
            location=str(path),
            size_bytes=len(token),
            checksum=_checksum(token),
            metadata={"encrypted": True, "plaintext": False},
        )

    def restore(self, artifact: BackupArtifact) -> bool:
        token = Path(artifact.location).read_bytes().decode()
        json.loads(decrypt_field(token))  # verify it decrypts + parses
        return True


# ===========================================================================
# Point-in-time recovery abstraction
# ===========================================================================
@dataclass
class PointInTimeRecovery:
    window_days: int

    def window(self, *, now: datetime | None = None) -> tuple[datetime, datetime]:
        ref = now or _utcnow()
        return (ref - timedelta(days=self.window_days), ref)

    def can_recover_to(self, target: datetime, *, now: datetime | None = None) -> bool:
        start, end = self.window(now=now)
        return start <= target <= end

    def resolve_restore_point(
        self, artifacts: list[BackupArtifact], target: datetime
    ) -> BackupArtifact | None:
        """Pick the most recent backup at or before ``target`` (base for PITR)."""
        candidates = [a for a in artifacts if datetime.fromisoformat(a.created_at) <= target]
        return max(candidates, key=lambda a: a.created_at) if candidates else None


# ===========================================================================
# Manager + catalog + retention
# ===========================================================================
class DrError(Exception):
    """Disaster-recovery operation error."""


class BackupManager:
    def __init__(self, backup_dir: str | None = None) -> None:
        settings = get_settings()
        self._dir = Path(backup_dir or settings.backup_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._catalog_path = self._dir / "catalog.json"
        self._targets: dict[str, BackupTarget] = {}

    def register(self, target: BackupTarget) -> None:
        self._targets[target.name] = target

    def run(self, name: str) -> BackupArtifact:
        if name not in self._targets:
            raise DrError(f"unknown backup target {name!r}")
        artifact = self._targets[name].backup(self._dir)
        self._append_catalog(artifact)
        return artifact

    def run_all(self) -> list[BackupArtifact]:
        return [self.run(name) for name in self._targets]

    def catalog(self) -> list[BackupArtifact]:
        if not self._catalog_path.exists():
            return []
        raw = json.loads(self._catalog_path.read_text() or "[]")
        return [BackupArtifact(**row) for row in raw]

    def _append_catalog(self, artifact: BackupArtifact) -> None:
        rows = [a.as_dict() for a in self.catalog()]
        rows.append(artifact.as_dict())
        self._catalog_path.write_text(json.dumps(rows, indent=2))

    def prune(self, *, retention_days: int | None = None, now: datetime | None = None) -> list[str]:
        settings = get_settings()
        days = retention_days if retention_days is not None else settings.backup_retention_days
        cutoff = (now or _utcnow()) - timedelta(days=days)
        kept, removed = [], []
        for a in self.catalog():
            if datetime.fromisoformat(a.created_at) < cutoff:
                Path(a.location).unlink(missing_ok=True)
                removed.append(a.id)
            else:
                kept.append(a.as_dict())
        self._catalog_path.write_text(json.dumps(kept, indent=2))
        return removed


class RestoreManager:
    def __init__(self, targets: dict[str, BackupTarget]) -> None:
        self._targets = targets

    def restore(self, artifact: BackupArtifact, **kwargs: Any) -> bool:
        target = self._targets.get(artifact.metadata.get("target", "")) or self._by_kind(
            artifact.kind
        )
        if target is None:
            raise DrError(f"no target able to restore artifact kind {artifact.kind!r}")
        return target.restore(artifact, **kwargs) if kwargs else target.restore(artifact)

    def _by_kind(self, kind: str) -> BackupTarget | None:
        for t in self._targets.values():
            if getattr(t, "kind", getattr(t, "name", None)) == kind:
                return t
        return None


# ===========================================================================
# Recovery testing + validation
# ===========================================================================
@dataclass
class DrillResult:
    target: str
    backed_up: bool
    restored: bool
    validated: bool
    artifact_id: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.backed_up and self.restored and self.validated


def validate_backup(artifact: BackupArtifact) -> bool:
    """Recompute the checksum of the stored artifact and confirm integrity."""
    path = Path(artifact.location)
    if not path.exists():
        return False
    return _checksum(path.read_bytes()) == artifact.checksum


def recovery_drill(
    target: BackupTarget,
    *,
    backup_dir: str | None = None,
    restore_kwargs: dict[str, Any] | None = None,
) -> DrillResult:
    """Backup → validate → restore round-trip for one target (a DR drill)."""
    tmp = Path(backup_dir or get_settings().backup_dir) / "drills"
    tmp.mkdir(parents=True, exist_ok=True)
    result = DrillResult(target=target.name, backed_up=False, restored=False, validated=False)
    try:
        artifact = target.backup(tmp)
        result.backed_up = True
        result.artifact_id = artifact.id
        result.validated = validate_backup(artifact)
        result.restored = (
            target.restore(artifact, **(restore_kwargs or {}))
            if restore_kwargs
            else target.restore(artifact)
        )
    except Exception as exc:
        result.error = str(exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return result


__all__ = [
    "BackupArtifact",
    "BackupManager",
    "BackupTarget",
    "ConfigBackupTarget",
    "DatabaseBackupTarget",
    "DrError",
    "DrillResult",
    "FileTreeBackupTarget",
    "PointInTimeRecovery",
    "RestoreManager",
    "SecretRefBackupTarget",
    "recovery_drill",
    "validate_backup",
]
