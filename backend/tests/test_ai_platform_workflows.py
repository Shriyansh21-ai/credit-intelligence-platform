""" M8 — AI workflow builder + execution engine tests."""

import unittest

from backend.tests._ai_platform_helpers import (
    client_for, fresh_session, make_user, seed_assessment, seed_rbac,
)

# A workflow: start → agent committee → condition(decision==APPROVE) →
# true: report ; false: approval gate → end
GRAPH = {
    "start": "n_start",
    "nodes": [
        {"id": "n_start", "type": "start", "next": "n_agent"},
        {"id": "n_agent", "type": "agent",
         "config": {"goal": "Assess for a term loan", "company_ref": "$input.company_ref"},
         "next": "n_cond"},
        {"id": "n_cond", "type": "condition",
         "config": {"field": "$ctx.n_agent.decision", "op": "eq", "value": "APPROVE"},
         "edges": {"true": "n_report", "false": "n_gate"}},
        {"id": "n_report", "type": "report",
         "config": {"report_type": "credit_memo", "company_ref": "$input.company_ref"},
         "next": "n_end"},
        {"id": "n_gate", "type": "approval", "config": {"auto_approve": True}, "next": "n_end"},
        {"id": "n_end", "type": "end"},
    ],
}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        seed_assessment(db, company_name="StrongCo", enterprise_credit_score=800,
                        probability_of_default=0.02, risk_rating="AA",
                        engine_input={"revenue": 400, "net_margin": 0.16,
                                      "current_ratio": 2.0, "debt_to_equity": 0.7,
                                      "operating_cash_flow": 100})
        seed_assessment(db, company_name="WeakCo", enterprise_credit_score=470,
                        probability_of_default=0.2, risk_rating="B",
                        engine_input={"revenue": 60, "net_margin": -0.1,
                                      "current_ratio": 0.6, "debt_to_equity": 4.0,
                                      "operating_cash_flow": -25})
        db.close()
        self.analyst = make_user(self.Session, "sa@x.com", "senior_analyst")
        self.viewer = make_user(self.Session, "v@x.com", "viewer")

    def test_node_types(self):
        c = client_for(self.Session, self.analyst)
        nt = c.get("/api/aip/workflows/node-types").json()["node_types"]
        self.assertIn("agent", nt)
        self.assertIn("approval", nt)

    def test_validate_rejects_bad_graph(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/workflows/validate", json={"key": "x", "name": "x",
                                                        "graph": {"start": "missing", "nodes": []}})
        self.assertFalse(r.json()["valid"])
        self.assertTrue(r.json()["errors"])

    def test_save_and_run_approve_branch(self):
        c = client_for(self.Session, self.analyst)
        wid = c.post("/api/aip/workflows", json={"key": "credit-flow", "name": "Credit Flow",
                                                 "graph": GRAPH}).json()["id"]
        r = c.post("/api/aip/workflows/run", json={"workflow_id": wid,
                                                   "input": {"company_ref": "StrongCo"}})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "completed")
        node_ids = [n["node_id"] for n in body["node_results"]]
        self.assertIn("n_report", node_ids)  # took the APPROVE branch
        self.assertNotIn("n_gate", node_ids)

    def test_run_review_branch_hits_gate(self):
        c = client_for(self.Session, self.analyst)
        c.post("/api/aip/workflows", json={"key": "credit-flow", "name": "Credit Flow", "graph": GRAPH})
        r = c.post("/api/aip/workflows/run", json={"key": "credit-flow",
                                                   "input": {"company_ref": "WeakCo"}})
        node_ids = [n["node_id"] for n in r.json()["node_results"]]
        self.assertIn("n_gate", node_ids)  # not APPROVE → approval gate

    def test_save_invalid_graph_rejected(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/workflows", json={"key": "bad", "name": "bad",
                                               "graph": {"start": "a", "nodes": [
                                                   {"id": "a", "type": "agent", "next": "ghost"}]}})
        self.assertEqual(r.status_code, 400)

    def test_rbac(self):
        c = client_for(self.Session, self.viewer)
        r = c.post("/api/aip/workflows", json={"key": "x", "name": "x", "graph": GRAPH})
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
