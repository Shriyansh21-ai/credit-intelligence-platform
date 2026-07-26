import unittest

from backend.tests._banking_os_helpers import (
    client_for, fresh_session, make_user, seed_assessment, seed_rbac,
)
from backend.app.services.banking_os import exec_center, fairness, graph_advanced
from backend.app.services.autonomous import graph as kg


# ---------------------------------------------------------------------------
# M13 — Fairness / Drift
# ---------------------------------------------------------------------------
class FairnessTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def _biased_records(self):
        recs = [{"group": "A", "approved": True} for _ in range(8)] + \
               [{"group": "A", "approved": False} for _ in range(2)] + \
               [{"group": "B", "approved": True} for _ in range(3)] + \
               [{"group": "B", "approved": False} for _ in range(7)]
        return recs

    def test_disparate_impact_flagged(self):
        out = fairness.evaluate_fairness(self._biased_records())
        self.assertFalse(out["passed"])
        self.assertLess(out["metrics"]["disparate_impact_ratio"], 0.8)
        self.assertAlmostEqual(out["metrics"]["demographic_parity_diff"], 0.5, places=3)

    def test_fair_records_pass(self):
        recs = [{"group": "A", "approved": i % 2 == 0} for i in range(10)] + \
               [{"group": "B", "approved": i % 2 == 0} for i in range(10)]
        out = fairness.evaluate_fairness(recs)
        self.assertTrue(out["passed"])

    def test_equal_opportunity_when_actuals(self):
        recs = [{"group": "A", "approved": True, "actual": True},
                {"group": "A", "approved": False, "actual": True},
                {"group": "B", "approved": True, "actual": True},
                {"group": "B", "approved": True, "actual": True}]
        out = fairness.evaluate_fairness(recs)
        self.assertIn("equal_opportunity_diff", out["metrics"])

    def test_psi_stable_vs_drift(self):
        base = [0.1 * (i % 10) for i in range(100)]
        same = list(base)
        stable = fairness.population_stability_index(base, same)
        self.assertLess(stable["psi"], 0.1)
        shifted = fairness.population_stability_index(base, [0.9 for _ in range(100)])
        self.assertGreater(shifted["psi"], stable["psi"])

    def test_run_fairness_persists(self):
        out = fairness.run_fairness(self.db, model_key="pd_model", records=self._biased_records())
        self.assertIn("run_id", out)
        hist = fairness.history(self.db, model_key="pd_model")
        self.assertEqual(len(hist), 1)

    def test_run_drift_persists(self):
        out = fairness.run_drift(self.db, model_key="pd_model",
                                 baseline=[0.1, 0.2, 0.3, 0.4], current=[0.1, 0.2, 0.3, 0.4])
        self.assertIn("psi", out)
        self.assertTrue(out["passed"])


# ---------------------------------------------------------------------------
# M1 — Advanced graph analytics
# ---------------------------------------------------------------------------
class GraphAdvancedTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def _ownership(self):
        acme = kg.upsert_entity(self.db, entity_type="company", ref="Acme", name="Acme")
        holdco = kg.upsert_entity(self.db, entity_type="company", ref="HoldCo", name="HoldCo")
        promoter = kg.upsert_entity(self.db, entity_type="promoter", ref="Promoter", name="Mr P")
        kg.add_relationship(self.db, holdco, acme, "parent_of", attributes={"ownership_pct": 100})
        kg.add_relationship(self.db, promoter, holdco, "shareholder_of", attributes={"ownership_pct": 60})
        return acme, holdco, promoter

    def test_ubo_resolution(self):
        self._ownership()
        out = graph_advanced.ultimate_beneficial_owners(self.db, "Acme")
        refs = {u["ref"]: u["effective_ownership"] for u in out["ubos"]}
        self.assertIn("Promoter", refs)
        self.assertAlmostEqual(refs["Promoter"], 0.6, places=3)

    def test_ubo_below_threshold_excluded(self):
        self._ownership()
        out = graph_advanced.ultimate_beneficial_owners(self.db, "Acme", min_fraction=0.7)
        self.assertEqual(out["ubos"], [])

    def test_connected_lending_flagged(self):
        acme = kg.upsert_entity(self.db, entity_type="company", ref="Acme", name="Acme")
        sister = kg.upsert_entity(self.db, entity_type="company", ref="Sister", name="Sister")
        promoter = kg.upsert_entity(self.db, entity_type="promoter", ref="P", name="P")
        kg.add_relationship(self.db, promoter, acme, "shareholder_of")
        kg.add_relationship(self.db, promoter, sister, "shareholder_of")
        kg.add_relationship(self.db, acme, sister, "lends_to", exposure=5_000_000)
        out = graph_advanced.connected_lending(self.db, "Acme")
        self.assertTrue(out["flag"])
        self.assertEqual(out["connected_exposure"], 5_000_000)

    def test_cross_holdings_cycle(self):
        x = kg.upsert_entity(self.db, entity_type="company", ref="X", name="X")
        y = kg.upsert_entity(self.db, entity_type="company", ref="Y", name="Y")
        kg.add_relationship(self.db, x, y, "parent_of")
        kg.add_relationship(self.db, y, x, "parent_of")
        out = graph_advanced.cross_holdings(self.db)
        self.assertGreaterEqual(out["count"], 1)

    def test_timeline(self):
        self._ownership()
        out = graph_advanced.timeline(self.db, "Acme")
        self.assertGreaterEqual(out["event_count"], 1)
        self.assertEqual(out["events"][0]["type"], "entity_created")

    def test_ubo_unknown_company(self):
        with self.assertRaises(ValueError):
            graph_advanced.ultimate_beneficial_owners(self.db, "Ghost")


# ---------------------------------------------------------------------------
# M10 — Executive Intelligence Center
# ---------------------------------------------------------------------------
class ExecCenterTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_assessment(self.db, company_name="A", probability_of_default=0.2,
                        recommended_loan_amount=10_000_000, risk_rating="B",
                        loan_recommendation="approve")
        seed_assessment(self.db, company_name="B", probability_of_default=0.03,
                        recommended_loan_amount=5_000_000, risk_rating="AA",
                        loan_recommendation="approve")

    def tearDown(self):
        self.db.close()

    def test_portfolio_metrics(self):
        m = exec_center.portfolio_metrics(self.db)
        self.assertEqual(m["obligors"], 2)
        self.assertEqual(m["total_exposure"], 15_000_000)
        self.assertIn("B", m["by_rating"])

    def test_all_personas_render(self):
        for persona in exec_center.PERSONAS:
            dash = exec_center.dashboard(self.db, persona)
            self.assertTrue(dash["cards"])
            self.assertEqual(dash["persona"], persona)

    def test_unknown_persona(self):
        with self.assertRaises(ValueError):
            exec_center.dashboard(self.db, "janitor")


class GovernanceApiTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()
        self.rm = make_user(self.Session, "rm@g.test", "risk_manager")

    def test_fairness_api(self):
        c = client_for(self.Session, self.rm)
        r = c.post("/api/os/fairness/evaluate", json={"model_key": "pd",
                   "records": [{"group": "A", "approved": True}, {"group": "B", "approved": False}]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("passed", r.json())

    def test_exec_dashboard_api(self):
        seed_assessment(self.Session(), company_name="Z", probability_of_default=0.1)
        c = client_for(self.Session, self.rm)
        r = c.get("/api/os/exec/dashboard/ceo")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["cards"])


if __name__ == "__main__":
    unittest.main()
