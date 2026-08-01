import unittest

from backend.app.services.security_compliance import catalog, threat_model


class ThreatModelTest(unittest.TestCase):
    def test_stride_has_six_categories(self):
        stride = threat_model.stride_analysis()
        cats = {c["category"] for c in stride["categories"]}
        self.assertEqual(cats, set(catalog.STRIDE_CATEGORIES))
        self.assertEqual(len(stride["categories"]), 6)

    def test_stride_total_threats_consistent(self):
        stride = threat_model.stride_analysis()
        total = sum(c["threat_count"] for c in stride["categories"])
        self.assertEqual(total, stride["total_threats"])
        self.assertEqual(total, len(catalog.STRIDE_THREATS))

    def test_every_threat_has_controls_and_category(self):
        for t in catalog.STRIDE_THREATS:
            self.assertIn(t["category"], catalog.STRIDE_CATEGORIES)
            self.assertTrue(t["existing_controls"])
            self.assertIn(t["residual"], ("low", "medium", "high"))

    def test_residual_distribution_sums(self):
        stride = threat_model.stride_analysis()
        dist = stride["residual_distribution"]
        self.assertEqual(sum(dist.values()), len(catalog.STRIDE_THREATS))

    def test_attack_surface(self):
        surface = threat_model.attack_surface()
        self.assertEqual(surface["total"], len(catalog.ATTACK_SURFACE))
        self.assertGreater(surface["high_risk"], 0)
        self.assertIn("Auth endpoints (/auth/*)", surface["public_surfaces"])

    def test_attack_trees_structure(self):
        trees = threat_model.attack_trees()
        self.assertGreaterEqual(len(trees), 4)
        for t in trees:
            self.assertIn("goal", t)
            self.assertIn(t["and_or"], ("AND", "OR"))
            self.assertTrue(t["paths"])
            for p in t["paths"]:
                self.assertTrue(p["mitigations"])

    def test_trust_boundaries(self):
        boundaries = threat_model.trust_boundaries()
        names = {b["name"] for b in boundaries}
        self.assertIn("Tenant A -> Tenant B", names)
        self.assertIn("Internet -> Edge", names)

    def test_build_threat_model_score_bounded(self):
        model = threat_model.build_threat_model()
        self.assertGreaterEqual(model["model_health_score"], 0)
        self.assertLessEqual(model["model_health_score"], 100)
        self.assertIn("stride", model)
        self.assertIn("attack_surface", model)
        self.assertIn("attack_trees", model)
        self.assertIn("trust_boundaries", model)

    def test_deterministic(self):
        a = threat_model.build_threat_model()
        b = threat_model.build_threat_model()
        self.assertEqual(a["model_health_score"], b["model_health_score"])


if __name__ == "__main__":
    unittest.main()
