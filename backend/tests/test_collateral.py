"""Phase 7 — collateral management tests (M9)."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.services.integrations.collateral import catalog, service as coll
from backend.tests._integrations_helpers import fresh_session


class CollateralTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_catalog_haircuts(self):
        self.assertEqual(catalog.default_haircut("fixed_deposit"), 0.10)
        self.assertEqual(catalog.default_haircut("guarantee"), 0.60)
        self.assertEqual(len(catalog.catalog()), 8)

    def test_create_derives_values(self):
        item = coll.create_collateral(self.db, collateral_type="real_estate", description="Plant",
                                      market_value=10_000_000, loan_amount=6_000_000, entity_ref="E1")
        self.assertEqual(item.haircut_pct, 0.25)
        self.assertEqual(item.realizable_value, 7_500_000)
        self.assertAlmostEqual(item.ltv, 0.6)
        self.assertAlmostEqual(item.coverage_ratio, 1.25)

    def test_invalid_type(self):
        with self.assertRaises(ValueError):
            coll.create_collateral(self.db, collateral_type="gold_bar", description="x", market_value=1)

    def test_custom_haircut(self):
        item = coll.create_collateral(self.db, collateral_type="machinery", description="CNC",
                                      market_value=1_000_000, haircut_pct=0.5)
        self.assertEqual(item.realizable_value, 500_000)

    def test_revalue_appends_history(self):
        item = coll.create_collateral(self.db, collateral_type="vehicle", description="Truck",
                                      market_value=1_000_000, loan_amount=500_000, entity_ref="E1")
        coll.revalue(self.db, item.id, market_value=800_000, valuer="ABC Valuers")
        d = coll.to_dict(item, db=self.db)
        self.assertEqual(item.market_value, 800_000)
        self.assertEqual(len(d["valuations"]), 2)
        current = [v for v in d["valuations"] if v["is_current"]]
        self.assertEqual(len(current), 1)

    def test_inspection_not_found_impairs(self):
        item = coll.create_collateral(self.db, collateral_type="inventory", description="Stock",
                                      market_value=500_000, entity_ref="E1")
        coll.add_inspection(self.db, item.id, outcome="not_found")
        self.db.refresh(item)
        self.assertEqual(item.status, "impaired")

    def test_coverage_summary(self):
        coll.create_collateral(self.db, collateral_type="real_estate", description="A",
                               market_value=10_000_000, loan_amount=5_000_000, entity_ref="E9")
        coll.create_collateral(self.db, collateral_type="fixed_deposit", description="B",
                               market_value=2_000_000, loan_amount=1_000_000, entity_ref="E9")
        summary = coll.coverage_summary(self.db, entity_ref="E9")
        self.assertEqual(summary["item_count"], 2)
        self.assertEqual(summary["total_exposure"], 6_000_000)
        self.assertGreater(summary["coverage_ratio"], 0)

    def test_status_change_excluded_from_coverage(self):
        item = coll.create_collateral(self.db, collateral_type="real_estate", description="A",
                                      market_value=10_000_000, loan_amount=5_000_000, entity_ref="E10")
        coll.set_status(self.db, item.id, "released")
        summary = coll.coverage_summary(self.db, entity_ref="E10")
        self.assertEqual(summary["item_count"], 0)


if __name__ == "__main__":
    unittest.main()
