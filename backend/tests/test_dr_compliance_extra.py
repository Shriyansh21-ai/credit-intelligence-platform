"""Phase 11, M14 — expanded disaster-recovery & compliance tests."""

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.app.core import compliance as comp
from backend.app.core import dr


class DrMultiTargetTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.mgr = dr.BackupManager(backup_dir=self.dir)
        self.mgr.register(dr.DatabaseBackupTarget("db", dump=lambda: b"d"))
        self.mgr.register(dr.SecretRefBackupTarget(lambda: [{"name": "k", "version": 1}]))

    def test_run_single_unknown(self):
        with self.assertRaises(dr.DrError):
            self.mgr.run("nope")

    def test_catalog_grows(self):
        self.mgr.run("db")
        self.mgr.run("db")
        self.assertEqual(len(self.mgr.catalog()), 2)

    def test_prune_keeps_recent(self):
        self.mgr.run("db")
        removed = self.mgr.prune(retention_days=35)
        self.assertEqual(removed, [])
        self.assertEqual(len(self.mgr.catalog()), 1)


class DrRestoreManagerTest(unittest.TestCase):
    def test_restore_by_target_metadata(self):
        loaded = {}
        db = dr.DatabaseBackupTarget("db", dump=lambda: b"x", load=lambda b: loaded.update(ok=1))
        tmp = Path(tempfile.mkdtemp())
        art = db.backup(tmp)
        rm = dr.RestoreManager({"db": db})
        self.assertTrue(rm.restore(art))
        self.assertEqual(loaded, {"ok": 1})

    def test_restore_no_target_raises(self):
        art = dr.BackupArtifact("i", "weird", datetime.now(UTC).isoformat(), "x", 1, "c")
        with self.assertRaises(dr.DrError):
            dr.RestoreManager({}).restore(art)


class PitrExtraTest(unittest.TestCase):
    def test_no_candidate_returns_none(self):
        pitr = dr.PointInTimeRecovery(window_days=7)
        now = datetime(2026, 7, 1, tzinfo=UTC)
        arts = [dr.BackupArtifact("a", "database", now.isoformat(), "x", 1, "c")]
        self.assertIsNone(pitr.resolve_restore_point(arts, now - timedelta(days=1)))

    def test_window_bounds(self):
        pitr = dr.PointInTimeRecovery(window_days=3)
        now = datetime(2026, 7, 1, tzinfo=UTC)
        start, end = pitr.window(now=now)
        self.assertEqual((end - start).days, 3)


class DrDrillFailureTest(unittest.TestCase):
    def test_drill_reports_backup_failure(self):
        class Bad:
            name = "bad"

            def backup(self, dest):
                raise OSError("disk full")

            def restore(self, artifact):
                return True

        result = dr.recovery_drill(Bad(), backup_dir=tempfile.mkdtemp())
        self.assertFalse(result.ok)
        self.assertIn("disk full", result.error)

    def test_validate_missing_file(self):
        art = dr.BackupArtifact(
            "i", "database", datetime.now(UTC).isoformat(), "/no/such/file", 1, "abc"
        )
        self.assertFalse(dr.validate_backup(art))


class ComplianceFrameworkMatrixTest(unittest.TestCase):
    def test_soc2_controls(self):
        rep = comp.generate_report(comp.Framework.SOC2)
        self.assertIn("CC6.1", rep["requirements_covered"])

    def test_iso_controls(self):
        rep = comp.generate_report(comp.Framework.ISO27001)
        self.assertIn("A.10.1", rep["requirements_covered"])

    def test_gdpr_controls(self):
        rep = comp.generate_report(comp.Framework.GDPR)
        self.assertIn("Art.17", rep["requirements_covered"])

    def test_rbi_controls(self):
        rep = comp.generate_report(comp.Framework.RBI)
        self.assertIn("data-localisation", rep["requirements_covered"])

    def test_report_control_detail_shape(self):
        rep = comp.generate_report(comp.Framework.PCI_DSS)
        first = rep["controls"][0]
        self.assertEqual(set(first), {"id", "title", "status", "requirements", "evidence"})


class ConsentExtraTest(unittest.TestCase):
    def setUp(self):
        self.clock = [datetime(2026, 1, 1, tzinfo=UTC)]
        self.ledger = comp.ConsentLedger(clock=lambda: self.clock[0])

    def test_reconsent_after_withdraw(self):
        self.ledger.grant("u", "p")
        self.ledger.withdraw("u", "p")
        self.ledger.grant("u", "p")
        self.assertTrue(self.ledger.has_consent("u", "p"))
        self.assertEqual(len(self.ledger.history("u")), 3)

    def test_unknown_subject_no_consent(self):
        self.assertFalse(self.ledger.has_consent("ghost", "p"))

    def test_versioned_policy_recorded(self):
        rec = self.ledger.grant("u", "p", policy_version="2.5")
        self.assertEqual(rec.policy_version, "2.5")


class ResidencyExtraTest(unittest.TestCase):
    def test_multiple_categories(self):
        pol = comp.ResidencyPolicy()
        pol.allow("kyc", {"ap-south-1"})
        pol.allow("logs", {"eu-west-1", "ap-south-1"})
        self.assertTrue(pol.is_allowed("logs", "eu-west-1"))
        self.assertFalse(pol.is_allowed("kyc", "eu-west-1"))

    def test_enforce_ok(self):
        pol = comp.ResidencyPolicy()
        pol.allow("x", {"r1"})
        pol.enforce("x", "r1")  # no raise


class DataRightsExtraTest(unittest.TestCase):
    def test_export_empty_when_no_collectors(self):
        bundle = comp.DataExporter().export("u")
        self.assertEqual(bundle["data"], {})

    def test_erase_zero_when_no_erasers(self):
        self.assertEqual(comp.DataEraser().erase("u").total, 0)

    def test_export_json_parseable(self):
        import json

        exp = comp.DataExporter()
        exp.register("x", lambda sid: {"v": 1})
        self.assertEqual(json.loads(exp.export_json("u"))["data"]["x"]["v"], 1)


class EvidenceExtraTest(unittest.TestCase):
    def test_collect_kind_recorded(self):
        col = comp.EvidenceCollector()
        col.register("c1", lambda: {"ok": True})
        ev = col.collect(kind="quarterly")
        self.assertEqual(ev[0].kind, "quarterly")

    def test_audit_export_empty(self):
        self.assertEqual(comp.export_audit_ndjson([]), "")


if __name__ == "__main__":
    unittest.main()
