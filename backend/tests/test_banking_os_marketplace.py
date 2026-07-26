import unittest

from backend.tests._banking_os_helpers import (
    client_for, fresh_session, make_user, seed_assessment, seed_rbac,
)
from backend.app.services.banking_os import marketplace


class MarketplacePluginTest(unittest.TestCase):
    def test_registry_has_playbook(self):
        for key in ("reject_application", "restructure_loan", "increase_collateral",
                    "reduce_exposure", "increase_pricing", "monitor_account",
                    "schedule_inspection", "recommend_covenant", "recommend_guarantee"):
            self.assertIn(key, marketplace.PLUGIN_REGISTRY)

    def test_reject_fires_on_high_pd(self):
        out = marketplace.PLUGIN_REGISTRY["reject_application"]["fn"]({"pd": 0.4})
        self.assertIsNotNone(out)
        self.assertEqual(out["action"], "reject")
        self.assertTrue(out["evidence"])

    def test_reject_silent_on_low_pd(self):
        self.assertIsNone(marketplace.PLUGIN_REGISTRY["reject_application"]["fn"]({"pd": 0.02}))

    def test_increase_collateral_gap(self):
        out = marketplace.PLUGIN_REGISTRY["increase_collateral"]["fn"](
            {"collateral_coverage": 0.5, "exposure": 1_000_000})
        self.assertEqual(out["params"]["coverage_gap"], 500_000.0)


class MarketplaceServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_seed_and_run(self):
        marketplace.seed_builtin_plugins(self.db)
        out = marketplace.run_marketplace(self.db, subject_ref="Acme",
                                          context={"pd": 0.4, "debt_to_equity": 2.5})
        actions = {r["action"] for r in out["recommendations"]}
        self.assertIn("reject", actions)
        self.assertIn("add_covenant", actions)
        # persisted
        recs = marketplace.list_recommendations(self.db, subject_ref="Acme")
        self.assertGreaterEqual(len(recs), 2)

    def test_disabled_plugin_excluded(self):
        marketplace.seed_builtin_plugins(self.db)
        marketplace.set_plugin_state(self.db, "reject_application", enabled=False)
        out = marketplace.run_marketplace(self.db, subject_ref="Acme", context={"pd": 0.4})
        self.assertNotIn("reject", {r["action"] for r in out["recommendations"]})

    def test_recommendations_sorted_by_priority(self):
        marketplace.seed_builtin_plugins(self.db)
        out = marketplace.run_marketplace(self.db, subject_ref="X",
                                          context={"pd": 0.4, "collateral_coverage": 0.5,
                                                   "exposure": 1_000_000})
        priorities = [r["priority"] for r in out["recommendations"]]
        rank = {"high": 0, "medium": 1, "low": 2}
        self.assertEqual(priorities, sorted(priorities, key=lambda p: rank[p]))

    def test_resolve_from_assessment(self):
        marketplace.seed_builtin_plugins(self.db)
        a = seed_assessment(self.db, company_name="RiskyCo", probability_of_default=0.4,
                            risk_rating="C")
        out = marketplace.run_marketplace(self.db, subject_ref="RiskyCo", assessment_id=a.id)
        self.assertIn("reject", {r["action"] for r in out["recommendations"]})

    def test_status_update(self):
        marketplace.seed_builtin_plugins(self.db)
        marketplace.run_marketplace(self.db, subject_ref="Acme", context={"pd": 0.4})
        rec = marketplace.list_recommendations(self.db, subject_ref="Acme")[0]
        updated = marketplace.set_recommendation_status(self.db, rec.id, "accepted")
        self.assertEqual(updated.status, "accepted")


class MarketplaceApiTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()
        self.rm = make_user(self.Session, "rm@m.test", "risk_manager")

    def test_seed_and_run_over_api(self):
        c = client_for(self.Session, self.rm)
        self.assertEqual(c.post("/api/os/marketplace/seed").status_code, 200)
        r = c.post("/api/os/marketplace/run", json={"subject_ref": "Acme", "context": {"pd": 0.4}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(any(x["action"] == "reject" for x in r.json()["recommendations"]))


if __name__ == "__main__":
    unittest.main()
