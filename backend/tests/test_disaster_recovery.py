"""Phase 11, M11 — disaster recovery tests (backup/restore/PITR/drill)."""

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.app.core import dr


class DatabaseBackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = {"data": b"CREATE TABLE t (id int);\nINSERT INTO t VALUES (1);"}

    def test_backup_restore_roundtrip(self):
        restored = {}
        target = dr.DatabaseBackupTarget(
            "primary",
            dump=lambda: self.store["data"],
            load=lambda b: restored.update(data=b),
        )
        artifact = target.backup(self.tmp)
        self.assertEqual(artifact.kind, "database")
        self.assertTrue(dr.validate_backup(artifact))
        self.assertTrue(target.restore(artifact))
        self.assertEqual(restored["data"], self.store["data"])

    def test_restore_detects_corruption(self):
        target = dr.DatabaseBackupTarget("primary", dump=lambda: b"payload", load=lambda b: None)
        artifact = target.backup(self.tmp)
        Path(artifact.location).write_bytes(b"tampered")
        with self.assertRaises(dr.DrError):
            target.restore(artifact)
        self.assertFalse(dr.validate_backup(artifact))


class FileTreeBackupTest(unittest.TestCase):
    def test_backup_and_restore_tree(self):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "docs"
        src.mkdir()
        (src / "a.txt").write_text("hello")
        (src / "b.txt").write_text("world")

        target = dr.FileTreeBackupTarget("documents", str(src), kind="storage")
        artifact = target.backup(tmp)
        self.assertEqual(artifact.kind, "storage")
        self.assertTrue(dr.validate_backup(artifact))

        into = tmp / "restored"
        self.assertTrue(target.restore(artifact, into=str(into)))
        self.assertTrue((into / "docs" / "a.txt").exists())
        self.assertEqual((into / "docs" / "a.txt").read_text(), "hello")


class SecretRefBackupTest(unittest.TestCase):
    def test_refs_encrypted_no_plaintext(self):
        tmp = Path(tempfile.mkdtemp())
        target = dr.SecretRefBackupTarget(
            lambda: [{"name": "app/jwt", "version": 3}, {"name": "app/enc", "version": 1}]
        )
        artifact = target.backup(tmp)
        raw = Path(artifact.location).read_bytes()
        self.assertNotIn(b"app/jwt", raw)  # manifest is encrypted at rest
        self.assertTrue(artifact.metadata["encrypted"])
        self.assertTrue(target.restore(artifact))


class ConfigBackupTest(unittest.TestCase):
    def test_config_snapshot(self):
        tmp = Path(tempfile.mkdtemp())
        artifact = dr.ConfigBackupTarget().backup(tmp)
        self.assertEqual(artifact.kind, "config")
        self.assertTrue(dr.validate_backup(artifact))


class ManagerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.mgr = dr.BackupManager(backup_dir=self.dir)
        self.mgr.register(dr.DatabaseBackupTarget("db", dump=lambda: b"dump"))
        self.mgr.register(dr.ConfigBackupTarget())

    def test_run_all_and_catalog(self):
        artifacts = self.mgr.run_all()
        self.assertEqual(len(artifacts), 2)
        catalog = self.mgr.catalog()
        self.assertEqual(len(catalog), 2)
        self.assertEqual({a.kind for a in catalog}, {"database", "config"})

    def test_prune_by_retention(self):
        self.mgr.run("db")
        # Backdate the catalog entry beyond retention and prune.
        cat_path = Path(self.dir) / "catalog.json"
        import json

        rows = json.loads(cat_path.read_text())
        rows[0]["created_at"] = (datetime.now(UTC) - timedelta(days=400)).isoformat()
        cat_path.write_text(json.dumps(rows))
        removed = self.mgr.prune(retention_days=35)
        self.assertEqual(len(removed), 1)
        self.assertEqual(self.mgr.catalog(), [])


class PitrTest(unittest.TestCase):
    def test_window_and_resolve(self):
        pitr = dr.PointInTimeRecovery(window_days=7)
        now = datetime(2026, 7, 1, tzinfo=UTC)
        self.assertTrue(pitr.can_recover_to(now - timedelta(days=3), now=now))
        self.assertFalse(pitr.can_recover_to(now - timedelta(days=10), now=now))

        arts = [
            dr.BackupArtifact("a", "database", (now - timedelta(days=2)).isoformat(), "x", 1, "c"),
            dr.BackupArtifact("b", "database", (now - timedelta(days=1)).isoformat(), "y", 1, "c"),
        ]
        point = pitr.resolve_restore_point(arts, now - timedelta(hours=12))
        self.assertEqual(point.id, "b")  # most recent at/before target


class DrillTest(unittest.TestCase):
    def test_recovery_drill_ok(self):
        loaded = {}
        target = dr.DatabaseBackupTarget(
            "db", dump=lambda: b"snapshot", load=lambda b: loaded.update(ok=True)
        )
        result = dr.recovery_drill(target, backup_dir=tempfile.mkdtemp())
        self.assertTrue(result.ok, result.error)
        self.assertTrue(result.backed_up and result.restored and result.validated)


if __name__ == "__main__":
    unittest.main()
