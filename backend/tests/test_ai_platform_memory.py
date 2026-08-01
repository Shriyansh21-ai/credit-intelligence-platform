""" M3 — Long-term memory tests."""

import unittest

from backend.tests._ai_platform_helpers import (
    client_for, fresh_session, make_user, seed_rbac,
)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()
        self.analyst = make_user(self.Session, "sa@x.com", "senior_analyst")
        self.viewer = make_user(self.Session, "v@x.com", "viewer")

    def test_write_and_recall(self):
        c = client_for(self.Session, self.analyst)
        c.post("/api/aip/memory/write", json={
            "content": "AcmeCorp defaulted on a working capital loan in 2021 due to a liquidity crunch.",
            "memory_type": "banking_case", "scope": "customer", "scope_ref": "AcmeCorp",
            "importance": 0.9})
        c.post("/api/aip/memory/write", json={
            "content": "The RM prefers quarterly review meetings with AcmeCorp.",
            "memory_type": "episodic", "scope": "customer", "scope_ref": "AcmeCorp",
            "importance": 0.3})
        r = c.post("/api/aip/memory/recall", json={
            "query": "did AcmeCorp ever default on a loan?",
            "scope": "customer", "scope_ref": "AcmeCorp"})
        self.assertEqual(r.status_code, 200)
        mems = r.json()["memories"]
        self.assertTrue(mems)
        self.assertIn("default", mems[0]["content"].lower())

    def test_scope_isolation(self):
        c = client_for(self.Session, self.analyst)
        c.post("/api/aip/memory/write", json={"content": "Customer A note", "scope": "customer",
                                              "scope_ref": "A"})
        c.post("/api/aip/memory/write", json={"content": "Customer B note", "scope": "customer",
                                              "scope_ref": "B"})
        r = c.post("/api/aip/memory/recall", json={"query": "note", "scope": "customer",
                                                   "scope_ref": "A"})
        mems = r.json()["memories"]
        self.assertTrue(all(m["scope_ref"] == "A" for m in mems))

    def test_graph_link_and_neighbors(self):
        c = client_for(self.Session, self.analyst)
        m1 = c.post("/api/aip/memory/write", json={"content": "Parent company GlobalHold"}).json()["memory_id"]
        m2 = c.post("/api/aip/memory/write", json={"content": "Subsidiary AcmeCorp"}).json()["memory_id"]
        c.post("/api/aip/memory/link", json={"memory_id": m1, "related_id": m2})
        nb = c.get(f"/api/aip/memory/neighbors/{m1}").json()["neighbors"]
        self.assertTrue(any(n["memory_id"] == m2 for n in nb))

    def test_summarize(self):
        c = client_for(self.Session, self.analyst)
        for i in range(3):
            c.post("/api/aip/memory/write", json={"content": f"Fact {i} about the committee",
                                                  "scope": "committee", "scope_ref": "C1",
                                                  "importance": 0.5 + i * 0.1})
        r = c.post("/api/aip/memory/summarize", json={"scope": "committee", "scope_ref": "C1"})
        self.assertEqual(r.json()["memory_count"], 3)
        self.assertIn("Summary", r.json()["summary"])

    def test_forgetting(self):
        c = client_for(self.Session, self.analyst)
        c.post("/api/aip/memory/write", json={"content": "trivial low-value note",
                                              "importance": 0.05, "decay": 0.5})
        c.post("/api/aip/memory/write", json={"content": "critical high-value note",
                                              "importance": 0.95, "decay": 0.0})
        r = c.post("/api/aip/memory/forget", json={"threshold": 0.15})
        self.assertGreaterEqual(r.json()["forgotten"], 1)
        stats = c.get("/api/aip/memory/stats").json()
        self.assertEqual(stats["active"], 1)

    def test_rbac(self):
        c = client_for(self.Session, self.viewer)
        r = c.post("/api/aip/memory/write", json={"content": "x"})
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
