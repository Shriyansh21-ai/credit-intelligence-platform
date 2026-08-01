""" Admin console (M12) + analytics platform (M13)."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.services.saas import admin, analytics
from backend.app.services.saas import tenancy as tsvc
from backend.app.services.saas.billing import service as billing
from backend.tests._saas_helpers import fresh_session, seed_all


class AdminAnalyticsTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_all(self.db)
        # Two customers on different plans.
        self.org1 = tsvc.create_organization(self.db, slug="c1", name="Cust 1")
        self.org2 = tsvc.create_organization(self.db, slug="c2", name="Cust 2")
        billing.subscribe(self.db, self.org1.id, "professional")
        billing.subscribe(self.db, self.org2.id, "enterprise")
        billing.record_usage(self.db, self.org1.id, "ml_predictions", 5000)
        billing.record_usage(self.db, self.org2.id, "ocr_pages", 200)

    def tearDown(self):
        self.db.close()

    # -- analytics -----------------------------------------------------
    def test_platform_overview(self):
        ov = analytics.platform_overview(self.db)
        self.assertGreaterEqual(ov["organizations"], 3)  # default + 2
        self.assertGreaterEqual(ov["active_subscriptions"], 2)

    def test_revenue_analytics(self):
        rev = analytics.revenue_analytics(self.db)
        self.assertGreater(rev["mrr"], 0)
        self.assertEqual(rev["arr"], round(rev["mrr"] * 12, 2))
        self.assertIn("professional", rev["by_plan"])
        self.assertIn("enterprise", rev["by_plan"])

    def test_usage_analytics(self):
        usage = analytics.usage_analytics(self.db)
        self.assertEqual(usage["totals"]["ml_predictions"], 5000)
        self.assertEqual(usage["totals"]["ocr_pages"], 200)

    def test_growth_metrics(self):
        g = analytics.growth_metrics(self.db)
        self.assertTrue(len(g["new_orgs_by_month"]) >= 1)
        self.assertTrue(len(g["cumulative_orgs"]) >= 1)

    def test_feature_adoption(self):
        adoption = analytics.feature_adoption(self.db)
        self.assertIn("white_label", adoption)
        self.assertGreater(adoption["white_label"]["adoption_rate"], 0)

    def test_tenant_analytics(self):
        tid = tsvc.default_tenant(self.db, self.org1.id).id
        ta = analytics.tenant_analytics(self.db, tid)
        self.assertEqual(ta["tenant_id"], tid)
        self.assertIn("storage_gb", ta)

    def test_executive_dashboard(self):
        dash = analytics.executive_dashboard(self.db)
        for key in ("overview", "revenue", "usage", "growth", "feature_adoption"):
            self.assertIn(key, dash)

    # -- admin console -------------------------------------------------
    def test_list_all_organizations(self):
        orgs = admin.list_all_organizations(self.db)
        slugs = {o["slug"] for o in orgs}
        self.assertIn("c1", slugs)
        self.assertIn("c2", slugs)

    def test_organization_detail(self):
        detail = admin.organization_detail(self.db, self.org1.id)
        self.assertEqual(detail["organization"]["slug"], "c1")
        self.assertGreaterEqual(len(detail["tenants"]), 1)
        self.assertIn("billing", detail)

    def test_suspend_cascades_to_tenants(self):
        org = admin.suspend_organization(self.db, self.org1.id, suspend=True)
        self.assertEqual(org.status, "suspended")
        tenants = tsvc.list_tenants(self.db, self.org1.id)
        self.assertTrue(all(t.status == "suspended" for t in tenants))

    def test_usage_console(self):
        console = admin.usage_console(self.db)
        self.assertIn(self.org1.id, console["by_organization"])
        self.assertEqual(console["by_organization"][self.org1.id]["ml_predictions"], 5000)

    def test_system_health(self):
        health = admin.system_health(self.db)
        self.assertIn("health", health)
        self.assertIn("service_map", health)

    def test_platform_summary(self):
        summary = admin.platform_summary(self.db)
        self.assertIn("overview", summary)
        self.assertIn("jobs", summary)


if __name__ == "__main__":
    unittest.main()
