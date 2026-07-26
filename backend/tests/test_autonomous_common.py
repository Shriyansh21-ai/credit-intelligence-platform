import unittest

from backend.app.services.autonomous import common


class CommonHelpersTest(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(common.clamp(1.5), 1.0)
        self.assertEqual(common.clamp(-0.5), 0.0)
        self.assertEqual(common.clamp(0.5), 0.5)
        self.assertEqual(common.clamp(50, 0, 100), 50)

    def test_safe_div(self):
        self.assertEqual(common.safe_div(10, 2), 5)
        self.assertIsNone(common.safe_div(10, 0))
        self.assertIsNone(common.safe_div(None, 2))
        self.assertIsNone(common.safe_div(1, None))

    def test_severity_rank_and_max(self):
        self.assertEqual(common.severity_rank("critical"), 4)
        self.assertEqual(common.severity_rank("unknown"), 0)
        self.assertEqual(common.max_severity(["low", "high", "medium"]), "high")
        self.assertEqual(common.max_severity([]), "info")

    def test_severity_from_score(self):
        self.assertEqual(common.severity_from_score(90), "critical")
        self.assertEqual(common.severity_from_score(70), "high")
        self.assertEqual(common.severity_from_score(50), "medium")
        self.assertEqual(common.severity_from_score(25), "low")
        self.assertEqual(common.severity_from_score(5), "info")

    def test_priority_score_monotonic(self):
        low = common.priority_score("low", 0.5)
        high = common.priority_score("high", 0.5)
        self.assertGreater(high, low)
        # exposure lifts priority
        self.assertGreaterEqual(common.priority_score("high", 0.8, exposure=1e8),
                                common.priority_score("high", 0.8, exposure=0))
        self.assertLessEqual(common.priority_score("critical", 1.0), 100)

    def test_band_from_score(self):
        self.assertEqual(common.band_from_score(70), "red")
        self.assertEqual(common.band_from_score(40), "amber")
        self.assertEqual(common.band_from_score(10), "green")

    def test_pct_change(self):
        self.assertAlmostEqual(common.pct_change(100, 80), -0.2)
        self.assertIsNone(common.pct_change(0, 80))
        self.assertIsNone(common.pct_change(None, 80))

    def test_rating_index_and_shift(self):
        self.assertEqual(common.rating_index("AAA"), 0)
        self.assertEqual(common.rating_index("D"), 9)
        self.assertEqual(common.rating_index("BBB+"), 3)
        self.assertIsNone(common.rating_index("ZZ"))
        self.assertEqual(common.shift_rating("A", 2), "BB")
        self.assertEqual(common.shift_rating("AAA", -5), "AAA")  # clamps
        self.assertEqual(common.shift_rating("D", 5), "D")

    def test_pd_from_score(self):
        low_risk = common.pd_from_score(900)
        high_risk = common.pd_from_score(300)
        self.assertLess(low_risk, high_risk)
        self.assertGreaterEqual(low_risk, 0.0)
        self.assertLessEqual(high_risk, 0.5)

    def test_evidence(self):
        e = common.evidence("pd", 0.1)
        self.assertEqual(e["label"], "pd")
        self.assertEqual(e["value"], 0.1)
        self.assertEqual(e["source"], "platform")


if __name__ == "__main__":
    unittest.main()
