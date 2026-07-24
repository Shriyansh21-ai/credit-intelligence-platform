"""Phase 8 — Subscription & billing engine (M4)."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.services.saas import tenancy as tsvc
from backend.app.services.saas.billing import service as billing
from backend.tests._saas_helpers import fresh_session, seed_all


class BillingTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_all(self.db)
        self.org = tsvc.create_organization(self.db, slug="lender", name="Lender Co")

    def tearDown(self):
        self.db.close()

    def test_plans_seeded(self):
        codes = {p.code for p in billing.list_plans(self.db)}
        self.assertEqual(codes, {"free", "professional", "enterprise"})

    def test_subscribe_and_active(self):
        sub = billing.subscribe(self.db, self.org.id, "professional", seats=10)
        self.assertEqual(sub.status, "active")
        active = billing.active_subscription(self.db, self.org.id)
        self.assertEqual(active.id, sub.id)

    def test_trial_subscription(self):
        sub = billing.subscribe(self.db, self.org.id, "professional", trial_days=14)
        self.assertEqual(sub.status, "trialing")
        self.assertIsNotNone(sub.trial_end)

    def test_upgrade_downgrade_events(self):
        billing.subscribe(self.db, self.org.id, "free")
        billing.change_plan(self.db, self.org.id, "enterprise")
        billing.change_plan(self.db, self.org.id, "professional")
        events = [e.event_type for e in billing.subscription_history(self.db, self.org.id)]
        self.assertIn("created", events)
        self.assertIn("upgraded", events)
        self.assertIn("downgraded", events)

    def test_unknown_plan_rejected(self):
        with self.assertRaises(ValueError):
            billing.subscribe(self.db, self.org.id, "platinum")

    def test_quota_enforcement(self):
        billing.subscribe(self.db, self.org.id, "free")  # api_calls limit 5000
        billing.record_usage(self.db, self.org.id, "api_calls", 4000)
        q = billing.check_quota(self.db, self.org.id, "api_calls", additional=500)
        self.assertTrue(q["allowed"])
        q2 = billing.check_quota(self.db, self.org.id, "api_calls", additional=2000)
        self.assertFalse(q2["allowed"])
        self.assertEqual(q2["remaining"], 1000)

    def test_enterprise_unlimited_quota(self):
        billing.subscribe(self.db, self.org.id, "enterprise")
        billing.record_usage(self.db, self.org.id, "api_calls", 10_000_000)
        q = billing.check_quota(self.db, self.org.id, "api_calls", additional=1_000_000)
        self.assertTrue(q["allowed"])
        self.assertIsNone(q["limit"])

    def test_usage_summary_aggregates(self):
        billing.subscribe(self.db, self.org.id, "professional")
        billing.record_usage(self.db, self.org.id, "ml_predictions", 100)
        billing.record_usage(self.db, self.org.id, "ml_predictions", 250)
        billing.record_usage(self.db, self.org.id, "ocr_pages", 40)
        summary = billing.usage_summary(self.db, self.org.id)
        self.assertEqual(summary["ml_predictions"], 350)
        self.assertEqual(summary["ocr_pages"], 40)

    def test_invoice_generation_with_overage(self):
        billing.subscribe(self.db, self.org.id, "professional")  # api limit 500k, price/1000=40
        billing.record_usage(self.db, self.org.id, "api_calls", 600_000)  # 100k overage
        inv = billing.generate_invoice(self.db, self.org.id)
        self.assertEqual(inv.status, "open")
        lines = billing.invoice_lines(self.db, inv.id)
        kinds = {l.kind for l in lines}
        self.assertIn("base", kinds)
        self.assertIn("overage", kinds)
        # base 49999 + overage (100 units * 40 = 4000) = 53999, +18% tax
        self.assertGreater(inv.total, 53999)

    def test_pay_invoice_internal_gateway(self):
        billing.subscribe(self.db, self.org.id, "professional")
        inv = billing.generate_invoice(self.db, self.org.id)
        paid = billing.pay_invoice(self.db, inv.id)
        self.assertEqual(paid.status, "paid")
        self.assertTrue(paid.provider_ref.startswith("pay_"))

    def test_has_feature(self):
        billing.subscribe(self.db, self.org.id, "enterprise")
        self.assertTrue(billing.has_feature(self.db, self.org.id, "sso"))
        self.assertFalse(billing.has_feature(self.db, self.org.id, "nonexistent"))

    def test_custom_plan(self):
        plan = billing.create_custom_plan(self.db, self.org.id, code="custom-lender",
                                          name="Lender Custom", base_price=500000,
                                          limits={"seats": 500}, unit_prices={},
                                          features=["everything"])
        self.assertEqual(plan.tier, "custom")
        billing.subscribe(self.db, self.org.id, "custom-lender")
        self.assertTrue(billing.has_feature(self.db, self.org.id, "everything"))

    def test_cancel_at_period_end(self):
        billing.subscribe(self.db, self.org.id, "professional")
        sub = billing.cancel_subscription(self.db, self.org.id, at_period_end=True)
        self.assertTrue(sub.cancel_at_period_end)

    def test_billing_analytics(self):
        billing.subscribe(self.db, self.org.id, "professional")
        inv = billing.generate_invoice(self.db, self.org.id)
        billing.pay_invoice(self.db, inv.id)
        a = billing.billing_analytics(self.db, self.org.id)
        self.assertEqual(a["current_plan"], "professional")
        self.assertGreater(a["total_paid"], 0)


if __name__ == "__main__":
    unittest.main()
