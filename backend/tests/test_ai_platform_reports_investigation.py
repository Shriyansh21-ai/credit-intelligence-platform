""" M6+M7 — Autonomous investigation and report generation tests."""

import unittest

from backend.tests._ai_platform_helpers import (
    client_for, fresh_session, make_user, seed_assessment, seed_rbac,
)


class ReportsInvestigationTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        seed_assessment(db, company_name="AcmeCorp", industry="pharma",
                        enterprise_credit_score=770, probability_of_default=0.028,
                        loss_given_default=0.4, expected_loss=60000, risk_rating="AA",
                        recommended_loan_amount=40000000,
                        engine_input={"revenue": 400, "net_margin": 0.15,
                                      "current_ratio": 1.9, "debt_to_equity": 0.9,
                                      "operating_cash_flow": 90})
        seed_assessment(db, company_name="RiskyCo", industry="textile",
                        enterprise_credit_score=470, probability_of_default=0.2,
                        loss_given_default=0.6, expected_loss=1200000, risk_rating="B",
                        recommended_loan_amount=8000000,
                        engine_input={"revenue": 80, "net_margin": -0.08,
                                      "current_ratio": 0.7, "debt_to_equity": 3.6,
                                      "operating_cash_flow": -20})
        db.close()
        self.analyst = make_user(self.Session, "sa@x.com", "senior_analyst")
        self.viewer = make_user(self.Session, "v@x.com", "viewer")

    # --- M7 reports ---
    def test_report_types(self):
        c = client_for(self.Session, self.analyst)
        types = c.get("/api/aip/reports/types").json()["report_types"]
        self.assertIn("credit_memo", types)
        self.assertEqual(len(types), 11)

    def test_generate_credit_memo(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/reports/generate", json={"report_type": "credit_memo",
                                                      "company_ref": "AcmeCorp"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["sections"])
        self.assertEqual(body["decision"], "APPROVE")
        self.assertTrue(body["charts"])
        self.assertGreater(body["confidence"], 0.5)
        # fetchable
        got = c.get(f"/api/aip/reports/{body['report_id']}")
        self.assertEqual(got.status_code, 200)

    def test_all_report_types_generate(self):
        c = client_for(self.Session, self.analyst)
        for rt in c.get("/api/aip/reports/types").json()["report_types"]:
            r = c.post("/api/aip/reports/generate", json={"report_type": rt,
                                                          "company_ref": "AcmeCorp"})
            self.assertEqual(r.status_code, 200, rt)
            self.assertTrue(r.json()["sections"], rt)

    def test_unknown_report_type(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/reports/generate", json={"report_type": "nope",
                                                      "company_ref": "AcmeCorp"})
        self.assertEqual(r.status_code, 400)

    # --- M6 investigation ---
    def test_investigation_full_workflow(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/investigate/run", json={"company_ref": "AcmeCorp"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["stages"], 10)
        self.assertEqual(len(body["trace"]), 10)
        self.assertIsNotNone(body["report_id"])
        self.assertTrue(body["reasoning_chain"])
        self.assertEqual(body["decision"], "APPROVE")

    def test_investigation_risky_company(self):
        c = client_for(self.Session, self.analyst)
        body = c.post("/api/aip/investigate/run", json={"company_ref": "RiskyCo"}).json()
        self.assertIn(body["decision"], ("DECLINE", "REVIEW"))
        # steps persisted + fetchable
        got = c.get(f"/api/aip/investigate/{body['investigation_id']}")
        self.assertEqual(len(got.json()["steps"]), 10)

    def test_rbac(self):
        c = client_for(self.Session, self.viewer)
        self.assertEqual(c.post("/api/aip/investigate/run", json={"company_ref": "AcmeCorp"}).status_code, 403)
        self.assertEqual(c.post("/api/aip/reports/generate", json={"report_type": "credit_memo",
                                                                   "company_ref": "AcmeCorp"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
