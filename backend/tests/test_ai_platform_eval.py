""" M5 — AI evaluation framework tests."""

import unittest

from backend.tests._ai_platform_helpers import (
    client_for, fresh_session, make_user, seed_assessment, seed_rbac,
)

GROUNDING = ("The borrower reported a current ratio of 1.4 and a debt to equity "
             "ratio of 0.9 with an expected loss of 100000.")


class EvalTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        seed_assessment(db, company_name="AcmeCorp", enterprise_credit_score=760,
                        probability_of_default=0.03)
        db.close()
        self.analyst = make_user(self.Session, "sa@x.com", "senior_analyst")
        self.viewer = make_user(self.Session, "v@x.com", "viewer")

    def test_grounded_answer_scores_high(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/eval/score", json={
            "target_type": "answer",
            "output_text": "The current ratio is 1.4 and debt to equity is 0.9, therefore liquidity is adequate.",
            "grounding_text": GROUNDING,
            "citations": [{"index": 1, "label": "financials"}]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertGreater(body["scores"]["groundedness"], 0.5)
        self.assertGreater(body["scores"]["hallucination"], 0.7)  # few hallucinations
        self.assertIn("evaluation_id", body)

    def test_hallucinated_numbers_detected(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/eval/score", json={
            "output_text": "The current ratio is 9.7 and revenue was 555000 with profit of 42.",
            "grounding_text": GROUNDING})
        body = r.json()
        # numbers 9.7, 555000, 42 are not in grounding → high hallucination_rate
        self.assertGreater(body["metrics"]["hallucination_rate"], 0.5)

    def test_consistency_metric(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/eval/score", json={
            "output_text": "Liquidity is adequate.",
            "grounding_text": GROUNDING,
            "samples": ["Liquidity is adequate and strong.", "Liquidity is adequate."]})
        self.assertGreater(r.json()["scores"]["consistency"], 0.3)

    def test_evaluate_persisted_rag_query(self):
        c = client_for(self.Session, self.analyst)
        c.post("/api/aip/rag/sources", json={"key": "p", "name": "P", "source_type": "credit_policy"})
        c.post("/api/aip/rag/documents", json={"title": "Policy", "source_key": "p",
                                               "text": "Minimum current ratio is 1.2 for working capital facilities."})
        qid = c.post("/api/aip/rag/answer", json={"question": "what is the minimum current ratio?"}).json()["query_id"]
        r = c.post(f"/api/aip/eval/rag/{qid}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("overall_score", r.json())

    def test_evaluate_agent_run(self):
        c = client_for(self.Session, self.analyst)
        rid = c.post("/api/aip/agents/run", json={"goal": "Assess AcmeCorp",
                                                  "company_ref": "AcmeCorp"}).json()["run_id"]
        r = c.post(f"/api/aip/eval/agent-run/{rid}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("grade", r.json())

    def test_summary_and_list(self):
        c = client_for(self.Session, self.analyst)
        c.post("/api/aip/eval/score", json={"output_text": "x is 1.4", "grounding_text": GROUNDING})
        s = c.get("/api/aip/eval/summary").json()
        self.assertGreaterEqual(s["count"], 1)
        self.assertTrue(c.get("/api/aip/eval/list").json()["evaluations"])

    def test_rbac(self):
        c = client_for(self.Session, self.viewer)
        r = c.post("/api/aip/eval/score", json={"output_text": "x", "grounding_text": "y"})
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
