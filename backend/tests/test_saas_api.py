"""Phase 8 — HTTP API + RBAC enforcement + deployment probes."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.services.saas import tenancy as tsvc
from backend.tests._saas_helpers import client_for, fresh_session, make_user, seed_all


class SaasApiTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_all(db)
        # A seeded org to operate on.
        self.org = tsvc.create_organization(db, slug="apibank", name="API Bank")
        self.tid = tsvc.default_tenant(db, self.org.id).id
        db.close()
        self.admin = make_user(self.Session, "admin@api", "administrator")
        self.viewer = make_user(self.Session, "viewer@api", "viewer")
        self.platform = make_user(self.Session, "pa@api", "platform_admin")

    # -- RBAC ----------------------------------------------------------
    def test_viewer_forbidden_from_tenancy_manage(self):
        c = client_for(self.Session, self.viewer)
        r = c.post("/api/saas/tenancy/organizations",
                   json={"slug": "x", "name": "X"})
        self.assertEqual(r.status_code, 403)

    def test_admin_can_create_org(self):
        c = client_for(self.Session, self.admin)
        r = c.post("/api/saas/tenancy/organizations",
                   json={"slug": "neworg", "name": "New Org", "org_type": "nbfc"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["slug"], "neworg")

    def test_list_orgs(self):
        c = client_for(self.Session, self.admin)
        r = c.get("/api/saas/tenancy/organizations")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.json()), 2)

    def test_hierarchy_endpoint(self):
        c = client_for(self.Session, self.admin)
        c.post(f"/api/saas/tenancy/tenants/{self.tid}/business-units", json={"name": "BU1"})
        r = c.get(f"/api/saas/tenancy/tenants/{self.tid}/hierarchy")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["business_units"]), 1)

    def test_invitation_flow_api(self):
        c = client_for(self.Session, self.admin)
        r = c.post(f"/api/saas/tenancy/tenants/{self.tid}/invitations",
                   json={"email": "invitee@api", "org_role": "member"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("token", r.json())

    # -- Branding ------------------------------------------------------
    def test_branding_get_and_update(self):
        c = client_for(self.Session, self.admin)
        r = c.get(f"/api/saas/branding/tenants/{self.tid}")
        self.assertEqual(r.status_code, 200)
        r2 = c.put(f"/api/saas/branding/tenants/{self.tid}",
                   json={"theme": {"colors": {"primary": "#123456"}}})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["theme"]["colors"]["primary"], "#123456")

    # -- Billing -------------------------------------------------------
    def test_billing_subscribe_and_invoice(self):
        c = client_for(self.Session, self.admin)
        r = c.post(f"/api/saas/billing/orgs/{self.org.id}/subscribe",
                   json={"plan_code": "professional", "seats": 5})
        self.assertEqual(r.status_code, 200, r.text)
        c.post(f"/api/saas/billing/orgs/{self.org.id}/usage",
               json={"meter": "api_calls", "quantity": 1000})
        inv = c.post(f"/api/saas/billing/orgs/{self.org.id}/invoices")
        self.assertEqual(inv.status_code, 200, inv.text)
        self.assertGreater(inv.json()["total"], 0)

    def test_billing_view_requires_permission(self):
        c = client_for(self.Session, self.viewer)
        r = c.get(f"/api/saas/billing/orgs/{self.org.id}/analytics")
        self.assertEqual(r.status_code, 403)

    # -- Feature flags -------------------------------------------------
    def test_flags_list_and_evaluate(self):
        c = client_for(self.Session, self.admin)
        self.assertEqual(c.get("/api/saas/flags").status_code, 200)
        ev = c.get(f"/api/saas/flags/evaluate?tenant_id={self.tid}")
        self.assertEqual(ev.status_code, 200)
        self.assertIn("white_label", ev.json())

    def test_flag_override_api(self):
        c = client_for(self.Session, self.admin)
        r = c.post("/api/saas/flags/customer360_v2/override",
                   json={"tenant_id": self.tid, "enabled": True})
        self.assertEqual(r.status_code, 200)
        g = c.get(f"/api/saas/flags/customer360_v2?tenant_id={self.tid}")
        self.assertTrue(g.json()["enabled"])

    # -- Jobs ----------------------------------------------------------
    def test_jobs_enqueue_and_run(self):
        c = client_for(self.Session, self.admin)
        r = c.post("/api/saas/jobs", json={"job_type": "noop", "payload": {"a": 1}})
        self.assertEqual(r.status_code, 200, r.text)
        jid = r.json()["id"]
        c.post("/api/saas/jobs/run")
        g = c.get(f"/api/saas/jobs/{jid}")
        self.assertEqual(g.json()["status"], "succeeded")

    def test_jobs_forbidden_for_viewer(self):
        c = client_for(self.Session, self.viewer)
        r = c.post("/api/saas/jobs", json={"job_type": "noop"})
        self.assertEqual(r.status_code, 403)

    # -- Storage -------------------------------------------------------
    def test_storage_put_get_delete(self):
        import base64
        from backend.app.services.saas import storage
        storage.set_active_backend("memory")
        storage._BACKENDS["memory"] = storage.MemoryBackend()
        c = client_for(self.Session, self.admin)
        payload = base64.b64encode(b"hello world").decode()
        r = c.post(f"/api/saas/storage/tenants/{self.tid}/objects",
                   json={"key": "a.txt", "content_base64": payload})
        self.assertEqual(r.status_code, 200, r.text)
        g = c.get(f"/api/saas/storage/tenants/{self.tid}/objects/default/a.txt")
        self.assertEqual(g.status_code, 200)
        self.assertEqual(base64.b64decode(g.json()["content_base64"]), b"hello world")

    # -- Observability / cache -----------------------------------------
    def test_observability_metrics_endpoint(self):
        c = client_for(self.Session, self.admin)
        r = c.get("/api/saas/observability/health")
        self.assertEqual(r.status_code, 200)
        self.assertIn("status", r.json())

    def test_cache_stats_requires_permission(self):
        c = client_for(self.Session, self.viewer)
        self.assertEqual(c.get("/api/saas/cache/stats").status_code, 403)

    # -- Security ------------------------------------------------------
    def test_security_ip_allow_api(self):
        c = client_for(self.Session, self.admin)
        r = c.post(f"/api/saas/security/tenants/{self.tid}/ip-allow",
                   json={"cidr": "10.0.0.0/8"})
        self.assertEqual(r.status_code, 200, r.text)
        chk = c.get(f"/api/saas/security/tenants/{self.tid}/ip-allow/check?ip=10.1.1.1")
        self.assertTrue(chk.json()["allowed"])

    def test_rate_limit_endpoint(self):
        c = client_for(self.Session, self.admin)
        r = c.post("/api/saas/security/rate-limit/check",
                   json={"key": "test", "limit": 5, "window_seconds": 60})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["allowed"])

    # -- Admin console (platform.admin) --------------------------------
    def test_admin_console_requires_platform_admin(self):
        c = client_for(self.Session, self.viewer)
        self.assertEqual(c.get("/api/saas/admin/organizations").status_code, 403)

    def test_platform_admin_can_view_console(self):
        c = client_for(self.Session, self.platform)
        r = c.get("/api/saas/admin/organizations")
        self.assertEqual(r.status_code, 200, r.text)

    def test_admin_but_not_platform_perms(self):
        # 'administrator' has "*" so it also passes platform.admin.
        c = client_for(self.Session, self.admin)
        self.assertEqual(c.get("/api/saas/admin/summary").status_code, 200)

    # -- Analytics -----------------------------------------------------
    def test_analytics_overview(self):
        c = client_for(self.Session, self.platform)
        r = c.get("/api/saas/analytics/overview")
        self.assertEqual(r.status_code, 200)
        self.assertIn("organizations", r.json())

    # -- Deployment probes (M11) ---------------------------------------
    def test_healthz_probe(self):
        c = client_for(self.Session, self.admin)
        self.assertEqual(c.get("/healthz").status_code, 200)

    def test_livez_probe(self):
        c = client_for(self.Session, self.admin)
        self.assertEqual(c.get("/livez").json()["status"], "alive")

    def test_readyz_probe(self):
        c = client_for(self.Session, self.admin)
        r = c.get("/readyz")
        self.assertEqual(r.status_code, 200)
        self.assertIn("status", r.json())


if __name__ == "__main__":
    unittest.main()
