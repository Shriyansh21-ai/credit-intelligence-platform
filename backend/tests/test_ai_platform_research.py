"""Track 2 M10 — AI research assistant tests."""

import unittest

from backend.tests._ai_platform_helpers import (
    client_for, fresh_session, make_user, seed_assessment, seed_rbac,
)


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        for i, (name, score, pd) in enumerate([("PharmaA", 780, 0.02), ("PharmaB", 720, 0.04),
                                               ("PharmaC", 660, 0.06)]):
            seed_assessment(db, company_name=name, industry="pharma",
                            enterprise_credit_score=score, probability_of_default=pd,
                            expected_loss=100000 * (i + 1))
        db.close()
        self.analyst = make_user(self.Session, "sa@x.com", "senior_analyst")
        self.viewer = make_user(self.Session, "v@x.com", "viewer")

    def test_types(self):
        c = client_for(self.Session, self.analyst)
        types = c.get("/api/aip/research/types").json()["research_types"]
        self.assertIn("peer_comparison", types)
        self.assertEqual(len(types), 9)

    def test_industry_benchmarking(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/research/run", json={"topic": "pharma", "research_type": "industry_benchmarking"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        stats = body["findings"]["portfolio_statistics"]
        self.assertEqual(stats["count"], 3)
        self.assertIsNotNone(stats["avg_score"])
        self.assertTrue(body["sections"])

    def test_peer_comparison_relative(self):
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/aip/research/run", json={"topic": "pharma peers",
                                                  "research_type": "peer_comparison",
                                                  "subject_ref": "PharmaA"})
        self.assertEqual(r.json()["findings"]["subject_vs_peers"], "above")

    def test_regulatory_updates_uses_rag(self):
        c = client_for(self.Session, self.analyst)
        c.post("/api/aip/rag/sources", json={"key": "rbi", "name": "RBI", "source_type": "rbi_circular"})
        c.post("/api/aip/rag/documents", json={"title": "Update", "source_key": "rbi",
                                               "text": "New provisioning norms for NPAs effective this quarter."})
        r = c.post("/api/aip/research/run", json={"topic": "provisioning norms",
                                                  "research_type": "regulatory_updates"})
        self.assertTrue(r.json()["sources"])

    def test_persistence(self):
        c = client_for(self.Session, self.analyst)
        rid = c.post("/api/aip/research/run", json={"topic": "esg", "research_type": "esg_research"}).json()["research_id"]
        self.assertEqual(c.get(f"/api/aip/research/{rid}").status_code, 200)
        self.assertTrue(c.get("/api/aip/research/list").json()["research"])

    def test_rbac(self):
        c = client_for(self.Session, self.viewer)
        r = c.post("/api/aip/research/run", json={"topic": "x"})
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
