import unittest

from backend.tests._banking_os_helpers import (
    client_for, fresh_session, make_user, seed_assessment, seed_rbac,
)
from backend.app.services.banking_os import search


class SearchServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def _index_corpus(self):
        search.index_document(self.db, doc_type="company", ref="TextileCo",
                              title="TextileCo Limited", body="textile manufacturer weaving cotton",
                              keywords=["textile"], numeric_fields={"score": 520, "amount": 10_000_000})
        search.index_document(self.db, doc_type="company", ref="PharmaInc",
                              title="PharmaInc", body="pharmaceutical drug maker",
                              keywords=["pharma"], numeric_fields={"score": 780, "amount": 50_000_000})
        search.index_document(self.db, doc_type="policy", ref="aml-1",
                              title="AML Screening Policy", body="anti money laundering sanctions",
                              keywords=["aml"])

    def test_index_is_idempotent_upsert(self):
        d1 = search.index_document(self.db, doc_type="company", ref="A", title="Acme")
        d2 = search.index_document(self.db, doc_type="company", ref="A", title="Acme Corp")
        self.assertEqual(d1.id, d2.id)
        self.assertEqual(d2.title, "Acme Corp")

    def test_keyword_search_ranks_match(self):
        self._index_corpus()
        out = search.search(self.db, query="textile", mode="keyword")
        self.assertGreaterEqual(out["count"], 1)
        self.assertEqual(out["results"][0]["ref"], "TextileCo")

    def test_semantic_matches_partial(self):
        self._index_corpus()
        out = search.search(self.db, query="pharmaceutical", mode="semantic")
        refs = [r["ref"] for r in out["results"]]
        self.assertIn("PharmaInc", refs)

    def test_hybrid_blends_signals(self):
        self._index_corpus()
        out = search.search(self.db, query="money laundering", mode="hybrid")
        self.assertEqual(out["results"][0]["ref"], "aml-1")
        self.assertIn("keyword", out["results"][0]["signals"])
        self.assertIn("semantic", out["results"][0]["signals"])

    def test_doc_type_filter(self):
        self._index_corpus()
        out = search.search(self.db, query="policy", doc_types=["policy"])
        self.assertTrue(all(r["doc_type"] == "policy" for r in out["results"]))

    def test_numeric_range_filter(self):
        self._index_corpus()
        out = search.search(self.db, query="", filters={"score": {"gte": 700}})
        refs = [r["ref"] for r in out["results"]]
        self.assertIn("PharmaInc", refs)
        self.assertNotIn("TextileCo", refs)

    def test_empty_query_browses(self):
        self._index_corpus()
        out = search.search(self.db, query="")
        self.assertEqual(out["count"], 3)

    def test_autocomplete_prefix(self):
        self._index_corpus()
        sugg = search.autocomplete(self.db, "pha")
        self.assertTrue(any(s["ref"] == "PharmaInc" for s in sugg))

    def test_facets(self):
        self._index_corpus()
        f = search.facets(self.db)
        self.assertEqual(f["total"], 3)
        self.assertEqual(f["by_doc_type"]["company"], 2)

    def test_history_recorded(self):
        self._index_corpus()
        search.search(self.db, query="textile", user_id=1, persist=True)
        h = search.history(self.db, user_id=1)
        self.assertEqual(len(h), 1)
        self.assertEqual(h[0]["query"], "textile")

    def test_saved_search(self):
        s = search.save_search(self.db, name="High risk", query="pd", filters={"score": {"lte": 550}},
                               user_id=1)
        saved = search.list_saved(self.db, user_id=1)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["name"], "High risk")

    def test_reindex_platform_pulls_assessments(self):
        seed_assessment(self.db, company_name="ReindexCo", industry="steel")
        counts = search.reindex_platform(self.db)
        self.assertGreaterEqual(counts.get("company", 0), 1)
        out = search.search(self.db, query="ReindexCo")
        self.assertTrue(any(r["ref"] == "ReindexCo" for r in out["results"]))


class SearchApiTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()
        self.analyst = make_user(self.Session, "a@s.test", "credit_analyst")

    def test_index_and_search_over_api(self):
        c = client_for(self.Session, self.analyst)
        c.post("/api/os/search/index", json={"doc_type": "company", "ref": "Zeta",
                                             "title": "Zeta Industries", "body": "manufacturing"})
        r = c.post("/api/os/search", json={"query": "zeta"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(any(x["ref"] == "Zeta" for x in r.json()["results"]))


if __name__ == "__main__":
    unittest.main()
