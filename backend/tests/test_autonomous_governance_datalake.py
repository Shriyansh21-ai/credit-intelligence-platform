import unittest

from backend.tests._autonomous_helpers import fresh_session, seed_portfolio
from backend.app.services.autonomous import governance, datalake
from backend.app.models.ml_platform import MLModel


def _make_model(db, key="xgboost", version=1, auc=0.8, production="none", approval="draft"):
    m = MLModel(model_key=key, name=f"{key} v{version}", algorithm=key, version=version,
                is_current=True, metrics={"auc": auc, "accuracy": 0.75, "ks": 0.4},
                feature_names=["f1", "f2"], report={"summary": "ok"},
                approval_status=approval, production_status=production)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


class GovernanceTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_validate_pass(self):
        m = _make_model(self.db, auc=0.8)
        res = governance.validate_model(self.db, m.id)
        self.assertEqual(res["status"], "passed")

    def test_validate_fail_low_auc(self):
        m = _make_model(self.db, auc=0.5)
        res = governance.validate_model(self.db, m.id)
        self.assertEqual(res["status"], "failed")

    def test_validate_missing_model(self):
        with self.assertRaises(ValueError):
            governance.validate_model(self.db, 9999)

    def test_approval_requires_validation(self):
        m = _make_model(self.db, auc=0.8)
        with self.assertRaises(ValueError):
            governance.approve_with_governance(self.db, m.id)

    def test_approval_after_validation(self):
        m = _make_model(self.db, auc=0.8)
        governance.validate_model(self.db, m.id)
        res = governance.approve_with_governance(self.db, m.id)
        self.assertEqual(res["approval_status"], "approved")

    def test_governance_events_recorded(self):
        m = _make_model(self.db, auc=0.8)
        governance.validate_model(self.db, m.id)
        lineage = governance.model_lineage(self.db, "xgboost")
        self.assertGreater(len(lineage["governance_events"]), 0)
        self.assertGreater(len(lineage["validations"]), 0)

    def test_champion_challenger(self):
        _make_model(self.db, key="m", version=1, auc=0.7, production="production")
        _make_model(self.db, key="m", version=2, auc=0.85)
        cc = governance.champion_challenger(self.db, "m")
        self.assertEqual(cc["verdict"], "challenger_wins")

    def test_champion_challenger_holds(self):
        _make_model(self.db, key="n", version=1, auc=0.9, production="production")
        _make_model(self.db, key="n", version=2, auc=0.7)
        cc = governance.champion_challenger(self.db, "n")
        self.assertEqual(cc["verdict"], "champion_holds")

    def test_dashboard(self):
        _make_model(self.db, auc=0.8)
        d = governance.governance_dashboard(self.db)
        self.assertEqual(d["total_versions"], 1)
        self.assertIn("xgboost", d["model_keys"])


class DataLakeTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_ingest_and_dedup(self):
        r1 = datalake.ingest(self.db, "assessments", {"company_ref": "A", "pd": 0.1})
        self.assertTrue(r1["ingested"])
        r2 = datalake.ingest(self.db, "assessments", {"company_ref": "A", "pd": 0.1})
        self.assertFalse(r2["ingested"])
        self.assertTrue(r2["duplicate"])

    def test_batch_ingest(self):
        res = datalake.ingest_batch(self.db, "predictions",
                                    [{"c": "A", "p": 1}, {"c": "B", "p": 2}],
                                    entity_key="c")
        self.assertEqual(res["ingested"], 2)

    def test_catalog_and_stats(self):
        datalake.ingest(self.db, "assessments", {"x": 1})
        cat = datalake.catalog(self.db)
        self.assertTrue(any(c["namespace"] == "assessments" for c in cat))
        st = datalake.stats(self.db)
        self.assertEqual(st["total_records"], 1)

    def test_query(self):
        datalake.ingest(self.db, "assessments", {"company_ref": "A", "pd": 0.1}, entity_ref="A")
        rows = datalake.query(self.db, "assessments", entity_ref="A")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pd"], 0.1)

    def test_aggregate_sum(self):
        datalake.ingest(self.db, "book", {"industry": "textile", "exposure": 100})
        datalake.ingest(self.db, "book", {"industry": "textile", "exposure": 50})
        datalake.ingest(self.db, "book", {"industry": "pharma", "exposure": 200})
        agg = datalake.aggregate(self.db, "book", group_by="industry", metric="exposure", agg="sum")
        self.assertEqual(agg["buckets"]["textile"], 150)
        self.assertEqual(agg["buckets"]["pharma"], 200)

    def test_aggregate_count(self):
        datalake.ingest(self.db, "book", {"industry": "textile"})
        datalake.ingest(self.db, "book", {"industry": "pharma"})
        agg = datalake.aggregate(self.db, "book", group_by="industry")
        self.assertEqual(agg["buckets"]["textile"], 1)

    def test_ingestion_adapters(self):
        seed_portfolio(self.db)
        res = datalake.run_ingestion(self.db, "assessments")
        self.assertEqual(res["ingested"], 3)

    def test_run_all_ingestion(self):
        seed_portfolio(self.db)
        res = datalake.run_all_ingestion(self.db)
        self.assertIn("assessments", res)

    def test_unknown_adapter(self):
        with self.assertRaises(ValueError):
            datalake.run_ingestion(self.db, "no_such_namespace")


if __name__ == "__main__":
    unittest.main()
