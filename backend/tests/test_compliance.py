"""Phase 11, M12 — compliance toolkit tests."""

import json
import unittest
from datetime import UTC, datetime

from backend.app.core import compliance as c


class ReportTest(unittest.TestCase):
    def test_generate_report_coverage(self):
        rep = c.generate_report(c.Framework.PCI_DSS)
        self.assertEqual(rep["framework"], "PCI_DSS")
        self.assertGreater(rep["controls_total"], 0)
        self.assertEqual(rep["controls_implemented"], rep["controls_total"])  # all implemented
        self.assertEqual(rep["coverage_percent"], 100.0)
        self.assertIn("3.4", rep["requirements_covered"])  # encryption at rest

    def test_all_frameworks_have_controls(self):
        for fw in c.Framework:
            rep = c.generate_report(fw)
            self.assertGreater(rep["controls_total"], 0, f"{fw} has no mapped controls")

    def test_policy_matrix(self):
        matrix = c.policy_matrix()
        self.assertIn("encryption-at-rest", matrix)
        self.assertIn("PCI_DSS", matrix["encryption-at-rest"])


class ConsentTest(unittest.TestCase):
    def setUp(self):
        self.clock = [datetime(2026, 1, 1, tzinfo=UTC)]
        self.ledger = c.ConsentLedger(clock=lambda: self.clock[0])

    def test_grant_withdraw_latest_wins(self):
        self.ledger.grant("u1", "marketing")
        self.assertTrue(self.ledger.has_consent("u1", "marketing"))
        self.ledger.withdraw("u1", "marketing")
        self.assertFalse(self.ledger.has_consent("u1", "marketing"))
        self.assertEqual(len(self.ledger.history("u1")), 2)

    def test_purpose_scoped(self):
        self.ledger.grant("u1", "analytics")
        self.assertTrue(self.ledger.has_consent("u1", "analytics"))
        self.assertFalse(self.ledger.has_consent("u1", "marketing"))


class ResidencyTest(unittest.TestCase):
    def test_enforce(self):
        pol = c.ResidencyPolicy()
        pol.allow("kyc", {"ap-south-1", "ap-south-2"})
        self.assertTrue(pol.is_allowed("kyc", "ap-south-1"))
        self.assertFalse(pol.is_allowed("kyc", "us-east-1"))
        with self.assertRaises(c.ResidencyViolation):
            pol.enforce("kyc", "us-east-1")
        # Unlisted category is unrestricted.
        self.assertTrue(pol.is_allowed("marketing", "us-east-1"))


class DataRightsTest(unittest.TestCase):
    def test_export(self):
        exp = c.DataExporter()
        exp.register("profile", lambda sid: {"id": sid, "name": "Jane"})
        exp.register("applications", lambda sid: [{"app": 1}])
        bundle = exp.export("u1")
        self.assertEqual(bundle["subject_id"], "u1")
        self.assertEqual(bundle["data"]["profile"]["name"], "Jane")
        parsed = json.loads(exp.export_json("u1"))
        self.assertIn("applications", parsed["data"])

    def test_erasure(self):
        er = c.DataEraser()
        er.register("profile", lambda sid: 1)
        er.register("applications", lambda sid: 3)
        result = er.erase("u1")
        self.assertEqual(result.total, 4)
        self.assertEqual(result.erased["applications"], 3)


class EvidenceTest(unittest.TestCase):
    def test_collect_and_bundle(self):
        col = c.EvidenceCollector()
        col.register("mfa", lambda: {"enabled": True})
        col.register("broken", lambda: (_ for _ in ()).throw(RuntimeError("x")))
        bundle = col.bundle()
        self.assertEqual(len(bundle["evidence"]), 2)
        by_id = {e["control_id"]: e for e in bundle["evidence"]}
        self.assertTrue(by_id["mfa"]["payload"]["enabled"])
        self.assertIn("error", by_id["broken"]["payload"])  # failure captured, not raised

    def test_audit_export_ndjson(self):
        out = c.export_audit_ndjson([{"a": 1}, {"b": 2}])
        self.assertEqual(out.count("\n"), 1)
        self.assertEqual(json.loads(out.splitlines()[0]), {"a": 1})


if __name__ == "__main__":
    unittest.main()
