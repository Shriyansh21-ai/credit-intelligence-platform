import unittest

from backend.tests._autonomous_helpers import fresh_session, seed_portfolio
from backend.app.services.autonomous import command, nlq, ews


class CommandCenterTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_portfolio(self.db)

    def tearDown(self):
        self.db.close()

    def test_portfolio_kpis(self):
        k = command.portfolio_kpis(self.db)
        self.assertEqual(k["companies"], 3)
        self.assertGreater(k["total_exposure"], 0)
        self.assertGreaterEqual(k["high_risk_count"], 1)

    def test_watchlist(self):
        wl = command.watchlist(self.db)
        self.assertTrue(any(w["company_ref"] == "TextileCo" for w in wl))

    def test_industry_exposure(self):
        ind = command.industry_exposure(self.db)
        self.assertGreaterEqual(len(ind), 3)
        self.assertIn("share", ind[0])

    def test_geographic_exposure(self):
        geo = command.geographic_exposure(self.db)
        self.assertTrue(any(g["region"] == "IN" for g in geo))

    def test_ceo_dashboard(self):
        d = command.dashboard(self.db, "ceo")
        self.assertEqual(d["persona"], "ceo")
        self.assertIn("growth", d)
        self.assertIsNotNone(d["generated_at"])

    def test_cro_dashboard(self):
        d = command.dashboard(self.db, "cro")
        self.assertEqual(d["persona"], "chief_risk_officer")
        self.assertIn("watchlist", d)
        self.assertIn("fraud_trends", d)

    def test_cco_dashboard(self):
        d = command.dashboard(self.db, "cco")
        self.assertIn("approvals_pipeline", d)
        self.assertIn("concentration", d)

    def test_board_dashboard(self):
        d = command.dashboard(self.db, "board")
        self.assertIn("capital_required", d)

    def test_regional_dashboard(self):
        d = command.dashboard(self.db, "regional_head", region="IN")
        self.assertEqual(d["region"], "IN")

    def test_unknown_persona(self):
        with self.assertRaises(ValueError):
            command.dashboard(self.db, "wizard")


class NLQTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_portfolio(self.db)

    def tearDown(self):
        self.db.close()

    def test_parse_covenant(self):
        p = nlq.parse("show covenant breaches", [])
        self.assertEqual(p["structured_query"]["intent"], "covenant_breaches")

    def test_parse_top_by(self):
        p = nlq.parse("top borrowers by exposure", [])
        self.assertEqual(p["structured_query"]["intent"], "top_by")
        self.assertEqual(p["structured_query"]["sort"], "exposure")

    def test_parse_deteriorated(self):
        p = nlq.parse("which customers deteriorated this month", [])
        self.assertEqual(p["structured_query"]["intent"], "deteriorated")
        self.assertEqual(p["structured_query"]["filters"]["window"], "month")

    def test_parse_risk_and_industry(self):
        p = nlq.parse("show high-risk textile companies", ["textile"])
        sq = p["structured_query"]
        self.assertEqual(sq["filters"]["risk"], "high")
        self.assertEqual(sq["filters"]["industry"], "textile")

    def test_parse_limit(self):
        p = nlq.parse("top 5 borrowers", [])
        self.assertEqual(p["structured_query"]["limit"], 5)

    def test_query_high_risk_textile(self):
        res = nlq.query(self.db, "show high-risk textile companies")
        self.assertEqual(res["intent"], "list_companies")
        self.assertTrue(all(r["industry"] == "textile" for r in res["rows"]))

    def test_query_top_borrowers(self):
        res = nlq.query(self.db, "top borrowers by exposure")
        self.assertEqual(res["rows"][0]["company_ref"], "PharmaInc")

    def test_query_improving_cash_flow(self):
        res = nlq.query(self.db, "which companies have improving cash flow")
        self.assertEqual(res["intent"], "improving_cash_flow")

    def test_query_deteriorated_uses_ews(self):
        ews.evaluate(self.db, company_ref="TextileCo", context={"auditor_resigned": True,
                     "director_changes": 3, "tax_default": True})
        res = nlq.query(self.db, "which customers deteriorated")
        self.assertGreaterEqual(res["count"], 1)

    def test_query_logged(self):
        nlq.query(self.db, "top borrowers by exposure")
        self.assertEqual(len(nlq.history(self.db)), 1)


if __name__ == "__main__":
    unittest.main()
