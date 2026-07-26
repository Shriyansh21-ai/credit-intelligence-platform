import unittest

from backend.tests._banking_os_helpers import (
    client_for, fresh_session, make_user, seed_rbac,
)
from backend.app.services.banking_os import data_fabric


class ContractEvaluationTest(unittest.TestCase):
    """Pure, DB-free record evaluation."""

    SPEC = {"fields": [
        {"name": "pd", "type": "number", "nullable": False, "min": 0, "max": 1},
        {"name": "rating", "type": "string", "allowed": ["A", "B", "C"]},
        {"name": "name", "type": "string", "nullable": False},
    ], "required": ["pd", "name"]}

    def test_clean_records_score_high(self):
        recs = [{"pd": 0.1, "rating": "A", "name": "Acme"},
                {"pd": 0.4, "rating": "B", "name": "Beta"}]
        out = data_fabric.evaluate_records(self.SPEC, recs)
        self.assertEqual(out["score"], 1.0)
        self.assertEqual(out["violations"], [])

    def test_missing_required_hits_completeness(self):
        recs = [{"pd": 0.1, "rating": "A"}]  # missing name
        out = data_fabric.evaluate_records(self.SPEC, recs)
        self.assertLess(out["dimensions"]["completeness"], 1.0)
        self.assertTrue(any(v["issue"] == "missing-required" for v in out["violations"]))

    def test_out_of_range_and_allowed(self):
        recs = [{"pd": 2.0, "rating": "Z", "name": "X"}]
        out = data_fabric.evaluate_records(self.SPEC, recs)
        issues = {v["issue"] for v in out["violations"]}
        self.assertIn("above-max", issues)
        self.assertIn("not-in-allowed", issues)
        self.assertLess(out["dimensions"]["validity"], 1.0)

    def test_type_inconsistency(self):
        recs = [{"pd": 0.1, "name": "A"}, {"pd": "high", "name": "B"}]
        out = data_fabric.evaluate_records(self.SPEC, recs)
        self.assertLess(out["dimensions"]["consistency"], 1.0)

    def test_empty_records(self):
        out = data_fabric.evaluate_records(self.SPEC, [])
        self.assertEqual(out["rows_checked"], 0)


class DataFabricServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_register_upsert(self):
        d1 = data_fabric.register_dataset(self.db, name="loans", domain="credit")
        d2 = data_fabric.register_dataset(self.db, name="loans", owner="risk@bank")
        self.assertEqual(d1.id, d2.id)
        self.assertEqual(d2.owner, "risk@bank")

    def test_bad_classification(self):
        with self.assertRaises(ValueError):
            data_fabric.register_dataset(self.db, name="x", classification="ultra-secret")

    def test_lineage_and_impact(self):
        for n in ("raw_gst", "loans", "portfolio", "board_report"):
            data_fabric.register_dataset(self.db, name=n)
        data_fabric.add_lineage(self.db, dataset="loans", upstream="raw_gst")
        data_fabric.add_lineage(self.db, dataset="portfolio", upstream="loans")
        data_fabric.add_lineage(self.db, dataset="board_report", upstream="portfolio")
        graph = data_fabric.lineage_graph(self.db, "loans")
        self.assertIn("raw_gst", graph["all_upstream"])
        self.assertIn("board_report", graph["all_downstream"])
        impact = data_fabric.impact_analysis(self.db, "raw_gst")
        self.assertEqual(impact["impacted_count"], 3)
        self.assertIn("board_report", impact["impacted_datasets"])

    def test_self_lineage_rejected(self):
        with self.assertRaises(ValueError):
            data_fabric.add_lineage(self.db, dataset="a", upstream="a")

    def test_contract_versioning_supersedes(self):
        spec = {"fields": [{"name": "x", "type": "number"}]}
        c1 = data_fabric.add_contract(self.db, dataset="loans", spec=spec)
        c2 = data_fabric.add_contract(self.db, dataset="loans", spec=spec)
        self.assertEqual(c1.version, 1)
        self.assertEqual(c2.version, 2)
        latest = data_fabric.latest_contract(self.db, "loans")
        self.assertEqual(latest.version, 2)
        self.assertEqual(latest.status, "active")

    def test_bad_contract_spec(self):
        with self.assertRaises(ValueError):
            data_fabric.add_contract(self.db, dataset="x", spec={"no_fields": True})

    def test_run_quality_updates_dataset(self):
        data_fabric.register_dataset(self.db, name="loans", domain="credit")
        data_fabric.add_contract(self.db, dataset="loans", spec={
            "fields": [{"name": "pd", "type": "number", "nullable": False, "min": 0, "max": 1}],
            "required": ["pd"]})
        out = data_fabric.run_quality(self.db, dataset="loans",
                                      records=[{"pd": 0.1}, {"pd": 0.2}])
        self.assertEqual(out["score"], 1.0)
        self.assertTrue(out["passed"])
        ds = data_fabric.get_dataset(self.db, "loans")
        self.assertEqual(ds.quality_score, 1.0)
        self.assertEqual(ds.row_count, 2)

    def test_run_quality_without_contract_raises(self):
        data_fabric.register_dataset(self.db, name="loans")
        with self.assertRaises(ValueError):
            data_fabric.run_quality(self.db, dataset="loans", records=[{"x": 1}])

    def test_catalog_stats(self):
        data_fabric.register_dataset(self.db, name="a", domain="credit", classification="restricted")
        data_fabric.register_dataset(self.db, name="b", domain="risk")
        stats = data_fabric.catalog_stats(self.db)
        self.assertEqual(stats["datasets"], 2)
        self.assertEqual(stats["by_classification"]["restricted"], 1)


class DataFabricApiTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()
        self.risk = make_user(self.Session, "rm@f.test", "risk_manager")
        self.analyst = make_user(self.Session, "a@f.test", "credit_analyst")

    def test_catalog_flow(self):
        c = client_for(self.Session, self.risk)
        r = c.post("/api/os/fabric/datasets", json={"name": "loans", "domain": "credit"})
        self.assertEqual(r.status_code, 200, r.text)
        c.post("/api/os/fabric/datasets", json={"name": "portfolio"})
        c.post("/api/os/fabric/lineage", json={"dataset": "portfolio", "upstream": "loans"})
        r = c.get("/api/os/fabric/impact/loans")
        self.assertEqual(r.status_code, 200)
        self.assertIn("portfolio", r.json()["impacted_datasets"])

    def test_analyst_can_view_not_manage(self):
        admin = client_for(self.Session, self.risk)
        admin.post("/api/os/fabric/datasets", json={"name": "loans"})
        analyst = client_for(self.Session, self.analyst)
        self.assertEqual(analyst.get("/api/os/fabric/catalog").status_code, 200)
        self.assertEqual(analyst.post("/api/os/fabric/datasets",
                                      json={"name": "x"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
