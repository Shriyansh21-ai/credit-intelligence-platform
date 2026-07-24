"""Phase 8 — Feature flags (M5) + white-label branding (M3)."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from datetime import datetime, timedelta

from backend.app.services.saas import branding as brand
from backend.app.services.saas import tenancy as tsvc
from backend.app.services.saas.flags import service as flags
from backend.tests._saas_helpers import fresh_session, seed_all


class FlagsTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_all(self.db)
        self.org = tsvc.create_organization(self.db, slug="ff", name="FF")
        self.tid = tsvc.default_tenant(self.db, self.org.id).id

    def tearDown(self):
        self.db.close()

    def test_flags_seeded(self):
        keys = {f.key for f in flags.list_flags(self.db)}
        self.assertIn("realtime_dashboards", keys)
        self.assertIn("white_label", keys)

    def test_globally_enabled_flag(self):
        self.assertTrue(flags.is_enabled(self.db, "realtime_dashboards", tenant_id=self.tid))

    def test_disabled_flag_default(self):
        self.assertFalse(flags.is_enabled(self.db, "customer360_v2", tenant_id=self.tid))

    def test_missing_flag_is_off(self):
        self.assertFalse(flags.is_enabled(self.db, "does_not_exist", tenant_id=self.tid))

    def test_override_wins(self):
        flags.set_override(self.db, "customer360_v2", self.tid, True)
        self.assertTrue(flags.is_enabled(self.db, "customer360_v2", tenant_id=self.tid))
        flags.clear_override(self.db, "customer360_v2", self.tid)
        self.assertFalse(flags.is_enabled(self.db, "customer360_v2", tenant_id=self.tid))

    def test_percentage_rollout_deterministic(self):
        flags.upsert_flag(self.db, "canary_x", name="Canary X", enabled=False,
                          rollout_percentage=50.0)
        r1 = flags.is_enabled(self.db, "canary_x", tenant_id=self.tid)
        r2 = flags.is_enabled(self.db, "canary_x", tenant_id=self.tid)
        self.assertEqual(r1, r2)  # stable per tenant

    def test_full_rollout_on_partial_off(self):
        flags.upsert_flag(self.db, "roll100", name="R100", enabled=False, rollout_percentage=100.0)
        flags.upsert_flag(self.db, "roll0", name="R0", enabled=False, rollout_percentage=0.0)
        self.assertTrue(flags.is_enabled(self.db, "roll100", tenant_id=self.tid))
        self.assertFalse(flags.is_enabled(self.db, "roll0", tenant_id=self.tid))

    def test_dependency_gating(self):
        # advanced_analytics depends on realtime_dashboards.
        flags.upsert_flag(self.db, "realtime_dashboards", enabled=False, rollout_percentage=0.0)
        self.assertFalse(flags.is_enabled(self.db, "advanced_analytics", tenant_id=self.tid))
        flags.upsert_flag(self.db, "realtime_dashboards", enabled=True)
        self.assertTrue(flags.is_enabled(self.db, "advanced_analytics", tenant_id=self.tid))

    def test_role_targeting(self):
        flags.upsert_flag(self.db, "admin_only", name="Admin only", enabled=True,
                          target_roles=["administrator"])
        self.assertFalse(flags.is_enabled(self.db, "admin_only", tenant_id=self.tid, roles=["viewer"]))
        self.assertTrue(flags.is_enabled(self.db, "admin_only", tenant_id=self.tid, roles=["administrator"]))

    def test_expired_flag_off(self):
        flags.upsert_flag(self.db, "expired", name="Expired", enabled=True)
        f = flags.list_flags(self.db)
        flags.upsert_flag(self.db, "expired", enabled=True)
        # set expiry in the past
        from backend.app.models.feature_flags import FeatureFlag
        row = self.db.query(FeatureFlag).filter(FeatureFlag.key == "expired").first()
        row.expires_at = datetime.utcnow() - timedelta(hours=1)
        self.db.commit()
        self.assertFalse(flags.is_enabled(self.db, "expired", tenant_id=self.tid))

    def test_evaluate_all(self):
        result = flags.evaluate_all(self.db, tenant_id=self.tid)
        self.assertIn("white_label", result)
        self.assertTrue(result["white_label"])

    def test_sync_preserves_ops_changes(self):
        flags.upsert_flag(self.db, "ml_autopilot", enabled=True, rollout_percentage=100.0)
        flags.sync_flags(self.db)  # re-sync should not clobber the ops change
        from backend.app.models.feature_flags import FeatureFlag
        row = self.db.query(FeatureFlag).filter(FeatureFlag.key == "ml_autopilot").first()
        self.assertTrue(row.enabled)


class BrandingTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_all(self.db)
        self.org = tsvc.create_organization(self.db, slug="brand", name="Brand")
        self.tid = tsvc.default_tenant(self.db, self.org.id).id

    def tearDown(self):
        self.db.close()

    def test_default_theme_before_customization(self):
        b = brand.get_branding(self.db, self.tid)
        self.assertFalse(b["customized"])
        self.assertEqual(b["theme"]["colors"]["primary"], "#1e40af")
        self.assertTrue(len(b["navigation"]) > 0)

    def test_partial_theme_merge(self):
        brand.update_branding(self.db, self.tid, {"theme": {"colors": {"primary": "#ff0000"}}})
        b = brand.get_branding(self.db, self.tid)
        self.assertEqual(b["theme"]["colors"]["primary"], "#ff0000")
        # untouched defaults remain
        self.assertEqual(b["theme"]["colors"]["secondary"], "#0f172a")
        self.assertTrue(b["customized"])

    def test_logo_and_email_branding(self):
        brand.update_branding(self.db, self.tid, {
            "logo_url": "https://cdn/x.png",
            "email_branding": {"from_name": "Brand Bank"},
        })
        b = brand.get_branding(self.db, self.tid)
        self.assertEqual(b["logo_url"], "https://cdn/x.png")
        self.assertEqual(b["email_branding"]["from_name"], "Brand Bank")

    def test_feature_visibility(self):
        brand.update_branding(self.db, self.tid, {"feature_visibility": {"portfolio": False}})
        self.assertFalse(brand.is_feature_visible(self.db, self.tid, "portfolio"))
        self.assertTrue(brand.is_feature_visible(self.db, self.tid, "dashboard"))

    def test_custom_navigation(self):
        nav = [{"key": "home", "label": "Home", "visible": True}]
        brand.update_branding(self.db, self.tid, {"navigation": nav})
        b = brand.get_branding(self.db, self.tid)
        self.assertEqual(b["navigation"], nav)


if __name__ == "__main__":
    unittest.main()
