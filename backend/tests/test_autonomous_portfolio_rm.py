import unittest

from backend.tests._autonomous_helpers import fresh_session, seed_assessment, seed_portfolio
from backend.app.services.autonomous import optimization, rm, alerts


class OptimizationTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_portfolio(self.db)

    def tearDown(self):
        self.db.close()

    def test_analyze_basic(self):
        res = optimization.analyze(self.db)
        self.assertEqual(res["position_count"], 3)
        self.assertGreater(res["total_exposure"], 0)

    def test_sector_and_geo_exposure(self):
        res = optimization.analyze(self.db)
        self.assertIn("textile", res["sector_exposure"])
        self.assertIn("IN", res["geographic_exposure"])

    def test_concentration_metrics(self):
        res = optimization.analyze(self.db)
        self.assertIn("hhi", res["concentration"])
        self.assertGreater(res["concentration"]["top_name_share"], 0)

    def test_raroc_present(self):
        res = optimization.analyze(self.db)
        self.assertIn("portfolio_raroc", res)

    def test_limit_breaches_detected(self):
        # PharmaInc is 50M of ~80M book -> single-name breach
        res = optimization.analyze(self.db)
        self.assertTrue(any(b["type"] == "single_name" for b in res["limit_breaches"]))

    def test_recommendations(self):
        res = optimization.analyze(self.db)
        self.assertGreater(len(res["recommendations"]), 0)

    def test_persist(self):
        optimization.analyze(self.db, persist=True)
        self.assertEqual(len(optimization.list_runs(self.db)), 1)

    def test_custom_limits(self):
        res = optimization.analyze(self.db, constraints={"limits": {"single_name": 0.9}})
        self.assertEqual(res["concentration_limits"]["single_name"], 0.9)


class RMWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_assessment(self.db, company_name="Acme", industry="manufacturing",
                        probability_of_default=0.04, risk_rating="A",
                        liquidity_health=55, working_capital_health=50,
                        recommended_loan_amount=10000000)

    def tearDown(self):
        self.db.close()

    def test_log_interaction(self):
        i = rm.log_interaction(self.db, "Acme", "call", subject="Intro call")
        self.assertEqual(i.interaction_type, "call")
        self.assertEqual(len(rm.list_interactions(self.db, "Acme")), 1)

    def test_invalid_interaction(self):
        with self.assertRaises(ValueError):
            rm.log_interaction(self.db, "Acme", "telepathy")

    def test_identify_opportunities(self):
        opps = rm.identify_opportunities(self.db, "Acme")
        self.assertGreater(len(opps), 0)
        self.assertIn("product", opps[0])

    def test_persist_opportunities(self):
        rm.identify_opportunities(self.db, "Acme", persist=True)
        self.assertGreater(len(rm.list_opportunities(self.db, "Acme")), 0)

    def test_customer_health(self):
        h = rm.customer_health(self.db, "Acme")
        self.assertIn("health_score", h)
        self.assertIn(h["band"], ["healthy", "watch", "at_risk"])

    def test_health_penalized_by_alerts(self):
        base = rm.customer_health(self.db, "Acme")["health_score"]
        alerts.raise_alert(self.db, company_ref="Acme", category="monitoring",
                           alert_type="t", title="t", severity="high")
        after = rm.customer_health(self.db, "Acme")["health_score"]
        self.assertLess(after, base)

    def test_timeline_merges_sources(self):
        rm.log_interaction(self.db, "Acme", "meeting", subject="Review")
        alerts.raise_alert(self.db, company_ref="Acme", category="ews", alert_type="t", title="EWS")
        tl = rm.timeline(self.db, "Acme")
        kinds = {e["kind"] for e in tl}
        self.assertIn("interaction", kinds)
        self.assertIn("assessment", kinds)
        self.assertIn("alert", kinds)

    def test_next_best_action_prefers_alert(self):
        alerts.raise_alert(self.db, company_ref="Acme", category="monitoring",
                           alert_type="t", title="t", severity="critical",
                           recommended_action="Freeze exposure")
        nba = rm.next_best_action(self.db, "Acme")
        self.assertEqual(nba["source"], "alert")

    def test_workspace_aggregates(self):
        ws = rm.workspace(self.db, "Acme")
        for key in ("profile", "health", "timeline", "opportunities",
                    "recommendations", "next_best_action", "ews"):
            self.assertIn(key, ws)


if __name__ == "__main__":
    unittest.main()
