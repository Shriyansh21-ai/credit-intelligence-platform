""" M1 — Enterprise RAG platform tests."""

import unittest

from backend.tests._ai_platform_helpers import (
    client_for, fresh_session, make_user, seed_rbac,
)

POLICY = (
    "Working capital facilities must maintain a minimum current ratio of 1.2. "
    "Debt service coverage ratio should exceed 1.5 for term loans. "
    "The bank requires collateral coverage of at least 1.4 times the exposure "
    "for sub-investment grade borrowers."
)
CIRCULAR = (
    "The Reserve Bank of India mandates that banks classify an account as a "
    "non-performing asset when interest or principal remains overdue for more "
    "than 90 days. Provisioning norms escalate with the age of the NPA."
)


class RagTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()
        self.analyst = make_user(self.Session, "sa@x.com", "senior_analyst")
        self.viewer = make_user(self.Session, "v@x.com", "viewer")

    def _ingest_corpus(self, c):
        c.post("/api/aip/rag/sources", json={"key": "policies", "name": "Credit Policies",
                                              "source_type": "credit_policy"})
        c.post("/api/aip/rag/sources", json={"key": "rbi", "name": "RBI Circulars",
                                              "source_type": "rbi_circular"})
        c.post("/api/aip/rag/documents", json={"title": "WC Policy 2026", "text": POLICY,
                                                "source_key": "policies", "external_id": "wc-2026"})
        c.post("/api/aip/rag/documents", json={"title": "NPA Norms", "text": CIRCULAR,
                                               "source_key": "rbi", "external_id": "npa"})

    def test_source_and_ingest(self):
        c = client_for(self.Session, self.analyst)
        self._ingest_corpus(c)
        srcs = c.get("/api/aip/rag/sources").json()
        self.assertEqual(len(srcs), 2)
        docs = c.get("/api/aip/rag/documents").json()
        self.assertEqual(len(docs), 2)
        self.assertTrue(all(d["chunk_count"] >= 1 for d in docs))

    def test_hybrid_search_relevance(self):
        c = client_for(self.Session, self.analyst)
        self._ingest_corpus(c)
        r = c.post("/api/aip/rag/search", json={"query": "what current ratio is required for working capital"})
        self.assertEqual(r.status_code, 200)
        hits = r.json()["hits"]
        self.assertTrue(hits)
        # The working-capital policy chunk must outrank the NPA circular.
        self.assertEqual(hits[0]["source_type"], "credit_policy")

    def test_metadata_filter_isolation(self):
        c = client_for(self.Session, self.analyst)
        self._ingest_corpus(c)
        r = c.post("/api/aip/rag/search", json={"query": "npa 90 days overdue",
                                                "source_types": ["rbi_circular"]})
        hits = r.json()["hits"]
        self.assertTrue(hits)
        self.assertTrue(all(h["source_type"] == "rbi_circular" for h in hits))

    def test_answer_has_citations_and_confidence(self):
        c = client_for(self.Session, self.analyst)
        self._ingest_corpus(c)
        r = c.post("/api/aip/rag/answer", json={"question": "When is an account classified as NPA?"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["citations"])
        self.assertGreater(body["confidence"], 0.0)
        self.assertTrue(body["grounded"])
        self.assertIn("query_id", body)

    def test_document_versioning(self):
        c = client_for(self.Session, self.analyst)
        c.post("/api/aip/rag/sources", json={"key": "policies", "name": "P",
                                             "source_type": "credit_policy"})
        r1 = c.post("/api/aip/rag/documents", json={"title": "P v1", "text": POLICY,
                                                    "source_key": "policies", "external_id": "p"})
        self.assertEqual(r1.json()["version"], 1)
        # Re-ingest identical content → idempotent (same version).
        r_same = c.post("/api/aip/rag/documents", json={"title": "P v1", "text": POLICY,
                                                        "source_key": "policies", "external_id": "p"})
        self.assertEqual(r_same.json()["version"], 1)
        # New content supersedes → version 2, only current doc listed.
        r2 = c.post("/api/aip/rag/documents", json={"title": "P v2", "text": POLICY + " Updated 2026.",
                                                    "source_key": "policies", "external_id": "p"})
        self.assertEqual(r2.json()["version"], 2)
        self.assertEqual(r2.json()["lineage"]["previous_version"], 1)
        docs = c.get("/api/aip/rag/documents").json()
        self.assertEqual(len(docs), 1)  # only current

    def test_rbac_enforced(self):
        c = client_for(self.Session, self.viewer)
        # viewer lacks aip.rag.manage
        r = c.post("/api/aip/rag/sources", json={"key": "x", "name": "X", "source_type": "other"})
        self.assertEqual(r.status_code, 403)

    def test_stats(self):
        c = client_for(self.Session, self.analyst)
        self._ingest_corpus(c)
        s = c.get("/api/aip/rag/stats").json()
        self.assertEqual(s["documents"], 2)
        self.assertGreaterEqual(s["vectors"], 2)
        self.assertTrue(s["embedder"]["offline_default"])


if __name__ == "__main__":
    unittest.main()
