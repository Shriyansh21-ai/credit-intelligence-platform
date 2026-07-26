import unittest

from backend.tests._banking_os_helpers import (
    client_for, fresh_session, make_user, seed_assessment, seed_rbac,
)
from backend.app.services.banking_os import scenario


POSITIONS = [
    {"ref": "A", "exposure": 10_000_000, "pd": 0.05, "lgd": 0.45},
    {"ref": "B", "exposure": 20_000_000, "pd": 0.10, "lgd": 0.50},
    {"ref": "C", "exposure": 5_000_000, "pd": 0.02, "lgd": 0.40},
]


class ScenarioCoreTest(unittest.TestCase):
    def test_expected_loss(self):
        el = scenario.expected_loss(POSITIONS)
        # 10m*.05*.45 + 20m*.1*.5 + 5m*.02*.4 = 225000 + 1000000 + 40000
        self.assertEqual(el, 1_265_000.0)

    def test_scenario_increases_loss(self):
        base = scenario.apply_scenario(POSITIONS, "base")
        stress = scenario.apply_scenario(POSITIONS, "stress")
        self.assertGreater(stress["expected_loss"], base["expected_loss"])
        self.assertGreater(stress["el_change"], 0)

    def test_monte_carlo_deterministic(self):
        a = scenario.monte_carlo(POSITIONS, draws=500, seed=7)
        b = scenario.monte_carlo(POSITIONS, draws=500, seed=7)
        self.assertEqual(a, b)
        self.assertGreaterEqual(a["var_99"], a["var_95"])
        self.assertGreaterEqual(a["max"], a["mean"])

    def test_sensitivity_monotonic(self):
        out = scenario.sensitivity(POSITIONS, factor="pd", grid=[0.5, 1.0, 2.0])
        els = [p["expected_loss"] for p in out["points"]]
        self.assertEqual(els, sorted(els))

    def test_sensitivity_bad_factor(self):
        with self.assertRaises(ValueError):
            scenario.sensitivity(POSITIONS, factor="nope")

    def test_custom_scenario(self):
        out = scenario.apply_scenario(POSITIONS, "custom", custom={"pd_mult": 5.0})
        self.assertGreater(out["expected_loss"], scenario.expected_loss(POSITIONS))


class ScenarioServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_run_plan_with_positions(self):
        out = scenario.run_plan(self.db, name="Q3 stress", positions=POSITIONS,
                                monte_carlo_draws=300)
        self.assertEqual(out["worst_case"]["scenario"], "black_swan")
        self.assertIn("monte_carlo", out)
        self.assertIn("plan_id", out)
        self.assertTrue(out["recommendations"])

    def test_run_plan_resolves_portfolio(self):
        seed_assessment(self.db, company_name="P1", probability_of_default=0.2,
                        recommended_loan_amount=10_000_000)
        out = scenario.run_plan(self.db, name="Portfolio", monte_carlo_draws=200)
        self.assertGreaterEqual(out["positions"], 1)

    def test_no_positions_raises(self):
        with self.assertRaises(ValueError):
            scenario.run_plan(self.db, name="Empty", positions=[])


class ScenarioApiTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()
        self.analyst = make_user(self.Session, "a@sc.test", "credit_analyst")

    def test_run_over_api(self):
        c = client_for(self.Session, self.analyst)
        r = c.get("/api/os/scenario/library")
        self.assertIn("black_swan", r.json()["scenarios"])
        r = c.post("/api/os/scenario/run", json={"name": "T", "positions": POSITIONS,
                                                "monte_carlo_draws": 200})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("monte_carlo", r.json())


if __name__ == "__main__":
    unittest.main()
