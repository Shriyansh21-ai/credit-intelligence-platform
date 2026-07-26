import unittest

from backend.tests._autonomous_helpers import fresh_session, seed_assessment, seed_portfolio
from backend.app.services.autonomous import simulation, stress


class SimulationTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_assessment(self.db, company_name="Acme", enterprise_credit_score=700,
                        probability_of_default=0.04, risk_rating="A",
                        recommended_loan_amount=10000000, loss_given_default=0.45)

    def tearDown(self):
        self.db.close()

    def test_available_scenarios(self):
        keys = {s["key"] for s in simulation.available_scenarios()}
        for expected in ("revenue_drop", "interest_increase", "acquisition", "merger"):
            self.assertIn(expected, keys)

    def test_revenue_drop_worsens(self):
        res = simulation.simulate(self.db, {"revenue_drop": 0.3}, company_ref="Acme")
        self.assertLess(res["delta"]["score_change"], 0)
        self.assertGreater(res["result"]["pd"], res["baseline"]["pd"])

    def test_combined_shocks(self):
        res = simulation.simulate(self.db, {"revenue_drop": 0.3, "interest_increase": 0.3},
                                  company_ref="Acme")
        self.assertLess(res["result"]["credit_score"], res["baseline"]["credit_score"])
        self.assertEqual(len(res["applied"]), 2)

    def test_rating_migration(self):
        res = simulation.simulate(self.db, {"market_recession": 1.0, "revenue_drop": 0.5},
                                  company_ref="Acme")
        self.assertGreaterEqual(res["delta"]["rating_notches"], 1)

    def test_score_clamped(self):
        res = simulation.simulate(self.db, {"revenue_drop": 1.0, "market_recession": 1.0,
                                            "interest_increase": 0.5, "customer_default": 1.0},
                                  company_ref="Acme")
        self.assertGreaterEqual(res["result"]["credit_score"], 300)

    def test_comparison_and_recommendations(self):
        res = simulation.simulate(self.db, {"revenue_drop": 0.4}, company_ref="Acme")
        self.assertEqual(len(res["comparison"]), 5)
        self.assertGreater(len(res["recommendations"]), 0)

    def test_persist_and_list(self):
        simulation.simulate(self.db, {"revenue_drop": 0.1}, company_ref="Acme")
        self.assertEqual(len(simulation.list_runs(self.db, company_ref="Acme")), 1)

    def test_no_company_uses_neutral_baseline(self):
        res = simulation.simulate(self.db, {"revenue_drop": 0.2}, persist=False)
        self.assertEqual(res["baseline"]["credit_score"], 650)


class StressTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_portfolio(self.db)

    def tearDown(self):
        self.db.close()

    def test_severe_run(self):
        res = stress.run(self.db, scenario="severe", scope="portfolio")
        self.assertEqual(res["position_count"], 3)
        self.assertGreater(res["expected_loss"]["stressed"], res["expected_loss"]["baseline"])

    def test_scenarios_ordered_by_severity(self):
        base = stress.run(self.db, scenario="base")["expected_loss"]["stressed"]
        severe = stress.run(self.db, scenario="severe")["expected_loss"]["stressed"]
        self.assertGreaterEqual(severe, base)

    def test_capital_impact(self):
        res = stress.run(self.db, scenario="severe")
        self.assertGreaterEqual(res["capital_impact"]["additional_required"], 0)

    def test_rating_migration_summary(self):
        res = stress.run(self.db, scenario="severe")
        summ = res["rating_migration_summary"]
        self.assertIn("downgraded", summ)

    def test_heatmap(self):
        res = stress.run(self.db, scenario="moderate")
        self.assertGreater(len(res["heatmap"]), 0)
        self.assertIn("loss_rate", res["heatmap"][0])

    def test_scope_company(self):
        res = stress.run(self.db, scenario="severe", scope="company", scope_ref="PharmaInc")
        self.assertEqual(res["position_count"], 1)

    def test_scope_industry(self):
        res = stress.run(self.db, scenario="severe", scope="industry", scope_ref="textile")
        self.assertEqual(res["position_count"], 1)

    def test_custom_scenario(self):
        res = stress.run(self.db, scenario="custom", custom_shocks={"revenue_drop": 0.5})
        self.assertEqual(res["shocks"], {"revenue_drop": 0.5})

    def test_compare_scenarios(self):
        cmp = stress.compare_scenarios(self.db)
        self.assertIn("base", cmp["scenarios"])
        self.assertIn("severe", cmp["scenarios"])

    def test_persist_and_list(self):
        stress.run(self.db, scenario="severe")
        self.assertEqual(len(stress.list_runs(self.db)), 1)


if __name__ == "__main__":
    unittest.main()
