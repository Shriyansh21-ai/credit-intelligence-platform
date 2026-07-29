"""Track 2 M2 — Multi-agent AI system tests."""

import unittest

from backend.tests._ai_platform_helpers import (
    client_for, fresh_session, make_user, seed_assessment, seed_rbac,
)


class AgentsTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        # A strong borrower and a weak one.
        seed_assessment(db, company_name="StrongCo", industry="pharma",
                        enterprise_credit_score=800, probability_of_default=0.02,
                        loss_given_default=0.4, expected_loss=50000, risk_rating="AA",
                        recommended_loan_amount=50000000,
                        engine_input={"revenue": 500, "net_margin": 0.18,
                                      "current_ratio": 2.1, "debt_to_equity": 0.8,
                                      "operating_cash_flow": 120})
        seed_assessment(db, company_name="WeakCo", industry="textile",
                        enterprise_credit_score=480, probability_of_default=0.18,
                        loss_given_default=0.55, expected_loss=900000, risk_rating="B",
                        recommended_loan_amount=10000000,
                        engine_input={"revenue": 90, "net_margin": -0.05,
                                      "current_ratio": 0.8, "debt_to_equity": 3.4,
                                      "operating_cash_flow": -15})
        db.close()
        self.analyst = make_user(self.Session, "sa@x.com", "senior_analyst")
        self.viewer = make_user(self.Session, "v@x.com", "viewer")

    def test_roster_has_12_roles(self):
        c = client_for(self.Session, self.analyst)
        r = c.get("/api/aip/agents/roster")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["roles"]), 12)

    def test_plan_selects_agents(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/agents/plan", json={"goal": "assess fraud risk and compliance for a loan"})
        plan = r.json()["plan"]
        roles = {p["role"] for p in plan}
        self.assertIn("credit_analyst", roles)
        self.assertIn("risk_analyst", roles)

    def test_run_strong_borrower_approves(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/agents/run", json={"goal": "Assess creditworthiness for a term loan",
                                                "company_ref": "StrongCo"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["decision"], "APPROVE")
        self.assertTrue(body["contributions"])
        self.assertTrue(body["executive_summary"])
        self.assertGreater(body["confidence"], 0.5)

    def test_run_weak_borrower_not_approved(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/agents/run", json={"goal": "Assess creditworthiness for a term loan",
                                                "company_ref": "WeakCo",
                                                "roles": ["credit_analyst", "risk_analyst",
                                                          "fraud_investigator",
                                                          "financial_statement_expert"]})
        body = r.json()
        self.assertIn(body["decision"], ("DECLINE", "REVIEW"))
        # Fraud investigator should flag the weak financials.
        fraud = [c for c in body["contributions"] if c["role"] == "fraud_investigator"][0]
        self.assertIn(fraud["signal"], ("caution", "negative"))

    def test_run_persisted_and_fetchable(self):
        c = client_for(self.Session, self.analyst)
        rid = c.post("/api/aip/agents/run", json={"goal": "Assess StrongCo",
                                                  "company_ref": "StrongCo"}).json()["run_id"]
        got = c.get(f"/api/aip/agents/runs/{rid}")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(len(got.json()["steps"]), len(got.json()["contributions"]))
        self.assertTrue(c.get("/api/aip/agents/runs").json()["runs"])

    def test_parallel_execution(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/agents/run", json={"goal": "Full committee review",
                                                "company_ref": "StrongCo",
                                                "parallel": True})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["contributions"])

    def test_rbac_denies_viewer(self):
        c = client_for(self.Session, self.viewer)
        r = c.post("/api/aip/agents/run", json={"goal": "x", "company_ref": "StrongCo"})
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
