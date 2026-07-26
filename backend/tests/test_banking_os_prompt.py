import unittest

from backend.tests._banking_os_helpers import (
    client_for, fresh_session, make_user, seed_rbac,
)
from backend.app.services.banking_os import prompt


class PromptServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_extract_variables(self):
        v = prompt.extract_variables("Summarize {{company}} with rating {{rating}} and {{company}}")
        self.assertEqual(v, ["company", "rating"])

    def test_duplicate_key_rejected(self):
        prompt.create_template(self.db, key="memo", name="Memo")
        with self.assertRaises(ValueError):
            prompt.create_template(self.db, key="memo", name="Memo2")

    def test_add_version_autodetects_vars(self):
        t = prompt.create_template(self.db, key="memo", name="Memo")
        v = prompt.add_version(self.db, t.id, content="Credit memo for {{company}} ({{sector}})")
        self.assertEqual(v.version, 1)
        self.assertEqual(set(v.variables), {"company", "sector"})

    def test_empty_content_rejected(self):
        t = prompt.create_template(self.db, key="memo", name="Memo")
        with self.assertRaises(ValueError):
            prompt.add_version(self.db, t.id, content="   ")

    def test_deploy_requires_approval(self):
        t = prompt.create_template(self.db, key="memo", name="Memo")
        prompt.add_version(self.db, t.id, content="Hello {{name}}")
        with self.assertRaises(ValueError):
            prompt.deploy_version(self.db, t.id, 1)

    def test_approve_then_deploy(self):
        t = prompt.create_template(self.db, key="memo", name="Memo")
        prompt.add_version(self.db, t.id, content="Hello {{name}}")
        prompt.approve_version(self.db, t.id, 1, approver="boss@bank")
        t2 = prompt.deploy_version(self.db, t.id, 1)
        self.assertEqual(t2.deployed_version, 1)
        self.assertEqual(t2.status, "active")

    def test_deploy_demotes_previous(self):
        t = prompt.create_template(self.db, key="memo", name="Memo")
        prompt.add_version(self.db, t.id, content="v1 {{x}}")
        prompt.add_version(self.db, t.id, content="v2 {{x}}")
        prompt.approve_version(self.db, t.id, 1)
        prompt.deploy_version(self.db, t.id, 1)
        prompt.approve_version(self.db, t.id, 2)
        prompt.deploy_version(self.db, t.id, 2)
        v1 = prompt.get_version(self.db, t.id, 1)
        v2 = prompt.get_version(self.db, t.id, 2)
        self.assertEqual(v1.status, "approved")
        self.assertEqual(v2.status, "deployed")

    def test_render_reports_missing(self):
        t = prompt.create_template(self.db, key="memo", name="Memo")
        prompt.add_version(self.db, t.id, content="Memo for {{company}} at {{rating}}")
        out = prompt.render(self.db, t.id, variables={"company": "Acme"}, version=1)
        self.assertIn("Acme", out["rendered"])
        self.assertEqual(out["missing_variables"], ["rating"])
        self.assertFalse(out["complete"])

    def test_render_complete(self):
        t = prompt.create_template(self.db, key="memo", name="Memo")
        prompt.add_version(self.db, t.id, content="Memo for {{company}}")
        out = prompt.render(self.db, t.id, variables={"company": "Acme"}, version=1)
        self.assertTrue(out["complete"])
        self.assertEqual(out["rendered"], "Memo for Acme")

    def test_evaluate_render_completeness(self):
        t = prompt.create_template(self.db, key="memo", name="Memo")
        prompt.add_version(self.db, t.id, content="Memo {{company}} {{rating}}")
        res = prompt.evaluate(self.db, t.id, version=1, cases=[
            {"input": {"company": "A", "rating": "B"}},
            {"input": {"company": "A"}},
        ])
        self.assertEqual(res["cases"][0]["score"], 1.0)
        self.assertTrue(res["cases"][0]["passed"])
        self.assertLess(res["cases"][1]["score"], 1.0)
        self.assertFalse(res["passed"])

    def test_evaluate_overlap_mode(self):
        t = prompt.create_template(self.db, key="memo", name="Memo")
        prompt.add_version(self.db, t.id, content="x {{y}}")
        res = prompt.evaluate(self.db, t.id, version=1, cases=[
            {"input": {}, "expected": "approve the loan", "output": "we approve the loan today"},
        ])
        self.assertTrue(res["cases"][0]["passed"])
        self.assertEqual(res["cases"][0]["mode"], "overlap")


class PromptApiTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()
        self.analyst = make_user(self.Session, "a@p.test", "credit_analyst")

    def test_lifecycle_over_api(self):
        c = client_for(self.Session, self.analyst)
        tid = c.post("/api/os/prompt", json={"key": "memo", "name": "Memo",
                                            "category": "credit_memo"}).json()["id"]
        r = c.post(f"/api/os/prompt/{tid}/versions", json={"content": "Memo for {{company}}"})
        self.assertEqual(r.status_code, 200, r.text)
        c.post(f"/api/os/prompt/{tid}/versions/1/approve")
        r = c.post(f"/api/os/prompt/{tid}/versions/1/deploy")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["deployed_version"], 1)
        r = c.post(f"/api/os/prompt/{tid}/render", json={"variables": {"company": "Acme"}})
        self.assertEqual(r.json()["rendered"], "Memo for Acme")


if __name__ == "__main__":
    unittest.main()
