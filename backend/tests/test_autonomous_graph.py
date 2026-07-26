import unittest

from backend.tests._autonomous_helpers import fresh_session, seed_assessment
from backend.app.services.autonomous import graph


class KnowledgeGraphTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def _triangle(self):
        c = graph.upsert_entity(self.db, entity_type="company", ref="Acme", name="Acme", risk_score=60)
        d = graph.upsert_entity(self.db, entity_type="director", ref="Jane", name="Jane", risk_score=10)
        s = graph.upsert_entity(self.db, entity_type="subsidiary", ref="AcmeSub", name="AcmeSub", risk_score=40)
        graph.add_relationship(self.db, c, d, "director_of")
        graph.add_relationship(self.db, c, s, "subsidiary_of", exposure=1000000)
        return c, d, s

    def test_upsert_is_idempotent(self):
        a = graph.upsert_entity(self.db, entity_type="company", ref="Acme", name="Acme")
        b = graph.upsert_entity(self.db, entity_type="company", ref="Acme", name="Acme Corp")
        self.assertEqual(a.id, b.id)
        self.assertEqual(b.name, "Acme Corp")

    def test_upsert_requires_ref(self):
        with self.assertRaises(ValueError):
            graph.upsert_entity(self.db, entity_type="company", ref="")

    def test_add_relationship_idempotent(self):
        c, d, _ = self._triangle()
        r1 = graph.add_relationship(self.db, c, d, "director_of")
        self.assertEqual(graph.stats(self.db)["relationships"], 2)

    def test_stats(self):
        self._triangle()
        st = graph.stats(self.db)
        self.assertEqual(st["entities"], 3)
        self.assertEqual(st["relationships"], 2)
        self.assertIn("company", st["by_entity_type"])

    def test_connected_entities(self):
        c, d, s = self._triangle()
        conn = graph.connected_entities(self.db, c.id, max_depth=2)
        refs = {x["ref"] for x in conn}
        self.assertIn("Jane", refs)
        self.assertIn("AcmeSub", refs)

    def test_connected_exposure(self):
        c, d, s = self._triangle()
        exp = graph.connected_exposure(self.db, c.id)
        self.assertGreater(exp["connected_exposure"], 0)
        self.assertGreaterEqual(exp["direct_exposure"], 1000000 * 0.9 - 1)

    def test_relationship_score(self):
        c, d, s = self._triangle()
        score = graph.relationship_score(self.db, c.id, d.id)
        self.assertTrue(score["connected"])
        self.assertEqual(score["distance"], 1)
        # unrelated node
        far = graph.upsert_entity(self.db, entity_type="company", ref="Far", name="Far")
        self.assertFalse(graph.relationship_score(self.db, c.id, far.id)["connected"])

    def test_entity_similarity(self):
        c1 = graph.upsert_entity(self.db, entity_type="company", ref="C1", name="C1")
        c2 = graph.upsert_entity(self.db, entity_type="company", ref="C2", name="C2")
        shared = graph.upsert_entity(self.db, entity_type="director", ref="Shared", name="Shared")
        graph.add_relationship(self.db, c1, shared, "director_of")
        graph.add_relationship(self.db, c2, shared, "director_of")
        sim = graph.entity_similarity(self.db, c1.id)
        self.assertTrue(any(s["ref"] == "C2" for s in sim))

    def test_propagate_risk(self):
        c, d, s = self._triangle()
        result = graph.propagate_risk(self.db, iterations=3)
        self.assertEqual(len(result), 3)
        # director connected to high-risk company should gain propagated risk
        self.assertGreater(result[d.id], 10)

    def test_network_payload(self):
        c, d, s = self._triangle()
        net = graph.network(self.db)
        self.assertEqual(net["node_count"], 3)
        self.assertEqual(net["edge_count"], 2)
        ego = graph.network(self.db, root_id=c.id, max_depth=1)
        self.assertGreaterEqual(ego["node_count"], 3)

    def test_seed_from_assessment(self):
        a = seed_assessment(self.db, company_name="SeedCo", industry="textile",
                            probability_of_default=0.1, enterprise_credit_score=600,
                            risk_rating="BB")
        node = graph.seed_from_assessment(self.db, a)
        self.assertEqual(node.entity_type, "company")
        self.assertIsNotNone(node.risk_score)
        # sector + region created
        st = graph.stats(self.db)
        self.assertIn("sector", st["by_entity_type"])

    def test_ingest_network(self):
        res = graph.ingest_network(self.db, "BankCo", [
            {"entity_type": "director", "ref": "D1", "name": "D1", "rel_type": "director_of"},
            {"entity_type": "supplier", "ref": "S1", "name": "S1", "rel_type": "supplies", "exposure": 5000},
        ])
        self.assertEqual(res["entities"], 2)
        self.assertEqual(res["relationships"], 2)

    def test_traverse_respects_depth(self):
        c, d, s = self._triangle()
        view = graph.load_view(self.db)
        reached = graph.traverse(view, c.id, max_depth=1)
        self.assertEqual(reached[c.id]["depth"], 0)
        self.assertTrue(all(v["depth"] <= 1 for v in reached.values()))


if __name__ == "__main__":
    unittest.main()
