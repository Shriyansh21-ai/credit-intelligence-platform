import unittest

from backend.app.services.security_compliance import common


class ScoringPrimitivesTest(unittest.TestCase):
    def test_clamp_bounds(self):
        self.assertEqual(common.clamp(150), 100.0)
        self.assertEqual(common.clamp(-10), 0.0)
        self.assertEqual(common.clamp(42), 42)
        self.assertEqual(common.clamp(5, 1, 3), 3)

    def test_grade_from_score_ordering(self):
        self.assertEqual(common.grade_from_score(99), "A+")
        self.assertEqual(common.grade_from_score(91), "A-")
        self.assertEqual(common.grade_from_score(85), "B")
        self.assertEqual(common.grade_from_score(72), "C")
        self.assertEqual(common.grade_from_score(10), "F")

    def test_grade_monotonic(self):
        order = ["F", "D", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]
        ranks = {g: i for i, g in enumerate(order)}
        prev = -1
        for s in range(0, 101, 5):
            g = common.grade_from_score(s)
            self.assertIn(g, ranks)
            self.assertGreaterEqual(ranks[g], prev)
            prev = ranks[g]

    def test_score_from_findings_monotonic(self):
        none = common.score_from_findings([])
        one_high = common.score_from_findings([{"severity": "high"}])
        one_crit = common.score_from_findings([{"severity": "critical"}])
        self.assertEqual(none, 100.0)
        self.assertLess(one_high, none)
        self.assertLess(one_crit, one_high)

    def test_score_never_negative(self):
        many = [{"severity": "critical"}] * 10
        self.assertEqual(common.score_from_findings(many), 0.0)

    def test_severity_counts_complete(self):
        counts = common.severity_counts([{"severity": "high"}, {"severity": "high"},
                                         {"severity": "low"}])
        self.assertEqual(counts["high"], 2)
        self.assertEqual(counts["low"], 1)
        self.assertEqual(counts["critical"], 0)
        self.assertEqual(set(counts), set(common.SEVERITY_ORDER))

    def test_readiness_label(self):
        self.assertEqual(common.readiness_label(95), "ready")
        self.assertEqual(common.readiness_label(80), "substantial")
        self.assertEqual(common.readiness_label(60), "partial")
        self.assertEqual(common.readiness_label(10), "not_ready")

    def test_compliance_score_excludes_na(self):
        results = [{"status": "satisfied"}, {"status": "satisfied"},
                   {"status": "not_applicable"}]
        # 2/2 applicable satisfied -> 100
        self.assertEqual(common.compliance_score(results), 100.0)

    def test_compliance_score_partial(self):
        results = [{"status": "satisfied"}, {"status": "partial"}, {"status": "gap"}]
        # (1 + 0.5 + 0)/3 = 0.5 -> 50
        self.assertEqual(common.compliance_score(results), 50.0)

    def test_compliance_score_empty(self):
        self.assertEqual(common.compliance_score([]), 0.0)

    def test_risk_score_and_level(self):
        self.assertEqual(common.risk_score(5, 5), 25)
        self.assertEqual(common.risk_score(1, 1), 1)
        self.assertEqual(common.risk_level(25), "critical")
        self.assertEqual(common.risk_level(15), "high")
        self.assertEqual(common.risk_level(8), "medium")
        self.assertEqual(common.risk_level(2), "low")

    def test_risk_score_clamps_inputs(self):
        self.assertEqual(common.risk_score(9, 9), 25)
        self.assertEqual(common.risk_score(0, 0), 1)

    def test_weighted_average(self):
        dims = {"a": 100.0, "b": 0.0}
        self.assertEqual(common.weighted_average(dims), 50.0)
        weighted = common.weighted_average(dims, {"a": 3.0, "b": 1.0})
        self.assertEqual(weighted, 75.0)

    def test_weighted_average_empty(self):
        self.assertEqual(common.weighted_average({}), 0.0)


if __name__ == "__main__":
    unittest.main()
