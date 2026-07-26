import unittest

from backend.tests._banking_os_helpers import (
    client_for, fresh_session, make_user, seed_rbac,
)
from backend.app.services.banking_os import workflow_studio as wf


LOAN_WF = {
    "nodes": [
        {"id": "start", "type": "start", "name": "Intake"},
        {"id": "score", "type": "task", "name": "Score"},
        {"id": "gate", "type": "decision", "name": "PD gate"},
        {"id": "auto", "type": "automation", "name": "Auto-approve", "config": {"action": "approve"}},
        {"id": "review", "type": "approval", "name": "Manual review"},
        {"id": "ok", "type": "end", "name": "Approved"},
        {"id": "no", "type": "end", "name": "Declined"},
    ],
    "edges": [
        {"from": "start", "to": "score"},
        {"from": "score", "to": "gate"},
        {"from": "gate", "to": "auto", "condition": {"field": "pd", "op": "lt", "value": 0.1}},
        {"from": "gate", "to": "review", "condition": {"field": "pd", "op": "lt", "value": 0.3}},
        {"from": "gate", "to": "no", "default": True},
        {"from": "auto", "to": "ok"},
        {"from": "review", "to": "ok", "condition": {"field": "approved", "op": "eq", "value": True}},
    ],
}


class WorkflowEngineTest(unittest.TestCase):
    def test_validate_good_graph(self):
        self.assertEqual(wf.validate_graph(LOAN_WF), [])

    def test_validate_missing_start(self):
        problems = wf.validate_graph({"nodes": [{"id": "e", "type": "end"}], "edges": []})
        self.assertTrue(any("start" in p for p in problems))

    def test_validate_bad_edge(self):
        g = {"nodes": [{"id": "start", "type": "start"}, {"id": "e", "type": "end"}],
             "edges": [{"from": "start", "to": "ghost"}]}
        self.assertTrue(any("unknown node" in p for p in wf.validate_graph(g)))

    def test_auto_approve_path(self):
        out = wf.execute_graph(LOAN_WF, {"pd": 0.05})
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["path"][-1], "ok")
        self.assertIn("auto", out["path"])

    def test_decline_default_path(self):
        out = wf.execute_graph(LOAN_WF, {"pd": 0.5})
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["path"][-1], "no")

    def test_approval_waits(self):
        out = wf.execute_graph(LOAN_WF, {"pd": 0.2})
        self.assertEqual(out["status"], "waiting")
        self.assertEqual(out["current_node"], "review")

    def test_loop_guard(self):
        loop = {"nodes": [{"id": "start", "type": "start"}, {"id": "a", "type": "task"},
                          {"id": "end", "type": "end"}],
                "edges": [{"from": "start", "to": "a"}, {"from": "a", "to": "start"}]}
        out = wf.execute_graph(loop, {})
        self.assertEqual(out["status"], "failed")


class WorkflowServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_create_validates(self):
        with self.assertRaises(ValueError):
            wf.create_definition(self.db, key="bad", name="Bad",
                                 graph={"nodes": [], "edges": []})

    def test_versioning(self):
        d1 = wf.create_definition(self.db, key="loan", name="Loan", graph=LOAN_WF)
        d2 = wf.create_definition(self.db, key="loan", name="Loan v2", graph=LOAN_WF)
        self.assertEqual(d1.version, 1)
        self.assertEqual(d2.version, 2)

    def test_run_and_resume(self):
        wf.create_definition(self.db, key="loan", name="Loan", graph=LOAN_WF, publish=True)
        run = wf.run(self.db, key="loan", context={"pd": 0.2}, subject_ref="Acme")
        self.assertEqual(run["status"], "waiting")
        resumed = wf.resume(self.db, run["run_id"], context_update={"approved": True})
        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(resumed["path"][-1], "ok")

    def test_run_unknown_raises(self):
        with self.assertRaises(ValueError):
            wf.run(self.db, key="nope", context={})


class WorkflowApiTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()
        self.rm = make_user(self.Session, "rm@w.test", "risk_manager")

    def test_design_and_run(self):
        c = client_for(self.Session, self.rm)
        r = c.post("/api/os/workflow/validate", json={"graph": LOAN_WF})
        self.assertTrue(r.json()["valid"])
        c.post("/api/os/workflow/definitions",
               json={"key": "loan", "name": "Loan", "graph": LOAN_WF, "publish": True})
        r = c.post("/api/os/workflow/run", json={"key": "loan", "context": {"pd": 0.05}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "completed")


if __name__ == "__main__":
    unittest.main()
