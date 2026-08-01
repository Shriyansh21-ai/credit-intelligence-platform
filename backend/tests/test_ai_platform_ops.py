""" M11-M14 — learning, governance, explainability, monitoring tests."""

import unittest

from backend.tests._ai_platform_helpers import (
    client_for, fresh_session, make_user, seed_assessment, seed_rbac,
)


class OpsTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        seed_assessment(db, company_name="AcmeCorp", enterprise_credit_score=770,
                        probability_of_default=0.028, risk_rating="AA",
                        engine_input={"revenue": 300, "net_margin": 0.15,
                                      "current_ratio": 1.9, "debt_to_equity": 0.8,
                                      "operating_cash_flow": 80})
        seed_assessment(db, company_name="WeakCo", enterprise_credit_score=470,
                        probability_of_default=0.2, risk_rating="B",
                        engine_input={"revenue": 60, "net_margin": -0.1,
                                      "current_ratio": 0.6, "debt_to_equity": 4.0,
                                      "operating_cash_flow": -25})
        db.close()
        self.rm = make_user(self.Session, "rm@x.com", "risk_manager")
        self.analyst = make_user(self.Session, "sa@x.com", "senior_analyst")
        self.viewer = make_user(self.Session, "v@x.com", "viewer")

    # --- M11 learning ---
    def test_feedback_and_triggers(self):
        c = client_for(self.Session, self.analyst)
        for _ in range(5):
            c.post("/api/aip/learning/feedback", json={"target_type": "prediction",
                                                       "rating": 0.1, "label": "wrong"})
        for _ in range(3):
            c.post("/api/aip/learning/signal", json={"signal_type": "default", "target_ref": "WeakCo"})
        r = c.post("/api/aip/learning/evaluate-triggers", json={})
        self.assertEqual(r.status_code, 200)
        fired = {f["trigger"] for f in r.json()["fired"]}
        self.assertIn("negative_feedback", fired)
        self.assertIn("default_signals", fired)
        self.assertTrue(r.json()["training_events"])
        stats = c.get("/api/aip/learning/stats").json()
        self.assertEqual(stats["feedback"], 5)

    # --- M12 governance ---
    def test_governance_lifecycle_and_lineage(self):
        c = client_for(self.Session, self.rm)
        aid = c.post("/api/aip/governance/assets", json={
            "asset_type": "prompt", "asset_ref": "credit_memo", "name": "Credit Memo Prompt",
            "version": "1", "lineage": {"template_hash": "abc"}}).json()["id"]
        # state machine
        self.assertEqual(c.post("/api/aip/governance/assets/transition",
                                json={"asset_id": aid, "action": "validate"}).json()["state"], "validated")
        self.assertEqual(c.post("/api/aip/governance/assets/transition",
                                json={"asset_id": aid, "action": "approve"}).json()["state"], "approved")
        self.assertEqual(c.post("/api/aip/governance/assets/transition",
                                json={"asset_id": aid, "action": "deploy"}).json()["state"], "deployed")
        # illegal transition
        bad = c.post("/api/aip/governance/assets/transition", json={"asset_id": aid, "action": "validate"})
        self.assertEqual(bad.status_code, 400)
        lin = c.get(f"/api/aip/governance/assets/{aid}/lineage").json()
        self.assertTrue(lin["reproducible"])
        self.assertGreaterEqual(len(lin["events"]), 4)  # register+validate+approve+deploy

    # --- M13 explainability ---
    def test_explain_decision(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/explain/decision", json={"company_ref": "AcmeCorp"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["decision"], "APPROVE")
        self.assertTrue(body["shap"])
        self.assertTrue(body["feature_importance"])
        self.assertTrue(body["reasoning_chain"])
        self.assertIn("low", body["confidence_interval"])
        # contributions sum roughly to logit
        s = sum(cx["contribution"] for cx in body["shap"])
        self.assertAlmostEqual(s, body["logit"], places=2)

    def test_explain_weak_has_counterfactuals(self):
        c = client_for(self.Session, self.analyst)
        body = c.post("/api/aip/explain/decision", json={"company_ref": "WeakCo"}).json()
        self.assertIn(body["decision"], ("DECLINE", "REVIEW"))
        self.assertTrue(body["counterfactuals"])

    # --- M14 monitoring ---
    def test_monitoring_run_and_dashboard(self):
        c = client_for(self.Session, self.rm)
        # Generate some evaluations to monitor.
        for _ in range(4):
            c.post("/api/aip/eval/score", json={"output_text": "x is 1.9 revenue 300",
                                                "grounding_text": "current ratio 1.9 revenue 300"})
        r = c.post("/api/aip/monitoring/run")
        self.assertEqual(r.status_code, 200)
        self.assertIn("metrics", r.json())
        dash = c.get("/api/aip/monitoring/dashboard").json()
        self.assertIn(dash["health"], ("healthy", "degraded", "critical"))

    def test_monitoring_raises_incident(self):
        c = client_for(self.Session, self.rm)
        # Hallucinated numbers → high hallucination metric → incident.
        for _ in range(4):
            c.post("/api/aip/eval/score", json={"output_text": "ratio 9.9 revenue 999999 profit 42",
                                                "grounding_text": "current ratio 1.9"})
        r = c.post("/api/aip/monitoring/run").json()
        self.assertGreaterEqual(r["incident_count"], 1)
        inc = c.get("/api/aip/monitoring/incidents", params={"status": "open"}).json()["incidents"]
        self.assertTrue(inc)
        rid = inc[0]["incident_id"]
        self.assertEqual(c.post(f"/api/aip/monitoring/incidents/{rid}/resolve").json()["status"], "resolved")

    # --- RBAC ---
    def test_rbac(self):
        c = client_for(self.Session, self.viewer)
        self.assertEqual(c.post("/api/aip/learning/feedback", json={"target_type": "x"}).status_code, 403)
        self.assertEqual(c.post("/api/aip/governance/assets", json={"asset_type": "prompt",
                                                                    "asset_ref": "x", "name": "x"}).status_code, 403)
        self.assertEqual(c.post("/api/aip/monitoring/run").status_code, 403)


if __name__ == "__main__":
    unittest.main()
