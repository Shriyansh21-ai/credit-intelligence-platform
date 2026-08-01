import unittest

from backend.app.services.security_compliance import ai_ml, hardening, privacy, supply_chain


class SupplyChainTest(unittest.TestCase):
    def test_sbom_has_components(self):
        sbom = supply_chain.sbom()
        self.assertGreater(sbom["component_count"], 0)
        self.assertEqual(sbom["component_count"], len(sbom["components"]))
        for c in sbom["components"][:5]:
            self.assertIn("name", c)
            self.assertIn("license", c)

    def test_sbom_includes_pypi(self):
        sbom = supply_chain.sbom()
        self.assertIn("pypi", sbom["ecosystems"])

    def test_dependency_report(self):
        dep = supply_chain.dependency_report()
        self.assertGreater(dep["total"], 0)
        self.assertEqual(dep["total"], dep["pinned"] + dep["unpinned"])
        self.assertGreaterEqual(dep["score"], 0)
        self.assertLessEqual(dep["score"], 100)

    def test_license_report_buckets(self):
        lic = supply_chain.license_report()
        self.assertIn("permissive", lic["buckets"])
        self.assertIn("copyleft", lic["buckets"])
        total = sum(lic["buckets"].values())
        self.assertEqual(total, len(lic["licenses"]))

    def test_scanning_signals(self):
        dep = supply_chain.dependency_report()
        # repo ships a gitleaks config and a .github dir
        self.assertTrue(dep["scanning"]["sbom_generated"])

    def test_report_aggregate(self):
        rep = supply_chain.supply_chain_report()
        self.assertIn("dependencies", rep)
        self.assertIn("licenses", rep)
        self.assertEqual(rep["open_findings"], len(rep["findings"]))


class HardeningTest(unittest.TestCase):
    def test_checks_present(self):
        res = hardening.container_hardening()
        self.assertGreater(res["total_checks"], 0)
        controls = {c["control"] for c in res["checks"]}
        self.assertTrue(any("Non-root" in c for c in controls))
        self.assertTrue(any("Network policy" in c for c in controls))
        self.assertTrue(any("Resource limits" in c for c in controls))

    def test_score_bounded(self):
        res = hardening.container_hardening()
        self.assertGreaterEqual(res["score"], 0)
        self.assertLessEqual(res["score"], 100)

    def test_findings_have_recommendations(self):
        res = hardening.container_hardening()
        for f in res["findings"]:
            self.assertTrue(f["recommendation"])
            self.assertEqual(f["category"], "container")


class AiMlSecurityTest(unittest.TestCase):
    def test_ai_security_maps_llm_top10(self):
        res = ai_ml.ai_security()
        self.assertEqual(len(res["controls"]), 10)
        self.assertIn("prompt injection", res["surface"])
        self.assertGreaterEqual(res["score"], 0)
        self.assertLessEqual(res["score"], 100)

    def test_ai_findings_reference_llm(self):
        res = ai_ml.ai_security()
        for f in res["findings"]:
            self.assertTrue(f["reference"].startswith("OWASP LLM"))

    def test_ml_security_areas(self):
        res = ai_ml.ml_security()
        for area in ("training pipeline", "model registry", "feature store",
                     "drift detection", "SHAP integrity"):
            self.assertIn(area, res["areas"])
        self.assertEqual(res["open_findings"], len(res["findings"]))


class PrivacyTest(unittest.TestCase):
    def test_request_types(self):
        res = privacy.privacy_overview()
        for t in ("access", "erasure", "rectification", "portability"):
            self.assertIn(t, res["request_types"])

    def test_retention_summary(self):
        res = privacy.privacy_overview()
        self.assertTrue(res["retention"])
        for r in res["retention"]:
            self.assertIn("years", r)

    def test_sla_due(self):
        from datetime import datetime
        due = privacy.request_sla_due("access", datetime(2026, 1, 1))
        self.assertEqual((due - datetime(2026, 1, 1)).days, 30)

    def test_score_bounded(self):
        res = privacy.privacy_overview()
        self.assertGreaterEqual(res["score"], 0)
        self.assertLessEqual(res["score"], 100)


if __name__ == "__main__":
    unittest.main()
