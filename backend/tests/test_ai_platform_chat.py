""" M9 — Conversational AI tests."""

import unittest

from backend.tests._ai_platform_helpers import (
    client_for, fresh_session, make_user, seed_assessment, seed_rbac,
)


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        seed_assessment(db, company_name="AcmeCorp", industry="pharma",
                        enterprise_credit_score=760, probability_of_default=0.03,
                        risk_rating="AA",
                        engine_input={"revenue": 300, "net_margin": 0.14,
                                      "current_ratio": 1.8, "debt_to_equity": 0.9,
                                      "operating_cash_flow": 70})
        db.close()
        self.analyst = make_user(self.Session, "sa@x.com", "senior_analyst")
        self.viewer = make_user(self.Session, "v@x.com", "viewer")

    def _conv(self, c, bindings=None):
        return c.post("/api/aip/chat/conversations",
                      json={"title": "T", "bindings": bindings or {}}).json()["conversation_id"]

    def test_answer_includes_evidence(self):
        c = client_for(self.Session, self.analyst)
        cid = self._conv(c, {"company_ref": "AcmeCorp"})
        r = c.post("/api/aip/chat/ask", json={"conversation_id": cid,
                                              "message": "What is the credit rating and PD?"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["evidence"])  # always includes evidence
        self.assertTrue(body["grounded"])
        self.assertGreater(body["confidence"], 0.0)

    def test_intent_classification(self):
        c = client_for(self.Session, self.analyst)
        cid = self._conv(c, {"company_ref": "AcmeCorp"})
        r = c.post("/api/aip/chat/ask", json={"conversation_id": cid,
                                              "message": "are there any fraud red flags?"})
        self.assertEqual(r.json()["intent"], "fraud")

    def test_rag_backed_answer_with_citations(self):
        c = client_for(self.Session, self.analyst)
        c.post("/api/aip/rag/sources", json={"key": "rbi", "name": "RBI", "source_type": "rbi_circular"})
        c.post("/api/aip/rag/documents", json={"title": "NPA", "source_key": "rbi",
                                               "text": "An account is classified as an NPA when overdue beyond 90 days."})
        cid = self._conv(c)
        r = c.post("/api/aip/chat/ask", json={"conversation_id": cid,
                                              "message": "When does an account become an NPA under RBI rules?"})
        body = r.json()
        self.assertEqual(body["intent"], "regulation")
        self.assertTrue(body["citations"])

    def test_conversation_persistence(self):
        c = client_for(self.Session, self.analyst)
        cid = self._conv(c, {"company_ref": "AcmeCorp"})
        c.post("/api/aip/chat/ask", json={"conversation_id": cid, "message": "hello"})
        detail = c.get(f"/api/aip/chat/conversations/{cid}").json()
        self.assertEqual(len(detail["messages"]), 2)  # user + assistant
        self.assertTrue(c.get("/api/aip/chat/conversations").json())

    def test_rbac(self):
        c = client_for(self.Session, self.viewer)
        r = c.post("/api/aip/chat/conversations", json={"title": "x"})
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
