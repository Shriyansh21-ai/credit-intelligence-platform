import unittest

from backend.app.services.security_compliance import catalog, compliance


class ComplianceFrameworkTest(unittest.TestCase):
    def test_all_frameworks_assessable(self):
        for fid in catalog.framework_ids():
            res = compliance.assess_framework(fid)
            self.assertEqual(res["framework"], fid)
            self.assertGreaterEqual(res["score"], 0)
            self.assertLessEqual(res["score"], 100)
            self.assertEqual(
                res["total_controls"],
                res["satisfied"] + res["partial"] + res["gaps"]
                + sum(1 for c in res["results"] if c["status"] == "not_applicable"),
            )

    def test_required_frameworks_present(self):
        ids = set(catalog.framework_ids())
        for expected in ("soc2", "iso27001", "gdpr", "pci_dss", "rbi_dl",
                         "rbi_cyber", "rbi_outsourcing", "nist_csf"):
            self.assertIn(expected, ids)

    def test_unknown_framework_raises(self):
        with self.assertRaises(ValueError):
            compliance.assess_framework("nonexistent")

    def test_readiness_label_consistent(self):
        for fid in catalog.framework_ids():
            res = compliance.assess_framework(fid)
            self.assertIn(res["readiness"],
                          ("ready", "substantial", "partial", "not_ready"))

    def test_matrix_aggregates_all(self):
        matrix = compliance.compliance_matrix()
        self.assertEqual(matrix["framework_count"], len(catalog.framework_ids()))
        self.assertGreaterEqual(matrix["overall_readiness_score"], 0)
        self.assertLessEqual(matrix["overall_readiness_score"], 100)

    def test_gap_analysis(self):
        gaps = compliance.gap_analysis()
        self.assertIn("gaps", gaps)
        # gaps must precede partials in ordering
        statuses = [g["status"] for g in gaps["gaps"]]
        if "gap" in statuses and "partial" in statuses:
            self.assertLessEqual(statuses.index("gap"), statuses.index("partial"))

    def test_gap_items_reference_framework(self):
        gaps = compliance.gap_analysis()
        for g in gaps["gaps"]:
            self.assertIn("framework", g)
            self.assertIn("remediation", g)

    def test_readiness_score(self):
        res = compliance.readiness_score()
        self.assertIn("by_framework", res)
        self.assertEqual(len(res["by_framework"]), len(catalog.framework_ids()))

    def test_every_control_valid_status(self):
        for fid in catalog.framework_ids():
            fw = catalog.COMPLIANCE_FRAMEWORKS[fid]
            for c in fw["controls"]:
                self.assertIn(c["status"],
                              ("satisfied", "partial", "gap", "not_applicable"))
                self.assertTrue(c["requirement"])


if __name__ == "__main__":
    unittest.main()
