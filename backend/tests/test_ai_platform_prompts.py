""" M4 — Prompt engineering platform tests."""

import unittest

from backend.tests._ai_platform_helpers import (
    client_for, fresh_session, make_user, seed_rbac,
)


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()
        self.analyst = make_user(self.Session, "sa@x.com", "senior_analyst")
        self.viewer = make_user(self.Session, "v@x.com", "viewer")

    def _make_prompt(self, c):
        pid = c.post("/api/aip/prompts", json={"key": "memo", "name": "Memo", "task": "report"}).json()["id"]
        vid = c.post("/api/aip/prompts/versions", json={
            "prompt_id": pid,
            "template": "Write a memo for {{company}} with rating {{rating}}.",
            "system": "You are precise."}).json()["id"]
        return pid, vid

    def test_lifecycle_and_render(self):
        c = client_for(self.Session, self.analyst)
        pid, vid = self._make_prompt(c)
        # Deploy requires approval first.
        r_deploy = c.post("/api/aip/prompts/deploy", json={"prompt_id": pid, "version": 1})
        self.assertEqual(r_deploy.status_code, 400)
        c.post("/api/aip/prompts/approve", json={"version_id": vid})
        c.post("/api/aip/prompts/deploy", json={"prompt_id": pid, "version": 1})
        r = c.post("/api/aip/prompts/render", json={"key": "memo",
                                                    "variables": {"company": "AcmeCorp", "rating": "BBB"}})
        self.assertEqual(r.status_code, 200)
        self.assertIn("AcmeCorp", r.json()["text"])
        self.assertIn("BBB", r.json()["text"])

    def test_render_missing_variable_fails(self):
        c = client_for(self.Session, self.analyst)
        pid, vid = self._make_prompt(c)
        c.post("/api/aip/prompts/approve", json={"version_id": vid})
        c.post("/api/aip/prompts/deploy", json={"prompt_id": pid, "version": 1})
        r = c.post("/api/aip/prompts/render", json={"key": "memo", "variables": {"company": "X"}})
        self.assertEqual(r.status_code, 400)
        self.assertIn("rating", r.json()["detail"])

    def test_versioning_and_rollback(self):
        c = client_for(self.Session, self.analyst)
        pid, vid1 = self._make_prompt(c)
        c.post("/api/aip/prompts/approve", json={"version_id": vid1})
        c.post("/api/aip/prompts/deploy", json={"prompt_id": pid, "version": 1})
        vid2 = c.post("/api/aip/prompts/versions", json={
            "prompt_id": pid, "template": "V2 memo for {{company}} rating {{rating}}."}).json()["id"]
        c.post("/api/aip/prompts/approve", json={"version_id": vid2})
        c.post("/api/aip/prompts/deploy", json={"prompt_id": pid, "version": 2})
        r = c.post("/api/aip/prompts/render", json={"key": "memo",
                                                    "variables": {"company": "X", "rating": "A"}})
        self.assertIn("V2", r.json()["text"])
        # Rollback to v1.
        c.post("/api/aip/prompts/rollback", json={"prompt_id": pid, "version": 1})
        r = c.post("/api/aip/prompts/render", json={"key": "memo",
                                                    "variables": {"company": "X", "rating": "A"}})
        self.assertNotIn("V2", r.json()["text"])

    def test_evaluation(self):
        c = client_for(self.Session, self.analyst)
        pid, vid = self._make_prompt(c)
        r = c.post("/api/aip/prompts/evaluate", json={
            "version_id": vid,
            "dataset": [{"variables": {"company": "AcmeCorp", "rating": "BBB"},
                         "must_include": ["AcmeCorp", "BBB"]}]})
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.json()["score"], 0.7)
        self.assertTrue(r.json()["passed"])

    def test_ab_experiment(self):
        c = client_for(self.Session, self.analyst)
        pid, vid1 = self._make_prompt(c)
        c.post("/api/aip/prompts/versions", json={
            "prompt_id": pid, "template": "Alt {{company}} {{rating}}."})
        eid = c.post("/api/aip/prompts/experiments", json={
            "prompt_id": pid, "name": "memo-ab", "variant_a_version": 1,
            "variant_b_version": 2}).json()["id"]
        c.post("/api/aip/prompts/experiments/result", json={"experiment_id": eid, "variant": "a", "score": 0.9})
        c.post("/api/aip/prompts/experiments/result", json={"experiment_id": eid, "variant": "b", "score": 0.4})
        r = c.post(f"/api/aip/prompts/experiments/{eid}/conclude")
        self.assertEqual(r.json()["winner"], "a")

    def test_seed_defaults(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/prompts/seed-defaults")
        self.assertIn("rag_answer", r.json()["seeded"])
        # deployed → renderable
        rr = c.post("/api/aip/prompts/render", json={"key": "credit_memo",
                                                     "variables": {"company": "X", "profile": "p"}})
        self.assertEqual(rr.status_code, 200)

    def test_rbac(self):
        c = client_for(self.Session, self.viewer)
        r = c.post("/api/aip/prompts", json={"key": "x", "name": "X"})
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
