import unittest

from backend.tests._autonomous_helpers import (
    fresh_session, seed_rbac, make_user, client_for, seed_portfolio,
)


class AutonomousApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.Session = fresh_session()
        db = cls.Session()
        seed_rbac(db)
        seed_portfolio(db)
        db.close()
        cls.rm_uid = make_user(cls.Session, "rm@x.com", "risk_manager")
        cls.analyst_uid = make_user(cls.Session, "an@x.com", "credit_analyst")
        cls.viewer_uid = make_user(cls.Session, "v@x.com", "viewer")
        cls.rm = client_for(cls.Session, cls.rm_uid)
        cls.analyst = client_for(cls.Session, cls.analyst_uid)
        cls.viewer = client_for(cls.Session, cls.viewer_uid)

    # -- Knowledge graph -----------------------------------------------------
    def test_graph_crud_and_network(self):
        r = self.rm.post("/api/ai/graph/entities",
                         json={"entity_type": "company", "ref": "GCo", "name": "GCo", "risk_score": 50})
        self.assertEqual(r.status_code, 200)
        cid = r.json()["id"]
        r2 = self.rm.post("/api/ai/graph/entities",
                          json={"entity_type": "director", "ref": "GD", "name": "GD"})
        did = r2.json()["id"]
        r3 = self.rm.post("/api/ai/graph/relationships",
                          json={"source_id": cid, "target_id": did, "rel_type": "director_of"})
        self.assertEqual(r3.status_code, 200)
        net = self.rm.get("/api/ai/graph/network").json()
        self.assertGreaterEqual(net["node_count"], 2)

    def test_graph_stats_view_permission(self):
        self.assertEqual(self.analyst.get("/api/ai/graph/stats").status_code, 200)

    def test_graph_manage_denied_for_viewer(self):
        r = self.viewer.post("/api/ai/graph/entities",
                             json={"entity_type": "company", "ref": "Z", "name": "Z"})
        self.assertEqual(r.status_code, 403)

    # -- Monitoring ----------------------------------------------------------
    def test_monitoring_run(self):
        r = self.rm.post("/api/ai/monitoring/run", json={
            "company_ref": "TextileCo",
            "observations": {"mca": {"auditor_resigned": True}}})
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.json()["signal_count"], 0)

    def test_monitoring_sources(self):
        self.assertEqual(self.analyst.get("/api/ai/monitoring/sources").status_code, 200)

    # -- EWS -----------------------------------------------------------------
    def test_ews_evaluate(self):
        r = self.analyst.post("/api/ai/ews/evaluate",
                              json={"company_ref": "TextileCo", "context": {"director_changes": 2}})
        self.assertEqual(r.status_code, 200)
        self.assertIn("ews_band", r.json())

    # -- Alerts --------------------------------------------------------------
    def test_alerts_list_and_summary(self):
        self.rm.post("/api/ai/monitoring/run", json={
            "company_ref": "TextileCo", "observations": {"mca": {"auditor_resigned": True}}})
        self.assertEqual(self.analyst.get("/api/ai/alerts").status_code, 200)
        self.assertEqual(self.analyst.get("/api/ai/alerts/summary").status_code, 200)

    # -- Copilot -------------------------------------------------------------
    def test_copilot_ask(self):
        r = self.analyst.post("/api/ai/copilot/ask",
                              json={"question": "explain assessment", "company_ref": "PharmaInc"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["provider"], "local")

    def test_copilot_provider_status(self):
        self.assertEqual(self.analyst.get("/api/ai/copilot/provider").status_code, 200)

    # -- Simulation ----------------------------------------------------------
    def test_simulation_run(self):
        r = self.analyst.post("/api/ai/simulation/run",
                              json={"shocks": {"revenue_drop": 0.3}, "company_ref": "PharmaInc"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("delta", r.json())

    def test_simulation_scenarios(self):
        self.assertEqual(self.analyst.get("/api/ai/simulation/scenarios").status_code, 200)

    # -- Stress --------------------------------------------------------------
    def test_stress_run(self):
        r = self.rm.post("/api/ai/stress/run", json={"scenario": "severe", "scope": "portfolio"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["position_count"], 3)

    def test_stress_denied_for_viewer(self):
        self.assertEqual(self.viewer.post("/api/ai/stress/run", json={}).status_code, 403)

    # -- Portfolio -----------------------------------------------------------
    def test_portfolio_optimize(self):
        r = self.rm.post("/api/ai/portfolio/optimize", json={})
        self.assertEqual(r.status_code, 200)
        self.assertIn("portfolio_raroc", r.json())

    def test_portfolio_optimize_denied_analyst(self):
        # credit_analyst does not have portfolio.optimize
        self.assertEqual(self.analyst.post("/api/ai/portfolio/optimize", json={}).status_code, 403)

    # -- RM ------------------------------------------------------------------
    def test_rm_workspace(self):
        r = self.rm.get("/api/ai/rm/workspace/PharmaInc")
        self.assertEqual(r.status_code, 200)
        self.assertIn("next_best_action", r.json())

    def test_rm_interaction(self):
        r = self.rm.post("/api/ai/rm/interactions",
                         json={"company_ref": "PharmaInc", "interaction_type": "call",
                               "subject": "call1"})
        self.assertEqual(r.status_code, 200)

    # -- Command -------------------------------------------------------------
    def test_command_dashboard(self):
        r = self.rm.get("/api/ai/command/dashboard/ceo")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["persona"], "ceo")

    def test_command_denied_viewer(self):
        self.assertEqual(self.viewer.get("/api/ai/command/dashboard/ceo").status_code, 403)

    # -- NLQ -----------------------------------------------------------------
    def test_nlq_query(self):
        r = self.analyst.post("/api/ai/nlq/query", json={"question": "top borrowers by exposure"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["rows"][0]["company_ref"], "PharmaInc")

    # -- Recommendations -----------------------------------------------------
    def test_recommendations_generate(self):
        r = self.analyst.post("/api/ai/recommendations/generate", json={"company_ref": "TextileCo"})
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.json()["recommendations"]), 0)

    # -- Workflow ------------------------------------------------------------
    def test_workflow_plan(self):
        r = self.analyst.post("/api/ai/workflow/plan", json={"company_ref": "TextileCo"})
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.json()["actions"]), 0)

    def test_workflow_run_requires_act(self):
        # analyst has recommendations.act
        r = self.analyst.post("/api/ai/workflow/run",
                              json={"company_ref": "TextileCo", "mode": "proposed"})
        self.assertEqual(r.status_code, 200)

    # -- Governance ----------------------------------------------------------
    def test_governance_dashboard(self):
        self.assertEqual(self.rm.get("/api/ai/governance/dashboard").status_code, 200)

    def test_governance_manage_denied_analyst(self):
        # credit_analyst lacks governance.manage
        r = self.analyst.post("/api/ai/governance/models/1/validate", json={})
        self.assertEqual(r.status_code, 403)

    # -- Data lake -----------------------------------------------------------
    def test_datalake_ingest_and_catalog(self):
        r = self.rm.post("/api/ai/datalake/ingest",
                         json={"namespace": "assessments", "content": {"c": "A", "pd": 0.1}})
        self.assertEqual(r.status_code, 200)
        cat = self.rm.get("/api/ai/datalake/catalog")
        self.assertEqual(cat.status_code, 200)

    def test_datalake_view_denied_viewer(self):
        self.assertEqual(self.viewer.get("/api/ai/datalake/catalog").status_code, 403)


if __name__ == "__main__":
    unittest.main()
