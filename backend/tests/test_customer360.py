""" Customer 360 aggregation tests (M10)."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.models.application import Application
from backend.app.services.integrations import service as import_svc
from backend.app.services.integrations.collateral import service as coll
from backend.app.services.integrations.customer360 import build_profile
from backend.tests._integrations_helpers import fresh_session, seed_configs

GSTIN = "27ABCDE1234F1Z5"


class Customer360Test(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_configs(self.db)
        self.app = Application(reference="APP-1", user_id=1, company_name="Acme Pvt Ltd",
                               industry="Manufacturing", gstin=GSTIN, pan="AAAAA1111A", status="draft")
        self.db.add(self.app)
        self.db.commit()
        self.db.refresh(self.app)

    def tearDown(self):
        self.db.close()

    def test_empty_profile_is_defensive(self):
        profile = build_profile(self.db, entity_ref="UNKNOWN")
        self.assertIsNone(profile["gst"])
        self.assertEqual(profile["completeness"]["sources_present"], 0)

    def test_profile_by_application_derives_entity(self):
        profile = build_profile(self.db, application_id=self.app.id)
        self.assertEqual(profile["entity_ref"], GSTIN)
        self.assertIsNotNone(profile["application"])

    def test_profile_aggregates_snapshots(self):
        import_svc.import_dataset(self.db, connector_key="gst", entity_ref=GSTIN, operation="get_profile")
        import_svc.import_dataset(self.db, connector_key="bureau", entity_ref=GSTIN, operation="get_business_score")
        profile = build_profile(self.db, application_id=self.app.id)
        self.assertIsNotNone(profile["gst"])
        self.assertIsNotNone(profile["bureau"])
        self.assertGreaterEqual(profile["completeness"]["sources_present"], 3)

    def test_relationship_network_from_mca(self):
        import_svc.import_bundle(self.db, connector_key="mca", entity_ref=GSTIN,
                                 operations=["get_director_network", "get_company_relationships"])
        profile = build_profile(self.db, application_id=self.app.id)
        net = profile["relationship_network"]
        self.assertGreaterEqual(net["node_count"], 1)

    def test_collateral_included(self):
        coll.create_collateral(self.db, collateral_type="real_estate", description="Plant",
                               market_value=5_000_000, loan_amount=2_000_000, application_id=self.app.id)
        profile = build_profile(self.db, application_id=self.app.id)
        self.assertEqual(len(profile["collateral"]["items"]), 1)

    def test_timeline_has_events(self):
        profile = build_profile(self.db, application_id=self.app.id)
        self.assertIsInstance(profile["timeline"], list)
        self.assertTrue(any(e["type"] == "application_created" for e in profile["timeline"]))


if __name__ == "__main__":
    unittest.main()
