import unittest

from backend.app.services.security_compliance import catalog, owasp


class OwaspTest(unittest.TestCase):
    def test_top10_has_ten(self):
        self.assertEqual(len(catalog.OWASP_TOP_10_2021), 10)
        res = owasp.owasp_top10()
        self.assertEqual(len(res["controls"]), 10)

    def test_api_top10_has_ten(self):
        self.assertEqual(len(catalog.OWASP_API_TOP_10_2023), 10)

    def test_scores_bounded(self):
        for res in (owasp.owasp_top10(), owasp.owasp_api_top10(), owasp.asvs()):
            self.assertGreaterEqual(res["score"], 0)
            self.assertLessEqual(res["score"], 100)

    def test_findings_only_for_non_satisfied(self):
        res = owasp.owasp_top10()
        for f in res["findings"]:
            self.assertIn(f["severity"], ("high", "medium"))
        satisfied = [c for c in res["controls"] if c["status"] == "satisfied"]
        self.assertEqual(len(res["controls"]) - len(satisfied), len(res["findings"]))

    def test_every_control_has_valid_status(self):
        for c in catalog.OWASP_TOP_10_2021 + catalog.OWASP_API_TOP_10_2023:
            self.assertIn(c["status"], ("satisfied", "partial", "gap"))
            self.assertTrue(c["platform_controls"])

    def test_assessment_aggregate(self):
        res = owasp.owasp_assessment()
        self.assertIn("top10", res)
        self.assertIn("api_top10", res)
        self.assertIn("asvs", res)
        self.assertEqual(res["open_findings"], len(res["findings"]))
        self.assertGreaterEqual(res["overall_score"], 0)
        self.assertLessEqual(res["overall_score"], 100)

    def test_finding_codes_unique_within_group(self):
        res = owasp.owasp_assessment()
        codes = [f["code"] for f in res["findings"]]
        self.assertEqual(len(codes), len(set(codes)))

    def test_broken_access_control_satisfied(self):
        a01 = next(c for c in catalog.OWASP_TOP_10_2021 if c["id"] == "A01")
        self.assertEqual(a01["status"], "satisfied")


if __name__ == "__main__":
    unittest.main()
